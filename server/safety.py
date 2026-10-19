"""CareBridge safety layer: plain-English rewrite, medical-information flags, risk tiers and
critical-detail checks. Rule-based on purpose: every decision is explainable and auditable."""
import re
from collections import Counter

# ---------------------------------------------------------------------------
# 1. Irish-English and clinical jargon -> plain English (applied before translation)
# ---------------------------------------------------------------------------
REWRITES = [
    (r"\bis there (any )?pain at you\b", "do you have any pain", "Irish English"),
    (r"\bis the pain (still )?at you\b", "are you in pain", "Irish English"),
    (r"\bhave you (a|any) pain\b", "do you have pain", "Irish English"),
    (r"\b(did|have) you (get|got|been) sick\b", "did you vomit", "Irish English"),
    (r"\b(been )?bringing up\b", "vomiting", "Idiom"),
    (r"\bthrowing up\b", "vomiting", "Idiom"),
    (r"\bhave you passed water\b", "have you urinated", "Idiom"),
    (r"\bpass(ing)? water\b", "urinate", "Idiom"),
    (r"\bgo for a wee\b", "urinate", "Idiom"),
    (r"\bwaterworks\b", "urination", "Idiom"),
    (r"\bspend a penny\b", "use the toilet", "Idiom"),
    (r"\bthe jacks\b", "the toilet", "Irish English"),
    (r"\bnil by mouth\b", "nothing to eat or drink", "Jargon"),
    (r"\bNBM\b", "nothing to eat or drink", "Jargon"),
    (r"\bfasting from midnight\b", "no food or drink after midnight", "Jargon"),
    (r"\bI'?ll (just )?pop (a|in a) cannula( in)?\b", "I will put a small tube into your vein", "Jargon"),
    (r"\bcannula\b", "small tube in the vein", "Jargon"),
    (r"\b(pop|hop) up on the (bed|trolley)\b", "lie down on the bed", "Idiom"),
    (r"\bfeeling (a bit )?off\b", "feeling unwell", "Idiom"),
    (r"\bunder the weather\b", "unwell", "Idiom"),
    (r"\bgiving you (gyp|grief|trouble)\b", "hurting you", "Irish English"),
    (r"\bhow'?s the form\b", "how are you feeling", "Irish English"),
    (r"\bpins and needles\b", "tingling", "Idiom"),
    (r"\bbloods\b", "blood tests", "Jargon"),
    (r"\bobs\b", "blood pressure, pulse and temperature checks", "Jargon"),
    (r"\b(a|the) drip\b", "an IV fluid line", "Jargon"),
    (r"\bquery (\w+)", r"possible \1", "Jargon"),
    (r"\bSOB\b", "short of breath", "Jargon"),
    (r"\bBD\b", "twice a day", "Jargon"),
    (r"\bTDS\b", "three times a day", "Jargon"),
    (r"\bQDS\b", "four times a day", "Jargon"),
    (r"\bPRN\b", "when needed", "Jargon"),
    (r"\bGP\b", "family doctor", "Jargon"),
    (r"\bA ?& ?E\b", "the emergency department", "Jargon"),
    (r"\bwould you be able to\b", "can you", "Indirect phrasing"),
    (r"\bI'?m grand\b", "I am fine", "Irish English"),
]
# Abbreviations are matched case-sensitively so that e.g. "sob" or "bd" inside normal speech is left alone.
CASE_SENSITIVE = {r"\bNBM\b", r"\bSOB\b", r"\bBD\b", r"\bTDS\b", r"\bQDS\b", r"\bPRN\b", r"\bGP\b"}
_REWRITES = [(re.compile(p, 0 if p in CASE_SENSITIVE else re.I), r, label) for p, r, label in REWRITES]


def plain_english(text: str):
    out, changes = text, []
    for rx, repl, label in _REWRITES:
        def sub(m, repl=repl, label=label):
            new = m.expand(repl)
            changes.append({"from": m.group(0), "to": new, "label": label})
            return new
        out = rx.sub(sub, out)
    out = re.sub(r"\s+", " ", out).strip()
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out, changes


