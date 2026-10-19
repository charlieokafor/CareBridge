"""Builds the CareBridge Clinical Lexicon from open data, in every language the app knows.

Sources (all open):
  - Wikidata, via the QLever SPARQL mirror (https://qlever.dev): medicines with WHO ATC codes and their brand
    names, diseases/conditions with ICD-10/ICD-11 codes, symptoms and signs, anatomy (FMA/TA98), medical
    procedures, common allergens. Names = labels + aliases in each language.
  - infra/lexicon/seed/*.json: hand-curated lists (Irish brand names, look-alike/sound-alike drug pairs,
    Irish-English ward words), merged on top.
Output: lexicon.json.gz (stable ids, codes, names per language, a commonness rank, review status). Stored in S3
and loaded by the server at start (server/lexicon.py); no size cap from AWS.

Usage: python build_lexicon.py OUT.json.gz"""
import gzip, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import defaultdict

EP = os.environ.get("CB_SPARQL", "https://qlever.dev/api/wikidata")
UA = "CareBridge-lexicon-builder/1.0 (open-source hospital translation safety project)"
HERE = os.path.dirname(os.path.abspath(__file__))
# Every language in the app's catalogue (server/phrasebank.py), Wikidata language codes
LANGS = ["en", "uk", "ru", "pl", "ro", "ar", "ga", "fr", "es", "ur", "ko", "pt", "zh", "lt", "lv", "ka", "sq", "tr",
         "fa", "ps", "ckb", "so", "ti", "am", "sw", "yo", "ha", "ig", "hi", "bn", "pa", "it", "de", "hu", "sk", "bg",
         "vi", "tl", "id", "ja", "cs", "el", "yue"]
PFX = """PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wikibase: <http://wikiba.se/ontology#> PREFIX schema: <http://schema.org/> """
LANG_FILTER = "FILTER(LANG(?l) IN (" + ",".join(f'"{l}"' for l in LANGS) + "))"

# category -> WHERE pattern binding ?d (the item) and optionally ?code
CATEGORIES = {
    "medicine": ("?d wdt:P267 ?code .", "atc"),
    # brand names: items whose active ingredient (P3781) is an ATC-coded medicine
    "brand": ("?d wdt:P3781 ?ing . ?ing wdt:P267 ?atc . BIND(?ing AS ?code)", "ingredient"),
    # diseases: ICD-10 or MONDO coded, or classed as a disease (ICD-11 alone also codes animals and objects)
    "condition": ("{ ?d wdt:P494 ?code . } UNION { ?d wdt:P4229 ?code . } UNION { ?d wdt:P493 ?x . } UNION "
                  "{ ?d wdt:P5270 ?m . } UNION { ?d wdt:P557 ?db . } UNION { ?d wdt:P604 ?mp . } UNION { ?d wdt:P31 wd:Q12136 . }", "icd"),
    "symptom": ("{ ?d wdt:P31 wd:Q169872 . } UNION { ?d wdt:P31 wd:Q1441305 . } UNION { ?d wdt:P279 wd:Q169872 . } "
                "UNION { ?d wdt:P31 wd:Q86746756 . }", None),
    "anatomy": ("{ ?d wdt:P1402 ?code . } UNION { ?d wdt:P1323 ?code . }", "fma"),
    "procedure": ("{ ?d wdt:P31 wd:Q796194 . } UNION { ?d wdt:P279 wd:Q796194 . } UNION { ?d wdt:P31 wd:Q2140699 . } "
                  "UNION { ?d wdt:P1690 ?code . }", None),
}
# Minimum Wikipedia articles (any language) for a non-medicine item to be kept: filters very rare or obscure
# entries that would only create false matches. Medicines and brands are always kept.
MIN_SITELINKS = {"condition": 8, "symptom": 3, "anatomy": 8, "procedure": 6}


CACHE = os.environ.get("CB_SPARQL_CACHE", os.path.join(HERE, ".cache"))


def sparql(q, tries=8):
    """Runs a query, politely: results are cached on disk (re-runs only fetch what changed) and a busy server
    gets a growing pause."""
    import hashlib
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1((EP + q).encode()).hexdigest() + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    for a in range(tries):
        try:
            data = urllib.parse.urlencode({"query": PFX + q}).encode()
            req = urllib.request.Request(EP, data=data, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                rows = json.load(r)["results"]["bindings"]
            json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(2)
            return rows
        except Exception as e:  # noqa: BLE001
            print("  retry", a, type(e).__name__, str(e)[:120], flush=True); time.sleep(min(300, 30 * (a + 1)))
    raise RuntimeError("SPARQL failed")


def qid(uri): return uri.rsplit("/", 1)[-1]


def clean_name(s, lang):
    s = unicodedata.normalize("NFC", s).strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)        # "insulin (medication)" -> "insulin"
    return s if 2 <= len(s) <= 60 else None


