#!/usr/bin/env python3
"""
Flask backend — ბიბლიის ვებ-აპლიკაცია + Hybrid Search (BM25 + LaBSE + RRF + Reranking).

სამი ფენის ძიება:
1. BM25 (ლექსიკური) — ზუსტი სიტყვები
2. LaBSE Dense (სემანტიკური) — აზრით
3. RRF Fusion — გაერთიანება
4. Cross-Encoder Reranking — საბოლოო ზუსტი რანჟირება
"""
import os
import json
import pickle
import re
import html
import time
import numpy as np
from flask import Flask, request, jsonify, send_from_directory, make_response, Response
from sentence_transformers import SentenceTransformer, CrossEncoder

# CPU-ზე — GPU მეხსიერება არ აყვება
os.environ["CUDA_VISIBLE_DEVICES"] = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

# === მონაცემების ჩატვირთვა ===
print("მონაცემების ჩატვირთვა...")

with open(os.path.join(DATA_DIR, "verse_index.json"), "r", encoding="utf-8") as f:
    VERSE_INDEX = json.load(f)

# LaBSE embeddings (უკეთესი ქართულისთვის) — თუ არსებობს
LABSE_FILE = os.path.join(DATA_DIR, "embeddings_labse.npz")
MINILM_FILE = os.path.join(DATA_DIR, "embeddings.npz")

if os.path.exists(LABSE_FILE):
    EMBEDDINGS = np.load(LABSE_FILE)["embeddings"].astype(np.float32)
    EMBED_MODEL_NAME = "LaBSE"
    print(f"  LaBSE embeddings: {EMBEDDINGS.shape}")
elif os.path.exists(MINILM_FILE):
    EMBEDDINGS = np.load(MINILM_FILE)["embeddings"].astype(np.float32)
    EMBED_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    print(f"  MiniLM embeddings (fallback): {EMBEDDINGS.shape}")
else:
    raise FileNotFoundError("Embeddings ფაილი არ მოიძებნა!")

# BM25 ინდექსი
BM25_FILE = os.path.join(DATA_DIR, "bm25_index.pkl")
if os.path.exists(BM25_FILE):
    with open(BM25_FILE, "rb") as f:
        BM25 = pickle.load(f)
    print(f"  BM25 ინდექსი ჩატვირთულია")
else:
    BM25 = None
    print(f"  [გაფრთხილება] BM25 ინდექსი არ მოიძებნა")

# Word Groups — სიტყვების დაჯგუფება ფუძეების მიხედვით
WORD_GROUPS_FILE = os.path.join(DATA_DIR, "bible_word_groups.json")
WORD_TO_GROUP = {}
GROUP_FORMS = {}
if os.path.exists(WORD_GROUPS_FILE):
    with open(WORD_GROUPS_FILE, "r", encoding="utf-8") as f:
        _wg = json.load(f)
    WORD_TO_GROUP = _wg["word_to_group"]
    GROUP_FORMS = {k: set(v) for k, v in _wg["groups"].items()}
    print(f"  Word groups: {len(GROUP_FORMS):,} ჯგუფი, {len(WORD_TO_GROUP):,} სიტყვა")
else:
    print(f"  [გაფრთხილება] Word groups არ მოიძებნა")

# ინვერსული ინდექსი: word -> [verse_keys] (ორივე თარგმანიდან)
# სიტყვა-თემა ინტეგრაციისთვის (რომელ თემებში გვხვდება ეს სიტყვა)
# ასევე სიტყვის კვლევის პანელისთვის (სად გვხვდება სიტყვა)
WORD_TO_VERSES = {}
VERSE_BY_KEY = {}
_WORD_RE = re.compile(r"[ა-ჰჱჲჳჴჵa-zA-Z]+")
_t0 = time.time()
for _v in VERSE_INDEX:
    _vk = f"{_v['book_slug']}:{_v['chapter']}:{_v['verse']}"
    VERSE_BY_KEY[_vk] = _v
    # ორივე თარგმანიდან ვაგროვებთ სიტყვებს
    _tokens = set()
    for _field in ("new", "old"):
        _text = _v.get(_field, "")
        if _text:
            _tokens.update(_WORD_RE.findall(_text.lower()))
    for _tok in _tokens:
        if _tok not in WORD_TO_VERSES:
            WORD_TO_VERSES[_tok] = []
        WORD_TO_VERSES[_tok].append(_vk)
print(f"  Word->verses ინდექსი: {len(WORD_TO_VERSES):,} სიტყვა, {len(VERSE_BY_KEY):,} მუხლი ({time.time()-_t0:.1f}s)")

# === სწრაფი ძიების ინდექსი (word -> {verse_idx: count}) ===
# შენიშვნა: ეს ინდექსი იყენებს _WORD_RE ტოკენიზატორს ([ა-ჰჱჲჳჴჵa-zA-Z]+), რომელიც
# ჭრის ტექსტს სიტყვებად.  word boundary-სგან განსხვავებით, ციფრები არ ითვლება
# სიტყვის ნაწილად. ბიბლიის ტექსტში მხოლოდ 2 მუხლი შეიცავს რიცხვებს ქართულ
# სიტყვებთან ახლოდ (ფეხნიშნები "ნფ8" და "თავი40"), რაც 0.01%-ია და
# პრაქტიკულად არ არსებობს მომხმარებლისთვის. ეს ცნობილი და მიღებული ცდომილებაა.
# 81 ტესტიდან (30 ხშირი, 20 იშვიათი, 19 პუნქტუაცია, 10 ფრაზა, 2 რიცხვი)
# მხოლოდ 2 mismatch აღმოჩნდა — ეს ორივე ფეხნიშნის მარკერებია.
WORD_TO_VERSE_COUNTS = {}      # word -> {verse_idx: count} (new + old)
WORD_TO_VERSE_COUNTS_NEW = {}  # word -> {verse_idx: count} (ახალი აღთქმა)
WORD_TO_VERSE_COUNTS_OLD = {}  # word -> {verse_idx: count} (ძველი აღთქმა)
_t0 = time.time()
for _idx, _v in enumerate(VERSE_INDEX):
    for _field, _target in [("new", WORD_TO_VERSE_COUNTS_NEW), ("old", WORD_TO_VERSE_COUNTS_OLD)]:
        _text = _v.get(_field, "") or ""
        if not _text:
            continue
        _tokens = _WORD_RE.findall(_text.lower())
        for _tok in _tokens:
            if _tok not in _target:
                _target[_tok] = {}
            _target[_tok][_idx] = _target[_tok].get(_idx, 0) + 1
            if _tok not in WORD_TO_VERSE_COUNTS:
                WORD_TO_VERSE_COUNTS[_tok] = {}
            WORD_TO_VERSE_COUNTS[_tok][_idx] = WORD_TO_VERSE_COUNTS[_tok].get(_idx, 0) + 1
print(f"  Word->verse_counts ინდექსი: {len(WORD_TO_VERSE_COUNTS):,} სიტყვა ({time.time()-_t0:.1f}s)")


def expand_query_words(query):
    """
    ძიების გაფართოება — ყველა სიტყვის ყველა ფორმით.

    მაგ: "უფალი" → {უფალი, უფალმა, უფალს, უფლის, ...}
    """
    tokens = tokenize_georgian(query)
    expanded = set()
    for token in tokens:
        expanded.add(token)
        if token in WORD_TO_GROUP:
            lemma = WORD_TO_GROUP[token]
            expanded.update(GROUP_FORMS.get(lemma, set()))
    return expanded


def parse_search_query(q):
    """
    ძიების query-ს დამუშავება — ბრჭყალების სინტაქსი.

    აბრუნებს dict:
      - is_phrase: bool — ზუსტი ფრაზაა (ბრჭყალებში)
      - phrase: str|None — ზუსტი ფრაზის ტექსტი (ბრჭყალების გარეშე)
      - words: [str] — ცალკეული სიტყვები (tokenize_georgian-ით)

    მაგალითები:
      '"იესო ქრისტე"' → {is_phrase: True, phrase: "იესო ქრისტე", words: ["იესო", "ქრისტე"]}
      'იესო ქრისტე'    → {is_phrase: False, phrase: None, words: ["იესო", "ქრისტე"]}
      'ღმერთი'          → {is_phrase: False, phrase: None, words: ["ღმერთი"]}
    """
    q = q.strip()
    # ბრჭყალების შემოწმება — ორმაგი ან ერთმაგი
    if (q.startswith('"') and q.endswith('"') and len(q) >= 2) or \
       (q.startswith("'") and q.endswith("'") and len(q) >= 2):
        inner = q[1:-1].strip()
        if inner:
            words = tokenize_georgian(inner)
            return {"is_phrase": True, "phrase": inner, "words": words}
    # ჩვეულებრივი ძიება
    words = tokenize_georgian(q)
    return {"is_phrase": False, "phrase": None, "words": words}


def count_word_occurrences(text, word):
    """
    სიტყვის რაოდენობის დათვლა word boundary-ით.

    str.count-ისგან განსხვავებით, პოულობს მხოლოდ სრულ სიტყვებს,
    არა substring-ს. მაგ: count_word_occurrences("მძევალი", "ძე") → 0
    """
    if not text or not word:
        return 0
    pattern = r'\b' + re.escape(word) + r'\b'
    return len(re.findall(pattern, text, re.IGNORECASE | re.UNICODE))


def count_phrase_occurrences(text, phrase):
    """
    ზუსტი ფრაზის რაოდენობის დათვლა (თანმიმდევრობით).

    ქართული ენის თავისებურების გათვალისწინებით:
      - დასაწყისში word boundary (მხოლოდ სრული სიტყვის დასაწყისი)
      - ბოლოში word boundary არ არის (ბოლო სიტყვას ემატება დანაერთი)

    მაგ: "იესო ქრისტე" იპოვის "იესო ქრისტეს", "იესო ქრისტემ",
    მაგრამ არ იპოვის "ანიესო ქრისტე".
    """
    if not text or not phrase:
        return 0
    # დასაწყისში word boundary, ბოლოში არა (ქართული დანაერთების გამო)
    pattern = r'\b' + re.escape(phrase)
    return len(re.findall(pattern, text, re.IGNORECASE | re.UNICODE))


print(f"  {len(VERSE_INDEX):,} მუხლი")

# === ლექსიკონის ჩატვირთვა ===
LEXICON_FILE = os.path.join(DATA_DIR, "lexicon.json")
LEXICON = None
if os.path.exists(LEXICON_FILE):
    with open(LEXICON_FILE, "r", encoding="utf-8") as f:
        LEXICON = json.load(f)
    print(f"  ლექსიკონი ჩატვირთულია: {LEXICON['metadata']['total_unique_words']:,} სიტყვა")
else:
    print(f"  [გაფრთხილება] ლექსიკონი არ მოიძებნა — გაუშვი build_lexicon.py")


# === მოდელების lazy ჩატვირთვა ===
_embed_model = None
_cross_encoder = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        print(f"Embedding მოდელის ჩატვირთვა: {EMBED_MODEL_NAME}")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")
        print("  მზადაა!")
    return _embed_model


def get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        print("Cross-Encoder მოდელის ჩატვირთვა...")
        # მრავალენოვანი cross-encoder — 14 ენა, კარგი რანჟირება
        try:
            _cross_encoder = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", device="cpu")
            print("  მზადაა!")
        except Exception as e:
            print(f"  Cross-Encoder ჩატვირთვა ვერ მოხერხდა: {e}")
            print("  გამოვრთავთ reranking-ს")
            _cross_encoder = False
    return _cross_encoder if _cross_encoder is not False else None


# === დამხმარე ფუნქციები ===
def tokenize_georgian(text):
    """
    სუფთა ტოკენიზაცია ბიბლიის ტექსტისთვის.
    - მხოლოდ ქართული ასოები (Mkhedruli)
    - lowercase
    - არანაირი დამახინჯება (არა წინასწარი stemming)
    - ციფრები, პუნქტუაცია, ლათინური — არ შედის
    """
    text = text.lower()
    # მხოლოდ ქართული ასოები: U+10D0-U+10FF (Mkhedruli)
    tokens = re.findall(r'[ა-ჰ]+', text)
    return [t for t in tokens if len(t) >= 1]


def reciprocal_rank_fusion(bm25_results, dense_results, k=60):
    """RRF — ორი რანჟირებული სიის გაერთიანება.
    score = 1/(k + rank_bm25) + 1/(k + rank_dense)
    """
    scores = {}
    # BM25 შედეგები
    for rank, idx in enumerate(bm25_results):
        scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
    # Dense შედეგები
    for rank, idx in enumerate(dense_results):
        scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
    # სორტირება
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


