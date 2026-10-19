"""CareBridge API + web app server (FastAPI)."""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import safety
from .engines import load_engines
from .lexicon import lexicon
from .brief import BODY_REGIONS, interpreter_brief
from .fhir import document_reference
from .phrasebank import (CLINICIAN_PHRASES, DEMO_CLIPS, LANGUAGES, PAIN_TEMPLATE, PATIENT_LANGS, PATIENT_UI,
                         PHRASES, PILOT_LANGS, QUICK_REPLIES, fix_medicine_words, glossary_checks, is_checked,
                         match_phrase, phrase)
from .store import load_store, now_ms

STAFF_CODE = os.environ.get("STAFF_CODE", "123456")
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-secret").encode()
ORIGIN_SECRET = os.environ.get("ORIGIN_SECRET", "")
BUCKET = os.environ.get("CB_BUCKET", "")
WEB = Path(__file__).resolve().parent.parent / "web"
VERSION = "1.0.0"

app = FastAPI(title="CareBridge", docs_url=None, redoc_url=None)
engines = load_engines()
TERM_TYPES = {"medicine", "brand", "drug_class", "allergen", "condition", "symptom", "procedure"}   # shown on each turn
store = load_store()


# --- Security: only API Gateway may reach the server; only signed-in staff may use the API ----------
@app.middleware("http")
async def guard(request: Request, call_next):
    if ORIGIN_SECRET and not hmac.compare_digest(request.headers.get("x-cb-origin", ""), ORIGIN_SECRET):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
    return response


def _sign(payload: str) -> str:
    return hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:40]


def make_token(name: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"n": name, "exp": int(time.time()) + 16 * 3600}).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def staff(authorization: Optional[str] = Header(None)) -> str:
    try:
        payload, sig = (authorization or "").removeprefix("Bearer ").split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload))
        if data["exp"] < time.time():
            raise ValueError
        return data["n"]
    except Exception:  # noqa: BLE001
        raise HTTPException(401, "Please sign in")


# --- Models ------------------------------------------------------------------------------------------
class Login(BaseModel):
    name: str
    code: str


class NewSession(BaseModel):
    mode: str = "standard"
    patientLang: Optional[str] = None
    mrn: Optional[str] = None


class Join(BaseModel):
    code: str


class SessionPatch(BaseModel):
    patientLang: Optional[str] = None
    langLocked: Optional[bool] = None
    consent: Optional[str] = None
    activity: Optional[dict] = None


class Analyze(BaseModel):
    text: str


class TurnIn(BaseModel):
    speaker: str                      # clinician | patient
    text: Optional[str] = None
    srcLang: str
    tgtLang: str
    mode: str = "standard"
    phraseId: Optional[str] = None
    pain: Optional[int] = None
    bodyRegions: Optional[list[str]] = None
    confirmed: bool = False
    override: Optional[str] = None
    asr: Optional[dict] = None


class EventIn(BaseModel):
    kind: str                         # escalation | override | consent | language | note
    detail: str = ""


class TTSIn(BaseModel):
    text: str
    lang: str


# --- Basics ------------------------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "version": VERSION, "engine": engines.name, "ready": engines.ready(),
            "models": engines.status, "modelInfo": engines.info, "audioStored": False, "voices": engines.voice_langs()}


@app.post("/api/login")
def login(body: Login):
    name = body.name.strip()[:40]
    if not name or not hmac.compare_digest(body.code.strip(), STAFF_CODE):
        raise HTTPException(401, "Name or staff code not recognised")
    return {"token": make_token(name), "name": name}