# ---------------------------------------------------------------------------
# 2. Medical-information detection (English), per the team's UI spec section 5
# ---------------------------------------------------------------------------
MEDICINES = [
    "paracetamol", "acetaminophen", "ibuprofen", "aspirin", "codeine", "morphine", "tramadol", "oxycodone",
    "penicillin", "amoxicillin", "co-amoxiclav", "flucloxacillin", "clarithromycin", "doxycycline",
    "ceftriaxone", "gentamicin", "metronidazole", "antibiotics?", "insulin", "metformin", "warfarin",
    "apixaban", "rivaroxaban", "heparin", "enoxaparin", "clopidogrel", "salbutamol", "inhaler",
    "prednisolone", "steroids?", "omeprazole", "lansoprazole", "ondansetron", "cyclizine", "diclofenac",
    "naproxen", "furosemide", "ramipril", "amlodipine", "atorvastatin", "levothyroxine", "sertraline",
    "diazepam", "lorazepam", "epipen", "adrenaline",
]
SYMPTOMS = [
    "chest pain", "pain", "headache", "dizziness", "dizzy", "nausea", "vomiting", "short of breath",
    "shortness of breath", "breathless", "fever", "temperature", "cough", "bleeding", "blood", "rash",
    "swelling", "numbness", "tingling", "faint", "fainted", "diarrhoea", "diarrhea", "constipation",
    "seizure", "fit", "confused", "weakness",
]
CONDITIONS = [
    "diabetes", "diabetic", "asthma", "epilepsy", "high blood pressure", "hypertension", "heart attack",
    "heart failure", "stroke", "kidney disease", "liver disease", "copd", "hiv", "hepatitis", "appendicitis",
    "infection", "sepsis", "fracture", "broken",
]
PROCEDURES = [
    "operation", "surgery", "procedure", "anaesthetic", "anesthetic", "general anaesthetic", "mri", "ct scan",
    "x-ray", "xray", "scan", "ultrasound", "blood test", "blood tests", "injection", "catheter", "drip",
    "endoscopy", "biopsy", "stitches", "iv fluid line", "small tube in the vein",
]
UNITS = r"(mg|milligrams?|mcg|micrograms?|g|grams?|ml|millilitres?|milliliters?|units?|puffs?|tablets?|capsules?|drops?|sachets?)"
NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
    "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100", "half": "0.5", "once": "1",
    "twice": "2",
}
NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(NUMBER_WORDS) + r")"

FLAG_RULES = [
    ("dose", "critical", "Check the dose and unit", rf"\b{NUM}\s?(?:-\s?)?{UNITS}\b"),
    ("frequency", "critical", "Check how often",
     rf"\b(every\s+{NUM}\s+hours?|{NUM}\s+times\s+(a|per)\s+(day|week)|once|twice)( a| per)?( day| daily| week)?\b"),
    ("allergy", "critical", "Allergy: confirm the exact substance", r"\ballerg(y|ic|ies)\b( to [\w-]+)?"),
    ("pregnancy", "critical", "Pregnancy changes treatment", r"\bpregnan(t|cy)\b"),
    ("laterality", "critical", "Left or right must be correct", r"\b(left|right|both sides)\b"),
    ("medication", "critical", "Check the medicine name", r"\b(" + "|".join(MEDICINES) + r")\b"),
    ("negation", "review", "A negation reverses the meaning",
     r"\b(no|not|don'?t|do not|never|none|nothing|without|isn'?t|aren'?t|won'?t|can'?t|cannot|didn'?t|haven'?t|no more than)\b"),
    ("number", "review", "Check this number", rf"\b{NUM}\b|\b\d{{2,3}}/\d{{2,3}}\b"),
    ("condition", "review", "Medical condition", r"\b(" + "|".join(CONDITIONS) + r")\b"),
    ("procedure", "review", "Procedure or test", r"\b(" + "|".join(PROCEDURES) + r")\b"),
    ("symptom", "info", "Symptom", r"\b(" + "|".join(SYMPTOMS) + r")\b"),
]
_FLAG_RULES = [(c, s, why, re.compile(p, re.I)) for c, s, why, p in FLAG_RULES]
SEVERITY_RANK = {"critical": 3, "review": 2, "info": 1}