# === წიგნების სია ===
# ბიბლიის კანონიკური თანმიმდევრობა (არა ანბანის მიხედვით!)
# არაკანონიკური = orthodoxy.ge-ის მიხედვით "ტექსტი არაკანონიკურია"
OLD_TESTAMENT_ORDER = [
    # === კანონიკური (27) ===
    "dabadeba",      # დაბადება — Genesis
    "gamosvla",      # გამოსვლა — Exodus
    "levianni",      # ლევიანნი — Leviticus
    "ritskhvni",     # რიცხვნი — Numbers
    "2rjuli",        # მეორე რჯული — Deuteronomy
    "iesonave",      # იესო ნავეს ძე — Joshua
    "msajulni",      # მსაჯულნი — Judges
    "ruti",          # რუთი — Ruth
    "1mepeta",       # I მეფეთა — 1 Samuel/Kings
    "2mepeta",       # II მეფეთა — 2 Samuel/Kings
    "3mepeta",       # III მეფეთა — 1 Kings
    "4mepeta",       # IV მეფეთა — 2 Kings
    "1neshtta",      # I ნეშტთა — 1 Chronicles
    "2neshtta",      # II ნეშტთა — 2 Chronicles
    "1ezra",         # I ეზრა — Ezra (კანონიკური)
    "neemia",        # ნეემია — Nehemiah
    # არაკანონიკური — orthodoxy.ge-ის რიგით
    "2ezra",         # II ეზრა* (არაკანონიკური)
    "tobiti",        # ტობითი* (არაკანონიკური)
    "ivditi",        # ივდითი* (არაკანონიკური)
    "esteri",        # ესთერი — Esther (კანონიკური)
    "iobi",          # იობი — Job
    "fsalmunni",     # ფსალმუნნი — Psalms
    "igavni",        # იგავნი სოლომონისა — Proverbs
    "eklesiaste",    # ეკლესიასტე — Ecclesiastes
    "qeba",          # ქებათა-ქება — Song of Solomon
    # არაკანონიკური
    "solomoni",      # სიბრძნე სოლომონისა* (არაკანონიკური)
    "ziraqi",        # სიბრძნე ზირაქისა* (არაკანონიკური)
    # კანონიკური წინასწარმეტყველნი
    "esaia",         # ესაია — Isaiah
    "ieremia",       # იერემია — Jeremiah
    "godeba",        # გოდება იერემიასი — Lamentations
    # ეპისტოლე იერემიასი — კანონიკური წიგნის (იერემია) დანართი
    "epistole",      # ეპისტოლე იერემიასი
    "baruqi",        # ბარუქი* (არაკანონიკური)
    # კანონიკური
    "ezekieli",      # ეზეკიელი — Ezekiel
    "danieli",       # დანიელი — Daniel
    # მცირე წინასწარმეტყველნი (12) — ყველა კანონიკური
    "osia",          # ოსია — Hosea
    "ioveli",        # იოველი — Joel
    "amos",          # ამოსი — Amos
    "abdia",         # აბდია — Obadiah
    "iona",          # იონა — Jonah
    "miqa",          # მიქა — Micah
    "naumi",         # ნაუმი — Nahum
    "abakumi",       # აბაკუმი — Habakkuk
    "sofonia",       # სოფონია — Zephaniah
    "angia",         # ანგია — Haggai
    "zaqaria",       # ზაქარია — Zechariah
    "malaqia",       # მალაქია — Malachi
    # არაკანონიკური მაკაბელთა
    "1makabelta",    # I მაკაბელთა* (არაკანონიკური)
    "2makabelta",    # II მაკაბელთა* (არაკანონიკური)
    "3makabelta",    # III მაკაბელთა* (არაკანონიკური)
    "4makabelta",    # IV მაკაბელთა* (არაკანონიკური)
    "3ezra",         # III ეზრა* (არაკანონიკური)
]

# არაკანონიკური წიგნები — orthodoxy.ge-ის მიხედვით
# "ებრაული დედანი შემონახული არ არის; თარგმნილია ბერძნულიდან. ტექსტი არაკანონიკურია"
# ეპისტოლე იერემიასი = orthodoxy.ge-ზე ვარსკვლავით (*) მონიშნული, ანუ დაუკანონებელი
NONCANONICAL_BOOKS = {
    "2ezra",         # II ეზრა
    "3ezra",         # III ეზრა
    "tobiti",        # ტობითი
    "ivditi",        # ივდითი
    "solomoni",      # სიბრძნე სოლომონისა
    "ziraqi",        # სიბრძნე ზირაქისა
    "baruqi",        # ბარუქი
    "epistole",      # ეპისტოლე იერემიასი
    "1makabelta",    # I მაკაბელთა
    "2makabelta",    # II მაკაბელთა
    "3makabelta",    # III მაკაბელთა
    "4makabelta",    # IV მაკაბელთა
}

NEW_TESTAMENT_ORDER = [
    "mate",              # მათეს სახარება — Matthew
    "markozi",           # მარკოზის სახარება — Mark
    "luka",              # ლუკას სახარება — Luke
    "ioane",             # იოანეს სახარება — John
    "saqme",             # მოციქულთა საქმენი — Acts
    "romaelta",          # რომაელთა მიმართ — Romans
    "1korintelta",       # პირველი კორინთელთა — 1 Corinthians
    "2korintelta",       # მეორე კორინთელთა — 2 Corinthians
    "galatelta",         # გალატელთა — Galatians
    "efeselta",          # ეფესელთა — Ephesians
    "filipelta",         # ფილიპელთა — Philippians
    "kolaselta",         # კოლასელთა — Colossians
    "1tesalonikelta",    # პირველი თესალონიკელთა — 1 Thessalonians
    "2tesalonikelta",    # მეორე თესალონიკელთა — 2 Thessalonians
    "1timote",           # პირველი ტიმოთე — 1 Timothy
    "2timote",           # მეორე ტიმოთე — 2 Timothy
    "tite",              # ტიტე — Titus
    "filimoni",          # ფილიმონი — Philemon
    "ebraelta",          # ებრაელთა — Hebrews
    "iakobi",            # იაკობი — James
    "1petre",            # პირველი პეტრე — 1 Peter
    "2petre",            # მეორე პეტრე — 2 Peter
    "1ioane",            # პირველი იოანე — 1 John
    "2ioane",            # მეორე იოანე — 2 John
    "3ioane",            # მესამე იოანე — 3 John
    "iuda",              # იუდა — Jude
    "apokalips",         # იოანეს გამოცხადება — Revelation
]


def build_books_list():
    books = {}
    for v in VERSE_INDEX:
        slug = v["book_slug"]
        if slug not in books:
            books[slug] = {
                "slug": slug,
                "name": v["book"],
                "testament": v["testament"],
                "chapters": set(),
                "apocryphal": slug in NONCANONICAL_BOOKS,
            }
        books[slug]["chapters"].add(v["chapter"])
    for b in books.values():
        b["chapters"] = sorted(b["chapters"])

    # კანონიკური თანმიმდევრობით (არა ანბანის მიხედვით!)
    old = []
    for slug in OLD_TESTAMENT_ORDER:
        if slug in books:
            old.append(books[slug])
    # თუ რამე დარჩა რაც სიაში არ არის — ბოლოში დავამატოთ
    for slug, b in books.items():
        if b["testament"] == "old" and slug not in OLD_TESTAMENT_ORDER:
            old.append(b)

    new = []
    for slug in NEW_TESTAMENT_ORDER:
        if slug in books:
            new.append(books[slug])
    for slug, b in books.items():
        if b["testament"] == "new" and slug not in NEW_TESTAMENT_ORDER:
            new.append(b)

    return {"old": old, "new": new}


BOOKS = build_books_list()


# === O(1) მუხლის ძიების ინდექსი ===
# (book_slug:chapter:verse) -> index VERSE_INDEX სიაში
VERSE_LOOKUP = {}
for _i, _v in enumerate(VERSE_INDEX):
    _key = f"{_v['book_slug']}:{_v['chapter']}:{_v['verse']}"
    VERSE_LOOKUP[_key] = _i
print(f"  Verse lookup: {len(VERSE_LOOKUP):,} მუხლი (O(1))")

# slug -> book_name მაპინგი
SLUG_TO_BOOK_NAME = {}
for _v in VERSE_INDEX:
    _s = _v["book_slug"]
    if _s not in SLUG_TO_BOOK_NAME:
        SLUG_TO_BOOK_NAME[_s] = _v["book"]


# === Cross-references ინდექსი ===
# პრიორიტეტი: გაერთიანებული (TSK + OpenBible) > TSK > OpenBible
CROSSREFS = {}
CROSSREFS_MERGED_FILE = os.path.join(DATA_DIR, "crossrefs_merged.json")
CROSSREFS_TSK_FILE = os.path.join(DATA_DIR, "crossrefs_tsk.json")
CROSSREFS_FILE = os.path.join(DATA_DIR, "crossrefs_index.json")

if os.path.exists(CROSSREFS_MERGED_FILE):
    with open(CROSSREFS_MERGED_FILE, "r", encoding="utf-8") as f:
        CROSSREFS = json.load(f)
    total_chains = sum(len(v) for v in CROSSREFS.values())
    print(f"  Cross-references (TSK+OpenBible merged): {len(CROSSREFS):,} მუხლი, {total_chains:,} ჯაჭვი")
elif os.path.exists(CROSSREFS_TSK_FILE):
    with open(CROSSREFS_TSK_FILE, "r", encoding="utf-8") as f:
        CROSSREFS = json.load(f)
    total_chains = sum(len(v) for v in CROSSREFS.values())
    print(f"  Cross-references (TSK only): {len(CROSSREFS):,} მუხლი, {total_chains:,} ჯაჭვი")
elif os.path.exists(CROSSREFS_FILE):
    with open(CROSSREFS_FILE, "r", encoding="utf-8") as f:
        CROSSREFS = json.load(f)
    print(f"  Cross-references (OpenBible only): {len(CROSSREFS):,} მუხლი")
else:
    print(f"  [გაფრთხილება] Cross-references არ მოიძებნა — გაუშვი build_crossrefs.py")

# === თემატური ენციკლოპედია (Nave's + Torrey's) ===
TOPICAL_INDEX = {}
TOPICAL_FILE = os.path.join(DATA_DIR, "topical_index.json")
TOPICAL_NAMES_KA = {}
TOPICAL_NAMES_FILE = os.path.join(DATA_DIR, "topic_names_ka.json")
if os.path.exists(TOPICAL_FILE):
    with open(TOPICAL_FILE, "r", encoding="utf-8") as f:
        TOPICAL_INDEX = json.load(f)
    topics = TOPICAL_INDEX.get("topics", [])
    print(f"  Topical index: {len(topics):,} თემა (Nave's + Torrey's)")
    # ქართული თარგმანის ჩატვირთვა
    if os.path.exists(TOPICAL_NAMES_FILE):
        with open(TOPICAL_NAMES_FILE, "r", encoding="utf-8") as f:
            TOPICAL_NAMES_KA = json.load(f)
        print(f"  ქართული თარგმანი: {len(TOPICAL_NAMES_KA):,} თემა")
else:
    print(f"  [გაფრთხილება] Topical index არ მოიძებნა — გაუშვი build_topical_index.py")


def get_topic_name(topic_slug, name_en=""):
    """თემის ქართული სახელი (თუ არსებობს), წინააღმდეგ ინგლისური."""
    return TOPICAL_NAMES_KA.get(topic_slug, name_en)


# Topical label-ების თარგმანის ლოგიკა ცალკე მოდულშია (topical_translate.py)
# ეს უზრუნველყოფს რომ თარგმანის ლოგიკა გამოყენებული იქნეს როგორც server.py-ის,
# ასევე translate_labels.py-ის (წინასწარი თარგმანის) მიერ.
from topical_translate import (
    BIBLE_ABBR_TO_KA,
    LABEL_PHRASES_KA,
    WORD_KA,
    translate_topic_label,
    _REF_PATTERN,
    _WORD_PATTERNS,
)

# წინასწარ თარგმნილი label-ების ჩატვირთვა (თუ არსებობს)
TOPIC_LABELS_KA = {}
_labels_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'topic_labels_ka.json')
if os.path.exists(_labels_path):
    try:
        with open(_labels_path, 'r', encoding='utf-8') as _f:
            TOPIC_LABELS_KA = json.load(_f)
        print(f"  წინასწარ თარგმნილი label-ები: {len(TOPIC_LABELS_KA):,}")
    except Exception as _e:
        print(f"  გაფრთხილება: topic_labels_ka.json ვერ ჩაიტვირთა: {_e}")

