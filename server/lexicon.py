"""CareBridge Clinical Lexicon: the safety layer's own dictionary and matcher, independent of any AI vendor.

The lexicon (built by infra/lexicon/build_lexicon.py from Wikidata + curated seed lists, stored in S3) holds
medicines, brand names, drug classes, allergens, conditions, symptoms, anatomy and procedures, each with a stable
id, codes (ATC, ICD), names in every app language, look-alike/sound-alike partners and a review status.

Three jobs, for any language:
  find(text, lang)            clinical terms in a sentence, with their ids (exact, inflected, multi-word)
  correct(text, lang)         speech-recognition near-misses of medicine names -> the right name, plus
                              "did you mean A or B?" when two medicines sound alike
  compare(src, sl, tgt, tl)   the cross-language check: every critical term said must come out as the SAME
                              entry in the translation, and no new one may appear
Loaded once into memory (indexes built per language on first use), so it has no size cap and no network call."""
import difflib
import gzip
import json
import os
import re
import threading
import unicodedata
from collections import defaultdict

LEXICON_PATH = os.environ.get("CB_LEXICON", os.path.join(os.path.dirname(__file__), "data", "lexicon.json.gz"))
CRITICAL = {"medicine", "brand", "drug_class", "allergen"}          # must survive translation exactly
CLINICAL = CRITICAL | {"condition", "symptom", "procedure", "anatomy"}
# Languages whose words change ending with grammatical case; a stem match is allowed
INFLECTING = {"uk", "ru", "pl", "ro", "lt", "lv", "sk", "bg", "hu", "tr", "ka", "sq", "ga", "de", "so", "sw", "ha", "fi",
              "cs", "el"}
NO_SPACE = {"zh", "ja", "yue"}                                          # scripts written without spaces
# Mandarin and Cantonese share written names; both are compared in Simplified characters, so a Hong Kong
# transcript (Traditional) finds a name stored in Simplified and the other way round
SHARED_NAMES = {"zh": ["yue"], "yue": ["zh"]}
KEEP_MARKS = {"hi", "bn", "pa", "ar", "fa", "ur", "ps", "ckb", "ti", "am", "ka", "ko", "ja"}  # ja: voicing marks   # marks are letters here
AR_PROCLITICS = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ب", "ل", "ف")
MIN_LEN = 4
_lock = threading.Lock()


_T2S = []


def _simplified(s):
    """Traditional -> Simplified Chinese, character for character (positions must not move)."""
    if not _T2S:
        try:
            import opencc
            _T2S.append(opencc.OpenCC("t2s"))
        except Exception:  # noqa: BLE001
            _T2S.append(None)
    if _T2S[0] is None:
        return s
    out = _T2S[0].convert(s)
    return out if len(out) == len(s) else s