def build():
    entries = {}
    for cat, (pattern, code_kind) in CATEGORIES.items():
        t = time.time()
        code_sel = "?code" if code_kind else ""
        rows = sparql(f"SELECT DISTINCT ?d {code_sel} ?sl WHERE {{ {pattern} ?d wikibase:sitelinks ?sl . }}")
        items = defaultdict(lambda: {"codes": set(), "sl": 0})
        for b in rows:
            d = qid(b["d"]["value"]); it = items[d]
            it["sl"] = max(it["sl"], int(b["sl"]["value"]))
            if code_kind and "code" in b:
                v = b["code"]["value"]; it["codes"].add(qid(v) if v.startswith("http") else v)
        keep = {d: it for d, it in items.items() if it["sl"] >= MIN_SITELINKS.get(cat, 0)}
        print(f"{cat}: {len(items)} items, {len(keep)} kept ({time.time() - t:.0f}s)", flush=True)
        # names: labels and aliases, in batches of items so each query stays small
        ids = list(keep)
        names = defaultdict(lambda: defaultdict(list))
        for i in range(0, len(ids), 2000):
            vals = " ".join(f"wd:{d}" for d in ids[i:i + 2000])
            for prop in ("rdfs:label", "skos:altLabel"):
                for b in sparql(f"SELECT ?d ?l WHERE {{ VALUES ?d {{ {vals} }} ?d {prop} ?l . {LANG_FILTER} }}"):
                    lang = b["l"]["xml:lang"]; n = clean_name(b["l"]["value"], lang)
                    if n and n not in names[qid(b["d"]["value"])][lang]:
                        names[qid(b["d"]["value"])][lang].append(n)
        for d, it in keep.items():
            if not names[d].get("en"):
                continue          # every entry needs an English name (the clinician's side)
            e = entries.setdefault(d, {"id": d, "types": [], "codes": {}, "rank": 0, "names": {}, "review": "machine",
                                       "source": "wikidata"})
            if cat not in e["types"]:
                e["types"].append(cat)
            if code_kind and it["codes"]:
                e["codes"].setdefault(code_kind, sorted(set(e["codes"].get(code_kind, [])) | it["codes"]))
            e["rank"] = max(e["rank"], it["sl"])
            for lang, ns in names[d].items():
                cur = e["names"].setdefault(lang, [])
                cur += [n for n in ns if n not in cur]
    return entries


DRUG_CLASSES = ["penicillin", "cephalosporin", "sulfonamide", "nonsteroidal anti-inflammatory drug", "opioid", "antibiotic",
                "anticoagulant", "beta blocker", "ACE inhibitor", "statin", "corticosteroid", "benzodiazepine", "insulin",
                "antihistamine", "antidepressant", "anesthetic", "local anesthetic", "chemotherapy", "vaccine",
                "contrast agent", "antiemetic", "diuretic", "laxative", "antipsychotic", "anticonvulsant", "bronchodilator",
                "proton-pump inhibitor", "painkiller", "sedative", "tetracycline", "macrolide", "quinolone", "aspirin"]


def by_label(labels, cat, aliases=False):
    """Wikidata items for English names (the most-linked item per name), with their names in every language."""
    vals = " ".join(json.dumps(l) + "@en" for l in labels)
    best = {}
    rows = []
    for prop in (("rdfs:label", "skos:altLabel") if aliases else ("rdfs:label",)):
        try:
            rows += sparql(f"SELECT ?d ?en ?sl WHERE {{ VALUES ?en {{ {vals} }} ?d {prop} ?en . ?d wikibase:sitelinks ?sl . }}")
        except RuntimeError as e:
            print("  lookup skipped:", prop, e, flush=True)
    for b in rows:
        en, sl = b["en"]["value"], int(b["sl"]["value"])
        if en not in best or sl > best[en][1]:
            best[en] = (qid(b["d"]["value"]), sl)
    ids = [v[0] for v in best.values()]
    names = defaultdict(lambda: defaultdict(list))
    if ids:
        vals = " ".join(f"wd:{d}" for d in ids)
        for prop in ("rdfs:label", "skos:altLabel"):
            for b in sparql(f"SELECT ?d ?l WHERE {{ VALUES ?d {{ {vals} }} ?d {prop} ?l . {LANG_FILTER} }}"):
                n = clean_name(b["l"]["value"], b["l"]["xml:lang"])
                if n and n not in names[qid(b["d"]["value"])][b["l"]["xml:lang"]]:
                    names[qid(b["d"]["value"])][b["l"]["xml:lang"]].append(n)
    return {en: (d, sl, {l: list(v) for l, v in names[d].items()}) for en, (d, sl) in best.items()}