# Cross-reference topic-ების ქართული თარგმანი
CROSSREF_TOPICS_KA = {}
_xref_topics_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'crossref_topics_ka.json')
if os.path.exists(_xref_topics_path):
    try:
        with open(_xref_topics_path, 'r', encoding='utf-8') as _f:
            CROSSREF_TOPICS_KA = json.load(_f)
        print(f"  Cross-ref topic-ების თარგმანი: {len(CROSSREF_TOPICS_KA):,}")
    except Exception as _e:
        print(f"  გაფრთხილება: crossref_topics_ka.json ვერ ჩაიტვირთა: {_e}")


def get_topic_label(label):
    """თარგმნის topical entry label-ს.
    ჯერ ცდილობს მზა თარგმანი ფაილიდან (სწრაფი),
    თუ არ არსებობს - თარგმნის ონლაინ (ნელი, მაგრამ მუშა).
    """
    if not label:
        return label
    if label in TOPIC_LABELS_KA:
        return TOPIC_LABELS_KA[label]
    # Fallback: ონლაინ თარგმანი
    return translate_topic_label(label)


def get_crossref_topic(topic_en):
    """თარგმნის cross-reference topic-ს ქართულად.
    აბრუნებს ქართულ თარგმანს, ან ცარიელს თუ თარგმანი არ არსებობს
    (კლიენტი ცარიელს არ გამოსახავს).
    "general" და "reciprocal" აბრუნებს ცარიელს - ესენი ფილტრავს app.js.
    """
    if not topic_en or topic_en in ("general", "reciprocal"):
        return ""
    ka = CROSSREF_TOPICS_KA.get(topic_en)
    if ka:
        return ka
    # Fallback: topical_translate.py-ის ლექსიკონით სცადოთ
    ka = translate_topic_label(topic_en)
    import re as _re
    if ka and not _re.search(r"[A-Za-z]{3,}", ka):
        return ka
    return ""


def get_verse_fast(book_slug, chapter, verse):
    """O(1) მუხლის მიღება, linear search-ის ნაცვლად."""
    key = f"{book_slug}:{chapter}:{verse}"
    idx = VERSE_LOOKUP.get(key)
    if idx is None:
        return None
    v = VERSE_INDEX[idx]
    return {
        "book": v["book"],
        "book_slug": v["book_slug"],
        "chapter": v["chapter"],
        "verse": v["verse"],
        "new": v["new"],
        "old": v["old"],
        "grc": v.get("grc", ""),
        "testament": v["testament"],
    }


# === API endpoints ===
@app.route("/")
def index():
    resp = send_from_directory(STATIC_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-transform, must-revalidate"
    return resp


@app.route("/b/<book_slug>/<int:chapter>")
def share_chapter(book_slug, chapter):
    """თავის გვერდი SEO-სთვის - server-side rendered მუხლებით + hash routing-ზე გადამისამართებით."""
    # წიგნის არსებობის შემოწმება - არარსებული წიგნი აბრუნებს 404
    book_obj = next((b for b in BOOKS["old"] + BOOKS["new"] if b["slug"] == book_slug), None)
    if not book_obj:
        return render_template("404.html") if "render_template" in dir() else ("წიგნი ვერ მოიძებნა", 404)
    # თავის ნომრის შემოწმება
    if chapter not in book_obj["chapters"]:
        return ("თავი ვერ მოიძებნა", 404)
    book_name = book_obj["name"]
    og_title = f"{book_name} {chapter} · წმიდა წერილი"
    og_desc = f"{book_name} {chapter} - ქართული ბიბლია ორ თარგმანში. ძველი და ახალი ქართული პარალელურად."
    base_url = "https://web.net.ge"
    canonical = f"{base_url}/b/{book_slug}/{chapter}"
    image_url = f"{base_url}/static/icon-512.png"

    # მუხლების მოძიება server-side (Googlebot-ისთვის ხილული)
    verses = []
    for v in VERSE_INDEX:
        if v["book_slug"] == book_slug and v["chapter"] == chapter:
            verses.append({"verse": v["verse"], "new": v["new"], "old": v.get("old", "")})
    verses.sort(key=lambda x: x["verse"])

    # მუხლების HTML რენდერი (noscript-ში, Googlebot-ისთვის ხილული)
    verses_html = ""
    for v in verses[:30]:  # პირველი 30 მუხლი (სერვერის დატვირთვის შესამცირებლად)
        verse_num = v["verse"]
        new_text = html.escape(v["new"])
        old_text = html.escape(v.get("old", "")) if v.get("old") else ""
        verses_html += f'<p><strong>{verse_num}.</strong> {new_text}'
        if old_text:
            verses_html += f'<br><em style="color:#6b5a3a;">{old_text}</em>'
        verses_html += '</p>\n'

    remaining = len(verses) - 30
    if remaining > 0:
        verses_html += f'<p style="color:#999;font-size:0.85em;">... და კიდევ {remaining} მუხლი</p>\n'

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Chapter",
        "name": og_title,
        "inLanguage": "ka",
        "url": canonical,
        "isPartOf": {
            "@type": "Book",
            "name": "წმიდა წერილი",
            "inLanguage": "ka"
        }
    }, ensure_ascii=False)

    # შიდა ბმულები SEO-სთვის (Googlebot-ისთვის ხილული, მომხმარებელი ვერ ხედავს JS redirect-ის გამო)
    book_obj = None
    for b in BOOKS["old"] + BOOKS["new"]:
        if b["slug"] == book_slug:
            book_obj = b
            break

    nav_html = ""
    if book_obj:
        chapters = book_obj["chapters"]
        ch_idx = chapters.index(chapter) if chapter in chapters else -1

        # წინა/შემდეგი თავი
        prev_link = f'<a href="{base_url}/b/{book_slug}/{chapters[ch_idx-1]}">{book_name} {chapters[ch_idx-1]}</a>' if ch_idx > 0 else ""
        next_link = f'<a href="{base_url}/b/{book_slug}/{chapters[ch_idx+1]}">{book_name} {chapters[ch_idx+1]}</a>' if ch_idx >= 0 and ch_idx < len(chapters) - 1 else ""
        nav_html = f'<nav style="margin:20px 0;text-align:center;font-size:0.9em;">{prev_link} | <a href="{base_url}/">წმიდა წერილი</a> | {next_link}</nav>'

        # წიგნის ყველა თავი (კომპაქტურად)
        chapters_links = " ".join(
            f'<a href="{base_url}/b/{book_slug}/{c}" style="display:inline-block;margin:2px 4px;">{c}</a>'
            for c in chapters
        )
        nav_html += f'\n<nav style="margin:10px 0;font-size:0.85em;line-height:2;">{chapters_links}</nav>'

    # სხვა წიგნების ბმულები (კომპაქტურად, მხოლო პირველი თავი)
    other_books = ""
    for b in (BOOKS["old"] + BOOKS["new"])[:20]:  # პირველი 20 წიგნი
        if b["slug"] != book_slug:
            other_books += f'<a href="{base_url}/b/{b["slug"]}/{b["chapters"][0]}" style="display:inline-block;margin:2px 4px;">{b["name"]}</a>'
    nav_html += f'\n<nav style="margin:10px 0;font-size:0.8em;line-height:2;color:#888;">{other_books}</nav>'

    page_html = f"""<!DOCTYPE html>
<html lang="ka">
<head>
<meta charset="UTF-8">
<title>{og_title}</title>
<meta name="description" content="{og_desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="წმიდა წერილი">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="ka_GE">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
<meta name="twitter:image" content="{image_url}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#1a1a2e">
<script type="application/ld+json">
{json_ld}
</script>
<script>setTimeout(function(){{window.location.replace("/#/{book_slug}/{chapter}");}},100);</script>
</head>
<body style="margin:0;padding:40px;font-family:Georgia,serif;background:#faf8f3;color:#1a1a1a;max-width:800px;margin:0 auto;">
<h1 style="color:#4a3828;font-size:1.5em;text-align:center;">{book_name} {chapter}</h1>
<div style="margin:20px 0;line-height:1.8;font-size:1.1em;">
{verses_html}
</div>
{nav_html}
<noscript><p style="color:#999;font-size:0.85em;text-align:center;">ჩართეთ JavaScript ინტერაქტიული ვერსიისთვის.</p></noscript>
</body>
</html>"""
    resp = make_response(page_html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, no-transform, max-age=3600"
    return resp


@app.route("/b/<book_slug>/<int:chapter>/<int:verse>")
def share_verse(book_slug, chapter, verse):
    """დინამიური OG თეგები მუხლის გაზიარებისთვის.

    ეს endpoint აბრუნებს მინიმალურ HTML-ს სწორი Open Graph თეგებით,
    რომელიც მესენჯერებში (WhatsApp, Facebook, Telegram) გამოჩნდება
    როგორც მუხლის ტექსტი. JavaScript კლიენტზე გადაიყვანს მომხმარებელს
    სწორ ადგილზე (hash routing).
    """
    verse_data = get_verse_fast(book_slug, chapter, verse)
    if verse_data is None:
        # თუ მუხლი არ მოიძებნა — გადამისამართდეს მთავარზე
        return index()

    book_name = verse_data["book"]
    ref = f"{book_name} {chapter}:{verse}"
    # OG description-ისთვის ტექსტი (მაქს 200 სიმბოლო)
    verse_text = verse_data["new"][:200]
    if len(verse_data["new"]) > 200:
        verse_text += "..."
    og_desc = f"{ref} - {verse_text}"
    og_title = f"{ref} · წმიდა წერილი"

    # აბსოლუტური URL-ები SEO-სთვის
    base_url = "https://web.net.ge"
    canonical = f"{base_url}/b/{book_slug}/{chapter}/{verse}"
    image_url = f"{base_url}/static/icon-512.png"
    target_url = f"{base_url}/#/{book_slug}/{chapter}/{verse}"

    # Schema.org JSON-LD სტრუქტურირებული მონაცემები
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": og_title,
        "headline": og_title,
        "text": og_desc,
        "inLanguage": "ka",
        "url": canonical,
        "isPartOf": {
            "@type": "Book",
            "name": "წმიდა წერილი",
            "inLanguage": "ka"
        }
    }, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ka">
<head>
<meta charset="UTF-8">
<title>{og_title}</title>
<meta name="description" content="{og_desc}">

<!-- Open Graph -->
<meta property="og:type" content="article">
<meta property="og:site_name" content="წმიდა წერილი">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="ka_GE">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
<meta name="twitter:image" content="{image_url}">

<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#1a1a2e">

<!-- Schema.org Structured Data -->
<script type="application/ld+json">
{json_ld}
</script>

<!-- კლიენტზე გადამისამართება hash routing-ზე -->
<script>setTimeout(function(){{window.location.replace("/#/{book_slug}/{chapter}/{verse}");}},100);</script>
</head>
<body style="margin:0;padding:40px;text-align:center;font-family:Georgia,serif;background:#faf8f3;color:#1a1a1a;">
  <p style="font-size:1.2em;color:#4a3828;font-weight:bold;">{ref}</p>
  <p style="font-size:1em;line-height:1.8;max-width:500px;margin:20px auto;">{verse_data["new"]}</p>
  <p style="color:#999;font-size:0.85em;">გადამისამართება...</p>
