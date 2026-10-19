"""Exports a finished session as an HL7 FHIR R4 DocumentReference for the patient record."""
import base64
from datetime import datetime, timezone

from .phrasebank import LANGUAGES


def _iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def transcript_text(session, turns):
    lang = LANGUAGES.get(session.get("patientLang") or "", {}).get("name", "not set")
    lines = [
        "CareBridge interpreted consultation (AI-assisted, pending clinical validation)",
        f"Patient record number: {session.get('mrn') or 'not recorded'}",
        f"Patient language: {lang}",
        f"Mode: {session.get('mode', 'standard')}   Staff: {session.get('createdBy', '')}",
        f"Started: {_iso(session['createdAt'])}",
        "",
    ]
    for t in turns:
        when = _iso(t["ts"])[11:19]
        if t.get("type") == "event":
            lines.append(f"[{when}] EVENT {t['kind'].upper()}: {t.get('detail', '')} ({t.get('by', '')})")
            continue
        who = "Clinician" if t["speaker"] == "clinician" else "Patient"
        lines.append(f"[{when}] {who} ({t['srcLang']}): {t['original']}")
        if t.get("plain") and t["plain"] != t["original"]:
            lines.append(f"           Plain English: {t['plain']}")
        lines.append(f"           Translation ({t['tgtLang']}): {t['translation']}")
        lines.append(f"           Back-translation: {t.get('backTranslation', '')}")
        lines.append(f"           Risk: {t['risk']['tier']}  Meaning score: {t['meaning']['score']}  "
                     f"Checks: {', '.join(c['name'] + ('=ok' if c['ok'] else '=FAIL') for c in t['checks']) or 'none'}"
                     f"  Engine: {t.get('engine')}")
    return "\n".join(lines)


def document_reference(session, turns):
    text = transcript_text(session, turns)
    end = session.get("endedAt") or (turns[-1]["ts"] if turns else session["createdAt"])
    return {
        "resourceType": "DocumentReference",
        "id": f"carebridge-{session['id']}",
        "status": "current",
        "docStatus": "final" if session.get("status") == "ended" else "preliminary",
        "type": {"coding": [{"system": "http://loinc.org", "code": "51855-5", "display": "Patient Note"}],
                 "text": "Interpreted consultation record (AI-assisted)"},
        "subject": {"identifier": {"system": "urn:tuh:mrn", "value": session.get("mrn") or "unknown"}},
        "date": _iso(end),
        "author": [{"display": session.get("createdBy", "CareBridge user")}],
        "description": "CareBridge bilingual transcript with risk tiers, safety checks and interpreter escalations",
        "securityLabel": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                                       "code": "R", "display": "restricted"}]}],
        "content": [{"attachment": {"contentType": "text/plain; charset=utf-8", "language": "en",
                                    "title": "Bilingual transcript",
                                    "data": base64.b64encode(text.encode("utf-8")).decode("ascii")}}],
        "context": {"period": {"start": _iso(session["createdAt"]), "end": _iso(end)}},
    }