def medical_flags(text: str):
    found = []
    for cat, sev, why, rx in _FLAG_RULES:
        for m in rx.finditer(text):
            span = (m.start(), m.end())
            if any(not (span[1] <= f["start"] or span[0] >= f["end"]) for f in found):
                continue  # earlier (higher-priority) rule already covers this text
            found.append({"text": m.group(0), "start": span[0], "end": span[1],
                          "category": cat, "severity": sev, "reason": why})
    return sorted(found, key=lambda f: f["start"])


# ---------------------------------------------------------------------------
# 3. Risk tiers: red topics always go to a human interpreter
# ---------------------------------------------------------------------------
RED_TOPICS = [
    ("Consent", r"\bconsent\b|\bsign (the|this) (form|paper)\b|\bagree to (the|this|an?) (operation|surgery|procedure)\b|\brisks? of (the )?(operation|surgery|procedure|anaesthetic)\b"),
    ("Mental capacity", r"\b(mental )?capacity\b"),
    ("Bad news", r"\b(cancer|tumou?r|malignan\w*|terminal|incurable|metasta\w*|bad news|passed away|miscarriage|no heartbeat|has died|have died)\b"),
    ("End of life", r"\b(end of life|palliative|do not resuscitate|dnr|dnar|resuscitat\w*|life support|comfort care)\b"),
    ("Safeguarding", r"\b(safe at home|(hurts?|hurting|hit|hits|hitting) you\b|abus\w*|violence|trafficking|afraid of (him|her|them|your))"),
    ("Self-harm", r"\b(suicid\w*|kill (my|your)self|end (my|your) life|self[- ]harm|hurt(ing)? (my|your)self|want to die|overdose)\b"),
]
_RED = [(name, re.compile(p, re.I)) for name, p in RED_TOPICS]
_DISCHARGE = re.compile(r"\b(discharge|discharged|going home|when you go home|at home)\b", re.I)


def risk_tier(text: str, flags):
    reasons = [name for name, rx in _RED if rx.search(text)]
    if _DISCHARGE.search(text) and any(f["category"] in ("medication", "dose", "frequency") for f in flags):
        reasons.append("Discharge medicines")
    if reasons:
        return {"tier": "red", "reasons": reasons,
                "message": f"{reasons[0]} needs a professional interpreter."}
    clinical = [f for f in flags if f["severity"] in ("critical", "review") or f["category"] in ("symptom", "condition")]
    if clinical:
        cats = sorted({f["category"] for f in clinical}, key=lambda c: -SEVERITY_RANK.get(
            next(f["severity"] for f in clinical if f["category"] == c), 0))
        return {"tier": "amber", "reasons": cats, "message": "Clinical details: checked after translation."}
    return {"tier": "green", "reasons": [], "message": "Routine conversation."}


