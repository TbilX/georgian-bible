#!/usr/bin/env python3
"""
fix_typos2.py — მეორე ჯგუფის დადასტურებული OCR/პუნქტუაციის შეცდომების გასწორება.

ყველა შეცდომა ვერიფიცირებულია orthodoxy.ge-ს წყაროსთან შედარებით:
- ჯგუფი D: სიტყვები რომლებიც ბოლოვდება "ღ"-ით (ძველი ქართული) — დ→ღ OCR შეცდომები
- ჯგუფი E: პუნქტუაციის შეცდომები (ძველი ქართული)
- ჯგუფი F: ციფრები ტექსტში (ძველი ქართული)

გამორიცხულია (ნამდვილი სიტყვები/ციტატის პატერნები):
- იერემია 39:3 — რაბამაღ (ბაბილონური ტიტული "Rabmag")
- იერემია 39:13 — ბამაღ (ბაბილონური ტიტული)
- II ტიმოთე 3:2 — ლაღ (ნამდვილი სიტყვა)
- რომაელთა 1:30 — ლაღ (ნამდვილი სიტყვა)
- I მეფეთა 20:29 — მივიდეო.აწ (ციტატის პატერნი)
- IV მეფეთა 9:19 — მშჳდობისა?უკმოდეგ (ციტატის პატერნი)
- დაბადება 5:29, 6:3, 6:7 — მეტყუელმან:ამან (ნამდვილი ციტატა)
- IV მეფეთა 1:11, 3:10 — ციტატის პატერნი
- დანარჩენი ციტატის პატერნები
"""

import json
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data" / "verse_index.json"


def load_verses():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save_verses(verses):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(verses, f, ensure_ascii=False, indent=2)


# ჯგუფი D: OCR შეცდომები — ღ → დ (ბოლო ასო)
# თითოეული დადასტურებულია ონლაინ ვერიფიკაციით
D_FIXES = [
    # (book_contains, chapter, verse, old_str, new_str, description)
    ("მეორე რჯული", 22, 3, "არამეღ", "არამედ", "OCR: დ→ღ"),
    ("IV მეფეთა", 2, 24, "მაღ- ნარით", "მაღალნარით", "ჰაერის აღდგენა + დამთავრება"),
    ("ეზეკიელი", 16, 28, "განსძეღ", "განსძედ", "OCR: დ→ღ"),
    ("ეზეკიელი", 29, 15, "ყოფაღ", "ყოფად", "OCR: დ→ღ"),
    ("ფსალმუნნი", 118, 75, "ჭეშმარიტაღ", "ჭეშმარიტად", "OCR: დ→ღ"),
    ("გამოსვლა", 10, 21, "უღაღ", "უღად", "OCR: დ→ღ"),
    ("იერემია", 31, 21, "შენდაღ", "შენდად", "OCR: დ→ღ"),
    ("ლევიანნი", 13, 8, "კუალაღ", "კუალად", "OCR: დ→ღ"),
    ("ტობითი", 7, 1, "სახიღ", "სახიდ", "OCR: დ→ღ"),
]

# ჯგუფი E: პუნქტუაციის შეცდომები
E_FIXES = [
    ("ესაია", 37, 4, "მ.აცხოვრისა", "მცხოვრისა", "ზედმეტი წერტილი"),
]

# ჯგუფი F: ციფრები ტექსტში
F_FIXES = [
    # I ეზრა 10:7 — "ნფ8." არ არსებობს როგორც სიტყვა; ვშლით "8"-ს
    ("I ეზრა", 10, 7, "ნფ8.", "ნფ.", "ციფრი 8 ზედმეტია"),
    # იობი 40:5 — "თავი40" მუხლის ნომერი ტექსტში შერეული
    ("იობი", 40, 5, "თავი40", "თავი", "მუხლის ნომერი ტექსტში"),
]


def apply_fixes(verses, fixes, group_name):
    """Apply a list of fixes to verses. Returns count of applied fixes."""
    applied = 0
    not_found = []

    for book_key, chapter, verse, old_str, new_str, desc in fixes:
        found = False
        for v in verses:
            if (
                book_key in v["book"]
                and int(v["chapter"]) == chapter
                and int(v["verse"]) == verse
            ):
                old_text = v.get("old", "") or ""
                if old_str in old_text:
                    v["old"] = old_text.replace(old_str, new_str, 1)
                    applied += 1
                    found = True
                    print(f"  ✅ {group_name}: {v['book']} {chapter}:{verse} — {desc}")
                    print(f"     '{old_str}' → '{new_str}'")
                    break
                else:
                    # სიტყვა ვერ მოიძებნა — შესაძლოა უკვე გასწორებულია
                    found = True
                    print(f"  ⚠️  {group_name}: {v['book']} {chapter}:{verse} — ვერ მოიძებნა '{old_str}' (შესაძლოა უკვე გასწორებულია)")
                    break
        if not found:
            not_found.append(f"{book_key} {chapter}:{verse}")

    if not_found:
        print(f"\n  ⚠️  ვერ მოიძებნა მუხლები: {', '.join(not_found)}")

    return applied


def main():
    print("=" * 70)
    print("fix_typos2.py — მეორე ჯგუფის შეცდომების გასწორება")
    print("=" * 70)

    verses = load_verses()
    total_applied = 0

    print(f"\n📖 ჯგუფი D: OCR შეცდომები (ღ → დ) — {len(D_FIXES)} შემთხვევა")
    print("-" * 70)
    total_applied += apply_fixes(verses, D_FIXES, "D")

    print(f"\n📖 ჯგუფი E: პუნქტუაციის შეცდომები — {len(E_FIXES)} შემთხვევა")
    print("-" * 70)
    total_applied += apply_fixes(verses, E_FIXES, "E")

    print(f"\n📖 ჯგუფი F: ციფრები ტექსტში — {len(F_FIXES)} შემთხვევა")
    print("-" * 70)
    total_applied += apply_fixes(verses, F_FIXES, "F")

    print("\n" + "=" * 70)
    print(f"ჯამში გასწორდა: {total_applied} შემთხვევა")
    print("=" * 70)

    if total_applied > 0:
        save_verses(verses)
        print(f"\n✅ შენახულია: {DATA}")
    else:
        print("\n⚠️  არაფერი შეცვლილა — ფაილი არ შენახულა")


if __name__ == "__main__":
    main()
