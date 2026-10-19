"""Human review of the lexicon (interpreters, pharmacists).

export: one CSV per language with the critical terms (medicines, drug classes, allergens, then common symptoms and
        body parts), where each name came from, and empty columns for the reviewer:
          python review.py export LEXICON.json.gz OUT_DIR [--langs uk,pl]
        Reviewer fills `decision` with  ok | wrong | fix  and, for fix, the right name in `correction`.
import: reviewed CSVs placed in infra/lexicon/seed/reviews/ are applied by curate.py (apply_reviews): approved names
        are marked reviewed, wrong ones removed, corrections added; the app shows the review status per term."""
import csv, gzip, json, os, sys

TYPES_ORDER = ["medicine", "drug_class", "allergen", "symptom", "anatomy", "condition"]


def export(src, out_dir, langs):
    lex = json.load(gzip.open(src, "rt", encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    entries = sorted(lex["entries"], key=lambda e: (min(TYPES_ORDER.index(t) for t in e["types"] if t in TYPES_ORDER)
                                                    if set(e["types"]) & set(TYPES_ORDER) else 9, -e.get("rank", 0)))
    for lang in langs:
        path = os.path.join(out_dir, f"lexicon-review-{lang}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:        # utf-8-sig: opens cleanly in Excel
            w = csv.writer(f)
            w.writerow(["id", "type", "english", "name", "source", "decision", "correction", "reviewer", "note"])
            n = 0
            for e in entries:
                if not set(e["types"]) & {"medicine", "drug_class", "allergen"} and e.get("rank", 0) < 40:
                    continue
                machine = set(e.get("machine", {}).get(lang, []))
                for name in e["names"].get(lang, [])[:3]:
                    w.writerow([e["id"], e["types"][0], e["names"]["en"][0], name,
                                "machine translation" if name in machine else e.get("source", "wikidata"), "", "", "", ""])
                    n += 1
        print(path, n, "names")


def apply_reviews(lex, review_dir):
    """Used by curate.py. Returns the number of decisions applied."""
    if not os.path.isdir(review_dir):
        return 0
    by_id = {e["id"]: e for e in lex["entries"]}
    applied = 0
    for fn in sorted(os.listdir(review_dir)):
        if not fn.endswith(".csv"):
            continue
        lang = fn.rsplit("-", 1)[-1][:-4]
        with open(os.path.join(review_dir, fn), encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                e, d = by_id.get(row["id"]), (row.get("decision") or "").strip().lower()
                if not e or not d:
                    continue
                names = e["names"].setdefault(lang, [])
                if d == "wrong" and row["name"] in names:
                    names.remove(row["name"])
                elif d == "fix" and row.get("correction"):
                    if row["name"] in names:
                        names[names.index(row["name"])] = row["correction"].strip()
                    else:
                        names.insert(0, row["correction"].strip())
                if d in ("ok", "fix"):
                    e.setdefault("reviewed", {})[lang] = row.get("reviewer") or "reviewed"
                    if e.get("review") == "machine":
                        e["review"] = "partly reviewed"
                applied += 1
    return applied


if __name__ == "__main__":
    if sys.argv[1] == "export":
        langs = (sys.argv[sys.argv.index("--langs") + 1] if "--langs" in sys.argv
                 else "uk,ru,pl,ro,ar,ga,fr,es,ur,ko,de,hi,pt,zh,it,tr,vi,tl,bn,sw,id,ja,cs,el").split(",")
        export(sys.argv[2], sys.argv[3], langs)
