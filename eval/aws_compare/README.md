# Self-hosted vs AWS benchmark (October 2026)

Every number in the CareBridge engine decision comes from these scripts and the JSON in `results/`.

| Question | Script | Result file |
|---|---|---|
| Speech accuracy in emergency-department noise (355 clips: FLEURS real speakers x 6 languages + clinical lines, 5 noise conditions) | `make_set.py`, `run_whisper.py` (Whisper variants, app pipeline), `transcribe_run.py` (batch), `transcribe_stream.py` / `stream_full.py` (real-time), `score.py` | `whisper_*.json`, `transcribe_*.json`, `stream_main_*.json`, `summary.json` |
| Language detection for the first sentence (116 clips) | `lid_parallel.py` (Transcribe in every language), `lid_stream.py` (Transcribe language ID), `wdetect.py` (Whisper) | `lid_parallel.json`, `lid_stream.json`, `whisper_detect.json` |
| Drug names heard right (10 drugs x 2 sentences x 6 languages x 3 noise levels) | `make_med_set.py`, `stream_full.py` with/without vocabulary; lexicon correction scored offline | `med_novocab.json`, `med_vocab.json`, `medset_meta.json` |
| Translation: NLLB vs Amazon Translate; terminology on/off | `translate_compare.py`, `terminology_test.py` | `translate.json`, `terminology.json` |

Synthetic noise and neural-voice clinical lines are the main limits: re-run with real ward recordings.
