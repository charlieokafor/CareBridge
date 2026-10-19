"""Key facts and the interpreter hand-off brief.

When a conversation is escalated, the human interpreter gets one screen with: why they were called,
the key clinical facts so far, anything the safety net flagged, and the recent exchange in both
languages. They start with context instead of starting from zero."""
import re

from .phrasebank import LANGUAGES

BODY_REGIONS = {
    "head": "head", "neck": "neck or throat", "chest_r": "right side of the chest", "chest_l": "left side of the chest",
    "abd_upper": "upper abdomen", "abd_r": "lower right abdomen", "abd_l": "lower left abdomen", "groin": "groin or pelvis",
    "arm_r": "right upper arm", "arm_l": "left upper arm", "hand_r": "right forearm or hand", "hand_l": "left forearm or hand",
    "thigh_r": "right thigh", "thigh_l": "left thigh", "knee_r": "right knee", "knee_l": "left knee",
    "leg_r": "right lower leg or foot", "leg_l": "left lower leg or foot",
    "head_back": "back of the head", "neck_back": "back of the neck", "back_ur": "right upper back", "back_ul": "left upper back",
    "back_lr": "right lower back", "back_ll": "left lower back", "buttocks": "buttocks",
}


def key_facts(turns):
    """Facts a clinician (or interpreter) must not miss, pulled from the conversation."""
    facts = {}
    meds = set()
    for t in turns:
        if t.get("type") != "utterance":
            continue
        english = t["translation"] if t["speaker"] == "patient" else t.get("plain", "")
        if t["speaker"] == "patient":
            m = re.search(r"allerg(?:ic|y|ies) (?:to )?([\w-]+(?: [\w-]+)?)", english, re.I)
            if m and not re.match(r"(any|anything|something|medicines?)$", m.group(1), re.I):
                facts["allergy"] = {"kind": "critical", "label": f"Allergy: {m.group(1).rstrip('.,')}"}
            if t.get("phraseId") == "pain_scale_reply":
                n = re.search(r"\d+", t["translation"])
                if n:
                    facts["pain"] = {"kind": "review", "label": f"Pain {n.group()}/10"}
            if t.get("bodyRegions"):
                facts["where"] = {"kind": "review", "label": "Pain: " + ", ".join(BODY_REGIONS.get(r, r) for r in t["bodyRegions"])}
            side = re.search(r"\b(left|right)\b", english, re.I)
            if side and "where" not in facts:
                facts["side"] = {"kind": "review", "label": f"Side mentioned: {side.group(1).lower()}"}
            if re.search(r"pregnan", english, re.I):
                facts["preg"] = {"kind": "review", "label": "Pregnancy mentioned"}
        for f in t.get("flags", []):
            if f["category"] == "medication":
                meds.add(f["text"].lower())
    if meds:
        facts["meds"] = {"kind": "review", "label": "Medicines mentioned: " + ", ".join(sorted(meds))}
    return list(facts.values())


def interpreter_brief(session, turns):
    lang = session.get("patientLang")
    escalations = [t for t in turns if t.get("type") == "event" and t["kind"] == "escalation"]
    utterances = [t for t in turns if t.get("type") == "utterance"]
    red = [t for t in utterances if t["risk"]["tier"] == "red"]
    flagged = [t for t in utterances if t.get("status") == "fail" or t["risk"]["tier"] == "red"]
    reasons = sorted({r for t in red for r in t["risk"]["reasons"]})
    return {
        "sessionId": session["id"], "code": session.get("code"), "mrn": session.get("mrn"),
        "language": {"code": lang, "name": LANGUAGES.get(lang, {}).get("name"), "native": LANGUAGES.get(lang, {}).get("native")},
        "requestedBy": escalations[-1]["by"] if escalations else session.get("createdBy"),
        "requestedAt": escalations[-1]["ts"] if escalations else None,
        "reason": escalations[-1]["detail"] if escalations else "Not yet requested",
        "redTopics": reasons, "consent": session.get("consent"), "keyFacts": key_facts(turns),
        "needsAttention": [{"ts": t["ts"], "speaker": t["speaker"], "english": t["plain"] if t["speaker"] == "clinician" else t["translation"],
                            "original": t["original"], "why": (t["risk"]["reasons"] if t["risk"]["tier"] == "red" else
                                                               [c["name"] + " check failed" for c in t["checks"] if not c["ok"]])}
                           for t in flagged][-6:],
        "recent": [{"ts": t["ts"], "speaker": t["speaker"], "english": t["plain"] if t["speaker"] == "clinician" else t["translation"],
                    "patientLanguage": t["translation"] if t["speaker"] == "clinician" else t["original"]}
                   for t in utterances][-10:],
        "turnCount": len(utterances),
    }
