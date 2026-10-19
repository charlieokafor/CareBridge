"""Turns the overnight evaluations into language licences (server/lang_licence.json).

Translation: every language was translated English -> language -> English with both NLLB sizes on 20
clinical sentences (eval/lang_eval.json). Each sentence passes when its meaning score is >= 80 and every
critical-detail check passes (re-scored here with the current checker). A language is licensed on the
model with the best pass rate (the faster 600M model when it is as good), and only if that model passes
at least 90% of sentences with an average meaning score of 92 or more. Otherwise it is removed.

Speech: only languages that passed the speech test (eval/speech_results.json: language detected correctly
in all clips, character error rate <= 0.2) may use speech; every other licensed language works by typing
and tap answers until it has been tested."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from server import safety  # noqa: E402

PASS_OK, PASS_AVG, MAX_CER = 0.9, 92, 0.2


def rescore(rows):
    ok = 0
    for r in rows:
        checks = safety.critical_checks(r["en"], "en", r["tr"], "xx", r["back"])
        r["failed"] = [c["name"] for c in checks if not c["ok"]]
        ok += r["score"] >= 80 and not r["failed"]
    return ok / len(rows), sum(r["score"] for r in rows) / len(rows)


def main():
    mt = json.load(open(os.path.join(HERE, "lang_eval.json")))
    speech_path = os.path.join(HERE, "speech_results.json")
    speech = json.load(open(speech_path)) if os.path.exists(speech_path) else {}
    licence = {}
    print(f"{'lang':5} {'600m ok/avg':>13} {'1.3b ok/avg':>13}  model   speech")
    for lang, res in mt.items():
        scores = {m: rescore(res[m]["rows"]) for m in ("600m", "1.3b") if m in res}
        best = max(scores, key=lambda m: scores[m])
        if "600m" in scores and scores["600m"][0] >= scores[best][0] and scores["600m"][1] >= scores[best][1] - 1.5:
            best = "600m"
        ok, avg = scores[best]
        model = best if ok >= PASS_OK and avg >= PASS_AVG else "remove"
        sp = speech.get(lang)
        speech_ok = (sp["detected"] == sp["of"] and sp["cer"] <= MAX_CER) if sp else None   # None = not tested yet
        licence[lang] = {"model": model, "speech": speech_ok, "mtScore": round(avg, 1), "okRate": round(ok, 2)}
        if sp:
            licence[lang].update({"asrCer": sp["cer"], "detection": f"{sp['detected']}/{sp['of']}"})
        fmt = lambda m: f"{scores[m][0]:.2f}/{scores[m][1]:5.1f}" if m in scores else "-"
        print(f"{lang:5} {fmt('600m'):>13} {fmt('1.3b'):>13}  {model:7} {'yes' if speech_ok else ('no (' + (str(sp['detected']) + '/3, cer ' + str(sp['cer']) + ')' if sp else 'untested)'))}")
    with open(os.path.join(os.path.dirname(HERE), "server", "lang_licence.json"), "w") as f:
        json.dump(licence, f, indent=1)
    kept = [l for l, v in licence.items() if v["model"] != "remove"]
    print(f"\nLicensed {len(kept)} of {len(licence)}: {', '.join(kept)}")
    print("Removed:", ", ".join(l for l, v in licence.items() if v["model"] == "remove"))
    print("Speech allowed:", ", ".join(l for l in kept if licence[l]["speech"]))


if __name__ == "__main__":
    main()
