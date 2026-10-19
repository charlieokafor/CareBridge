"""Curation pass over the Wikidata lexicon (no network): guarantees the core hospital medicines, links brands and
look-alike/sound-alike pairs, and records review status. Run after build_lexicon.py, before fill_gaps.py.
Usage: python curate.py IN.json.gz OUT.json.gz"""
import gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def seed(name):
    return json.load(open(os.path.join(HERE, "seed", name + ".json"), encoding="utf-8"))


def main(src, dst):
    lex = json.load(gzip.open(src, "rt", encoding="utf-8"))
    entries = lex["entries"]
    by_id = {e["id"]: e for e in entries}

    def index():
        out = {}
        for e in entries:
            for n in e["names"].get("en", []) + e.get("brands", []):
                out.setdefault(n.lower(), e)
        return out

    core = seed("core_medicines")
    # 1. plain names for medicines Wikidata files under a variant ("rac-salbutamol" -> salbutamol)
    for name, qid in core["aliases"].items():
        e = by_id.get(qid)
        if e and name not in e["names"]["en"]:
            e["names"]["en"].insert(0, name)
            e.setdefault("curated", []).append(f"en alias {name}")
    # 2. core medicines Wikidata lacks entirely
    for name in core["missing"]:
        if name.lower() not in index():
            e = {"id": f"cb:{name}", "types": ["medicine"], "codes": {}, "rank": 40, "names": {"en": [name]},
                 "review": "curated", "source": "carebridge"}
            entries.append(e); by_id[e["id"]] = e
    by_en = index()
    # 3. Irish brand names -> their generic
    for brand, generic in seed("irish_brands")["brands"].items():
        e = by_en.get(generic.lower())
        if e is not None and brand not in e.setdefault("brands", []):
            e["brands"].append(brand)
    # 4. look-alike / sound-alike pairs
    unlinked = []
    for a, b in seed("lasa")["pairs"]:
        ea, eb = by_en.get(a.lower()), by_en.get(b.lower())
        if ea is None or eb is None:
            unlinked += [x for x, e in ((a, ea), (b, eb)) if e is None]
            continue
        for x, y in ((ea, eb), (eb, ea)):
            if y["id"] not in x.setdefault("lasa", []):
                x["lasa"].append(y["id"])
    # 5. everyday body words -> the anatomical item (a name lookup can land on the wrong sense: "chest" found the
    #    furniture, "spine" a plant's spike). The lay word becomes an alias of the right item; the wrong item loses
    #    its anatomy tag (and is dropped if nothing else).
    LAY = {"chest": "thorax", "belly": "abdomen", "tummy": "abdomen", "spine": "human vertebral column",
           "backbone": "human vertebral column", "bladder": "urinary bladder", "back": "human back", "bum": "buttocks",
           "bottom": "buttocks", "buttock": "buttocks", "womb": "uterus", "gut": "gastrointestinal tract",
           "bowel": "intestine", "voice box": "larynx", "windpipe": "trachea", "collarbone": "clavicle",
           "shin": "tibia", "kneecap": "patella", "breastbone": "sternum", "eardrum": "eardrum"}
    fixed = []
    for lay, target in LAY.items():
        tgt = [e for e in entries if target in [n.lower() for n in e["names"].get("en", [])] and "anatomy" in e["types"]]
        if not tgt:
            continue
        t = max(tgt, key=lambda e: (bool(e["codes"].get("fma")), e.get("rank", 0)))
        for e in entries:
            if e is not t and "anatomy" in e["types"] and lay in [n.lower() for n in e["names"].get("en", [])] \
                    and not e["codes"].get("fma"):
                e["types"] = [x for x in e["types"] if x != "anatomy"]
        if lay not in t["names"]["en"]:
            t["names"]["en"].append(lay); fixed.append(f"{lay}->{target}")
    entries[:] = [e for e in entries if e["types"]]
    # 5b. everyday names per language that Wikidata lacks (seed/extra_names.json)
    by_en = index()
    for en, per_lang in seed("extra_names").items():
        e = by_en.get(en.lower())
        if en.startswith("_") or e is None:
            continue
        for lang, ns in per_lang.items():
            cur = e["names"].setdefault(lang, [])
            for n in ns:
                if n not in cur:
                    cur.insert(0, n); e.setdefault("curated", []).append(f"{lang} {n}")
    lex["entries"] = entries
    print("lay body words mapped:", fixed)
    by_en = index()
    missing_core = [n for n in core["core"] if n.lower() not in by_en]
    # 6. interpreter / pharmacist review decisions (seed/reviews/lexicon-review-<lang>.csv, from review.py export)
    sys.path.insert(0, HERE)
    from review import apply_reviews
    print("review decisions applied:", apply_reviews(lex, os.path.join(HERE, "seed", "reviews")))
    lex.setdefault("sources", []).append("CareBridge curation (core medicines, Irish brands, LASA pairs)")
    with gzip.open(dst, "wt", encoding="utf-8") as f:
        json.dump(lex, f, ensure_ascii=False)
    print(f"entries {len(entries)} | core medicines missing: {missing_core} | LASA names not linked: {sorted(set(unlinked))}")
    print("brands linked:", sum(len(e.get('brands', [])) for e in entries),
          "| LASA links:", sum(len(e.get('lasa', [])) for e in entries) // 2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