</body>
</html>"""
    resp = make_response(html_content)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, no-transform, max-age=3600"  # 1 საათი
    return resp


@app.route("/t/<topic_slug>")
def share_topic(topic_slug):
    """თემატური ენციკლოპედიის გვერდი SEO-სთვის - SSR + hash routing-ზე გადამისამართებით."""
    if not TOPICAL_INDEX:
        return index()

    topics = TOPICAL_INDEX.get("topics", [])
    by_slug = TOPICAL_INDEX.get("by_slug", {})
    idx = by_slug.get(topic_slug)
    if idx is None:
        return index()

    topic = topics[idx]
    topic_name = get_topic_name(topic_slug, topic.get("name_en", ""))
    topic_name_en = topic.get("name_en", "")
    verse_count = topic.get("verse_count", 0)
    source = topic.get("source", "nave")

    base_url = "https://web.net.ge"
    canonical = f"{base_url}/t/{topic_slug}"
    image_url = f"{base_url}/static/icon-512.png"
    og_title = f"{topic_name} · წმიდა წერილი"
    og_desc = f"{topic_name} - ბიბლიური თემა, {verse_count} მუხლი. ქართული ბიბლია ორ თარგმანში."

    # ენტრიების რენდერი (პირველი 5 ენტრი, თითოეულიდან 5 მუხლი)
    entries_html = ""
    total_shown = 0
    for entry in topic.get("entries", [])[:5]:
        label = get_topic_label(entry.get("label", ""))
        entries_html += f'<h3>{html.escape(label)}</h3>\n<ul>\n'
        for v in entry.get("verses", [])[:5]:
            verse_data = get_verse_fast(v["book"], v["chapter"], v["vs"])
            book_name = SLUG_TO_BOOK_NAME.get(v["book"], v["book"])
            ref = f"{book_name} {v['chapter']}:{v['vs']}"
            if v["vs"] != v["ve"]:
                ref = f"{book_name} {v['chapter']}:{v['vs']}-{v['ve']}"
            preview = ""
            if verse_data:
                text = verse_data.get("new", "") or verse_data.get("old", "")
                if len(text) > 150:
                    preview = text[:150] + "..."
                else:
                    preview = text
            entries_html += f'<li><strong>{html.escape(ref)}</strong> — {html.escape(preview)}</li>\n'
            total_shown += 1
        entries_html += '</ul>\n'

    remaining_entries = len(topic.get("entries", [])) - 5
    if remaining_entries > 0:
        entries_html += f'<p style="color:#999;font-size:0.85em;">... და კიდევ {remaining_entries} ქვეთემა</p>\n'

    # see_also
    see_also_html = ""
    if topic.get("see_also"):
        see_also_html = '<h3>დაკავშირებული თემები</h3>\n<p>'
        for ref_slug in topic["see_also"][:10]:
            ref_idx = by_slug.get(ref_slug)
            if ref_idx is not None:
                ref_topic = topics[ref_idx]
                ref_name = get_topic_name(ref_slug, ref_topic.get("name_en", ""))
                see_also_html += f'<a href="/t/{ref_slug}">{html.escape(ref_name)}</a> '
        see_also_html += '</p>\n'

    source_label = "ნეივის თემატიკური ბიბლია" if source == "nave" else "ტორეის სახელმძღვანელო"

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "name": og_title,
        "headline": topic_name,
        "description": og_desc,
        "inLanguage": "ka",
        "url": canonical,
        "isPartOf": {
            "@type": "Book",
            "name": "წმიდა წერილი",
            "inLanguage": "ka"
        }
    }, ensure_ascii=False)

    page_html = f"""<!DOCTYPE html>
<html lang="ka">
<head>
<meta charset="UTF-8">
<title>{og_title}</title>
<meta name="description" content="{og_desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="წმიდა წერილი">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="ka_GE">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_desc}">
<meta name="twitter:image" content="{image_url}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#1a1a2e">
<script type="application/ld+json">
{json_ld}
</script>
<script>setTimeout(function(){{window.location.replace("/#topical/{topic_slug}");}},100);</script>
</head>
<body style="margin:0;padding:40px;font-family:Georgia,serif;background:#faf8f3;color:#1a1a1a;max-width:800px;margin:0 auto;">
<h1 style="color:#4a3828;font-size:1.5em;">{html.escape(topic_name)}</h1>
<p style="color:#999;font-size:0.85em;">{source_label} · {verse_count} მუხლი</p>
<div style="margin:20px 0;line-height:1.8;font-size:1.05em;">
{entries_html}
{see_also_html}
</div>
<noscript><p style="color:#999;font-size:0.85em;text-align:center;">ჩართეთ JavaScript ინტერაქტიული ვერსიისთვის.</p></noscript>
</body>
</html>"""
    resp = make_response(page_html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "public, no-transform, max-age=3600"
    return resp


@app.after_request
def add_cache_headers(resp):
    # Audio ფაილები - ხანგრძლივი კეშირება (არ იცვლებიან, დიდი ფაილებია)
    if request.path.startswith("/static/audio/"):
        resp.headers["Cache-Control"] = "public, max-age=2592000"  # 30 დღე
    # დანარჩენი static ფაილები - მცირე კეშირება, ყოველთვის შემოწმებით
    elif request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache, no-transform, must-revalidate"

    # === ენის ჰედერი ===
    resp.headers["Content-Language"] = "ka"

    return resp


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(STATIC_DIR, "sw.js")
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route("/favicon.ico")
def favicon():
    # ბრაუზერი ავტომატურად ითხოვს /favicon.ico — ვაბრუნებთ favicon.png-ს
    resp = send_from_directory(STATIC_DIR, "favicon.png")
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/googlef9bb9bdad6d4fe6d.html")
def google_verification():
    """Google Search Console ვერიფიკაციის ფაილი."""
    content = "google-site-verification: googlef9bb9bdad6d4fe6d.html"
    resp = Response(content, content_type="text/html; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/robots.txt")
def robots():
    """robots.txt — საძიებო სისტემებისთვის."""
    base_url = "https://web.net.ge"
    content = f"""User-agent: *
Allow: /
Allow: /b/
Disallow: /api/
Disallow: /static/sw.js

Sitemap: {base_url}/sitemap.xml
"""
    resp = Response(content, content_type="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/llms.txt")
def llms_txt():
    """llms.txt — AI სერჩის სისტემებისთვის (GEO/AEO)."""
    try:
        with open(os.path.join(os.path.dirname(__file__), "static", "llms.txt"), "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# წმიდა წერილი - ქართული ბიბლია\n\n> ქართული ბიბლია ორ თარგმანში\n\n- [წმიდა წერილი](https://web.net.ge/)"
    resp = Response(content, content_type="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/sitemap.xml")
def sitemap():
    """sitemap.xml — ყველა წიგნის, თავისა და თემის ბმული საძიებო სისტემებისთვის."""
    base_url = "https://web.net.ge"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = [f"  <url><loc>{base_url}/</loc><lastmod>{now}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>"]

    # თავები
    all_books = BOOKS["old"] + BOOKS["new"]
    for book in all_books:
        slug = book["slug"]
        for chapter in book["chapters"]:
            priority = "0.8" if chapter == 1 else "0.6"
            urls.append(
                f"  <url><loc>{base_url}/b/{slug}/{chapter}</loc>"
                f"<changefreq>monthly</changefreq><priority>{priority}</priority></url>"
            )

    # თემატური ენციკლოპედია (უნიკალური slug-ები)
    if TOPICAL_INDEX:
        topics = TOPICAL_INDEX.get("topics", [])
        by_slug = TOPICAL_INDEX.get("by_slug", {})
        seen_slugs = set()
        for slug in by_slug.keys():
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            idx = by_slug[slug]
            topic = topics[idx]
            verse_count = topic.get("verse_count", 0)
            if verse_count >= 50:
                priority = "0.7"
            elif verse_count >= 10:
                priority = "0.6"
            else:
                priority = "0.5"
            urls.append(
                f"  <url><loc>{base_url}/t/{slug}</loc>"
                f"<changefreq>monthly</changefreq><priority>{priority}</priority></url>"
            )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    resp = Response(xml, content_type="application/xml; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/api/books")
def api_books():
    return jsonify(BOOKS)


@app.route("/api/chapter/<book_slug>/<int:chapter>")
def api_chapter(book_slug, chapter):
    verses = []
    for v in VERSE_INDEX:
        if v["book_slug"] == book_slug and v["chapter"] == chapter:
            verses.append({
                "verse": v["verse"],
                "new": v["new"],
                "old": v["old"],
                "grc": v.get("grc", ""),
            })
    verses.sort(key=lambda x: x["verse"])
    book_name = next((b["name"] for b in BOOKS["old"] + BOOKS["new"] if b["slug"] == book_slug), book_slug)
    return jsonify({
        "book": book_name,
        "book_slug": book_slug,
        "chapter": chapter,
        "verses": verses,
    })


@app.route("/api/search/keyword")
def api_search_keyword():
    """სიტყვიერი ძიება — სრული სტატისტიკით, თავების დაჯგუფებით და მარკირებით.

    სამი რეჟიმი:
      1. ზუსტი ფრაზა (ბრჭყალებში): '"იესო ქრისტე"' — თანმიმდევრობით, გაფართოების გარეშე
      2. AND ლოგიკა (მრავალსიტყვიანი): 'იესო ქრისტე' — ყველა სიტყვა უნდა იყოს, გაფართოებით
      3. ერთი სიტყვა: 'ღმერთი' — გაფართოებით, word boundary-ით
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "total": 0, "total_occurrences": 0, "chapters": []})

    limit = min(int(request.args.get("limit", 200)), 2000)
    testament = request.args.get("testament", "")  # old, new, or ""
    book_slug = request.args.get("book", "")
    translation = request.args.get("translation", "")  # new, old, or "" (ეტაპი B)

    # query-ს დამუშავება — ბრჭყალების სინტაქსი
    parsed = parse_search_query(q)
    is_phrase = parsed["is_phrase"]
    phrase = parsed["phrase"]
    words = parsed["words"]

    if not words and not phrase:
        return jsonify({"results": [], "total": 0, "total_occurrences": 0, "chapters": []})

    # მარკირებისთვის საჭირო ფორმების მომზადება
    if is_phrase:
        # ზუსტი ფრაზა — გაფართოების გარეშე
        highlight_forms = {phrase.lower()}
        # ძიების ლოგიკა: ერთი phrase, word boundary-ით
        search_mode = "phrase"
    elif len(words) == 1:
        # ერთი სიტყვა — გაფართოებით
        expanded = expand_query_words(q)
        highlight_forms = {f.lower() for f in expanded}
        search_mode = "single"
    else:
        # AND ლოგიკა — თითოეული სიტყვის გაფართოება ცალკე
        per_word_forms = []  # [[form1, form2], [form3, form4], ...]
        all_forms = set()
        for w in words:
            expanded_w = expand_query_words(w)
            forms_lower = {f.lower() for f in expanded_w}
            per_word_forms.append(forms_lower)
            all_forms.update(forms_lower)
        highlight_forms = all_forms
        search_mode = "and"

    # პირველ ფაზაში დავთვალოთ ყველა შესაბამისი მუხლი (limit-ის გარეშე)
    all_matches = []
    total_occurrences = 0
    chapters_map = {}  # key: "slug:chapter" -> info

    # თარგმანის ფილტრის მიხედვით ვარჩევთ ინდექსს
    if translation == "new":
        _w2vc = WORD_TO_VERSE_COUNTS_NEW
    elif translation == "old":
        _w2vc = WORD_TO_VERSE_COUNTS_OLD
    else:
        _w2vc = WORD_TO_VERSE_COUNTS

    if search_mode == "phrase":
        # ზუსტი ფრაზა — სრული სკანირება (phrase search უკვე სწრაფია, ~0.4s)
        # არ ვიყენებთ W2VC კანდიდატებს რადგან count_phrase_occurrences-ს არ აქვს
        # ბოლო word boundary (ქართული დანაერთების გამო), რაც ნიშნავს რომ ფრაზა
        # იესო ქრისტე მოიძებნება როგორც იესო ქრისტეს, იესო ქრისტეთა და ა.შ.
        # W2VC ინდექსი ეძებს ზუსტ სიტყვებს და ვერ პოულობს ამ შემთხვევებს
        for v in VERSE_INDEX:
            if testament and v["testament"] != testament:
                continue
            if book_slug and v["book_slug"] != book_slug:
                continue
            new_text = v["new"] or ""
            old_text = v["old"] or ""
            if translation == "new":
                old_text = ""
            elif translation == "old":
                new_text = ""
            total_count = count_phrase_occurrences(new_text, phrase)
            total_count += count_phrase_occurrences(old_text, phrase)
            exact_count = total_count  # ფრაზის შემთხვევაში ყველა exact-ია
            if total_count == 0:
                continue
            total_occurrences += total_count
            ch_key = f"{v['book_slug']}:{v['chapter']}"
            if ch_key not in chapters_map:
                chapters_map[ch_key] = {
                    "book": v["book"],
                    "book_slug": v["book_slug"],
                    "chapter": v["chapter"],
                    "verse_count": 0,
                    "occurrences": 0,
                }
            chapters_map[ch_key]["verse_count"] += 1
            chapters_map[ch_key]["occurrences"] += total_count
            all_matches.append((v, total_count, exact_count))

    elif search_mode == "single":
        # ერთი სიტყვა — W2VC-ით სწრაფი lookup (regex loop-ის ნაცვლად)
        query_word_lower = words[0].lower() if words else ""
        _verse_total = {}
        _verse_exact = {}
        for _form in highlight_forms:
            if _form in _w2vc:
                for _vidx, _cnt in _w2vc[_form].items():
                    _verse_total[_vidx] = _verse_total.get(_vidx, 0) + _cnt
                    if _form == query_word_lower:
                        _verse_exact[_vidx] = _verse_exact.get(_vidx, 0) + _cnt

        for _vidx, total_count in _verse_total.items():
            v = VERSE_INDEX[_vidx]
            if testament and v["testament"] != testament:
                continue
            if book_slug and v["book_slug"] != book_slug:
                continue
            exact_count = _verse_exact.get(_vidx, 0)
            if total_count == 0:
                continue
            total_occurrences += total_count
            ch_key = f"{v['book_slug']}:{v['chapter']}"
            if ch_key not in chapters_map:
                chapters_map[ch_key] = {
                    "book": v["book"],
                    "book_slug": v["book_slug"],
                    "chapter": v["chapter"],
                    "verse_count": 0,
                    "occurrences": 0,
                }
            chapters_map[ch_key]["verse_count"] += 1
            chapters_map[ch_key]["occurrences"] += total_count
            all_matches.append((v, total_count, exact_count))

    else:
        # AND ლოგიკა — თითოეული სიტყვის W2VC lookup, შემდეგ ინტერსექცია
        _per_word_counts = []
        for _word_forms in per_word_forms:
            _word_total = {}
            for _form in _word_forms:
                if _form in _w2vc:
                    for _vidx, _cnt in _w2vc[_form].items():
                        _word_total[_vidx] = _word_total.get(_vidx, 0) + _cnt
            _per_word_counts.append(_word_total)

        # ინტერსექცია — ყველა სიტყვა უნდა იყოს წარმოდგენილი
        if _per_word_counts:
            _candidate_verses = set(_per_word_counts[0].keys())
            for _wc in _per_word_counts[1:]:
                _candidate_verses = _candidate_verses & set(_wc.keys())
        else:
            _candidate_verses = set()

        for _vidx in _candidate_verses:
            v = VERSE_INDEX[_vidx]
            if testament and v["testament"] != testament:
                continue
            if book_slug and v["book_slug"] != book_slug:
                continue
            total_count = sum(_wc.get(_vidx, 0) for _wc in _per_word_counts)
            exact_count = 0
            for _wi, _word_forms in enumerate(per_word_forms):
                _query_word_lower = words[_wi].lower() if _wi < len(words) else ""
                if _query_word_lower in _word_forms and _query_word_lower in _w2vc:
                    exact_count += _w2vc[_query_word_lower].get(_vidx, 0)
            if total_count == 0:
                continue
            total_occurrences += total_count
            ch_key = f"{v['book_slug']}:{v['chapter']}"
            if ch_key not in chapters_map:
                chapters_map[ch_key] = {
                    "book": v["book"],
                    "book_slug": v["book_slug"],
                    "chapter": v["chapter"],
                    "verse_count": 0,
                    "occurrences": 0,
                }
            chapters_map[ch_key]["verse_count"] += 1
            chapters_map[ch_key]["occurrences"] += total_count
            all_matches.append((v, total_count, exact_count))

    # თავების სია — დალაგებული რაოდენობის მიხედვით
    chapters = sorted(
        chapters_map.values(),
        key=lambda x: x["occurrences"],
        reverse=True
    )

    # მუხლების სია — დალაგებული: ჯერ exact_count (ზუსტი სიტყვა), მერე total_count
    all_matches.sort(key=lambda x: (x[2], x[1]), reverse=True)

    # მუხლების სია — მხოლოდ პირველ limit მუხლისთვის ვამზადებთ მარკირებულ ტექსტს
    results = []
    for v, total_count, exact_count in all_matches[:limit]:
        new_text = v["new"] or ""
        old_text = v["old"] or ""
        # თარგმანის ფილტრი (ეტაპი B) — მარკირებაშიც
        if translation == "new":
            old_text = ""
        elif translation == "old":
            new_text = ""
        # მარკირება — word boundary-ით
        # ჯერ ესკეიპდება HTML, მერე მარკირდება (defense-in-depth)
        marked_new = html.escape(new_text)
        marked_old = html.escape(old_text)
        # ფრაზის შემთხვევაში ბოლო word boundary არ არის (ქართული დანაერთები)
        end_wb = not is_phrase
        for form in sorted(highlight_forms, key=len, reverse=True):
            marked_new = _highlight_word(marked_new, form, end_boundary=end_wb)
            marked_old = _highlight_word(marked_old, form, end_boundary=end_wb) if marked_old else ""
        results.append({
            "book": v["book"],
            "book_slug": v["book_slug"],
            "chapter": v["chapter"],
            "verse": v["verse"],
            "new": new_text,
            "old": old_text,
            "new_marked": marked_new,
            "old_marked": marked_old,
            "occurrences": total_count,
            "exact_count": exact_count,
            "testament": v["testament"],
            "score": float(total_count),
        })

    return jsonify({
        "results": results,
        "total": len(all_matches),  # სრული რაოდენობა (limit-ის გარეშე)
        "total_occurrences": total_occurrences,
        "total_chapters": len(chapters),
        "chapters": chapters,
        "query": q,
        "showing": len(results),  # რამდენი მუხლი ვაჩვენეთ
        "expanded_forms": sorted(highlight_forms),
        "expanded_count": len(highlight_forms),
        "search_mode": search_mode,  # phrase / single / and
    })


