# CareBridge

Safe medical conversations across languages, for hospital staff. Built for the Healthcare Innovation
Challenge 2026 (Tallaght University Hospital, Challenge 6) by Mohd Wafa, Chijindu Okafor, Bakht Zia Khan and Eriitunu Adesioye.

**Live app:** https://on11sjoe8f.execute-api.eu-west-1.amazonaws.com (Dublin, staff sign-in required)

## What it does

- **Standard Consultation**: speak or type, then review an editable transcript with highlighted medical
  details. Critical details (doses, medicines, allergies, left/right, negations) must be confirmed before
  translation. Irish English and jargon are rewritten into plain English first.
- **Emergency**: one tap to start. Tap to talk (one button per speaker once the language is known), or hands-free in a quiet room. Detects the language, cleans up background noise, translates and speaks immediately; recordings too noisy to trust are never translated. Alerts never block.
- **Risk tiers**: routine (green), clinical (amber, checked), interpreter (red: consent, bad news,
  safeguarding, self-harm, discharge medicines), which stops and offers a human interpreter.
- **Safety net on every sentence**: back-translation, a meaning score, and hard checks that numbers,
  negations, left/right, medicines and glossary terms survive translation.
- **25 patient languages** (Oct 2026): 5 pilot languages with team-drafted phrases; Irish, French, Spanish, Urdu and
  Korean team-drafted; German, Hindi and (added Oct 2026) Portuguese (Brazil), Mandarin, Cantonese, Italian, Turkish, Vietnamese, Filipino, Bengali,
  Swahili, Indonesian, Japanese, Czech and Greek with interface text from Amazon Translate (pending interpreter
  review). Each new language passed the 20-sentence clinical screen through the app's own safety net
  (`eval/aws_compare/clinical_screen.py`: 18-20/20, level with Polish and Ukrainian). All but Irish have speech
  recognition and a voice (Amazon Transcribe does not offer Irish; it works by typing and tap answers).
  Cantonese is translated through Amazon's Mandarin model + Hong Kong character conversion (its Traditional
  Chinese model mistranslated clinical terms).
