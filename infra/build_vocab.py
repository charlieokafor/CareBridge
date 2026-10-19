"""Loads CareBridge's medical vocabulary (the lexicon, server/data/lexicon.json.gz) into AWS:
  - Amazon Transcribe custom vocabularies "carebridge-<locale>" (speech recognition hears drug names correctly)
  - Amazon Translate custom terminology "carebridge-medicines" (drug names translate to the right local name)
Safe to re-run after editing the JSON: updates in place. Run from the repo with AWS credentials for the account:
    python3 infra/build_vocab.py [--region eu-west-1]"""
import csv, io, json, os, re, sys, time, unicodedata
import boto3

REGION = sys.argv[sys.argv.index("--region") + 1] if "--region" in sys.argv else os.environ.get("CB_REGION", "eu-west-1")
HERE = os.path.dirname(os.path.abspath(__file__))
import gzip
LEX = json.load(gzip.open(os.path.join(HERE, "..", "server", "data", "lexicon.json.gz"), "rt", encoding="utf-8"))["entries"]
# Transcribe vocabularies hold at most 50 KB: the most-used medicines, drug classes and allergens go in first
# (Wikipedia coverage as the measure of use), then Irish brand names. The full lexicon is still used by the
# CareBridge correction layer, which has no size limit.
VOCAB_TYPES = {"medicine", "drug_class", "allergen"}
# Measured (eval/aws_compare, drug test): a vocabulary only helps for the words it contains (+3 points when it held
# the test drugs; 400 mixed terms or a list padded with brand names helped nothing). The CareBridge lexicon, which
# has no size limit, gave +29 points. So the AWS list holds generic names of the core hospital medicines only.
MAX_PHRASES = int(os.environ.get("CB_VOCAB_MAX", "60"))
CORE = [c.lower() for c in json.load(open(os.path.join(HERE, "lexicon", "seed", "core_medicines.json")))["core"]]
TERMS = {}


def _core_pos(e):
    ns = [n.lower() for n in e["names"].get("en", [])]
    return min((CORE.index(n) for n in ns if n in CORE), default=None)


for e in sorted((e for e in LEX if set(e["types"]) & VOCAB_TYPES and _core_pos(e) is not None),
                key=lambda e: -e.get("rank", 0)):
    row = {l: ns[0] for l, ns in e["names"].items() if ns}
    TERMS[e["id"]] = row
# CareBridge language -> Amazon Transcribe locale (languages Transcribe cannot recognise are left out: ga, ur)
LOCALES = {"en": "en-IE", "uk": "uk-UA", "ru": "ru-RU", "pl": "pl-PL", "ro": "ro-RO", "ar": "ar-SA",
           "fr": "fr-FR", "es": "es-ES", "de": "de-DE", "hi": "hi-IN", "ko": "ko-KR",
           # added Oct 2026
           "pt": "pt-BR", "it": "it-IT", "tr": "tr-TR", "vi": "vi-VN", "id": "id-ID", "cs": "cs-CZ", "el": "el-GR",
           "sw": "sw-KE", "tl": "tl-PH", "bn": "bn-IN", "zh": "zh-CN", "ja": "ja-JP", "yue": "zh-HK"}
tx = boto3.client("transcribe", region_name=REGION)
tr = boto3.client("translate", region_name=REGION)


def forms(word, lang):
    """The spellings a speaker produces: Arabic with and without the article, Polish/Ukrainian/Russian common cases."""
    if lang == "hi":   # Transcribe's Hindi character set has no nukta: फ़ -> फ
        word = unicodedata.normalize("NFD", word).replace("\u093c", "")
    out = {word}
    if lang == "ar" and word.startswith("ال"):
        out.add(word[2:])
    if lang == "pl" and word.endswith("a"):
        out.add(word[:-1] + "ę")      # accusative: "biorę metforminę", "uczulony na penicylinę"
    if lang == "ro" and word.endswith("ă"):
        out.add(word[:-1] + "a")      # definite: "metformina"
    return out


# Transcribe accepts only the language's own alphabet in a vocabulary (no digits, Greek, or other scripts)
ALPHABET = {
    "en": "a-z", "pl": "a-ząćęłńóśźż", "ro": "a-zăâîșşțţ", "fr": "a-zàâæçéèêëîïôœùûüÿ", "es": "a-záéíñóúü",
    "de": "a-zäöüß", "uk": "а-щьюяєіїґ'", "ru": "а-яё", "ar": "\u0621-\u064A", "hi": "\u0900-\u0963\u0970-\u097F",
    "ko": "\uAC00-\uD7A3",
    "pt": "a-záâãàçéêíóôõú", "it": "a-zàèéìíîòóùú", "tr": "a-zçğıöşüâî", "id": "a-z", "sw": "a-z", "tl": "a-zñ",
    "vi": "a-zàáâãèéêìíòóôõùúýăđĩũơưạ-ỹ", "cs": "a-záčďéěíňóřšťúůýž", "el": "α-ωάέήίόύώϊϋΐΰς",
    "bn": "\u0980-\u09E5\u09F0-\u09FF", "zh": "\u4e00-\u9fff", "yue": "\u4e00-\u9fff",
    "ja": "\u3040-\u30ff\u4e00-\u9fff",
}