def _highlight_word(text, word, end_boundary=True):
    """სიტყვის გამოყოფა <mark> ტეგით (case-insensitive, word boundary-ით).

    end_boundary=True — სრული სიტყვა (ერთსიტყვიანი ძიება)
    end_boundary=False — მხოლოდ დასაწყისის wb (ფრაზის ძიება, ქართული დანაერთების გამო)
    """
    if not text or not word:
        return text or ""
    # word boundary — მხოლოდ სრული სიტყვების მარკირება
    if end_boundary:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE | re.UNICODE)
    else:
        pattern = re.compile(r'\b' + re.escape(word), re.IGNORECASE | re.UNICODE)
    return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', text)


@app.route("/api/search/ai")
def api_search_ai():
    """AI ძიება — LaBSE dense + BM25 + RRF + Cross-Encoder reranking."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "total": 0})

    # ბრჭყალების მოცილება AI ძიებისთვის (სემანტიკური ძიება ფრაზის სინტაქსს არ იყენებს)
    parsed = parse_search_query(q)
    if parsed["is_phrase"]:
        q = parsed["phrase"]

    limit = int(request.args.get("limit", 20))
    threshold = float(request.args.get("threshold", 0.2))
    testament = request.args.get("testament", "")
    book_slug = request.args.get("book", "")
    rerank = request.args.get("rerank", "true").lower() != "false"

    # === ფენა 1: BM25 (ლექსიკური) — გაფართოებული ტოკენებით ===
    bm25_candidates = []
    if BM25 is not None:
        tokens = tokenize_georgian(q)
        # გაფართოება — დავამატოთ ყველა ფორმა ყველა სიტყვის
        expanded_tokens = list(expand_query_words(q))
        # BM25-სთვის ვიყენებთ გაფართოებულ ტოკენებს
        bm25_scores = BM25.get_scores(expanded_tokens)
        # ვიღებთ top 100-ს
        bm25_top = np.argsort(bm25_scores)[::-1][:100]
        bm25_candidates = [int(i) for i in bm25_top if bm25_scores[i] > 0]

    # === ფენა 2: LaBSE Dense (სემანტიკური) ===
    model = get_embed_model()
    query_emb = model.encode([q], normalize_embeddings=True, convert_to_numpy=True)[0]
    dense_scores = EMBEDDINGS @ query_emb
    dense_top = np.argsort(dense_scores)[::-1][:100]
    dense_candidates = [int(i) for i in dense_top if dense_scores[i] > threshold]

    # === ფენა 2.5: Exact Match (გარანტია — ყოველთვის ჩართული) ===
    # გარანტია: ნებისმიერი სიტყვა, რომელიც ბიბლიაშია, უნდა მოიძებნოს.
    # Exact match word boundary-ით (keyword endpoint-თან კონსისტენტური)
    # ზღვარი არ არის — ყველა exact match იპოვება
    expanded_forms = expand_query_words(q)
    expanded_forms_lower = {f.lower() for f in expanded_forms}
    exact_candidates = []  # (idx, occurrence_count)
    # სწრაფი lookup WORD_TO_VERSE_COUNTS ინდექსიდან (regex loop-ის ნაცვლად)
    verse_occ = {}
    for form in expanded_forms_lower:
        if form in WORD_TO_VERSE_COUNTS:
            for vidx, cnt in WORD_TO_VERSE_COUNTS[form].items():
                verse_occ[vidx] = verse_occ.get(vidx, 0) + cnt
    for vidx, occ in verse_occ.items():
        v = VERSE_INDEX[vidx]
        if testament and v["testament"] != testament:
            continue
        if book_slug and v["book_slug"] != book_slug:
            continue
        if occ > 0:
            exact_candidates.append((vidx, occ))

    # Exact matches დალაგება სიხშირის მიხედვით
    exact_candidates.sort(key=lambda x: x[1], reverse=True)
    exact_idx_set = {idx for idx, _ in exact_candidates}

    # === ფენა 3: RRF Fusion (სემანტიკური შედეგებისთვის) ===
    fused = reciprocal_rank_fusion(bm25_candidates, dense_candidates, k=60)

    # თუ არაფერი მოიძებნა (არც exact, არც BM25, არც dense)
    if not exact_candidates and not bm25_candidates:
        if not dense_candidates or dense_scores[dense_candidates[0]] < threshold * 2:
            return jsonify({
                "results": [],
                "total": 0,
                "query": q,
                "method": "არ მოიძებნა",
            })

    # სემანტიკური შედეგები (exact match-ის გარეშე) — დამატებითი შედეგები
    semantic_filtered = []
    for idx, score in fused:
        if idx in exact_idx_set:
            continue  # exact match-ები ცალკე ვაქვთ
        v = VERSE_INDEX[idx]
        if testament and v["testament"] != testament:
            continue
        if book_slug and v["book_slug"] != book_slug:
            continue
        semantic_filtered.append((idx, score))
        if len(semantic_filtered) >= 30:
            break

    # === ფენა 4: Cross-Encoder Reranking ===
    ce = get_cross_encoder() if rerank else None

    # 4a: Exact matches-ის რერანჟირება CE-ით (მაგრამ ყოველთვის პირველი)
    exact_results = []
    if exact_candidates:
        exact_top = exact_candidates[:30]  # top 30 exact match CE-ისთვის
        if ce is not None and len(exact_top) > 0:
            pairs = []
            for idx, occ in exact_top:
                v = VERSE_INDEX[idx]
                doc = v["new"]
                if v["old"]:
                    doc += " " + v["old"]
                pairs.append((q, doc))
            ce_scores = ce.predict(pairs)
            for i, (idx, occ) in enumerate(exact_top):
                ce_score = float(ce_scores[i])
                # exact match: occ + CE — სიხშირე და სემანტიკური მსგავსება
                final_score = 0.5 * occ + 0.5 * (ce_score + 1) / 2
                exact_results.append((idx, final_score, ce_score))
            exact_results.sort(key=lambda x: x[1], reverse=True)
        else:
            for idx, occ in exact_top:
                exact_results.append((idx, float(occ), 0.0))

    # 4b: სემანტიკური შედეგების რერანჟირება CE-ით
    semantic_results = []
    if semantic_filtered:
        if ce is not None and len(semantic_filtered) > 0:
            pairs = []
            for idx, _ in semantic_filtered[:20]:
                v = VERSE_INDEX[idx]
                doc = v["new"]
                if v["old"]:
                    doc += " " + v["old"]
                pairs.append((q, doc))
            ce_scores = ce.predict(pairs)
            for i, (idx, rrf_score) in enumerate(semantic_filtered[:20]):
                ce_score = float(ce_scores[i])
                final_score = 0.3 * rrf_score * 60 + 0.7 * (ce_score + 1) / 2
                semantic_results.append((idx, final_score, ce_score))
            semantic_results.sort(key=lambda x: x[1], reverse=True)
        else:
            for idx, score in semantic_filtered[:20]:
                semantic_results.append((idx, float(score), 0.0))

    # შედეგების გაერთიანება: exact matches პირველი, შემდეგ სემანტიკური
    results = []
    for idx, final_score, ce_score in exact_results[:limit]:
        v = VERSE_INDEX[idx]
        results.append(_make_result(v, float(final_score), ce_score=float(ce_score), exact=True))
    # დანარჩენი ადგილები სემანტიკური შედეგებით
    remaining = limit - len(results)
    if remaining > 0:
        for idx, final_score, ce_score in semantic_results[:remaining]:
            v = VERSE_INDEX[idx]
            results.append(_make_result(v, float(final_score), ce_score=float(ce_score), exact=False))

    return jsonify({
        "results": results,
        "total": len(results),
        "exact_count": len(exact_candidates),  # რამდენი exact match იპოვა
        "query": q,
        "method": "ჰიბრიდული+რერანკი" if (rerank and ce is not None) else "ჰიბრიდული",
    })


@app.route("/api/search/hybrid")
def api_search_hybrid():
    """Hybrid search — alias for AI search."""
    return api_search_ai()


@app.route("/api/verse/<book_slug>/<int:chapter>/<int:verse>")
def api_verse(book_slug, chapter, verse):
    result = get_verse_fast(book_slug, chapter, verse)
    if result is None:
        return jsonify({"error": "არ მოიძებნა"}), 404
    return jsonify(result)


@app.route("/api/crossrefs/<book_slug>/<int:chapter>/<int:verse>")
def api_crossrefs(book_slug, chapter, verse):
    """მუხლის cross-references.

    GET /api/crossrefs/dabadeba/1/1?limit=15&min_confidence=50

    აბრუნებს დაკავშირებულ მუხლებს confidence-ის მიხედვით დალაგებულს,
    თითო შედეგში პირველი მუხლის ტექსტის preview-ით, თემატური
    კატეგორიით და სანდოობის ქულით.

    წყაროები:
    - tsk: Treasury of Scripture Knowledge (აკადემიური, 1800-იანი წლები)
    - openbible: OpenBible.info (ხმების მიხედვით)
    - both: ორივე ბაზაშია (ორმაგი სანდოობა)
    """
    if not CROSSREFS:
        return jsonify({"error": "ჯვარედინი მითითებები მიუწვდომელია"}), 503

    key = f"{book_slug}:{chapter}:{verse}"
    refs = CROSSREFS.get(key, [])

    limit = min(int(request.args.get("limit", 15)), 50)
    min_confidence = int(request.args.get("min_confidence", 50))
    # min_votes შენარჩუნებულია უკანა თავსებადობისთვის
    min_votes = int(request.args.get("min_votes", 0))

    # ფილტრაცია confidence-ის მიხედვით
    filtered = []
    for r in refs:
        conf = r.get("confidence", 0)
        votes = r.get("votes", 0)
        if conf >= min_confidence and votes >= min_votes:
            filtered.append(r)
    filtered = filtered[:limit]

    enriched = []
    for ref in filtered:
        book_name = SLUG_TO_BOOK_NAME.get(ref["book"], ref["book"])
        # პირველი მუხლის ტექსტი preview-სთვის
        first_verse = get_verse_fast(ref["book"], ref["chapter"], ref["vs"])
        preview = ""
        if first_verse:
            text = first_verse.get("new", "") or first_verse.get("old", "")
            if len(text) > 200:
                preview = text[:200] + "..."
            else:
                preview = text
        enriched.append({
            "book": ref["book"],
            "book_name": book_name,
            "chapter": ref["chapter"],
            "vs": ref["vs"],
            "ve": ref["ve"],
            "votes": ref.get("votes", 0),
            "confidence": ref.get("confidence", 0),
            "source": ref.get("source", "openbible"),
            "topic": ref.get("topic", "general"),
            "topic_ka": get_crossref_topic(ref.get("topic", "")),
            "type": ref.get("type", "thematic"),
            "text_preview": preview,
        })

    source_name = SLUG_TO_BOOK_NAME.get(book_slug, book_slug)

    return jsonify({
        "source": {
            "book": book_slug,
            "book_name": source_name,
            "chapter": chapter,
            "verse": verse,
        },
        "total": len(refs),
        "shown": len(enriched),
        "crossrefs": enriched,
    })


# === თემატური ენციკლოპედია API ===

@app.route("/api/topics/search")
def api_topics_search():
    """თემების ძიება სახელის მიხედვით.

    GET /api/topics/search?q=god&limit=20
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ენციკლოპედია მიუწვდომელია"}), 503

    q = request.args.get("q", "").strip().lower()
    limit = min(int(request.args.get("limit", 20)), 100)

    topics = TOPICAL_INDEX.get("topics", [])
    results = []

    for topic in topics:
        name_en_raw = topic.get("name_en", "")
        name_en_lower = name_en_raw.lower()
        slug = topic.get("slug", "")
        name_ka = get_topic_name(slug, name_en_raw)

        if not q:
            # ყველა თემა verse_count-ის მიხედვით
            results.append({
                "slug": slug,
                "name": name_ka,
                "name_en": name_en_raw,
                "verse_count": topic.get("verse_count", 0),
                "source": topic.get("source", "nave"),
            })
        elif q in name_en_lower or q in slug or q in name_ka.lower():
            results.append({
                "slug": slug,
                "name": name_ka,
                "name_en": name_en_raw,
                "verse_count": topic.get("verse_count", 0),
                "source": topic.get("source", "nave"),
            })

    # დალაგება verse_count-ის მიხედვით
    results.sort(key=lambda x: -x["verse_count"])

    return jsonify({
        "results": results[:limit],
        "total": len(results),
        "query": q,
    })