def norm(s: str, lang: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    if lang in ("zh", "yue"):
        s = _simplified(s)
    if lang in ("ar", "fa", "ur", "ps", "ckb"):
        s = re.sub(r"[ً-ٰٟـ]", "", s)                # vowel marks, tatweel
        s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")
    elif lang not in KEEP_MARKS:
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = unicodedata.normalize("NFC", s)
    return s


def tokens(s: str, lang: str):
    """[(token, start, end)] on the normalised text; hyphens and slashes split words (co-amoxiclav -> co amoxiclav)."""
    n = norm(s, lang)
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\w+", n)], n


VOWELISH = set("aeiouyąęăâîáéíóúàèìòùäöüаеиоуыэюяіїєьйαεηιουωاويىة")


def _stem(w: str) -> str:
    """The part of a name every inflected form keeps: the whole name, or the name without one final vowel
    (metformina -> metformin-ę, калий -> кали-я, інсулін -> інсулін-у)."""
    return w[:-1] if w[-1] in VOWELISH else w


def _inflects(token: str, name: str) -> bool:
    """True when `token` is a grammatical form of `name`: the stem plus a short ending (at most 2 letters after a
    dropped vowel, 3 after the full name)."""
    st = _stem(name)
    if len(st) < 5 or not token.startswith(st) or token == name:
        return False
    extra = len(token) - len(st)
    return 0 < extra <= (2 if st != name else 3)


class Lexicon:
    def __init__(self, path=LEXICON_PATH):
        self.ok = False
        self.entries, self.by_id, self._idx = [], {}, {}
        self.version = None
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = data["entries"]
            self.version = data.get("version")
            self.by_id = {e["id"]: e for e in self.entries}
            # brands from Wikidata point at their ingredient: treat them as that medicine when comparing
            self.equiv = {}
            for e in self.entries:
                for ing in e.get("codes", {}).get("ingredient", []):
                    if ing in self.by_id:
                        self.equiv[e["id"]] = ing
            self.ok = True
        except Exception as e:  # noqa: BLE001 - the app still works, with the older English-only checks
            self.error = f"{type(e).__name__}: {e}"

    # -- index ------------------------------------------------------------------------------------
    _CHEM_PREFIX = re.compile(r"^(?:rac|dl|\(±\)|\(\+/-\)|\(\+\)|\(-\)|[dlrs]|\([rs]\))[-‐ ]", re.I)

    def _names(self, e, lang):
        ns = list(e["names"].get(lang, []))
        for other in SHARED_NAMES.get(lang, []):
            ns += [n for n in e["names"].get(other, []) if n not in ns]
        # chemistry prefixes nobody says aloud: "rac-warfaryna" is also "warfaryna", "(±)-salbutamol" "salbutamol"
        ns += [n2 for n2 in (self._CHEM_PREFIX.sub("", n) for n in ns) if n2 not in ns and len(n2) >= 4]
        if lang == "sw" and set(e["types"]) & CRITICAL:
            # Swahili loanwords end in a vowel: penicillin -> penisilini, insulin -> insulini, aspirin -> aspirini
            base = [n for n in ns + e["names"].get("en", [])[:2] if n.isascii()]
            ns += [v for n in base if n[-1:].isalpha() and n[-1].lower() not in "aeiou"
                   for v in {n + "i", n.lower().replace("c", "s") + "i", n.lower().replace("c", "s").replace("ll", "l") + "i"}
                   if v not in ns]
        ns += [b for b in e.get("brands", []) if b not in ns]          # brand names are said the same everywhere
        if lang != "en":
            # Latin-script international names (INN, brands) are often said as-is in any language
            ns += [n for n in e["names"].get("en", []) if n not in ns and set(e["types"]) & CRITICAL]
        return ns

    def _index(self, lang):
        if lang in self._idx:
            return self._idx[lang]
        with _lock:
            if lang in self._idx:
                return self._idx[lang]
            exact, stems, multi, tri = defaultdict(set), defaultdict(set), defaultdict(list), defaultdict(set)
            single = {}
            for i, e in enumerate(self.entries):
                for name in self._names(e, lang):
                    toks = [t for t, _, _ in tokens(name, lang)[0]]
                    if not toks or sum(len(t) for t in toks) < MIN_LEN:
                        continue
                    key = " ".join(toks)
                    exact[key].add(i)
                    if len(toks) == 1:
                        w = toks[0]
                        single.setdefault(w, set()).add(i)
                        if lang in INFLECTING and len(_stem(w)) >= 5:
                            stems[_stem(w)].add(i)
                        if set(e["types"]) & CRITICAL and len(w) >= 5:
                            for g in {w[j:j + 3] for j in range(len(w) - 2)}:
                                tri[g].add(w)
                    else:
                        multi[toks[0]].append((toks, i))
                        if lang in INFLECTING and len(_stem(toks[0])) >= 5:
                            multi[_stem(toks[0])].append((toks, i))
            cjk = []
            if lang in NO_SPACE:          # no spaces between words: names are found as substrings, longest first
                seen = set()
                for i, e in enumerate(self.entries):
                    for name in self._names(e, lang):
                        if name.isascii() and not set(e["types"]) & CRITICAL:
                            continue
                        n = norm(name, lang).replace(" ", "")
                        if len(n) >= 2 and (n, i) not in seen:
                            seen.add((n, i)); cjk.append((n, i))
                cjk.sort(key=lambda x: -len(x[0]))
            self._idx[lang] = {"exact": exact, "stems": stems, "multi": multi, "tri": tri, "single": single, "cjk": cjk}
            return self._idx[lang]

    # -- find -------------------------------------------------------------------------------------
    def _token_hits(self, t, lang, idx):
        """Entry indexes a single token names: exact, Arabic without its prefix, or an inflected form."""
        cands = [t]
        if lang in ("ar", "fa", "ur"):
            cands += [t[len(p):] for p in AR_PROCLITICS if t.startswith(p) and len(t) - len(p) >= 3]
        for c in cands:
            if c in idx["exact"]:
                return idx["exact"][c], "exact"
        if lang in INFLECTING and len(t) >= 6 and self._freq(t, lang) < 3.5:   # common words never inflect into a drug
            for cut in (1, 2, 3):
                hit = idx["stems"].get(t[:len(t) - cut])
                if hit:
                    hit = {i for i in hit if any(_inflects(t, w) for w in self._single_names(i, lang, idx))}
                    if hit:
                        return hit, "inflected"
        return set(), None

    def _single_names(self, i, lang, idx):
        e = self.entries[i]
        return [w for w in (" ".join(t for t, _, _ in tokens(n, lang)[0]) for n in self._names(e, lang)) if " " not in w]

    def find(self, text: str, lang: str, types=CLINICAL):
        if not self.ok or not text:
            return []
        idx = self._index(lang)
        if lang in NO_SPACE:
            return self._find_cjk(text, lang, idx, types)
        toks, normed = tokens(text, lang)
        out, used = [], set()
        # multi-word names first (longest wins), then single words
        for k, (t, s, _) in enumerate(toks):
            keys = {t} | ({t[:len(t) - c] for c in (1, 2, 3)} if lang in INFLECTING else set())
            cands = [x for key in keys for x in idx["multi"].get(key, [])]
            for cand_toks, i in sorted(cands, key=lambda x: -len(x[0])):
                n = len(cand_toks)
                window = [x[0] for x in toks[k:k + n]]
                if len(window) < n or any(p in used for p in range(k, k + n)):
                    continue
                if all(a == b or (lang in INFLECTING and _inflects(a, b)) for a, b in zip(window, cand_toks)):
                    out.append(self._hit(i, text, toks[k][1], toks[k + n - 1][2], "exact" if window == cand_toks else "inflected"))
                    used.update(range(k, k + n))
                    break
        for k, (t, s, e_) in enumerate(toks):
            if k in used or len(t) < MIN_LEN:
                continue
            hits, how = self._token_hits(t, lang, idx)
            if hits and self._freq(t, lang) >= 5.0 and not any("medicine" in self.entries[i]["types"] for i in hits):
                hits = set()          # "peste" (Romanian: fish / over), "prawie": too common to mean the allergen
            if hits:
                best = max(hits, key=lambda i: self.entries[i].get("rank", 0))
                out.append(self._hit(best, text, s, e_, how, others=hits - {best}))
                used.add(k)
        return sorted([h for h in out if set(h["types"]) & set(types)], key=lambda h: h["start"])

    def _find_cjk(self, text, lang, idx, types):
        n = norm(text, lang)
        taken = [False] * len(n)
        out = []
        for name, i in idx["cjk"]:
            if len(name) < 3 and not set(self.entries[i]["types"]) & CRITICAL:
                continue          # 2-character everyday words (body parts, symptoms) are too ambiguous here
            start = n.find(name)
            while start != -1:
                if not any(taken[start:start + len(name)]):
                    for j in range(start, start + len(name)):
                        taken[j] = True
                    out.append(self._hit(i, text, start, start + len(name), "exact"))
                start = n.find(name, start + 1)
        return sorted([h for h in out if set(h["types"]) & set(types)], key=lambda h: h["start"])

    def _hit(self, i, text, s, e, how, others=()):
        en = self.entries[i]
        return {"id": en["id"], "types": en["types"], "name": self.display(en),
                "surface": text[s:e] if len(text) == len(unicodedata.normalize("NFKC", text)) else None,
                "start": s, "end": e, "match": how, "review": en.get("review", "machine"),
                "lasa": [self.display(self.by_id[x]) for x in en.get("lasa", []) if x in self.by_id],
                "also": [self.entries[j]["id"] for j in others][:3]}

    @staticmethod
    def display(e):
        """The plain English name to show staff: the shortest letters-only name ("warfarin", not "rac-warfarin")."""
        ns = e["names"].get("en") or [e["id"]]
        plain = [n for n in ns if re.fullmatch(r"[A-Za-z][A-Za-z ]{3,}", n) and not n.isupper()
                 and not re.fullmatch(r"[A-Z][a-z]{0,3}", n)]
        if plain and plain[0] == ns[0]:
            return ns[0]
        return min(plain, key=len) if plain else ns[0]

    # -- correct ----------------------------------------------------------------------------------
    # Words that announce a medicine: what follows is matched more loosely ("I'm allergic to ...", "I take ...")
    CUES = {
        "en": r"allerg\w*( to)?|tak(e|es|ing)|on|using|prescribed|given",
        "uk": r"алергі\w*( на)?|приймаю|приймав\w*|вживаю|п'ю|колю",
        "ru": r"аллерги\w*( на)?|принима\w*|пью|колю",
        "pl": r"uczulon\w*( na)?|alergi\w*( na)?|bior[ęe]|przyjmuj\w*|zażywam",
        "ro": r"alergic\w*( la)?|iau|folosesc|primesc",
        "ar": r"حساسية( من| ل)?|آخذ|اخذ|أخذ|أتناول|اتناول",
        "fr": r"allergique( à| au| aux)?|prends|prend",
        "es": r"al[ée]rgic\w*( a| al)?|tomo",
        "de": r"allergisch( gegen)?|nehme",
        "pt": r"al[ée]rgic\w*( [àa]| ao| aos)?|tomo|uso",
        "it": r"allergic\w*( a| al| alla| alle| agli)?|prendo|assumo",
        "cs": r"alergi\w*( na)?|beru|užívám",
        "el": r"αλλεργικ\w*( στ\w*)?|παίρνω",
        "id": r"alergi( terhadap)?|minum|pakai|memakai",
        "sw": r"mzio( wa)?|ninatumia|natumia|ninakunywa",
        "tl": r"allergy( sa)?|allergic( sa)?|umiinom( ako)?( ng)?|iniinom( ko)?( ang)?",
        "vi": r"dị ứng( với)?|uống|đang uống",
        "tr": r"ilacı|ilaç",
    }

    @staticmethod
    def _skeleton(w, lang):
        """Arabic-script spelling varies in its long vowels (الورفرين / الوارفارين): compare consonants only."""
        if lang in ("ar", "fa", "ur", "ps"):
            w = w[2:] if w.startswith("ال") else w
            return re.sub(r"[اويىءئؤة]", "", w)
        return w

    RANK_WEIGHT = 0.03     # tuned on the drug test set (grid search): commoner medicines win near-ties
    AMBIG_WINDOW = (0.04, 0.06)   # tuned: (outside a cue, after a cue) candidates this close -> ask, never guess

    def _fuzzy(self, w, lang, idx, min_ratio):
        """[(ratio, name)] best medicine-name candidates for a word ASR may have misspelt or split."""
        grams = {w[j:j + 3] for j in range(len(w) - 2)}
        pool = defaultdict(int)
        for g in grams:
            for cand in idx["tri"].get(g, ()):
                pool[cand] += 1
        sk = self._skeleton(w, lang)
        scored = []
        for c, n in pool.items():
            if n < max(1, len(grams) // 4) or abs(len(c) - len(w)) > 4:
                continue
            r = difflib.SequenceMatcher(None, w, c).ratio()
            if lang in ("ar", "fa", "ur", "ps"):
                r = max(r, difflib.SequenceMatcher(None, sk, self._skeleton(c, lang)).ratio() - 0.03)
            if r >= min_ratio:
                import math
                rank = max((self.entries[i].get("rank", 0) for i in idx["single"].get(c, ())), default=0)
                r = r + self.RANK_WEIGHT * math.log10(1 + rank)
            scored.append((r, c))
        scored.sort(reverse=True)
        return [x for x in scored[:5] if x[0] >= min_ratio]

    _WF_LANGS = set()

    @classmethod
    def _knows(cls, lang):
        """True when wordfreq has an everyday word list for the language."""
        try:
            from wordfreq import available_languages
            if not cls._WF_LANGS:
                cls._WF_LANGS.update(available_languages())
        except Exception:  # noqa: BLE001
            return False
        return {"tl": "fil", "prs": "fa", "yue": "zh"}.get(lang, lang) in cls._WF_LANGS

    @staticmethod
    def _freq(word, lang):
        """How common a word is in everyday language (Zipf scale; 0 = not a known word). Needs wordfreq."""
        try:
            from wordfreq import available_languages, zipf_frequency
            code = {"tl": "fil", "prs": "fa", "yue": "zh"}.get(lang, lang)
            if code not in Lexicon._WF_LANGS:
                Lexicon._WF_LANGS.update(available_languages())
            if code not in Lexicon._WF_LANGS:      # e.g. Swahili: unknown, rather than English frequencies
                return 0.0
            return zipf_frequency(word, code)
        except Exception:  # noqa: BLE001 - language not covered, or wordfreq missing: treat as unknown
            return 0.0

    def correct(self, text: str, lang: str, min_ratio=0.86, cue_ratio=0.7):
        """Speech-recognition near-misses of medicine/allergen names -> the right name. Handles misspellings,
        names split into pieces ("Саль Бутамо", "الميت فور مين") and, right after a cue ("allergic to", "I take"),
        looser matches. Returns (text, fixes, ambiguous); `ambiguous` = a word close to two different medicines,
        which must be asked ("did you mean A or B?"), never guessed."""
        if not self.ok or not text:
            return text, [], []
        idx = self._index(lang)
        words = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\w+", text)]
        cue_rx = re.compile(r"(?:^|\W)(?:" + self.CUES[lang] + r")\W*$", re.I) if lang in self.CUES else None
        fixes, ambiguous, edits = [], [], []
        k = 0
        while k < len(words):
            done = False
            after_cue = bool(cue_rx and cue_rx.search(text[max(0, words[k][1] - 40): words[k][1]]))
            # Outside a medicine context only clear misspellings of a single word are fixed (never a real word);
            # after "allergic to" / "I take" split names and looser matches are fixed, but never a common word.
            for span in ((3, 2, 1) if after_cue else (1,)):    # longest join first: "Саль Бутамо" -> "сальбутамол"
                if k + span > len(words):
                    continue
                fr = max(self._freq(norm(p[0], lang), lang) for p in words[k:k + span])
                # a single real word is never changed outside a cue; after a cue a pieces-join may include common
                # words ("الميت فور مين" -> metformin) but must then match closely
                if span == 1 and fr >= (3.5 if after_cue else 0.01):
                    continue
                parts = words[k:k + span]
                if span > 1 and any(len(p[0]) < 2 for p in parts):
                    continue
                # never swallow a small everyday word at the edge of a join ("كل" every, "من" from, "na" on)
                if span > 1 and max(self._freq(norm(parts[0][0], lang), lang),
                                    self._freq(norm(parts[-1][0], lang), lang)) >= 5.0:
                    continue
                # no word list for this language (e.g. Swahili): a 1-2 letter edge word is a function word
                # ("wa penisilini na" must not become one word)
                if span > 1 and not self._knows(lang) and min(len(parts[0][0]), len(parts[-1][0])) <= 2:
                    continue
                joined = norm("".join(p[0] for p in parts), lang)
                if len(joined) < 6:
                    continue
                if span == 1 and (joined in idx["single"] or self._token_hits(joined, lang, idx)[0]):
                    break                                   # already a known word
                if span > 1 and any(norm(p[0], lang) in idx["single"] for p in parts):
                    continue
                cands = self._fuzzy(joined, lang, idx, (cue_ratio if fr < 3.5 else 0.8) if after_cue else min_ratio)
                if not cands:
                    continue
                # a loose match (after a cue) must be clearly better than any other medicine, else ask
                top = [c for r, c in cands if r >= cands[0][0] - self.AMBIG_WINDOW[after_cue]]
                ids = {self.entries[i]["id"] for c in top for i in idx["single"].get(c, ())}
                orig = text[parts[0][1]:parts[-1][2]]
                if len(ids) > 1:
                    ambiguous.append({"heard": orig, "options": sorted({self.display(self.by_id[x]) for x in ids})})
                else:
                    best = cands[0][1]
                    edits.append((parts[0][1], parts[-1][2], best.capitalize() if orig[:1].isupper() else best))
                    fixes.append({"from": orig, "to": edits[-1][2], "score": round(cands[0][0], 2)})
                k += span; done = True
                break
            if not done:
                k += 1
        out = text
        for s_, e_, r in reversed(edits):
            out = out[:s_] + r + out[e_:]
        return out, fixes, ambiguous

    # -- compare (the cross-language check) ---------------------------------------------------------
    def _canon(self, h):
        return self.equiv.get(h["id"], h["id"])

    def compare(self, src: str, src_lang: str, tgt: str, tgt_lang: str):
        """None when the source has no critical clinical term; else a safety-net check:
        {"name": "Clinical terms", "ok", "detail", "missing": [...], "added": [...], "unverified": [...]}"""
        if not self.ok:
            return None
        a = [h for h in self.find(src, src_lang, CRITICAL)]
        b = [h for h in self.find(tgt, tgt_lang, CRITICAL)]
        if not a and not b:
            return None
        sa, sb = {self._canon(h) for h in a}, {self._canon(h) for h in b}
        hard = {"medicine", "brand", "allergen"}    # a specific medicine or allergen must never change
        # drug classes are hard too (penicillin -> "antibiotics" loses the allergy), except those normally said as
        # a procedure ("after the anaesthetic" -> "after anaesthesia")
        SOFT = {"anesthetic", "local anesthetic", "chemotherapy", "vaccine", "sedative", "contrast agent", "painkiller"}

        def is_hard(h):
            return bool(set(h["types"]) & hard) or ("drug_class" in h["types"] and h["name"].lower() not in SOFT)
        missing, unverified, soft = [], [], []
        for h in a:
            c = self._canon(h)
            if c in sb:
                continue
            e = self.by_id.get(c, {})
            if self._near(tgt, tgt_lang, c):
                continue                          # same medicine, another spelling or case form of its name
            if not (e.get("names", {}).get(tgt_lang) or tgt_lang == "en"):
                unverified.append(h["name"])
            elif is_hard(h):
                missing.append(h["name"])
            else:
                soft.append(h["name"])            # a drug class rendered by a related word ("anaesthetic" -> anaesthesia)
        added = [h["name"] for h in b if self._canon(h) not in sa and is_hard(h)]
        soft += [h["name"] for h in b if self._canon(h) not in sa and not is_hard(h)]
        ok = not missing and not added
        parts = []
        if missing:
            parts.append("Missing in translation: " + ", ".join(sorted(set(missing))))
        if added:
            parts.append("New in translation: " + ", ".join(sorted(set(added))))
        if soft:
            parts.append("Check wording: " + ", ".join(sorted(set(soft))))
        if not parts:
            parts.append("Kept: " + ", ".join(sorted({h["name"] for h in a})) if a else "No clinical terms")
        if unverified:
            parts.append(f"no {tgt_lang} name on file for: {', '.join(sorted(set(unverified)))}")
        return {"name": "Clinical terms", "ok": ok, "warn": bool(soft) and ok, "detail": "; ".join(parts),
                "missing": sorted(set(missing)), "added": sorted(set(added)), "check": sorted(set(soft)),
                "unverified": sorted(set(unverified))}

    def _near(self, text, lang, want, min_ratio=0.82):
        """True when a word of `text` is a close spelling of entry `want`'s name and the lexicon's best match for
        that word is `want` itself, by a clear margin: "antibiyotiği" is antibiotic, but "penisilamin" never
        passes for penicillin (penicillamine is the better match)."""
        if lang in NO_SPACE:
            return False
        idx = self._index(lang)
        for t, _, _ in tokens(text, lang)[0]:
            if len(t) < 5:
                continue
            ranked = []
            for r, name in self._fuzzy(t, lang, idx, min_ratio):
                for i in idx["single"].get(name, ()):
                    ranked.append((r, self._canon({"id": self.entries[i]["id"]})))
            if not ranked:
                continue
            ranked.sort(reverse=True)
            best_r, best = ranked[0]
            rival = next((r for r, c in ranked if c != best), 0.0)
            if best == want and best_r - rival >= 0.04:
                return True
        return False

    def stats(self):
        from collections import Counter
        return {"version": self.version, "entries": len(self.entries),
                "types": dict(Counter(t for e in self.entries for t in e["types"]))}


_LEX = None


def _from_s3():
    """The current lexicon lives in S3 (s3://$CB_BUCKET/lexicon/lexicon.json.gz, versioned), so the team can update
    the dictionary without redeploying the app. Falls back to the copy bundled with the app."""
    bucket = os.environ.get("CB_BUCKET")
    if not bucket or os.environ.get("CB_LEXICON"):
        return LEXICON_PATH
    dest = "/tmp/carebridge-lexicon.json.gz"
    try:
        import boto3
        boto3.client("s3").download_file(bucket, "lexicon/lexicon.json.gz", dest)
        return dest
    except Exception:  # noqa: BLE001
        return LEXICON_PATH


def lexicon():
    global _LEX
    if _LEX is None:
        with _lock:
            if _LEX is None:
                _LEX = Lexicon(_from_s3())
    return _LEX


def reload():
    """Picks up a new lexicon version from S3 (admin action)."""
    global _LEX
    new = Lexicon(_from_s3())
    if new.ok:
        _LEX = new
    return (_LEX or new).stats()