def clean(w, lang):
    w = re.sub(r"^(?:rac|dl|\(±\)|[dlrs])[-‐ ]", "", w.strip(), flags=re.I)     # "rac-warfarin" -> warfarin
    w = w.lower() if lang not in ("ar", "hi", "ko", "bn", "zh", "yue", "ja") else w
    w = re.sub(r"[\s\-‐]+", "-", w).strip("-")
    return w if re.fullmatch(f"[{ALPHABET[lang]}]+(-[{ALPHABET[lang]}]+)*", w) else None


def phrases(lang):
    words, size = [], 0
    for row in TERMS.values():
        w = row.get(lang)
        if lang == "yue" and not w and row.get("zh"):      # Cantonese is written with the Chinese names
            import opencc
            w = opencc.OpenCC("s2hk").convert(row["zh"])
        w = clean(w, lang) if w else None
        if not w or len(w) < (2 if lang in ("zh", "yue", "ja") else 4):
            continue
        for f in forms(w.strip(), lang):
            p = clean(f, lang)
            if not p:
                continue
            if p not in words and size + len(p.encode()) + 1 < 48_000:
                words.append(p); size += len(p.encode()) + 1
        if len(words) >= MAX_PHRASES:
            break
    return sorted(set(words))


REJECTED = {}     # locale -> characters Transcribe refused (learned from FAILED vocabularies, then retried)


def upsert_vocabulary(lang, locale):
    name = f"carebridge-{locale}"
    ph = [p for p in phrases(lang) if not set(p) & REJECTED.get(locale, set())]
    try:
        tx.get_vocabulary(VocabularyName=name)
        exists = True
    except (tx.exceptions.NotFoundException, tx.exceptions.BadRequestException):   # "couldn't be found"
        exists = False
    (tx.update_vocabulary if exists else tx.create_vocabulary)(VocabularyName=name, LanguageCode=locale, Phrases=ph)
    return name, len(ph)


if __name__ == "__main__":
    pending, failed = {}, {}
    for lang, locale in LOCALES.items():
        while len(pending) >= 8:                 # Transcribe processes at most 10 vocabularies at a time
            time.sleep(5)
            for name in list(pending):
                state = tx.get_vocabulary(VocabularyName=name)["VocabularyState"]
                if state == "READY":
                    print(f"  {name}: READY ({pending.pop(name)} phrases)")
                elif state == "FAILED":
                    failed[name] = pending.pop(name)          # looked at again (and retried) below
        try:
            name, n = upsert_vocabulary(lang, locale)
            pending[name] = n
        except Exception as e:  # noqa: BLE001
            print(f"  {locale}: not created ({type(e).__name__}: {str(e)[:160]})")
    retries = {}
    pending.update(failed)
    while pending:
        time.sleep(5)
        for name in list(pending):
            v = tx.get_vocabulary(VocabularyName=name)
            bad = re.search(r'unsupported characters \("(.+?)"\)', v.get("FailureReason", ""))
            if v["VocabularyState"] == "FAILED" and bad and retries.get(name, 0) < 8:
                # a rare character (e.g. 莨 in a Chinese drug name): drop phrases containing it and try again
                locale = name[len("carebridge-"):]
                REJECTED.setdefault(locale, set()).update(bad.group(1))
                retries[name] = retries.get(name, 0) + 1
                lang = next(l for l, loc in LOCALES.items() if loc == locale)
                pending[name] = upsert_vocabulary(lang, locale)[1]
                continue
            if v["VocabularyState"] in ("READY", "FAILED"):
                print(f"  {name}: {v['VocabularyState']} ({pending.pop(name)} phrases)"
                      + (f" {v.get('FailureReason', '')[:200]}" if v["VocabularyState"] == "FAILED" else ""))
    # Translate terminology: one CSV, every language a column, usable in every direction
    langs = ["en", "uk", "ru", "pl", "ro", "ar", "ga", "fr", "es", "ur", "ko", "de", "hi"]
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(langs)
    n_terms = 0
    for key, row in TERMS.items():
        if key.startswith("brand:") or not row.get("en") or sum(1 for l in langs if row.get(l)) < 4:
            continue
        w.writerow([row.get(l, "") for l in langs]); n_terms += 1
    tr.import_terminology(Name="carebridge-medicines", MergeStrategy="OVERWRITE",
                          Description="CareBridge medicine names (server/medical_terms.json)",
                          TerminologyData={"File": buf.getvalue().encode("utf-8"), "Format": "CSV", "Directionality": "MULTI"})
    print(f"  Translate terminology carebridge-medicines: {n_terms} medicines x {len(langs)} languages")
