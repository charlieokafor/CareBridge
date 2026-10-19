"""Runs the same noise test set through Amazon Transcribe (batch API; same models as streaming).
Modes: "known" = language given (like pressing a speaker's Tap-to-talk button), "auto" = Transcribe identifies the
language among the Emergency-mode languages. Reads s3://BUCKET/bench/set/mix/*.wav, writes OUT/transcribe_<mode>.json.
Usage: python transcribe_run.py BUCKET REGION OUT_DIR [known,auto]"""
import json, os, sys, time, uuid
import boto3
BUCKET, REGION, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
MODES = (sys.argv[4] if len(sys.argv) > 4 else "known,auto").split(",")
tx = boto3.client("transcribe", region_name=REGION); s3 = boto3.client("s3", region_name=REGION)
meta = json.loads(s3.get_object(Bucket=BUCKET, Key="bench/set/meta.json")["Body"].read())
LOCALE = {"uk": "uk-UA", "pl": "pl-PL", "ro": "ro-RO", "ru": "ru-RU", "ar": "ar-SA"}
AUTO = ["en-IE", "uk-UA", "ru-RU", "pl-PL", "ro-RO", "ar-SA", "fr-FR", "de-DE", "hi-IN", "ko-KR", "es-ES"]
BACK = {v: k for k, v in LOCALE.items()} | {"en-IE": "en", "en-US": "en", "en-GB": "en", "fr-FR": "fr", "de-DE": "de",
                                             "hi-IN": "hi", "ko-KR": "ko", "es-ES": "es"}
run = uuid.uuid4().hex[:6]
for mode in MODES:
    path = f"{OUT}/transcribe_{mode}.json"
    out = json.load(open(path)) if os.path.exists(path) else {}
    todo = [k for k in sorted(meta) if k not in out]
    jobs = {}
    for k in todo:
        m = meta[k]
        name = f"cb-{run}-{mode}-{len(jobs)}"
        args = dict(TranscriptionJobName=name, Media={"MediaFileUri": f"s3://{BUCKET}/bench/set/mix/{k}.wav"},
                    MediaFormat="wav", OutputBucketName=BUCKET, OutputKey=f"bench/transcribe/{name}.json")
        if mode == "known":
            args["LanguageCode"] = LOCALE.get(m["lang"]) or ("en-US" if m["kind"] == "fleurs" else "en-IE")
        else:
            args["IdentifyLanguage"] = True; args["LanguageOptions"] = AUTO
        for attempt in range(8):
            try:
                tx.start_transcription_job(**args); break
            except tx.exceptions.LimitExceededException:
                time.sleep(2 + attempt * 2)
        jobs[name] = (k, time.time())
        time.sleep(0.06)
        if len(jobs) % 100 == 0:
            print(mode, "started", len(jobs), flush=True)
    pending = dict(jobs)
    while pending:
        time.sleep(5)
        for name in list(pending)[:150]:
            j = tx.get_transcription_job(TranscriptionJobName=name)["TranscriptionJob"]
            st = j["TranscriptionJobStatus"]
            if st not in ("COMPLETED", "FAILED"):
                continue
            k, t0 = pending.pop(name)
            if st == "FAILED":
                out[k] = {"text": "", "lang": None, "error": j.get("FailureReason")}
                continue
            r = json.loads(s3.get_object(Bucket=BUCKET, Key=f"bench/transcribe/{name}.json")["Body"].read())
            items = [i for i in r["results"]["items"] if i["type"] == "pronunciation"]
            confs = [float(i["alternatives"][0].get("confidence", 0)) for i in items]
            lc = j.get("LanguageCode")
            out[k] = {"text": r["results"]["transcripts"][0]["transcript"] if r["results"]["transcripts"] else "",
                      "lang": BACK.get(lc, lc), "langScore": j.get("IdentifiedLanguageScore"),
                      "conf": round(sum(confs) / len(confs), 3) if confs else None,
                      "jobSeconds": round(time.time() - t0, 1)}
        print(mode, "remaining", len(pending), flush=True)
        json.dump(out, open(path, "w"), ensure_ascii=False)
    json.dump(out, open(path, "w"), ensure_ascii=False)
    print("done", mode, len(out))
