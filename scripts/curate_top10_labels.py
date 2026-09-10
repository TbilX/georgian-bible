#!/usr/bin/env python3
"""
curate_top10_labels.py
======================
ტოპ 10 თემის label-ების ხელით კურაცია (ეტაპი C).

ეს ფაილი შეიცავს ცხადად არასწორი თარგმანების გასწორებებს
ტოპ 10 თემისთვის (verse_count-ის მიხედვით).

გამოყენება:
    python3 curate_top10_labels.py              # მშრალი გაშვება
    python3 curate_top10_labels.py --apply      # შენახვა
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"
TOPICAL_FILE = DATA_DIR / "topical_index.json"

# ხელით კურაცირებული თარგმანები
# key = ინგლისური label (ზუსტი match)
# value = ქართული თარგმანი
CURATED_FIXES = {
    # === church ===
    # მეტობითი ბრუნვის გასწორება
    "HOUSE OF GOD Ge 28:17,22; Jos 9:23; Jud 18:31; 20:18,26; 21:2; 1Ch 9:11; 24:5; 2": "ღმერთის სახლი დაბ 28:17,22; იენ 9:23; იუდ 18:31; 20:18,26; 21:2; I ნეშ 9:11; 24:5; II",
    "HOUSE OF THE LORD Ex 23:19; 34:26; De 23:18; Jos 6:24; Jud 19:18; 1Sa 1:7,24; 2S": "უფლის სახლი გამ 23:19; 34:26; მრჟ 23:18; იენ 6:24; იუდ 19:18; I მეფ 1:7,24; II მ",
    "HOUSE OF PRAYER Isa 56:7; Mt 21:13": "ლოცვის სახლი ესა 56:7; მათე 21:13",
    ".HOUSE OF GOD 1Ti 3:15; Heb 10:21": "ღმერთის სახლი I ტიმ 3:15; ებრ 10:21",
    ".HOUSE OF CHRIST Heb 3:6": "ქრისტეს სახლი ებრ 3:6",
    "MY FATHER\u2019S HOUSE Joh 2:16; 14:2": "მამაჩემის სახლი იოა 2:16; 14:2",
    ".MOUNTAIN OF THE LORD\u2019S HOUSE Isa 2:2": "უფლის სახლის მთა ესა 2:2",

    # SANCTUARY -> საწმიდარი (არა სამღვდელო)
    "SANCTUARY Ex 25:8; Le 19:30; 21:12; Nu 3:28; 4:12; 7:9; 8:19; 10:21; 18:1,5; 19:": "საწმიდარი გამ 25:8; ლევ 19:30; 21:12; რიც 3:28; 4:12; 7:9; 8:19; 10:21; 18:1,5; 19:",
    ".SANCTUARY OF GOD Ps 114:2": "ღმერთის საწმიდარი ფსა 114:2",

    # Called COURTS -> ეწოდება ეზოები (არა წოდებული)
    "Called COURTS Ps 65:4; 84:2,10; 92:13; 96:8; 100:4; 116:19; Isa 1:12; 62:9; Zec ": "ეწოდება ეზოები ფსა 65:4; 84:2,10; 92:13; 96:8; 100:4; 116:19; ესა 1:12; 62:9; ზ",

    # === jesus-the-christ ===
    # appears -> გამოეცხადება (არა ჩანს)
    ".The angel Gabriel appears to Mary (at Nazareth) Lu 1:26-38": "ანგელოზი გაბრიელი გამოეცხადება მარიამს (ნაზარეთში) ლუკა 1:26-38",
    ".An angel appears to Joseph concerning Mary (at Nazareth) Mt 1:18-25": "ანგელოზი გამოეცხადება იოსებს მარიამის შესახებ (ნაზარეთში) მათე 1:18-25",

    # visits -> ესტუმრა (არა ეწვევა)
    ".Mary visits Elisabeth (at Hebron?) Lu 1:39-56": "მარიამი ესტუმრა ელისაბედს (ხებრონში?) ლუკა 1:39-56",
    ".Magi (the wise men from the east) visit (at Bethlehem) Mt 2:1-12": "მოგვები (ბრძენები აღმოსავლეთიდან) ესტუმრნენ (ბეთლემში) მათე 2:1-12",
    ".Visits Sychar and teaches the Samaritan woman Joh 4:4-42": "ესტუმრა სიქარს და ასწავლის სამარიელ დედაკაცს იოა 4:4-42",
    ".Visits Zacchaeus Lu 19:1-10": "ესტუმრა ზაქეს ლუკა 19:1-10",

    # Is presented -> წარადგინეს (არა არის წარდგენილი)
    ".Is presented in the temple (in Jerusalem) Lu 2:21-38": "წარადგინეს ტაძარში (იერუსალიმში) ლუკა 2:21-38",

    # sanctuary -> საწმიდარი
    ".Minister of the sanctuary Heb 8:2": "საწმიდრის მსახური ებრ 8:2",
    ".Sanctuary Isa 8:14": "საწმიდარი ესა 8:14",

    # === afflictions-and-adversities ===
    # Does not willingly send -> არ გაგზავნის სურვილით
    ".Does not willingly send La 3:33": "არ გაგზავნის სურვილით გოდ 3:33",

    # Consequent upon the fall -> დაცემის შედეგი
    ".Consequent upon the fall Ge 3:16-19": "დაცემის შედეგი დაბ 3:16-19",

    # Against his house were foretold -> მის სახლზე იწინასწარმეტყველეს
    ".Against his house were foretold 1Sa 3:15-18": "მის სახლზე იწინასწარმეტყველეს I მეფ 3:15-18",

    # === minister-christian ===
    ".OF THE SANCTUARY Eze 45:4": "საწმიდრისა ეზე 45:4",

    # დამატებითი ფიქსები
    ".THE FATHER\u2019S HOUSE Joh 14:2": "მამის სახლი იოა 14:2",
    ".MOUNTAIN OF THE LORD\u2019 S HOUSE Isa 2:2": "უფლის სახლის მთა ესა 2:2",
    ".FATHER\u2019 S HOUSE Joh 2:16": "მამის სახლი იოა 2:16",
}


def main():
    apply = '--apply' in sys.argv

    print("=== ტოპ 10 თემის კურაცია (ეტაპი C) ===")
    print()

    with open(LABELS_FILE, 'r', encoding='utf-8') as f:
        labels = json.load(f)

    with open(TOPICAL_FILE, 'r', encoding='utf-8') as f:
        ti = json.load(f)

    # ტოპ 10 თემა
    topics = sorted(ti['topics'], key=lambda t: t.get('verse_count', 0), reverse=True)[:10]
    top_slugs = {t['slug'] for t in topics}

    # შევაგროვოთ ამ თემების label-ები
    top_labels = set()
    for t in ti['topics']:
        if t['slug'] in top_slugs:
            for e in t.get('entries', []):
                top_labels.add(e.get('label', ''))

    print(f"ტოპ 10 თემაში სულ label: {len(top_labels)}")
    print(f"კურაციის ფიქსები: {len(CURATED_FIXES)}")
    print()

    # გამოვიყენოთ ფიქსები
    fixed = 0
    not_found = 0
    samples = []

    for en_label, new_ka in CURATED_FIXES.items():
        # ვპოვოთ ზუსტი match ან ნაწილობრივი
        found = False
        for key in list(labels.keys()):
            if key == en_label or key.startswith(en_label[:50]):
                old_ka = labels[key]
                if old_ka != new_ka:
                    labels[key] = new_ka
                    fixed += 1
                    if len(samples) < 30:
                        samples.append((key[:60], old_ka[:60], new_ka[:60]))
                found = True
                break

        if not found:
            # ვეძებოთ ნაწილობრივი match
            for key in labels:
                if en_label[:40] in key or key[:40] in en_label:
                    old_ka = labels[key]
                    if old_ka != new_ka:
                        labels[key] = new_ka
                        fixed += 1
                        if len(samples) < 30:
                            samples.append((key[:60], old_ka[:60], new_ka[:60]))
                    found = True
                    break

        if not found:
            not_found += 1
            print(f"  [ვერ მოიძებნა] {en_label[:60]}")

    print()
    print(f"გასწორდა: {fixed}")
    print(f"ვერ მოიძებნა: {not_found}")
    print()

    # ნიმუშები
    if samples:
        print("=== ნიმუშები (before/after) ===")
        for en, old, new in samples[:20]:
            print(f"  EN: {en}")
            print(f"  OLD: {old}")
            print(f"  NEW: {new}")
            print()

    if apply:
        with open(LABELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"შენახულია: {LABELS_FILE}")
    else:
        print("--apply გარეშე: ცვლილებები არ შენახულა")


if __name__ == '__main__':
    main()