def merge_seeds(entries):
    seed = {f[:-5]: json.load(open(os.path.join(HERE, "seed", f), encoding="utf-8"))
            for f in sorted(os.listdir(os.path.join(HERE, "seed"))) if f.endswith(".json")}
    by_en = {}
    for e in entries.values():
        for n in e["names"].get("en", []):
            by_en.setdefault(n.lower(), e)
    # drug classes + non-drug allergens, found by English name
    for cat, labels in (("drug_class", DRUG_CLASSES), ("allergen", seed.get("allergens", {}).get("allergens", [])),
                        ("anatomy", seed.get("lay_terms", {}).get("body", [])),
                        ("symptom", seed.get("lay_terms", {}).get("symptoms", []))):
        for en, (d, sl, names) in by_label(labels, cat).items():
            e = entries.get(d) or entries.setdefault(d, {"id": d, "types": [], "codes": {}, "rank": sl, "names": {},
                                                         "review": "machine", "source": "wikidata"})
            if cat not in e["types"]:
                e["types"].append(cat)
            for l, ns in names.items():
                cur = e["names"].setdefault(l, []); cur += [n for n in ns if n not in cur]
            e["names"].setdefault("en", [])
            if en not in e["names"]["en"]:
                e["names"]["en"].insert(0, en)
            by_en.setdefault(en.lower(), e)
    # generic names used by the seed lists but filed under another main name in Wikidata: find them by alias
    SYN = {"co-amoxiclav": "amoxicillin/clavulanic acid", "morphine sulfate": "morphine", "iron": "iron supplement",
           "oral rehydration salts": "oral rehydration therapy", "hespan": "hydroxyethyl starch"}
    wanted = {g for g in list(seed.get("irish_brands", {}).get("brands", {}).values())
              + [x for p in seed.get("lasa", {}).get("pairs", []) for x in p] if g.lower() not in by_en}
    found = by_label(sorted({SYN.get(w, w) for w in wanted}), "medicine", aliases=True)
    for w in wanted:
        hit = found.get(SYN.get(w, w))
        if not hit:
            continue
        d, sl, names = hit
        e = entries.get(d) or entries.setdefault(d, {"id": d, "types": ["medicine"], "codes": {}, "rank": sl, "names": {},
                                                     "review": "machine", "source": "wikidata"})
        for l, ns in names.items():
            cur = e["names"].setdefault(l, []); cur += [n for n in ns if n not in cur]
        if w not in e["names"].setdefault("en", []):
            e["names"]["en"].append(w)
        by_en[w.lower()] = e
    # Irish brand names -> their generic medicine (same entry gets the brand as an extra name in every language)
    missing = []
    for brand, generic in seed.get("irish_brands", {}).get("brands", {}).items():
        e = by_en.get(generic.lower())
        if not e:
            missing.append(generic); continue
        e.setdefault("brands", [])
        if brand not in e["brands"]:
            e["brands"].append(brand)
    # look-alike / sound-alike pairs
    for a, b in seed.get("lasa", {}).get("pairs", []):
        ea, eb = by_en.get(a.lower()), by_en.get(b.lower())
        if ea and eb:
            ea.setdefault("lasa", []); eb.setdefault("lasa", [])
            if eb["id"] not in ea["lasa"]: ea["lasa"].append(eb["id"])
            if ea["id"] not in eb["lasa"]: eb["lasa"].append(ea["id"])
        else:
            missing += [x for x, e in ((a, ea), (b, eb)) if not e]
    print("seed names not found in the lexicon:", sorted(set(missing)))
    return {k: v.get("_about", "") for k, v in seed.items()}


if __name__ == "__main__":
    out = sys.argv[1]
    entries = build()
    seeds = merge_seeds(entries)
    # an item that is mainly an animal, plant or object should not stay in as a "condition"
    entries = {d: e for d, e in entries.items() if e["names"].get("en")}
    lex = {"version": time.strftime("%Y-%m-%d"), "languages": LANGS,
           "sources": ["Wikidata (CC0) via QLever", "CareBridge seed lists"],
           "entries": sorted(entries.values(), key=lambda e: -e["rank"]), "seeds": seeds}
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(lex, f, ensure_ascii=False)
    from collections import Counter
    c = Counter(t for e in entries.values() for t in e["types"])
    langs = Counter(l for e in entries.values() for l in e["names"])
    print("entries", len(entries), dict(c))
    print("names per language:", {l: langs[l] for l in ["en", "uk", "ru", "pl", "ro", "ar", "fr", "es", "de", "hi", "ko", "ga", "ur"]})