@app.get("/api/config")
def config(user: str = Depends(staff)):
    return {
        "languages": LANGUAGES, "patientLangs": PATIENT_LANGS, "patientUi": PATIENT_UI,
        "phrases": {pid: {lang: phrase(pid, lang) for lang in LANGUAGES if phrase(pid, lang)}
                    for pid in QUICK_REPLIES + CLINICIAN_PHRASES},
        "commonLangs": PILOT_LANGS,
        "bodyRegions": BODY_REGIONS,
        "voiceLangs": engines.voice_langs(),   # languages with a server voice (Emergency needs one)
        "quickReplies": QUICK_REPLIES, "clinicianPhrases": CLINICIAN_PHRASES, "painTemplate": PAIN_TEMPLATE,
        "demoClips": DEMO_CLIPS, "redTopics": [name for name, _ in safety.RED_TOPICS] + ["Discharge medicines"],
        "user": user,
    }


# --- Sessions ----------------------------------------------------------------------------------------
def _session_or_404(sid):
    s = store.get_session(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@app.post("/api/sessions")
def create_session(body: NewSession, user: str = Depends(staff)):
    lang = body.patientLang if body.patientLang in PATIENT_LANGS else None
    if lang:
        engines.warm(lang)
    s = store.create_session({"mode": body.mode, "patientLang": lang, "langLocked": bool(lang),
                              "mrn": (body.mrn or "").strip()[:30] or None, "createdBy": user,
                              "consent": None, "activity": None, "escalations": 0})
    store.add_turn(s["id"], {"type": "event", "kind": "session", "detail": f"{body.mode.capitalize()} session started", "by": user})
    return s


@app.post("/api/sessions/join")
def join_session(body: Join, user: str = Depends(staff)):
    s = store.find_by_code(body.code.strip())
    if not s or s.get("status") == "ended":
        raise HTTPException(404, "No active session with that code")
    store.add_turn(s["id"], {"type": "event", "kind": "device", "detail": "Another device joined", "by": user})
    return s


@app.get("/api/sessions")
def list_sessions(user: str = Depends(staff)):
    return {"sessions": store.list_sessions()[:50]}


@app.get("/api/sessions/{sid}")
def get_session(sid: str, since: int = 0, user: str = Depends(staff)):
    return {"session": _session_or_404(sid), "turns": store.list_turns(sid, since), "now": now_ms()}


@app.patch("/api/sessions/{sid}")
def patch_session(sid: str, body: SessionPatch, user: str = Depends(staff)):
    s = _session_or_404(sid)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "patientLang" in fields:
        if fields["patientLang"] not in PATIENT_LANGS:
            raise HTTPException(400, "Unsupported language")
        if fields["patientLang"] != s.get("patientLang"):
            store.add_turn(sid, {"type": "event", "kind": "language",
                                 "detail": f"Patient language set to {LANGUAGES[fields['patientLang']]['name']}"
                                           + (" and locked" if fields.get("langLocked") else ""), "by": user})
    if fields.get("patientLang"):
        engines.warm(fields["patientLang"])   # load the patient's voice now, not at the first sentence
    if "consent" in fields:
        store.add_turn(sid, {"type": "event", "kind": "consent", "detail": f"Patient consent: {fields['consent']}", "by": "patient"})
    if "activity" in fields:
        fields["activity"] = {**fields["activity"], "at": now_ms()}
    return store.update_session(sid, **fields)


@app.post("/api/sessions/{sid}/events")
def add_event(sid: str, body: EventIn, user: str = Depends(staff)):
    s = _session_or_404(sid)
    if body.kind == "escalation":
        store.update_session(sid, escalations=s.get("escalations", 0) + 1, escalated=True)
    return store.add_turn(sid, {"type": "event", "kind": body.kind, "detail": body.detail[:300], "by": user})


@app.post("/api/sessions/{sid}/end")
def end_session(sid: str, user: str = Depends(staff)):
    _session_or_404(sid)
    s = store.update_session(sid, status="ended", endedAt=now_ms(), activity=None)
    store.add_turn(sid, {"type": "event", "kind": "session", "detail": "Session ended", "by": user})
    doc = document_reference(s, store.list_turns(sid))
    if BUCKET:
        try:
            import boto3
            boto3.client("s3").put_object(Bucket=BUCKET, Key=f"fhir/{sid}.json", ContentType="application/fhir+json",
                                          Body=json.dumps(doc, ensure_ascii=False, indent=2).encode())
            s = store.update_session(sid, fhirKey=f"s3://{BUCKET}/fhir/{sid}.json")
        except Exception as e:  # noqa: BLE001
            s = store.update_session(sid, fhirError=str(e)[:200])
    return s


@app.get("/api/sessions/{sid}/brief")
def brief(sid: str, user: str = Depends(staff)):
    return interpreter_brief(_session_or_404(sid), store.list_turns(sid))


@app.get("/api/sessions/{sid}/fhir")
def fhir(sid: str, user: str = Depends(staff)):
    s = _session_or_404(sid)
    return JSONResponse(document_reference(s, store.list_turns(sid)), media_type="application/fhir+json")


# --- Speech, analysis and translation ------------------------------------------------------------------
@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), lang: Optional[str] = Form(None),
                     candidates: Optional[str] = Form(None), user: str = Depends(staff)):
    data = await audio.read()
    if len(data) < 800:
        raise HTTPException(400, "No audio was captured")
    if lang in LANGUAGES and not LANGUAGES[lang]["whisper"]:
        raise HTTPException(400, f"Speech recognition isn't available for {LANGUAGES[lang]['name']} yet. "
                                 "Type the words or use the tap answers.")
    cands = [c for c in (candidates or "").split(",") if c in LANGUAGES and LANGUAGES[c]["whisper"]] or None
    t0 = time.time()
    from starlette.concurrency import run_in_threadpool
    result = await run_in_threadpool(engines.transcribe, data, lang if lang in LANGUAGES else None, cands)
    tlang = result.get("lang") or lang
    lex = lexicon()
    if lex.ok and tlang:
        # CareBridge lexicon: misheard medicine names -> the right name; two sound-alikes -> ask, never guess
        result["text"], fixes, ambiguous = lex.correct(result.get("text", ""), tlang)
        if ambiguous:
            result["ambiguous"] = ambiguous
    else:
        result["text"], fixes = fix_medicine_words(result.get("text", ""), tlang)
    if fixes:
        result["corrections"] = fixes
    if (fixes or result.get("ambiguous")) and result.get("clarity") == "clear":
        result["clarity"] = "noisy"     # a corrected or uncertain medicine is checked before it is spoken
    result["ms"] = int((time.time() - t0) * 1000)
    return result