@app.route("/api/topics/<topic_slug>")
def api_topic_detail(topic_slug):
    """თემის დეტალური ინფორმაცია - ყველა ენტრი და მუხლი.

    GET /api/topics/god
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ენციკლოპედია მიუწვდომელია"}), 503

    topics = TOPICAL_INDEX.get("topics", [])
    by_slug = TOPICAL_INDEX.get("by_slug", {})

    idx = by_slug.get(topic_slug)
    if idx is None:
        return jsonify({"error": "თემა არ მოიძებნა"}), 404

    topic = topics[idx]

    # ენტრიების გამდიდრება მუხლის ტექსტით
    enriched_entries = []
    for entry in topic.get("entries", []):
        enriched_verses = []
        for v in entry.get("verses", []):
            verse_data = get_verse_fast(v["book"], v["chapter"], v["vs"])
            preview = ""
            if verse_data:
                text = verse_data.get("new", "") or verse_data.get("old", "")
                if len(text) > 200:
                    preview = text[:200] + "..."
                else:
                    preview = text

            book_name = SLUG_TO_BOOK_NAME.get(v["book"], v["book"])
            enriched_verses.append({
                "book": v["book"],
                "book_name": book_name,
                "chapter": v["chapter"],
                "vs": v["vs"],
                "ve": v["ve"],
                "text_preview": preview,
            })
        enriched_entries.append({
            "label": get_topic_label(entry.get("label", "")),
            "verses": enriched_verses,
        })

    # see_also თემების გამდიდრება
    see_also_enriched = []
    for ref_slug in topic.get("see_also", []):
        ref_idx = by_slug.get(ref_slug)
        if ref_idx is not None:
            ref_topic = topics[ref_idx]
            see_also_enriched.append({
                "slug": ref_slug,
                "name": get_topic_name(ref_slug, ref_topic.get("name_en", "")),
                "name_en": ref_topic.get("name_en", ""),
                "verse_count": ref_topic.get("verse_count", 0),
            })

    return jsonify({
        "slug": topic["slug"],
        "name": get_topic_name(topic["slug"], topic.get("name_en", "")),
        "name_en": topic.get("name_en", ""),
        "source": topic.get("source", "nave"),
        "verse_count": topic.get("verse_count", 0),
        "entries": enriched_entries,
        "see_also": see_also_enriched,
    })


@app.route("/api/topics/verse/<book_slug>/<int:chapter>/<int:verse>")
def api_topics_for_verse(book_slug, chapter, verse):
    """მუხლის თემები - რა თემებს ეკუთვნის ეს მუხლი.

    GET /api/topics/verse/dabadeba/1/1
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ენციკლოპედია მიუწვდომელია"}), 503

    by_verse = TOPICAL_INDEX.get("by_verse", {})
    key = f"{book_slug}:{chapter}:{verse}"
    topic_slugs = by_verse.get(key, [])

    topics = TOPICAL_INDEX.get("topics", [])
    by_slug = TOPICAL_INDEX.get("by_slug", {})

    results = []
    for slug in topic_slugs:
        idx = by_slug.get(slug)
        if idx is not None:
            t = topics[idx]
            results.append({
                "slug": slug,
                "name": get_topic_name(slug, t.get("name_en", "")),
                "name_en": t.get("name_en", ""),
                "verse_count": t.get("verse_count", 0),
                "source": t.get("source", "nave"),
            })

    # დალაგება verse_count-ის მიხედვით
    results.sort(key=lambda x: -x["verse_count"])

    return jsonify({
        "book": book_slug,
        "chapter": chapter,
        "verse": verse,
        "topics": results,
        "total": len(results),
    })


@app.route("/api/topics/testament/<testament>")
def api_topics_by_testament(testament):
    """აღთქმის მიხედვით თემების ფილტრაცია.

    GET /api/topics/testament/old
    GET /api/topics/testament/new
    GET /api/topics/testament/apocrypha
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ენციკლოპედია მიუწვდომელია"}), 503

    testament = testament.lower()
    if testament not in ("old", "new", "apocrypha"):
        return jsonify({"error": "არასწორი აღთქმა. გამოიყენეთ: old, new, apocrypha"}), 400

    by_book = TOPICAL_INDEX.get("by_book", {})
    topics = TOPICAL_INDEX.get("topics", [])
    by_slug = TOPICAL_INDEX.get("by_slug", {})

    # აღთქმის წიგნების მოძებნა
    book_slugs = [b["slug"] for b in BOOKS["old"] + BOOKS["new"]
                  if (testament == "apocrypha" and b.get("apocryphal"))
                  or (testament == "old" and b["testament"] == "old" and not b.get("apocryphal"))
                  or (testament == "new" and b["testament"] == "new")]

    # თემების შეგროვება აღთქმის წიგნებიდან
    topic_verse_counts = {}  # slug -> total verses in this testament
    for book_slug in book_slugs:
        book_data = by_book.get(book_slug)
        if not book_data:
            continue
        for tt in book_data.get("top_topics", []):
            slug = tt["slug"]
            topic_verse_counts[slug] = topic_verse_counts.get(slug, 0) + tt["verses_in_book"]

    # შედეგების ფორმირება
    results = []
    for slug, verses_in_testament in sorted(topic_verse_counts.items(),
                                             key=lambda x: -x[1]):
        idx = by_slug.get(slug)
        if idx is not None:
            t = topics[idx]
            results.append({
                "slug": slug,
                "name": get_topic_name(slug, t.get("name_en", "")),
                "name_en": t.get("name_en", ""),
                "verses_in_testament": verses_in_testament,
                "total_verses": t.get("verse_count", 0),
                "source": t.get("source", "nave"),
            })

    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify({
        "testament": testament,
        "book_count": len(book_slugs),
        "topic_count": len(results),
        "topics": results[:limit],
        "total": len(results),
    })


@app.route("/api/topics/book/<book_slug>")
def api_topics_by_book(book_slug):
    """კონკრეტული წიგნის თემები.

    GET /api/topics/book/dabadeba
    GET /api/topics/book/fsalmunni
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ენციკლოპედია მიუწვდომელია"}), 503

    book_slug = book_slug.lower()
    by_book = TOPICAL_INDEX.get("by_book", {})
    book_data = by_book.get(book_slug)

    if not book_data:
        return jsonify({"error": "წიგნი ვერ მოიძებნა თემატურ ინდექსში"}), 404

    topics = TOPICAL_INDEX.get("topics", [])
    by_slug = TOPICAL_INDEX.get("by_slug", {})

    # წიგნის ინფორმაცია
    book_info = None
    for b in BOOKS["old"] + BOOKS["new"]:
        if b["slug"] == book_slug:
            book_info = b
            break

    # თემების შეგროვება
    results = []
    for tt in book_data.get("top_topics", []):
        slug = tt["slug"]
        idx = by_slug.get(slug)
        if idx is not None:
            t = topics[idx]
            results.append({
                "slug": slug,
                "name": get_topic_name(slug, t.get("name_en", "")),
                "name_en": t.get("name_en", ""),
                "verses_in_book": tt["verses_in_book"],
                "total_verses": t.get("verse_count", 0),
                "source": t.get("source", "nave"),
            })

    limit = min(int(request.args.get("limit", 100)), 500)
    return jsonify({
        "book": book_slug,
        "book_name": book_info["name"] if book_info else book_slug,
        "testament": book_data.get("testament", "old"),
        "apocryphal": book_info.get("apocryphal", False) if book_info else False,
        "topic_count": book_data.get("topic_count", 0),
        "verse_count": book_data.get("verse_count", 0),
        "topics": results[:limit],
        "total": len(results),
    })