# ---------------------------------------------------------------------------
# 4. Critical-detail checks: numbers, negation, left/right, medicines must survive translation
# ---------------------------------------------------------------------------
NEGATION = {
    "en": r"\b(no|not|never|none|nothing|without|cannot|neither|nor)\b|\b\w+n['’]t\b",   # any "n't": don't, shouldn't, mustn't…
    "uk": r"(?<!\w)(не|ні|немає|нема|ніколи|ніщо|нічого|без)(?!\w)",
    "ru": r"(?<!\w)(не|нет|никогда|ничего|ни|без)(?!\w)",
    "pl": r"(?<!\w)(nie|nigdy|nic|brak|bez|żadn\w*)(?!\w)",
    "ro": r"(?<!\w)(nu|niciodată|nimic|fără|niciun\w*)(?!\w)",
    "ar": r"(?<![ء-ي])(?:و|ف)?(لا|لم|لن|ليس|ليست|غير|بدون|دون)(?![ء-ي])",
    "ga": r"(?<!\w)(ní|níl|níor|nach|nár|gan|ná|cha)(?!\w)",
    "fr": r"(?<!\w)(ne|n['’]|pas|jamais|rien|aucun\w*|sans|non)(?!\w)",
    "es": r"(?<!\w)(no|nunca|nada|ningún|ninguna|ninguno|sin|tampoco)(?!\w)",
    "pt": r"(?<!\w)(não|nunca|nada|nenhum\w*|sem)(?!\w)",
    "it": r"(?<!\w)(non|mai|niente|nulla|nessun\w*|senza)(?!\w)",
    "de": r"(?<!\w)(nicht|kein\w*|nie|niemals|nichts|ohne)(?!\w)",
    "ur": r"(نہیں|نہ|مت|بغیر)",
    "ko": r"(안\s|않|못|없|아니|말고|마세요|마십시오)",
    "zh": r"(不|没|沒|无|無|别|別|勿)",
}
LEFT = {"en": r"\bleft\b", "uk": r"лів", "ru": r"лев", "pl": r"\blew", "ro": r"stâng|stang", "ar": r"يسار|أيسر|يسرى|اليسرى|الأيسر",
        "ga": r"\bclé\b|\bchlé\b", "fr": r"gauche", "es": r"izquierd", "pt": r"esquerd", "it": r"sinistr", "de": r"\blink",
        "ur": r"بائیں|بایاں", "ko": r"왼", "zh": r"左"}
RIGHT = {"en": r"\bright\b", "uk": r"прав(?!д)", "ru": r"прав(?!д)", "pl": r"\bpraw(?!d)", "ro": r"\bdrept|dreapt", "ar": r"يمين|أيمن|يمنى|اليمنى|الأيمن",
         "ga": r"\bdeis\b|\bdheis\b", "fr": r"\bdroit", "es": r"derech", "pt": r"direit", "it": r"\bdestr", "de": r"\brecht",
         "ur": r"دائیں|دایاں", "ko": r"오른", "zh": r"右"}
# Arabic-Indic, Persian/Urdu, Devanagari, Bengali and Gurmukhi digits -> 0-9
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹०१२३४५६७८९০১২৩৪৫৬৭৮৯੦੧੨੩੪੫੬੭੮੯", "0123456789" * 5)