@app.post("/api/analyze")
def analyze(body: Analyze, user: str = Depends(staff)):
    plain, rewrites = safety.plain_english(body.text)
    flags = safety.medical_flags(plain)
    return {"plain": plain, "rewrites": rewrites, "flags": flags, "risk": safety.risk_tier(plain, flags),
            "phrase": match_phrase(plain)}


@app.post("/api/sessions/{sid}/turns")
def add_turn(sid: str, body: TurnIn, user: str = Depends(staff)):
    _session_or_404(sid)
    if body.srcLang not in LANGUAGES or body.tgtLang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    t0 = time.time()
    src, tgt = body.srcLang, body.tgtLang
    pid = body.phraseId
    translation = back = None
    engine = engines.model_label(src, tgt)

    # Patient tap answers (meaning known exactly), or free text / clinician phrases
    if body.bodyRegions:
        regions = [r for r in body.bodyRegions if r in BODY_REGIONS][:6]
        if not regions:
            raise HTTPException(400, "Unknown body region")
        names = ", ".join(BODY_REGIONS[r] for r in regions)
        original = f"[Body map] {names}"
        translation = f"It hurts here: {names}." if tgt == "en" else original
        back, pid, engine = original, "body_map", "tap answer"
    elif body.pain is not None:
        n = max(0, min(10, int(body.pain)))
        original = PAIN_TEMPLATE.get(src, PAIN_TEMPLATE["en"]).format(n=n)
        translation = PAIN_TEMPLATE.get(tgt, PAIN_TEMPLATE["en"]).format(n=n)
        back, pid, engine = original, "pain_scale_reply", "tap answer"
    elif pid and pid in PHRASES and src != "en":
        original = phrase(pid, src) or PHRASES[pid]["en"]
        translation = PHRASES[pid]["en"] if tgt == "en" else phrase(pid, tgt)
        back, engine = original, "tap answer"
    else:
        original = (body.text or "").strip() or (PHRASES[pid]["en"] if pid in PHRASES else "")
        pid = None
    if not original:
        raise HTTPException(400, "Nothing to translate")

    rewrites = []
    plain = original
    if src == "en" and translation is None:
        plain, rewrites = safety.plain_english(original)
        pid = match_phrase(plain)
        if pid and is_checked(pid, tgt):   # only team-drafted translations count as pre-checked
            translation, back, engine = PHRASES[pid][tgt], PHRASES[pid]["en"], "pre-checked phrase"
        else:
            pid = None

    t_mt = time.time()
    if translation is None:
        translation = engines.translate(plain, src, tgt)
    if back is None:
        back = engines.translate(translation, tgt, src)
    mt_ms = int((time.time() - t_mt) * 1000)

    english = plain if src == "en" else translation
    flags = safety.medical_flags(english)
    risk = safety.risk_tier(english, flags)
    tap = engine == "tap answer"   # meaning known exactly: nothing to check
    checks = [] if tap else safety.critical_checks(plain, src, translation, tgt, back)
    glossary = [] if tap else glossary_checks(english, translation if src == "en" else plain, tgt if src == "en" else src)
    # CareBridge lexicon: every medicine, brand, drug class and allergen must come out as the same entry in the
    # other language, checked in that language itself (not only through the English back-translation)
    lex = lexicon()
    terms = []
    if lex.ok and not tap:
        term_check = lex.compare(plain, src, translation, tgt)
        if term_check:
            checks = [c for c in checks if c["name"] != "Medicines"] + [term_check]
        terms = [{k: h[k] for k in ("id", "types", "name", "match", "review", "lasa")}
                 for h in lex.find(english, "en", TERM_TYPES)]
    sim = 1.0 if engine in ("pre-checked phrase", "tap answer") else engines.similarity(plain, back)
    meaning = safety.meaning_verdict(sim)
    status = safety.turn_status(checks, meaning, glossary)
    hold = None
    if body.mode == "emergency" and body.speaker == "clinician" and src == "en" and not tap \
            and safety.medication_instruction(plain, flags):
        hold = {"reason": "medication", "suggest": "standard",
                "message": "Medication or dose instructions are checked in Standard mode before they are spoken."}

    turn = {
        "type": "utterance", "speaker": body.speaker, "by": user, "mode": body.mode,
        "srcLang": src, "tgtLang": tgt, "original": original, "plain": plain, "rewrites": rewrites,
        "translation": translation, "backTranslation": back, "engine": engine, "phraseId": pid,
        "flags": flags, "risk": risk, "checks": checks, "glossary": glossary, "meaning": meaning,
        "status": status, "confirmed": body.confirmed, "override": body.override, "asr": body.asr,
        "terms": terms, "hold": hold,
        "bodyRegions": body.bodyRegions if pid == "body_map" else None,
        "latencyMs": {"translate": mt_ms, "total": int((time.time() - t0) * 1000)},
    }
    turn = store.add_turn(sid, turn)
    if body.override:
        store.add_turn(sid, {"type": "event", "kind": "override",
                             "detail": f"Interpreter advice overridden ({', '.join(risk['reasons'])}): {body.override}", "by": user})
    return turn