@app.route("/api/stats")
def api_stats():
    """სტატისტიკა — წიგნების და მუხლების რაოდენობა."""
    from collections import Counter
    verse_counts = Counter(v["book_slug"] for v in VERSE_INDEX)
    total_verses = len(VERSE_INDEX)
    total_books = len(verse_counts)

    old_canon_books = 0
    old_canon_verses = 0
    new_books = 0
    new_verses = 0
    noncanon_books = 0
    noncanon_verses = 0

    for b in BOOKS["old"] + BOOKS["new"]:
        slug = b["slug"]
        count = verse_counts.get(slug, 0)
        if b.get("apocryphal"):
            noncanon_books += 1
            noncanon_verses += count
        elif b["testament"] == "new":
            new_books += 1
            new_verses += count
        else:
            old_canon_books += 1
            old_canon_verses += count

    canon_books = old_canon_books + new_books
    canon_verses = old_canon_verses + new_verses

    return jsonify({
        "total_books": total_books,
        "total_verses": total_verses,
        "canonical_books": canon_books,
        "canonical_verses": canon_verses,
        "ot_books": old_canon_books,
        "ot_verses": old_canon_verses,
        "nt_books": new_books,
        "nt_verses": new_verses,
        "noncanon_books": noncanon_books,
        "noncanon_verses": noncanon_verses,
        "embedding_dim": int(EMBEDDINGS.shape[1]),
        "embedding_model": EMBED_MODEL_NAME,
        "bm25_enabled": BM25 is not None,
    })


def _make_result(v, score, ce_score=None, exact=False):
    result = {
        "book": v["book"],
        "book_slug": v["book_slug"],
        "chapter": v["chapter"],
        "verse": v["verse"],
        "new": v["new"],
        "old": v["old"],
        "testament": v["testament"],
        "score": round(score, 4),
        "exact": exact,
    }
    if ce_score is not None:
        result["ce_score"] = round(ce_score, 4)
    return result


# === ლექსიკონის API ===

def _build_translation_scope(translation_field):
    """ააგებს თარგმანის სკოპს (old_trans / new_trans) letters სტრუქტურას
    არსებული letters მონაცემებიდან, ფილტრავს სიტყვებს translation_field-ის მიხედვით."""
    from collections import defaultdict
    scope_letters = defaultdict(list)
    total_unique = 0
    total_occ = 0

    for letter, ld in LEXICON["letters"].items():
        for w in ld["words"]:
            count = w.get(translation_field, 0)
            if count > 0:
                scope_letters[letter].append({
                    "word": w["word"],
                    "total": count,
                    "old": w.get("old", 0),
                    "new": w.get("new", 0),
                    "books": w.get("books", 0),
                })
                total_unique += 1
                total_occ += count

    # დალაგება სიხშირით
    letters_out = {}
    for letter, words in scope_letters.items():
        words.sort(key=lambda x: x["total"], reverse=True)
        letters_out[letter] = {
            "letter": letter,
            "total_words": len(words),
            "total_occurrences": sum(w["total"] for w in words),
            "words": words,
        }

    return letters_out, total_unique, total_occ


# cache თარგმანის სკოპებისთვის
_TRANS_SCOPE_CACHE = {}


def _get_translation_scope(translation_field):
    """აბრუნებს cached თარგმანის სკოპს."""
    if translation_field not in _TRANS_SCOPE_CACHE:
        letters, unique, occ = _build_translation_scope(translation_field)
        _TRANS_SCOPE_CACHE[translation_field] = {
            "letters": letters,
            "total_unique": unique,
            "total_occurrences": occ,
        }
    return _TRANS_SCOPE_CACHE[translation_field]


def _get_scope_letters(scope, book_slug=None):
    """აბრუნებს სკოპის letters დიქტს მიღებული პარამეტრების მიხედვით."""
    if scope == "all" or scope is None:
        return LEXICON["letters"]
    if scope in ("old", "new", "canonical", "noncanonical"):
        s = LEXICON["scopes"].get(scope)
        if s:
            return s["letters"]
        return {}
    if scope in ("old_trans", "new_trans"):
        field = "old" if scope == "old_trans" else "new"
        return _get_translation_scope(field)["letters"]
    if scope == "book" and book_slug:
        b = LEXICON["scopes"]["books"].get(book_slug)
        if b:
            return b["letters"]
        return {}
    return LEXICON["letters"]


def _get_scope_stats(scope, book_slug=None):
    """აბრუნებს სკოპის სტატისტიკას."""
    if scope == "all" or scope is None:
        return {
            "total_unique": LEXICON["metadata"]["total_unique_words"],
            "total_occurrences": LEXICON["metadata"]["total_word_occurrences"],
        }
    if scope in ("old", "new", "canonical", "noncanonical"):
        s = LEXICON["scopes"].get(scope)
        if s:
            return {"total_unique": s["total_unique"], "total_occurrences": s["total_occurrences"]}
    if scope in ("old_trans", "new_trans"):
        field = "old" if scope == "old_trans" else "new"
        s = _get_translation_scope(field)
        return {"total_unique": s["total_unique"], "total_occurrences": s["total_occurrences"]}
    if scope == "book" and book_slug:
        b = LEXICON["scopes"]["books"].get(book_slug)
        if b:
            return {"total_unique": b["total_unique"], "total_occurrences": b["total_occurrences"]}
    return {"total_unique": 0, "total_occurrences": 0}


@app.route("/api/lexicon")
def api_lexicon():
    """ლექსიკონის მეტადანები + ასოების სია."""
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503

    scope = request.args.get("scope", "all")
    book_slug = request.args.get("book", "")

    letters_data = _get_scope_letters(scope, book_slug)
    scope_stats = _get_scope_stats(scope, book_slug)

    letters_summary = {}
    for letter, ld in letters_data.items():
        letters_summary[letter] = {
            "letter": ld["letter"],
            "total_words": ld["total_words"],
            "total_occurrences": ld["total_occurrences"],
        }

    # თარგმანის უნიკალური სიტყვების რაოდენობა (dynamic)
    old_trans = _get_translation_scope("old")
    new_trans = _get_translation_scope("new")
    meta_with_trans = dict(LEXICON["metadata"])
    meta_with_trans["old_trans_unique"] = old_trans["total_unique"]
    meta_with_trans["new_trans_unique"] = new_trans["total_unique"]

    return jsonify({
        "metadata": meta_with_trans,
        "scope": scope,
        "book": book_slug,
        "scope_stats": scope_stats,
        "letters": letters_summary,
        "book_stats": LEXICON["book_stats"],
    })


@app.route("/api/lexicon/<letter>")
def api_lexicon_letter(letter):
    """კონკრეტული ასოს სიტყვების სრული სია (სიხშირით დალაგებული)."""
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503

    scope = request.args.get("scope", "all")
    book_slug = request.args.get("book", "")

    letters_data = _get_scope_letters(scope, book_slug)
    ld = letters_data.get(letter)
    if ld is None:
        return jsonify({"error": f"ასო '{letter}' ვერ მოიძებნა ამ სკოპში"}), 404

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 500))
    per_page = min(per_page, 2000)
    offset = (page - 1) * per_page
    total = len(ld["words"])
    words_page = ld["words"][offset:offset + per_page]

    # გაუმჯობესება: word groups-დან ფორმების რაოდენობის დამატება
    for w in words_page:
        word = w["word"]
        if word in WORD_TO_GROUP:
            lemma = WORD_TO_GROUP[word]
            w["forms_count"] = len(GROUP_FORMS.get(lemma, set()))
            w["lemma"] = lemma
        else:
            w["forms_count"] = 1
            w["lemma"] = word

    return jsonify({
        "letter": ld["letter"],
        "total_words": total,
        "total_occurrences": ld["total_occurrences"],
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "words": words_page,
        "scope": scope,
        "book": book_slug,
    })


@app.route("/api/lexicon/stats")
def api_lexicon_stats():
    """წიგნების სტატისტიკა."""
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503
    return jsonify({
        "metadata": LEXICON["metadata"],
        "book_stats": LEXICON["book_stats"],
    })


@app.route("/api/lexicon/search")
def api_lexicon_search():
    """სიტყვების ძიება ლექსიკონში (substring match)."""
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503

    q = request.args.get("q", "").strip().lower()
    if not q or len(q) < 1:
        return jsonify({"results": [], "total": 0})

    scope = request.args.get("scope", "all")
    book_slug = request.args.get("book", "")
    limit = min(int(request.args.get("limit", 200)), 500)

    letters_data = _get_scope_letters(scope, book_slug)

    results = []
    for letter, ld in letters_data.items():
        for w in ld["words"]:
            if q in w["word"].lower():
                # word groups ინფორმაციის დამატება
                word = w["word"]
                if word in WORD_TO_GROUP:
                    w_copy = dict(w)
                    w_copy["forms_count"] = len(GROUP_FORMS.get(WORD_TO_GROUP[word], set()))
                    w_copy["lemma"] = WORD_TO_GROUP[word]
                    results.append(w_copy)
                else:
                    w_copy = dict(w)
                    w_copy["forms_count"] = 1
                    w_copy["lemma"] = word
                    results.append(w_copy)
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    results.sort(key=lambda x: x["total"], reverse=True)

    return jsonify({
        "query": q,
        "results": results[:limit],
        "total": len(results),
        "scope": scope,
        "book": book_slug,
    })


@app.route("/api/word/forms/<word>")
def api_word_forms(word):
    """სიტყვის ყველა ფორმის მიღება (word groups-დან)."""
    word_lower = word.lower()
    if word_lower in WORD_TO_GROUP:
        lemma = WORD_TO_GROUP[word_lower]
        forms = sorted(GROUP_FORMS.get(lemma, set()))
        return jsonify({
            "word": word_lower,
            "lemma": lemma,
            "forms": forms,
            "forms_count": len(forms),
        })
    return jsonify({
        "word": word_lower,
        "lemma": word_lower,
        "forms": [word_lower],
        "forms_count": 1,
    })


@app.route("/api/word/stats/<word>")
def api_word_stats(word):
    """სიტყვის ზუსტი სტატისტიკა (ლექსიკონიდან).

    ეძებს ზუსტ სიტყვას და აბრუნებს სტატისტიკას.
    თუ სიტყვა არის მორფოლოგიური ჯგუფის ნაწილი, ეძებს ლემასაც.
    """
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503

    word_lower = word.lower()

    # მორფოლოგიური ფორმების მიღება
    forms_to_search = {word_lower}
    lemma = word_lower
    if word_lower in WORD_TO_GROUP:
        lemma = WORD_TO_GROUP[word_lower]
        forms_to_search = GROUP_FORMS.get(lemma, {word_lower})

    # ზუსტი სიტყვის მოძებნა ლექსიკონში
    result = None
    for letter, ld in LEXICON["letters"].items():
        for w in ld["words"]:
            if w["word"] in forms_to_search:
                if result is None:
                    result = dict(w)
                    result["lemma"] = lemma
                    result["forms_count"] = len(forms_to_search)
                else:
                    # დავამატოთ სხვა ფორმის სტატისტიკა
                    result["total"] += w["total"]
                    result["old"] += w.get("old", 0)
                    result["new"] += w.get("new", 0)
                    result["books"] = max(result["books"], w.get("books", 0))

    if result:
        return jsonify(result)

    # თუ არ მოიძებნა
    return jsonify({
        "word": word_lower,
        "lemma": lemma,
        "total": 0,
        "old": 0,
        "new": 0,
        "books": 0,
        "forms_count": len(forms_to_search),
    })


@app.route("/api/word/distribution/<word>")
def api_word_distribution(word):
    """სიტყვის გავრცელება წიგნების მიხედვით.

    იყენებს lexicon-ის scopes.books სტრუქტურას.
    აბრუნებს წიგნების სიას სიტყვის სიხშირით, დალაგებულს კლებადობით.
    თუ სიტყვა არის მორფოლოგიური ჯგუფის ნაწილი, ყველა ფორმა მოიძებნება.
    """
    if LEXICON is None:
        return jsonify({"error": "ლექსიკონი არ არის ხელმისაწვდომი"}), 503

    word_lower = word.lower()

    # მორფოლოგიური ფორმების მიღება
    forms_to_search = {word_lower}
    if word_lower in WORD_TO_GROUP:
        lemma = WORD_TO_GROUP[word_lower]
        forms_to_search = GROUP_FORMS.get(lemma, {word_lower})

    books_scope = LEXICON["scopes"]["books"]
    distribution = []

    for book_slug, book_data in books_scope.items():
        count = 0
        for letter, ld in book_data["letters"].items():
            for w in ld["words"]:
                if w["word"] in forms_to_search:
                    count += w["total"]
        if count > 0:
            book_name = SLUG_TO_BOOK_NAME.get(book_slug, book_slug)
            distribution.append({
                "slug": book_slug,
                "name": book_name,
                "count": count,
            })

    # დალაგება კლებადობით
    distribution.sort(key=lambda x: x["count"], reverse=True)

    return jsonify({
        "word": word_lower,
        "forms_searched": sorted(forms_to_search),
        "total_books": len(distribution),
        "total_occurrences": sum(d["count"] for d in distribution),
        "distribution": distribution,
    })