def _numbers(text: str, lang: str):
    t = text.translate(_ARABIC_DIGITS).lower()
    freq = []
    if lang == "en":
        # How often: "twice", "2 times" and "two times" are the same instruction ("2x"); "twice" -> "once" is caught
        def _freq(m):
            w = m.group(1)
            freq.append((w if w.isdigit() else NUMBER_WORDS.get(w, w)) + "x")
            return " "
        t = re.sub(r"\b(once|twice)\b", lambda m: _freq(m), t)
        t = re.sub(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+times\b", _freq, t)
    nums = [n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", t)]
    if lang == "en":
        nums += [NUMBER_WORDS[w] for w in re.findall(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", t)]
    return Counter([n.rstrip("0").rstrip(".") if "." in n else n for n in nums] + freq)


def tokens(text: str, lang: str):
    """None means "we have no word list for this language", so that check is skipped rather than guessed."""
    if lang == "en":
        text = re.sub(r"\s+(['’]\w)", r"\1", text)   # the translator sometimes writes "Don 't"
    return {
        "numbers": _numbers(text, lang),
        "negation": len(re.findall(NEGATION[lang], text, re.I)) if lang in NEGATION else None,
        "left": bool(re.search(LEFT[lang], text, re.I)) if lang in LEFT else None,
        "right": bool(re.search(RIGHT[lang], text, re.I)) if lang in RIGHT else None,
        "meds": {m.lower() for m in re.findall(r"\b(" + "|".join(MEDICINES) + r")\b", text, re.I)} if lang == "en" else set(),
    }


def critical_checks(source: str, src_lang: str, translation: str, tgt_lang: str, back: str):
    """Compare what must not change. For clinician turns the source and the back-translation are both
    English; for patient turns we compare the patient's words with the English translation."""
    s = tokens(source, src_lang)
    e_lang = "en"
    english_side = back if src_lang == "en" else translation
    e = tokens(english_side, e_lang)
    if src_lang != "en":   # the patient's "2 razy" is the English "twice": compare frequencies as plain numbers
        e["numbers"] = Counter({k.rstrip("x"): v for k, v in e["numbers"].items()})
    checks = []
    if s["numbers"] or e["numbers"]:
        missing = [n for n in s["numbers"] if n not in e["numbers"]]
        added = [n for n in e["numbers"] if n not in s["numbers"]]
        # "one tablet" may come back as "a tablet": that is fine, as long as no other number took its place
        if missing == ["1"] and not added and re.search(r"\b(a|an)\b", english_side, re.I):
            missing = []
        ok = not missing and not added
        detail = ("All numbers kept: " + ", ".join(s["numbers"])) if ok else "; ".join(
            x for x in ("Missing after translation: " + ", ".join(missing) if missing else "",
                        "New number appeared: " + ", ".join(added) if added else "") if x)
        checks.append({"name": "Numbers", "ok": ok, "detail": detail})
    if s["negation"] is not None and (s["negation"] or e["negation"]):
        # English vs English back-translation: every negation must survive ("do NOT stop ... without" needs both).
        # Across languages (patient turns) only presence is compared, because Slavic double negation
        # ("нічого не їла" = "haven't eaten anything") changes the count naturally.
        ok = s["negation"] == e["negation"] if src_lang == "en" else bool(s["negation"]) == bool(e["negation"])
        checks.append({"name": "Negation", "ok": ok,
                       "detail": "\"Not / no\" kept" if ok else "A \"not / no\" was lost or added"})
    for side in ("left", "right"):
        if s[side] is not None and (s[side] or e[side]):
            ok = s[side] == e[side]
            checks.append({"name": side.capitalize(), "ok": ok,
                           "detail": f"\"{side}\" kept" if ok else f"\"{side}\" changed in translation"})
    if s["meds"]:
        missing = [m for m in s["meds"] if not any(m[:5] in x for x in e["meds"]) and m[:5] not in back.lower()]
        checks.append({"name": "Medicines", "ok": not missing,
                       "detail": "Medicine names kept" if not missing else "Check: " + ", ".join(missing)})
    return checks


def meaning_verdict(sim: float):
    score = max(0, min(100, round((sim - 0.45) / 0.5 * 100)))
    if score >= 80:
        return {"score": score, "sim": round(sim, 3), "verdict": "Meaning kept"}
    if score >= 60:
        return {"score": score, "sim": round(sim, 3), "verdict": "Check the meaning"}
    return {"score": score, "sim": round(sim, 3), "verdict": "Meaning may be lost: rephrase"}


def turn_status(checks, meaning, glossary):
    if any(not c["ok"] for c in checks) or meaning["score"] < 60:
        return "fail"
    if meaning["score"] < 80 or any(not g["ok"] for g in glossary) or any(c.get("warn") for c in checks):
        return "warn"
    return "ok"


# ---------------------------------------------------------------------------
# Emergency mode: medication instructions belong in Standard mode
# ---------------------------------------------------------------------------
_QUESTION = re.compile(r"\?\s*$|^\s*(are|do|did|does|have|has|had|is|was|were|any|what|which|when|how|who|can you|could you|"
                       r"would you|will you|tell me|show me)\b", re.I)
_INSTRUCTION = re.compile(r"\b(take|taking|give|giving|use|inject|apply|start|stop|continue|increase|reduce|double|halve|"
                          r"swallow|inhale|chew|we('ll| will) give|you (need|should|must|have) to|you('ll| will) (need|get|have))\b", re.I)


def medication_instruction(text: str, flags):
    """True when a clinician sentence tells the patient what medicine or dose to take (not a question about it).
    In Emergency mode these are held and the clinician is offered Standard mode, where the dose is checked on
    screen before it is spoken."""
    cats = {f["category"] for f in flags}
    if not cats & {"medication", "dose", "frequency"}:
        return False
    if _QUESTION.search(text):
        return False
    return bool(cats & {"dose", "frequency"}) or bool(_INSTRUCTION.search(text))