class BatchIn(BaseModel):
    texts: list[str]
    src: str = "en"
    tgt: str


@app.post("/api/translate-batch")
def translate_batch(body: BatchIn, user: str = Depends(staff)):
    """Batch translation used once to generate interface text for the machine-translated languages."""
    if body.src not in LANGUAGES or body.tgt not in LANGUAGES or not body.texts or len(body.texts) > 60:
        raise HTTPException(400, "Bad request")
    return {"translations": engines.translate_many([t[:400] for t in body.texts], body.src, body.tgt)}


class EvalIn(BaseModel):
    source: str
    srcLang: str = "en"
    tgtLang: str = "uk"
    translation: Optional[str] = None   # pass a (deliberately corrupted) translation to test the safety net


@app.get("/api/lexicon")
def lexicon_info(q: Optional[str] = None, lang: str = "en", user: str = Depends(staff)):
    """The clinical lexicon: version and coverage, or the entries a text mentions (?q=...&lang=uk)."""
    lex = lexicon()
    if not lex.ok:
        return {"ok": False}
    out = {"ok": True, **lex.stats()}
    if q:
        hits = lex.find(q[:400], lang if lang in LANGUAGES else "en", {"medicine", "brand", "drug_class", "allergen",
                                                                       "condition", "symptom", "procedure", "anatomy"})
        out["matches"] = [{**h, "names": {l: lex.by_id[h["id"]]["names"].get(l, [])[:3] for l in ("en", lang)},
                           "codes": lex.by_id[h["id"]].get("codes", {}), "brands": lex.by_id[h["id"]].get("brands", [])[:8]}
                          for h in hits]
        out["corrected"], out["fixes"], out["ambiguous"] = lex.correct(q[:400], lang)
    return out