@app.route("/api/word/topics/<word>")
def api_word_topics(word):
    """სიტყვის კავშირი თემებთან (სიტყვა-თემა ინტეგრაცია).

    ეძებს სიტყვის ყველა ფორმას, პოულობს მუხლებს სადაც გვხვდება,
    და თითო მუხლისთვის პოულობს თემებს (by_verse ინდექსიდან).
    აბრუნებს თემების სიას დალაგებულს lift-ის მიხედვით
    (statistical overrepresentation - რამდენად მეტჯერ გვხვდება თემა
    ამ სიტყვის მუხლებში, ვიდრე შემთხვევით უნდა იყოს).
    """
    if not TOPICAL_INDEX:
        return jsonify({"error": "თემატური ინდექსი არ არის ხელმისაწვდომი"}), 503

    word_lower = word.lower()

    # მორფოლოგიური ფორმების მიღება
    forms_to_search = {word_lower}
    if word_lower in WORD_TO_GROUP:
        lemma = WORD_TO_GROUP[word_lower]
        forms_to_search = GROUP_FORMS.get(lemma, {word_lower})

    # ვიპოვოთ ყველა მუხლი სადაც რომელიმე ფორმა გვხვდება
    verse_keys = set()
    for form in forms_to_search:
        verse_keys.update(WORD_TO_VERSES.get(form, []))

    if not verse_keys:
        return jsonify({
            "word": word_lower,
            "lemma": word_lower if word_lower not in WORD_TO_GROUP else WORD_TO_GROUP[word_lower],
            "forms_searched": sorted(forms_to_search),
            "total_verses": 0,
            "total_topics": 0,
            "topics": [],
        })

    # თითო მუხლისთვის ვიპოვოთ თემები by_verse-დან
    by_verse = TOPICAL_INDEX.get("by_verse", {})
    by_slug = TOPICAL_INDEX.get("by_slug", {})
    topics_list_data = TOPICAL_INDEX.get("topics", [])

    # თითო თემის სრული მუხლების რაოდენობა (სულ ბიბლიაში)
    topic_total_verses = {}
    for vk, slugs in by_verse.items():
        for s in slugs:
            topic_total_verses[s] = topic_total_verses.get(s, 0) + 1

    total_verses_with_topics = len(by_verse)  # სულ მუხლები თემებით

    # ვიპოვოთ თემები ამ სიტყვის მუხლებში
    topic_verse_counts = {}  # slug -> count (ამ სიტყვის მუხლებში)
    topic_verse_keys = {}    # slug -> [verse_keys] (პირველი 5 მაგალითი)

    for vk in verse_keys:
        slugs = by_verse.get(vk, [])
        for slug in slugs:
            if slug not in topic_verse_counts:
                topic_verse_counts[slug] = 0
                topic_verse_keys[slug] = []
            topic_verse_counts[slug] += 1
            if len(topic_verse_keys[slug]) < 5:
                topic_verse_keys[slug].append(vk)

    # სიტყვის მუხლები რომლებსაც თემები აქვთ
    word_verses_with_topics = sum(1 for vk in verse_keys if vk in by_verse)

    # შევადგინოთ თემების სია lift-ით
    topics_list = []
    for slug, count in topic_verse_counts.items():
        idx = by_slug.get(slug)
        name_en = slug
        if idx is not None and idx < len(topics_list_data):
            name_en = topics_list_data[idx].get("name_en", slug)
        name_ka = TOPICAL_NAMES_KA.get(slug, name_en)

        # lift = actual / expected
        # expected = word_verses_with_topics * (topic_total / total_verses_with_topics)
        topic_total = topic_total_verses.get(slug, 0)
        expected = (word_verses_with_topics * topic_total / total_verses_with_topics) if total_verses_with_topics > 0 else 0
        lift = (count / expected) if expected > 0 else 0

        topics_list.append({
            "slug": slug,
            "name_en": name_en,
            "name_ka": name_ka,
            "verse_count": count,
            "topic_total": topic_total,
            "lift": round(lift, 2),
            "sample_verses": topic_verse_keys[slug],
        })

    # დალაგება lift-ის მიხედვით (კლებადობით) - რამდენად დამახასიათებელია თემა ამ სიტყვისთვის
    # ფილტრი: მინიმუმ 2 მუხლი უნდა ემთხვეოდეს (1 მუხლი სტატისტიკურად არასანდოა)
    meaningful_topics = [t for t in topics_list if t["verse_count"] >= 2]
    meaningful_topics.sort(key=lambda x: (-x["lift"], -x["verse_count"]))

    # ხშირი სიტყვის შემოწმება - თუ სიტყვა ბევრ მუხლშია, თემები ნაკლებად მნიშვნელოვანია
    word_coverage = word_verses_with_topics / total_verses_with_topics if total_verses_with_topics > 0 else 0
    is_common_word = word_coverage > 0.3  # 30%+ მუხლებშია

    # შეზღუდოთ ტოპ-20 თემა
    top_topics = meaningful_topics[:20]

    return jsonify({
        "word": word_lower,
        "lemma": word_lower if word_lower not in WORD_TO_GROUP else WORD_TO_GROUP[word_lower],
        "forms_searched": sorted(forms_to_search),
        "total_verses": len(verse_keys),
        "total_topics": len(meaningful_topics),
        "topics_shown": len(top_topics),
        "topics": top_topics,
        "is_common_word": is_common_word,
        "word_coverage": round(word_coverage, 3),
    })


@app.route("/api/word/verses/<word>")
def api_word_verses(word):
    """სიტყვის გამოყენების ადგილები - მუხლები კონტექსტთან ერთად.

    აბრუნებს მუხლების სიას სადაც სიტყვა (ან მისი ფორმები) გვხვდება.
    ჩვენების ლიმიტი: პირველი 50 მუხლი (pagination შესაძლებელია offset-ით).
    """
    word_lower = word.lower()

    # მორფოლოგიური ფორმების მიღება
    forms_to_search = {word_lower}
    if word_lower in WORD_TO_GROUP:
        lemma = WORD_TO_GROUP[word_lower]
        forms_to_search = GROUP_FORMS.get(lemma, {word_lower})

    # ვიპოვოთ ყველა მუხლი სადაც რომელიმე ფორმა გვხვდება
    verse_keys = set()
    for form in forms_to_search:
        verse_keys.update(WORD_TO_VERSES.get(form, []))

    if not verse_keys:
        return jsonify({
            "word": word_lower,
            "lemma": word_lower if word_lower not in WORD_TO_GROUP else WORD_TO_GROUP[word_lower],
            "forms_searched": sorted(forms_to_search),
            "total_verses": 0,
            "verses": [],
        })

    # დალაგება: ჯერ წიგნის, შემდეგ თავის, შემდეგ მუხლის მიხედვით
    sorted_keys = sorted(verse_keys, key=lambda k: (
        VERSE_BY_KEY[k]["book_slug"] if k in VERSE_BY_KEY else "",
        VERSE_BY_KEY[k]["chapter"] if k in VERSE_BY_KEY else 0,
        VERSE_BY_KEY[k]["verse"] if k in VERSE_BY_KEY else 0,
    ))

    # pagination
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 50))
    limit = min(limit, 100)
    page_keys = sorted_keys[offset:offset + limit]

    verses = []
    for vk in page_keys:
        v = VERSE_BY_KEY.get(vk)
        if not v:
            continue
        # მოვნიშნოთ სიტყვა ტექსტში
        new_text = v.get("new", "")
        old_text = v.get("old", "")
        for form in forms_to_search:
            # case-insensitive მონიშვნა
            import re as _re
            pattern = _re.compile(r'(?<![\u10d0-\u10ff])(' + _re.escape(form) + r')(?![\u10d0-\u10ff])', _re.IGNORECASE)
            new_text = pattern.sub(r'<mark>\1</mark>', new_text)
            if old_text:
                old_text = pattern.sub(r'<mark>\1</mark>', old_text)
        verses.append({
            "key": vk,
            "book": v.get("book", ""),
            "book_slug": v.get("book_slug", ""),
            "chapter": v.get("chapter", 0),
            "verse": v.get("verse", 0),
            "testament": v.get("testament", ""),
            "new": new_text,
            "old": old_text,
        })

    return jsonify({
        "word": word_lower,
        "lemma": word_lower if word_lower not in WORD_TO_GROUP else WORD_TO_GROUP[word_lower],
        "forms_searched": sorted(forms_to_search),
        "total_verses": len(verse_keys),
        "offset": offset,
        "limit": limit,
        "verses": verses,
    })


@app.route("/api/verse/words/<book_slug>/<int:chapter>/<int:verse>")
def api_verse_words(book_slug, chapter, verse):
    """მუხლის სიტყვები სტატისტიკით.

    აბრუნებს მუხლში არსებულ სიტყვებს მათი გამოყენების სიხშირით მთელ ბიბლიაში.
    დალაგებულია სიხშირის კლებადობით (იშვიათი სიტყვები პირველად - ისინი არიან სასწავლად საინტერესო).
    """
    vk = f"{book_slug}:{chapter}:{verse}"
    v = VERSE_BY_KEY.get(vk)
    if not v:
        return jsonify({"error": "მუხლი ვერ მოიძებნა"}), 404

    word_re = re.compile(r"[ა-ჰჱჲჳჴჵa-zA-Z]+")

    # ვიპოვოთ სიტყვები ორივე თარგმანიდან
    words_with_stats = {}
    for field in ("new", "old"):
        text = v.get(field, "")
        if not text:
            continue
        tokens = word_re.findall(text.lower())
        for tok in tokens:
            if tok not in words_with_stats:
                # ვიპოვოთ სტატისტიკა
                total = 0
                forms_to_search = {tok}
                if tok in WORD_TO_GROUP:
                    lemma = WORD_TO_GROUP[tok]
                    forms_to_search = GROUP_FORMS.get(lemma, {tok})
                for form in forms_to_search:
                    total += len(WORD_TO_VERSES.get(form, []))
                words_with_stats[tok] = {
                    "word": tok,
                    "total": total,
                    "forms_count": len(forms_to_search),
                    "lemma": lemma if tok in WORD_TO_GROUP else tok,
                }

    # დალაგება: ჯერ იშვიათი სიტყვები (სასწავლად საინტერესო), შემდეგ ხშირი
    words_list = sorted(words_with_stats.values(), key=lambda x: x["total"])

    return jsonify({
        "book": v.get("book", ""),
        "book_slug": book_slug,
        "chapter": chapter,
        "verse": verse,
        "new": v.get("new", ""),
        "old": v.get("old", ""),
        "words": words_list,
        "total_words": len(words_list),
    })


@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 გვერდი - SEO-სთვის საჭირო."""
    html = """<!DOCTYPE html>
<html lang="ka">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<title>404 - გვერდი ვერ მოიძებნა · წმიდა წერილი</title>
<meta name="description" content="გვერდი ვერ მოიძებნა. დაბრუნდით ქართული ბიბლიის მთავარ გვერდზე.">
<link rel="canonical" href="https://web.net.ge/">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,serif;background:#f5efe1;color:#2c3e50;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:20px}
.container{max-width:500px}
h1{font-size:72px;color:#4a6ca1;margin-bottom:10px}
h2{font-size:24px;margin-bottom:20px;color:#2c3e50}
p{font-size:16px;color:#666;margin-bottom:30px;line-height:1.6}
a{display:inline-block;padding:14px 32px;background:#4a6ca1;color:#fff;text-decoration:none;border-radius:8px;font-size:16px;transition:background .2s}
a:hover{background:#3a5a91}
</style>
</head>
<body>
<div class="container">
<h1>404</h1>
<h2>გვერდი ვერ მოიძებნა</h2>
<p>მოთხოვნილი გვერდი არ არსებობს. შესაძლოა ბმული არასწორია ან გვერდი გადატანილია.</p>
<a href="https://web.net.ge/">← მთავარ გვერდზე დაბრუნება</a>
</div>
</body>
</html>"""
    resp = Response(html, status=404, content_type="text/html; charset=utf-8")
    resp.headers["Cache-Control"] = "no-cache, no-transform, must-revalidate"
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