- **Multi-device sessions**: clinician phone, patient bedside iPad (consent, quick replies, pain faces,
  everything in the patient's language) and a live audit laptop, joined with a 4-digit code.
- **Body map**: the patient taps where it hurts (front and back views); the clinician sees "Pain: lower right abdomen"
  with the region highlighted. Needs no shared language.
- **Interpreter hand-off brief**: when a conversation is escalated, the interpreter opens a live brief (why they were
  called, key facts such as allergies, pain and location, sentences the safety net flagged, and the conversation so far).
  Join with the session code as "Interpreter".
- **Offline phrasebook**: checked phrases, tap answers, pain scale and body map work without Wi-Fi (service worker +
  a copy of the phrasebook on the device); taps are logged and added to the audit log when back online.
- **Audit and record**: every turn is stored as text (never audio) in DynamoDB; a finished session exports as
  an HL7 FHIR R4 DocumentReference (also saved to S3).

## Architecture

```
iPad / phone / laptop ──https──> API Gateway (HTTP API, adds a shared-secret header)        AWS eu-west-1 (Dublin)
                                     │
                                     ▼
                     EC2 m7i-flex.large (FastAPI, Amazon Linux 2023)
                     ├─ CareBridge safety layer
                     │   ├─ Clinical Lexicon: 13,000+ medicines, brands, drug classes, allergens, conditions,
                     │   │  symptoms, body parts; codes (ATC, ICD); names in 12+ languages; look-alike drug pairs
                     │   ├─ correction of misheard medicine names, "did you mean A or B?" for sound-alikes
                     │   ├─ cross-language check: every critical term must come out as the same coded entry
                     │   └─ safety.py rules (plain English, flags, risk tiers, numbers/negation/left-right checks,
                     │      Emergency medication hold)
                     ├─ Amazon Transcribe real-time ──(fallback)── Whisper small (also the 2nd language opinion)
                     ├─ Amazon Translate ──(fallback)── NLLB-200 600M / 1.3B
                     ├─ Amazon Polly neural ──(fallback)── Piper / MMS voices
                     └─ multilingual MiniLM (meaning check)
                                     │
        DynamoDB (sessions, turns, audit; point-in-time recovery)   S3 (lexicon, versioned; FHIR exports; deploys)
```

Why these engines: see `eval/aws_compare` and the benchmark report. In emergency-department noise at 5 dB,
Transcribe got 22–28% of words wrong vs 67% for the previous Whisper set-up; the lexicon layer raised correct
recognition of spoken drug names from 60% to 86% with no wrong changes to ordinary speech.

**Language detection (Emergency mode):** the first patient sentence is transcribed in every candidate language in
parallel and checked against Whisper's language guess. It is accepted only when both agree, enough of the sentence
was recognised and no second language fits almost as well (0 wrong on 116 noisy test clips and on 144 real-speaker
clips in 18 languages, `eval/aws_compare/lid_newlangs.py`; 68-72% decided automatically); otherwise the patient taps
their language. Mandarin and Cantonese are told apart by Transcribe (16 clips, 0 confused). The patient then confirms the
language once, and it is locked: one Tap-to-talk button per speaker.

**Confidence tiers:** Transcribe word confidence ≥ 0.8 → spoken; 0.6–0.8, a corrected medicine name, or a number or
medicine heard below 0.9 → shown for checking first; < 0.6 → asked to repeat.

**Emergency mode** is for language, symptoms, allergies and questions. A clinician sentence that instructs a
medicine or dose is held and the clinician is offered Standard mode (the dose is checked on screen first).

## Layout

| Path | What |
| --- | --- |
| `server/main.py` | API routes, staff auth, sessions, turns, FHIR export, test endpoint |
| `server/safety.py` | Plain-English rewrite, medical flags, risk tiers, critical-detail checks |
| `server/aws_engines.py`, `server/aws_transcribe.py` | Amazon Transcribe (WebSocket streaming), Translate, Polly, with the self-hosted models as fallback |
| `server/lexicon.py`, `server/data/lexicon.json.gz` | The Clinical Lexicon: matching, correction, cross-language term check |
| `server/engines.py` | Whisper, NLLB, MiniLM, Piper (and mock engines for laptop development) |
| `server/phrasebank.py` | Languages, patient-facing text, pre-checked phrases, glossary, demo clips (drafts pending interpreter review) |
| `server/store.py`, `server/fhir.py` | DynamoDB/in-memory storage, FHIR DocumentReference |
| `web/` | The app (vanilla HTML/CSS/JS, Apple-style design, works on iPad, phone and laptop) |
| `infra/` | `create-infra.sh`, `ec2-setup.sh` (model install), `deploy.sh`, `remote.sh` (Systems Manager) |
| `eval/error_injection.py` | Safety-net stress test: 27 of 28 planted errors caught, 0 false alarms on 20 sentences |
| `eval/lang_eval_server.py`, `eval/speech_eval.py`, `eval/build_licence.py` | Per-language licensing: translation quality with both NLLB sizes on 20 clinical sentences, speech and language-detection tests, and the resulting `server/lang_licence.json` (model per language, speech allowed or not, languages removed) |
| `infra/lexicon/` | Lexicon pipeline: Wikidata build, curation, gap fill, review CSVs, seed lists |
| `eval/aws_compare/` | Self-hosted vs AWS benchmark: speech in noise, language detection, drug names, translation |
| `pitch/` | Source of the pitch deck |

## Running

Local development (no models): `CB_ENGINE=mock uvicorn server.main:app --port 8765`, then open http://127.0.0.1:8765
(staff code `123456` locally).

AWS (any Linux/macOS shell or WSL with the AWS CLI configured; region defaults to eu-west-1):
- `infra/create-infra.sh` once, then `infra/deploy.sh` for each code change. `infra/start.sh` / `infra/stop.sh`.
- `infra/create-start-link.sh`: a web link that starts the server. `infra/autostop.sh` (run on the server via
  `infra/remote.sh`) stops it N hours after each start (`AUTOSTOP_HOURS=0` turns this off).
- `infra/lexicon/build_all.sh`: rebuilds and publishes the Clinical Lexicon and the AWS vocabularies.
- `infra/lexicon/review.py export`: CSVs for interpreter/pharmacist review; put the filled CSVs in
  `infra/lexicon/seed/reviews/` and rebuild.

Secrets and resource IDs live in `~/carebridge-aws/` (outside the repo). `CB_ENGINE=selfhosted` runs without the
AWS AI services.