@app.post("/api/lexicon/reload")
def lexicon_reload(user: str = Depends(staff)):
    from .lexicon import reload
    stats = reload()
    import logging
    logging.getLogger("carebridge").warning("lexicon reloaded by %s: %s", user, stats)
    return stats


@app.post("/api/eval/check")
def eval_check(body: EvalIn, user: str = Depends(staff)):
    """Runs the safety net on one sentence without storing anything (used by the error-injection test)."""
    if body.srcLang not in LANGUAGES or body.tgtLang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    plain = safety.plain_english(body.source)[0] if body.srcLang == "en" else body.source
    translation = body.translation or engines.translate(plain, body.srcLang, body.tgtLang)
    back = engines.translate(translation, body.tgtLang, body.srcLang)
    english = plain if body.srcLang == "en" else translation
    checks = safety.critical_checks(plain, body.srcLang, translation, body.tgtLang, back)
    lex = lexicon()
    term_check = lex.compare(plain, body.srcLang, translation, body.tgtLang) if lex.ok else None
    if term_check:
        checks = [c for c in checks if c["name"] != "Medicines"] + [term_check]
    glossary = glossary_checks(english, translation if body.srcLang == "en" else plain,
                               body.tgtLang if body.srcLang == "en" else body.srcLang)
    meaning = safety.meaning_verdict(engines.similarity(plain, back))
    return {"translation": translation, "back": back, "checks": checks, "glossary": glossary,
            "meaning": meaning, "status": safety.turn_status(checks, meaning, glossary)}


class WarmIn(BaseModel):
    lang: str


@app.post("/api/tts/warm")
def tts_warm(body: WarmIn, user: str = Depends(staff)):
    """Loads a language's voice in the background as soon as the patient's language is known."""
    if body.lang in LANGUAGES:
        engines.warm(body.lang)
    return {"ok": True}


@app.post("/api/tts")
def tts(body: TTSIn, user: str = Depends(staff)):
    if body.lang not in LANGUAGES or not body.text.strip():
        raise HTTPException(400, "Bad request")
    wav = engines.tts(body.text[:600], body.lang)
    if not wav:
        return Response(status_code=204)
    return Response(wav, media_type="audio/wav")


# --- Web app -----------------------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
