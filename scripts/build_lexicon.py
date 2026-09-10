#!/usr/bin/env python3
"""
ბიბლიის ლექსიკონის გენერატორი
================================
ითვლის ბიბლიაში გამოყენებულ ყველა სიტყვას ორივე თარგმანში (ძველი + ახალი),
აჯგუფებს ანბანის მიხედვით და ალაგებს სიხშირით (კლებადი).

გამომავალი: data/lexicon.json — ვებ აპლიკაციისთვის.

სტრუქტურა:
  - metadata: საერთო სტატისტიკა
  - letters: ანბანის ასოების მიხედვით დაჯგუფებული სიტყვები
  - book_stats: თითო წიგნის სტატისტიკა
"""
import json
import re
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
VERSES_FILE = os.path.join(DATA_DIR, "verses.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "lexicon.json")

# ========================================
# ქართული ანბანი
# ========================================
# 33 სტანდარტული ასო + 5 არქაული (რომლებიც ბიბლიაში გვხვდება)
MKHEDRULI = list("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ")
ARCHAIC = list("ჱჲჳჴჵ")  # ჶ, ჷ, ჸ, ჹ, ამები ბიბლიაში არ გვხვდება
ALL_LETTERS = MKHEDRULI + ARCHAIC

# ასომთავრული → მხედრული შესაბამისობა (სტანდარტული ასოები)
ASOMTAVRULI_TO_MKHEDRULI = {
    'Ⴀ': 'ა', 'Ⴁ': 'ბ', 'Ⴂ': 'გ', 'Ⴃ': 'დ', 'Ⴄ': 'ე',
    'Ⴅ': 'ვ', 'Ⴆ': 'ზ', 'Ⴇ': 'თ', 'Ⴈ': 'ი', 'Ⴉ': 'კ',
    'Ⴊ': 'ლ', 'Ⴋ': 'მ', 'Ⴌ': 'ნ', 'Ⴍ': 'ო', 'Ⴎ': 'პ',
    'Ⴏ': 'ჟ', 'Ⴐ': 'რ', 'Ⴑ': 'ს', 'Ⴒ': 'ტ', 'Ⴓ': 'უ',
    'Ⴔ': 'ფ', 'Ⴕ': 'ქ', 'Ⴖ': 'ღ', 'Ⴗ': 'ყ', 'Ⴘ': 'შ',
    'Ⴙ': 'ჩ', 'Ⴚ': 'ც', 'Ⴛ': 'ძ', 'Ⴜ': 'წ', 'Ⴝ': 'ჭ',
    'Ⴞ': 'ხ', 'Ⴟ': 'ჯ', 'Ⴠ': 'ჰ',
    # არქაული ასოები (ასომთავრულში იშვიათად გვხვდება, მაგრამ სტანდარტიზებულია)
    'Ⴡ': 'ჱ', 'Ⴢ': 'ჲ', 'Ⴣ': 'ჳ', 'Ⴤ': 'ჴ', 'Ⴥ': 'ჵ',
}

# ნუსხური → მხედრული შესაბამისობა
NUSKHURI_TO_MKHEDRULI = {
    'ⴀ': 'ა', 'ⴁ': 'ბ', 'ⴂ': 'გ', 'ⴃ': 'დ', 'ⴄ': 'ე',
    'ⴅ': 'ვ', 'ⴆ': 'ზ', 'ⴇ': 'თ', 'ⴈ': 'ი', 'ⴉ': 'კ',
    'ⴊ': 'ლ', 'ⴋ': 'მ', 'ⴌ': 'ნ', 'ⴍ': 'ო', 'ⴎ': 'პ',
    'ⴏ': 'ჟ', 'ⴐ': 'რ', 'ⴑ': 'ს', 'ⴒ': 'ტ', 'ⴓ': 'უ',
    'ⴔ': 'ფ', 'ⴕ': 'ქ', 'ⴖ': 'ღ', 'ⴗ': 'ყ', 'ⴘ': 'შ',
    'ⴙ': 'ჩ', 'ⴚ': 'ც', 'ⴛ': 'ძ', 'ⴜ': 'წ', 'ⴝ': 'ჭ',
    'ⴞ': 'ხ', 'ⴟ': 'ჯ', 'ⴠ': 'ჰ',
    # არქაული
    'ⴡ': 'ჱ', 'ⴢ': 'ჲ', 'ⴣ': 'ჳ', 'ⴤ': 'ჴ', 'ⴥ': 'ჵ',
}

# უკუ შესაბამისობა (ვებისთვის — მხედრულის გამოსახულება სხვა სკრიპტებში)
MKHEDRULI_TO_ASOMTAVRULI = {v: k for k, v in ASOMTAVRULI_TO_MKHEDRULI.items()}
MKHEDRULI_TO_NUSKHURI = {v: k for k, v in NUSKHURI_TO_MKHEDRULI.items()}


def normalize_to_mkhedruli(text: str) -> str:
    """ასომთავრულს/ნუსხურს გარდაქმნის მხედრულად (თუ შემთხვევით შემოსულა)."""
    result = []
    for char in text:
        if char in ASOMTAVRULI_TO_MKHEDRULI:
            result.append(ASOMTAVRULI_TO_MKHEDRULI[char])
        elif char in NUSKHURI_TO_MKHEDRULI:
            result.append(NUSKHURI_TO_MKHEDRULI[char])
        else:
            result.append(char)
    return ''.join(result)


# ქართული სიტყვების რეგულარული გამოსახულება
# მხედრული: U+10D0-U+10F0 (33 სტანდარტული + არქაული ჱ-ჵ U+10F1-U+10F5)
GEORGIAN_WORD_RE = re.compile(r'[ა-ჰჱჲჳჴჵ]+')


def extract_georgian_words(text: str) -> list:
    """ტექსტიდან ამოიღებს მხოლოდ ქართულ სიტყვებს."""
    if not text:
        return []
    normalized = normalize_to_mkhedruli(text)
    return GEORGIAN_WORD_RE.findall(normalized)


def letter_sort_key(letter: str) -> int:
    """ასოს სორტირების გასაღები ანბანის მიხედვით."""
    if letter in ALL_LETTERS:
        return ALL_LETTERS.index(letter)
    return 999


def build_lexicon(verses: list) -> dict:
    """
    აგებს სრულ ლექსიკონს.

    დააბრუნებს:
      {
        "metadata": {...},
        "letters": { "ა": {...}, ... },       # სრული ბიბლია
        "scopes": {                             # ფილტრისთვის
          "old": { "letters": {...}, "total_unique": N, "total_occurrences": N },
          "new": {...},
          "canonical": {...},
          "noncanonical": {...},
          "books": { "dabadeba": {...}, ... }
        },
        "book_stats": [...]
      }
    """
    # word -> {"total": N, "old": N, "new": N, "books": set(), "book_counts": Counter()}
    word_data = defaultdict(lambda: {
        "total": 0, "old": 0, "new": 0,
        "books": set(), "book_counts": Counter()
    })

    # წიგნის სტატისტიკა
    book_stats = {}

    total_old_words = 0
    total_new_words = 0

    print(f"  დამუშავება {len(verses):,} მუხლი...")

    for i, v in enumerate(verses):
        slug = v["book_slug"]
        book_name = v["book"]
        testament = v["testament"]

        if slug not in book_stats:
            book_stats[slug] = {
                "slug": slug,
                "name": book_name,
                "testament": testament,
                "verses": 0,
                "unique_words": set(),
                "total_words": 0,
            }
        book_stats[slug]["verses"] += 1

        # ძველი თარგმანი
        old_text = v.get("old") or ""
        old_words = extract_georgian_words(old_text)
        for w in old_words:
            word_data[w]["total"] += 1
            word_data[w]["old"] += 1
            word_data[w]["books"].add(slug)
            word_data[w]["book_counts"][slug] += 1
            book_stats[slug]["unique_words"].add(w)
            book_stats[slug]["total_words"] += 1
        total_old_words += len(old_words)

        # ახალი თარგმანი
        new_text = v.get("new") or ""
        new_words = extract_georgian_words(new_text)
        for w in new_words:
            word_data[w]["total"] += 1
            word_data[w]["new"] += 1
            word_data[w]["books"].add(slug)
            word_data[w]["book_counts"][slug] += 1
            book_stats[slug]["unique_words"].add(w)
            book_stats[slug]["total_words"] += 1
        total_new_words += len(new_words)

        if (i + 1) % 5000 == 0:
            print(f"    {i+1:,}/{len(verses):,} მუხლი დამუშავებული...")

    print(f"  დამუშავებულია. უნიკალური სიტყვები: {len(word_data):,}")

    # ანბანის მიხედვით დაჯგუფება
    letters_index = defaultdict(list)
    for word, data in word_data.items():
        if not word:
            continue
        first_letter = word[0]
        letters_index[first_letter].append({
            "word": word,
            "total": data["total"],
            "old": data["old"],
            "new": data["new"],
            "books": len(data["books"]),
        })

    # თითოეულ ასოში სიხშირით დალაგება (total-ის მიხედვით, კლებადი)
    for letter in letters_index:
        letters_index[letter].sort(key=lambda x: x["total"], reverse=True)

    # გამოყენებული ასოები ანბანის მიხედვით
    used_letters = sorted(letters_index.keys(), key=letter_sort_key)

    # === სკოპების აგება (ფილტრისთვის) ===
    print(f"  სკოპების აგება (წიგნები, აღთქმები, კანონიკური)...")
    book_order = _get_book_order()

    def book_sort_key(slug):
        if slug in book_order:
            return book_order.index(slug)
        return 999

    noncanonical_set = _get_noncanonical_set()

    # წიგნების კლასიფიკაცია
    old_books = [s for s in book_stats if book_stats[s]["testament"] == "old"]
    new_books = [s for s in book_stats if book_stats[s]["testament"] == "new"]
    canonical_books = [s for s in book_stats if s not in noncanonical_set]
    noncanonical_books = [s for s in book_stats if s in noncanonical_set]

    # სკოპის აგება — მიღებული სიტყვების სიის გარდაქმნა letters სტრუქტურად
    def build_scope(word_counts: dict, scope_label: str) -> dict:
        """word_counts: {word: count} -> letters სტრუქტურა"""
        if not word_counts:
            return {"letters": {}, "total_unique": 0, "total_occurrences": 0}

        scope_letters = defaultdict(list)
        for word, count in word_counts.items():
            if not word:
                continue
            scope_letters[word[0]].append({
                "word": word,
                "total": count,
            })

        for letter in scope_letters:
            scope_letters[letter].sort(key=lambda x: x["total"], reverse=True)

        scope_used = sorted(scope_letters.keys(), key=letter_sort_key)
        letters_out = {}
        for letter in scope_used:
            words = scope_letters[letter]
            letters_out[letter] = {
                "letter": letter,
                "total_words": len(words),
                "total_occurrences": sum(w["total"] for w in words),
                "words": words,
            }

        total_unique = len(word_counts)
        total_occ = sum(word_counts.values())
        print(f"    {scope_label}: {total_unique:,} სიტყვა, {total_occ:,} გამოყენება")
        return {
            "letters": letters_out,
            "total_unique": total_unique,
            "total_occurrences": total_occ,
        }

    # 1. თითო წიგნის სკოპი
    scopes = {"books": {}}
    for slug in sorted(book_stats.keys(), key=book_sort_key):
        wc = {}
        for word, data in word_data.items():
            c = data["book_counts"].get(slug, 0)
            if c > 0:
                wc[word] = c
        scopes["books"][slug] = build_scope(wc, f"  წიგნი: {book_stats[slug]['name']}")

    # 2. ძველი აღთქმა
    old_wc = Counter()
    for slug in old_books:
        for word, data in word_data.items():
            c = data["book_counts"].get(slug, 0)
            if c > 0:
                old_wc[word] += c
    scopes["old"] = build_scope(dict(old_wc), "ძველი აღთქმა")

    # 3. ახალი აღთქმა
    new_wc = Counter()
    for slug in new_books:
        for word, data in word_data.items():
            c = data["book_counts"].get(slug, 0)
            if c > 0:
                new_wc[word] += c
    scopes["new"] = build_scope(dict(new_wc), "ახალი აღთქმა")

    # 4. კანონიკური
    canon_wc = Counter()
    for slug in canonical_books:
        for word, data in word_data.items():
            c = data["book_counts"].get(slug, 0)
            if c > 0:
                canon_wc[word] += c
    scopes["canonical"] = build_scope(dict(canon_wc), "კანონიკური")

    # 5. არაკანონიკური
    noncanon_wc = Counter()
    for slug in noncanonical_books:
        for word, data in word_data.items():
            c = data["book_counts"].get(slug, 0)
            if c > 0:
                noncanon_wc[word] += c
    scopes["noncanonical"] = build_scope(dict(noncanon_wc), "არაკანონიკური")

    # სრული სტრუქტურა
    total_unique = len(word_data)
    total_occurrences = total_old_words + total_new_words

    output = {
        "metadata": {
            "total_unique_words": total_unique,
            "total_word_occurrences": total_occurrences,
            "total_old_words": total_old_words,
            "total_new_words": total_new_words,
            "total_books": len(book_stats),
            "total_verses": len(verses),
            "letters_used": used_letters,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "alphabet": {
                "mkhedruli": " ".join(MKHEDRULI),
                "archaic": " ".join(ARCHAIC),
            },
            "scope_counts": {
                "old": scopes["old"]["total_unique"],
                "new": scopes["new"]["total_unique"],
                "canonical": scopes["canonical"]["total_unique"],
                "noncanonical": scopes["noncanonical"]["total_unique"],
            },
        },
        "letters": {},
        "scopes": scopes,
        "book_stats": [],
    }

    # letters სექცია
    for letter in used_letters:
        words = letters_index[letter]
        letter_occurrences = sum(w["total"] for w in words)
        output["letters"][letter] = {
            "letter": letter,
            "asomtavruli": MKHEDRULI_TO_ASOMTAVRULI.get(letter, letter),
            "nuskhuri": MKHEDRULI_TO_NUSKHURI.get(letter, letter),
            "total_words": len(words),
            "total_occurrences": letter_occurrences,
            "words": words,
        }

    # book_stats სექცია — წიგნების თანმიმდევრობით
    for slug in sorted(book_stats.keys(), key=book_sort_key):
        bs = book_stats[slug]
        output["book_stats"].append({
            "slug": bs["slug"],
            "name": bs["name"],
            "testament": bs["testament"],
            "canonical": slug not in noncanonical_set,
            "verses": bs["verses"],
            "unique_words": len(bs["unique_words"]),
            "total_words": bs["total_words"],
        })

    return output


def _get_book_order() -> list:
    """წიგნების კანონიკური თანმიმდევრობა server.py-დან."""
    # იმპორტის გარეშე — პირდაპირ აქ დავტოვოთ იგივე თანმიმდევრობა
    return [
        "dabadeba", "gamosvla", "levianni", "ritskhvni", "2rjuli",
        "iesonave", "msajulni", "ruti", "1mepeta", "2mepeta",
        "3mepeta", "4mepeta", "1neshtta", "2neshtta", "1ezra", "neemia",
        "2ezra", "tobiti", "ivditi", "esteri", "iobi", "fsalmunni",
        "igavni", "eklesiaste", "qeba", "solomoni", "ziraqi",
        "esaia", "ieremia", "godeba", "epistole", "baruqi",
        "ezekieli", "danieli", "osia", "ioveli", "amos", "abdia",
        "iona", "miqa", "naumi", "abakumi", "sofonia", "angia",
        "zaqaria", "malaqia", "1makabelta", "2makabelta",
        "3makabelta", "4makabelta", "3ezra",
        "mate", "markozi", "luka", "ioane", "saqme",
        "romaelta", "1korintelta", "2korintelta", "galatelta",
        "efeselta", "filipelta", "kolaselta", "1tesalonikelta",
        "2tesalonikelta", "1timote", "2timote", "tite", "filimoni",
        "ebraelta", "iakobi", "1petre", "2petre", "1ioane",
        "2ioane", "3ioane", "iuda", "apokalips",
    ]


def _get_noncanonical_set() -> set:
    """არაკანონიკური წიგნების სია server.py-დან."""
    return {
        "2ezra", "3ezra", "tobiti", "ivditi",
        "solomoni", "ziraqi", "epistole", "baruqi",
        "1makabelta", "2makabelta", "3makabelta", "4makabelta",
    }


def print_stats(lexicon: dict):
    """კონსოლში სტატისტიკის ჩვენება."""
    meta = lexicon["metadata"]
    print("\n" + "=" * 70)
    print("📊 ბიბლიის ლექსიკონის სტატისტიკა")
    print("=" * 70)
    print(f"\n  უნიკალური სიტყვები:        {meta['total_unique_words']:>10,}")
    print(f"  სულ სიტყვა (გამეორებით):  {meta['total_word_occurrences']:>10,}")
    print(f"    - ძველი თარგმანი:        {meta['total_old_words']:>10,}")
    print(f"    - ახალი თარგმანი:        {meta['total_new_words']:>10,}")
    print(f"  წიგნები:                  {meta['total_books']:>10}")
    print(f"  მუხლები:                  {meta['total_verses']:>10,}")
    print(f"  გამოყენებული ასოები:      {len(meta['letters_used'])}")

    print(f"\n{'ასო':<5} {'ასომთ.':<6} {'ნუსხ.':<5} {'სიტყვები':>10} {'გამოყენება':>12}  ტოპ-5 სიტყვა")
    print("-" * 90)

    for letter in meta["letters_used"]:
        ld = lexicon["letters"][letter]
        top5 = ", ".join(f"{w['word']}({w['total']})" for w in ld["words"][:5])
        print(f"  {letter:<3} {ld['asomtavruli']:<6} {ld['nuskhuri']:<5} "
              f"{ld['total_words']:>10,} {ld['total_occurrences']:>12,}  {top5}")

    # ტოპ-30 სიტყვა მთლიან ბიბლიაში
    all_words = []
    for ld in lexicon["letters"].values():
        all_words.extend(ld["words"])
    all_words.sort(key=lambda x: x["total"], reverse=True)

    print(f"\n🏆 ტოპ-30 ყველაზე ხშირი სიტყვა:")
    print("-" * 50)
    for i, w in enumerate(all_words[:30], 1):
        bar = "█" * min(w["total"] // 500, 30)
        print(f"  {i:>3}. {w['word']:<20} {w['total']:>7,}  {bar}")

    # წიგნების სტატისტიკა (ტოპ-10 სიტყვების რაოდენობით)
    print(f"\n📚 წიგნების სტატისტიკა (ტოპ-15 სიტყვების რაოდენობით):")
    print("-" * 70)
    print(f"  {'წიგნი':<30} {'მუხლი':>6} {'უნიკალური':>10} {'სულ სიტყვა':>12}")
    print("-" * 70)
    sorted_books = sorted(lexicon["book_stats"],
                          key=lambda x: x["total_words"], reverse=True)
    for bs in sorted_books[:15]:
        print(f"  {bs['name']:<30} {bs['verses']:>6} {bs['unique_words']:>10,} {bs['total_words']:>12,}")


def main():
    print("📖 ბიბლიის ლექსიკონის გენერატორი")
    print("=" * 50)

    # 1. მონაცემების ჩატვირთვა
    print(f"\n📂 მონაცემების ჩატვირთვა: {VERSES_FILE}")
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        verses = json.load(f)
    print(f"   ✅ ჩაიტვირთა {len(verses):,} მუხლი")

    # 2. ლექსიკონის აგება
    print(f"\n🔤 სიტყვების დათვლა და ინდექსირება...")
    lexicon = build_lexicon(verses)

    # 3. შენახვა
    print(f"\n💾 შენახვა: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(lexicon, f, ensure_ascii=False, indent=2)
    file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"   ✅ შენახულია: {OUTPUT_FILE} ({file_size:.1f} MB)")

    # 4. სტატისტიკა
    print_stats(lexicon)

    print(f"\n✨ მზადაა! ლექსიკონი შენახულია: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
