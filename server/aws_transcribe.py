"""Amazon Transcribe real-time (streaming) over its WebSocket API, for one recorded utterance.

CareBridge records one turn at a time (tap to talk), so the whole clip is streamed as fast as Transcribe accepts it
and the final transcript comes back a fraction of a second after the last chunk. Supports a fixed language (a
speaker's button) or language identification among a short list (Emergency mode before the language is known),
and a custom vocabulary per language (drug names, symptoms).

Uses only botocore (SigV4 presigning + event-stream decoding) and the `websockets` package that ships with
uvicorn[standard], so it works on the server's Python 3.11. Protocol:
https://docs.aws.amazon.com/transcribe/latest/dg/websocket.html"""
import asyncio
import binascii
import json
import os
import struct
from urllib.parse import urlencode

import botocore.session
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.eventstream import EventStreamBuffer

REGION = os.environ.get("CB_AWS_REGION") or os.environ.get("AWS_REGION") or "eu-west-1"
CHUNK = 6400            # 200 ms of 16 kHz 16-bit mono per audio event
SEND_GAP = 0.004        # seconds between events: ~50x real time
_session = botocore.session.get_session()


class TranscribeError(Exception):
    pass


def _presigned_url(params):
    host = f"transcribestreaming.{REGION}.amazonaws.com:8443"
    url = f"wss://{host}/stream-transcription-websocket?" + urlencode(sorted(params.items()))
    creds = _session.get_credentials().get_frozen_credentials()
    req = AWSRequest(method="GET", url=url.replace("wss://", "https://"))
    SigV4QueryAuth(creds, "transcribe", REGION, expires=300).add_auth(req)
    return req.url.replace("https://", "wss://")


def _header(name, value):
    n, v = name.encode(), value.encode()
    return struct.pack("B", len(n)) + n + b"\x07" + struct.pack(">H", len(v)) + v   # type 7 = string


def _audio_event(chunk: bytes) -> bytes:
    headers = _header(":content-type", "application/octet-stream") + _header(":event-type", "AudioEvent") \
        + _header(":message-type", "event")
    total = 12 + len(headers) + len(chunk) + 4
    prelude = struct.pack(">II", total, len(headers))
    prelude += struct.pack(">I", binascii.crc32(prelude) & 0xFFFFFFFF)
    msg = prelude + headers + chunk
    return msg + struct.pack(">I", binascii.crc32(msg) & 0xFFFFFFFF)


async def _stream(pcm: bytes, params: dict):
    import websockets
    url = _presigned_url(params)
    results, ident = [], None
    async with websockets.connect(url, max_size=2 ** 22, open_timeout=10) as ws:
        async def send():
            for i in range(0, len(pcm), CHUNK):
                await ws.send(_audio_event(pcm[i:i + CHUNK]))
                await asyncio.sleep(SEND_GAP)
            await ws.send(_audio_event(b""))   # empty audio event = end of stream

        async def receive():
            buf = EventStreamBuffer()
            async for raw in ws:
                buf.add_data(raw)
                for msg in buf:
                    h = msg.headers
                    if h.get(":message-type") == "exception":
                        raise TranscribeError(f"{h.get(':exception-type')}: {msg.payload.decode(errors='replace')[:300]}")
                    if h.get(":event-type") != "TranscriptEvent":
                        continue
                    for r in json.loads(msg.payload)["Transcript"]["Results"]:
                        if not r.get("IsPartial") and r.get("Alternatives"):
                            results.append(r)
        await asyncio.gather(send(), receive())
    return results


def transcribe_pcm(pcm: bytes, language_code=None, language_options=None, vocabularies=None, timeout=20.0):
    """pcm = 16 kHz mono 16-bit little-endian. Returns dict: text, languageCode, languageScores, confidence (mean word
    confidence 0-1), words. Give language_code, or language_options (2+ locale codes) for identification."""
    params = {"media-encoding": "pcm", "sample-rate": "16000"}
    if language_code:
        params["language-code"] = language_code
        if vocabularies and vocabularies.get(language_code):
            params["vocabulary-name"] = vocabularies[language_code]
    else:
        params["identify-language"] = "true"
        params["language-options"] = ",".join(language_options)
        names = [vocabularies[c] for c in language_options if vocabularies and vocabularies.get(c)]
        if names:
            params["vocabulary-names"] = ",".join(names)
    results = asyncio.run(asyncio.wait_for(_stream(pcm, params), timeout))
    words, scores, lang = [], {}, language_code
    for r in results:
        alt = r["Alternatives"][0]
        words += [i for i in alt.get("Items", []) if i.get("Type") == "pronunciation"]
        lang = r.get("LanguageCode") or lang
        for li in r.get("LanguageIdentification") or []:
            scores[li["LanguageCode"]] = max(scores.get(li["LanguageCode"], 0.0), float(li.get("Score", 0)))
    confs = [float(w["Confidence"]) for w in words if w.get("Confidence") is not None]
    return {"text": " ".join(r["Alternatives"][0]["Transcript"] for r in results).strip(),
            "languageCode": lang, "languageScores": scores,
            "confidence": round(sum(confs) / len(confs), 3) if confs else None,
            "words": [(w["Content"], w.get("Confidence")) for w in words]}
