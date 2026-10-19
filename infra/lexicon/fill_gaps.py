"""Fills names missing from the lexicon in the app's active languages with Amazon Translate.

Wikidata has no Ukrainian name for about half of all medicines, and almost none in Irish, Urdu or Hindi. Medicine
names are international (INN), so a machine translation inside a carrier sentence ("The medicine X.") gives the
local spelling reliably; each added name is recorded in entry["machine"][lang] so the app and reviewers can tell
it apart from curated names. Usage: python fill_gaps.py IN.json.gz OUT.json.gz [--region eu-west-1]"""
import gzip, json, re, sys, time
from collections import Counter
import boto3

LANGS = ["uk", "ru", "pl", "ro", "ar", "ga", "fr", "es", "ur", "ko", "de", "hi",
         "pt", "zh", "it", "tr", "vi", "tl", "bn", "sw", "id", "ja", "cs", "el"]   # Cantonese shares the zh names
# Languages written without spaces: the carrier word cannot be split off, so the sense goes in a parenthesis
PAREN = {"zh", "ja"}
PAREN_CARRIER = {"medicine": "{x} (a medicine)", "drug_class": "{x} (a type of medicine)",
                 "allergen": "{x} (an allergen)"}
TYPES = {"medicine", "drug_class", "allergen", "symptom", "anatomy"}
REGION = sys.argv[sys.argv.index("--region") + 1] if "--region" in sys.argv else "eu-west-1"
tr = boto3.client("translate", region_name=REGION)
CARRIER = {"medicine": "The medicine {x}.", "drug_class": "The medicine {x}.", "allergen": "An allergy to {x}.",
           # a bare word has no context ("chest" became a storage chest): the parenthesis says which sense
           "symptom": "{x} (a medical symptom)", "anatomy": "{x} (a part of the human body)"}
# carrier words a language puts in different places, removed explicitly
CARRIER_WORDS = {"ko": {"약", "약물", "약품", "의약품", "약이", "약을"}, "hi": {"दवा", "दवाई"}, "ur": {"دوا", "دوائی"},
                 "ga": {"An", "leigheas", "cógas"}, "ar": {"الدواء", "دواء"}}


def translate_lines(lines, lang):
    """Translates numbered lines in one request; returns {index: text}."""
    text = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines))
    for a in range(5):
        try:
            out = tr.translate_text(Text=text, SourceLanguageCode="en", TargetLanguageCode=lang)["TranslatedText"]
            break
        except Exception as e:  # noqa: BLE001
            time.sleep(2 * (a + 1)); err = e
    else:
        raise err
    res = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s*[.)।:]\s*(.+)", line)
        if m:
            res[int(m.group(1)) - 1] = m.group(2).strip()
    return res


def strip_carrier(texts, lang):
    """Removes the carrier words (those present in most outputs, plus known ones) and punctuation."""
    toks = [re.sub(r"[.,।۔!؟?«»\"“”]", " ", t).split() for t in texts]
    common = {w for w, c in Counter(w for t in toks for w in set(t)).items() if c > len(texts) * 0.5}
    common |= CARRIER_WORDS.get(lang, set())
    return [" ".join(w for w in t if w not in common).strip() for t in toks]


def display(e):
    """The proper English name to translate from (not an abbreviation such as "DMBG" for metformin)."""
    ns = e["names"]["en"]
    plain = [n for n in ns if re.fullmatch(r"[A-Za-z][A-Za-z ]{3,}", n) and not n.isupper()]
    return plain[0] if plain else ns[0]


def main(src, dst):
    lex = json.load(gzip.open(src, "rt", encoding="utf-8"))
    entries = [e for e in lex["entries"] if set(e["types"]) & TYPES
               and (set(e["types"]) & {"medicine", "drug_class", "allergen"} or e.get("rank", 0) >= 30)]
    added = Counter()
    for lang in LANGS:
        for kind in ("medicine", "drug_class", "allergen", "symptom", "anatomy"):
            todo = [e for e in entries if kind in e["types"] and not e["names"].get(lang)
                    and kind == next(t for t in ("medicine", "drug_class", "allergen", "symptom", "anatomy") if t in e["types"])]
            for i in range(0, len(todo), 40):
                batch = todo[i:i + 40]
                ens = [display(e) for e in batch]
                carrier = PAREN_CARRIER.get(kind, CARRIER[kind]) if lang in PAREN else CARRIER[kind]
                out = translate_lines([carrier.format(x=x) for x in ens], lang)
                texts = [out.get(j, "") for j in range(len(batch))]
                if kind in ("symptom", "anatomy") or lang in PAREN:
                    names = [re.split(r"[(（]", t)[0] for t in texts]
                else:
                    names = strip_carrier(texts, lang)
                for e, n in zip(batch, names):
                    n = n.strip(" .")
                    if 2 <= len(n) <= 60 and len(n.split()) <= 4 and not (lang in PAREN and n.isascii()):
                        e["names"].setdefault(lang, []).append(n)
                        e.setdefault("machine", {}).setdefault(lang, []).append(n)
                        added[lang] += 1
            print(lang, kind, "filled", sum(1 for e in todo if e["names"].get(lang)), "/", len(todo), flush=True)
    lex.setdefault("sources", []).append("Amazon Translate (gap fill, machine, pending review)")
    with gzip.open(dst, "wt", encoding="utf-8") as f:
        json.dump(lex, f, ensure_ascii=False)
    print("added", dict(added))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
