"""Amazon Transcribe REAL-TIME (streaming) on the noise test set, language known (Tap-to-talk case).
Audio is sent in 100 ms chunks at 2x real time. Records the final transcript and time from end of audio to final result.
Usage: python transcribe_stream.py SET_DIR REGION   (SET_DIR has meta.json and mix/*.wav) -> SET_DIR/transcribe_stream.json"""
import asyncio, json, os, sys, time, wave
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
D, REGION = sys.argv[1], sys.argv[2]
meta = json.load(open(f"{D}/meta.json"))
LOCALE = {"uk": "uk-UA", "pl": "pl-PL", "ro": "ro-RO", "ru": "ru-RU", "ar": "ar-SA"}
OUT = f"{D}/transcribe_stream.json"
out = json.load(open(OUT)) if os.path.exists(OUT) else {}


class H(TranscriptResultStreamHandler):
    def __init__(self, s):
        super().__init__(s); self.parts, self.confs, self.last = [], [], None

    async def handle_transcript_event(self, ev):
        for r in ev.transcript.results:
            if not r.is_partial and r.alternatives:
                a = r.alternatives[0]; self.parts.append(a.transcript); self.last = time.time()
                self.confs += [i.confidence for i in (a.items or []) if i.confidence is not None]


async def one(k, sem):
    async with sem:
        m = meta[k]
        lang = LOCALE.get(m["lang"]) or ("en-US" if m["kind"] == "fleurs" else "en-IE")
        with wave.open(f"{D}/mix/{k}.wav") as w:
            pcm = w.readframes(w.getnframes())
        for attempt in range(4):
            try:
                client = TranscribeStreamingClient(region=REGION)
                st = await client.start_stream_transcription(language_code=lang, media_sample_rate_hz=16000,
                                                             media_encoding="pcm")
                h = H(st.output_stream)

                async def feed():
                    step = 3200   # 100 ms
                    for i in range(0, len(pcm), step):
                        await st.input_stream.send_audio_event(audio_chunk=pcm[i:i + step]); await asyncio.sleep(0.05)
                    await st.input_stream.end_stream()
                    return time.time()
                t_end, _ = await asyncio.gather(feed(), h.handle_events())
                out[k] = {"text": " ".join(h.parts).strip(), "lang": m["lang"],
                          "conf": round(sum(h.confs) / len(h.confs), 3) if h.confs else None,
                          "s": round(max(0.0, (h.last or t_end) - t_end), 2)}   # wait after speech ends
                return
            except Exception as e:  # throttling etc.
                err = e; await asyncio.sleep(3 * (attempt + 1))
        out[k] = {"text": "", "lang": None, "error": str(err)[:200]}


async def main():
    sem = asyncio.Semaphore(10)
    todo = [k for k in sorted(meta) if k not in out]
    for i in range(0, len(todo), 50):
        await asyncio.gather(*[one(k, sem) for k in todo[i:i + 50]])
        json.dump(out, open(OUT, "w"), ensure_ascii=False); print(len(out), flush=True)
asyncio.run(main())
print("done", len(out), sum(1 for v in out.values() if v.get("error")), "errors")
