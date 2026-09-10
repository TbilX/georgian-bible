#!/usr/bin/env python3
"""
build_apocrypha_topics.py
=========================
აპოკრიფის წიგნების თემების შექმნა topical_index.json-ში.

ეტაპი A: აპოკრიფის თემების შექმნა (12 წიგნი)

სტრატეგია:
1. თითო აპოკრიფის წიგნისთვის შევქმნათ თემა წიგნის სახელით
2. დავამატოთ მთავარი პერსონაჟები და მოვლენები
3. განვაახლოთ by_book, by_slug, by_verse ინდექსები

გამოყენება:
    python3 build_apocrypha_topics.py              # მშრალი გაშვება
    python3 build_apocrypha_topics.py --apply      # შენახვა
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TOPICAL_FILE = DATA_DIR / "topical_index.json"
VERSES_FILE = DATA_DIR / "verses.json"
TOPIC_NAMES_FILE = DATA_DIR / "topic_names_ka.json"

# აპოკრიფის წიგნების მონაცემები
# slug: (ქართული სახელი, ინგლისური სახელი, თემები)
# თემები: (slug, ქართული სახელი, ინგლისური სახელი, ლეიბლი, თავები)
APOCRYPHA_BOOKS = [
    {
        'book_slug': '2ezra',
        'book_name_ka': 'II ეზრა',
        'book_name_en': '2 Ezra',
        'topics': [
            ('ezra-2', 'II ეზრა', '2 Ezra', 'წიგნის შინაარსი', [(1, 1, 9), (2, 1, 30)]),
        ],
    },
    {
        'book_slug': 'tobiti',
        'book_name_ka': 'ტობითი',
        'book_name_en': 'Tobit',
        'topics': [
            ('tobit', 'ტობითი', 'Tobit', 'წიგნის შინაარსი', [(1, 1, 22), (2, 1, 14), (3, 1, 17)]),
            ('tobias', 'ტობია', 'Tobias', 'ტობიას მოგზაურობა', [(4, 1, 21), (5, 1, 22), (6, 1, 17)]),
            ('raphael-angel', 'რაფაელ ანგელოზი', 'Raphael (Angel)', 'ანგელოზი რაფაელი ეხმარება ტობიას', [(5, 4, 22), (6, 1, 17), (7, 1, 16)]),
            ('tobit-righteous', 'ტობითი მართალი', 'Tobit (Righteous)', 'ტობითის მართლმოსავლება', [(1, 3, 8), (2, 1, 9)]),
        ],
    },
    {
        'book_slug': 'ivditi',
        'book_name_ka': 'ივდითი',
        'book_name_en': 'Judith',
        'topics': [
            ('judith', 'ივდითი', 'Judith', 'წიგნის შინაარსი', [(1, 1, 16), (2, 1, 28), (3, 1, 10)]),
            ('judith-heroine', 'ივდითი გმირი', 'Judith (Heroine)', 'ივდითი ხსნა ბეთულიას', [(8, 1, 36), (10, 1, 23), (11, 1, 23), (12, 1, 20), (13, 1, 20)]),
            ('holofernes', 'ოლოფერნესი', 'Holofernes', 'ოლოფერნესის მეთაურობა', [(2, 1, 28), (3, 1, 10), (4, 1, 15)]),
            ('bethulia', 'ბეთულია', 'Bethulia', 'ბეთულიას ალყა', [(7, 1, 32), (8, 1, 36)]),
        ],
    },
    {
        'book_slug': 'solomoni',
        'book_name_ka': 'სიბრძნე სოლომონისა',
        'book_name_en': 'Wisdom of Solomon',
        'topics': [
            ('wisdom-solomon', 'სიბრძნე სოლომონისა', 'Wisdom of Solomon', 'წიგნის შინაარსი', [(1, 1, 16), (2, 1, 24), (3, 1, 19)]),
            ('wisdom-divine', 'სიბრძნე ღვთიური', 'Divine Wisdom', 'სიბრძნის დაფასება', [(6, 1, 27), (7, 1, 30), (8, 1, 21)]),
            ('wisdom-immortality', 'უკვდავყოფა', 'Immortality', 'მართალთა უკვდავყოფა', [(3, 1, 19), (4, 1, 20), (5, 1, 23)]),
        ],
    },
    {
        'book_slug': 'ziraqi',
        'book_name_ka': 'სიბრძნე ზირაქისა',
        'book_name_en': 'Sirach (Ecclesiasticus)',
        'topics': [
            ('sirach', 'სიბრძნე ზირაქისა', 'Sirach', 'წიგნის შინაარსი', [(1, 1, 30), (2, 1, 18), (3, 1, 19)]),
            ('sirach-wisdom', 'ზირაქის სიბრძნე', 'Sirach Wisdom', 'სიბრძნის დაფასება', [(4, 1, 35), (6, 1, 37), (14, 1, 27)]),
            ('sirach-fear-god', 'ღვთის შიში', 'Fear of God', 'ღვთის შიში სიბრძნის დასაწყისი', [(1, 11, 30), (2, 1, 18), (25, 6, 12)]),
        ],
    },
    {
        'book_slug': 'epistole',
        'book_name_ka': 'ეპისტოლე იერემიასი',
        'book_name_en': 'Epistle of Jeremiah',
        'topics': [
            ('epistle-jeremiah', 'ეპისტოლე იერემიასი', 'Epistle of Jeremiah', 'წიგნის შინაარსი', [(1, 1, 72)]),
        ],
    },
    {
        'book_slug': 'baruqi',
        'book_name_ka': 'ბარუქი',
        'book_name_en': 'Baruch',
        'topics': [
            ('baruch', 'ბარუქი', 'Baruch', 'წიგნის შინაარსი', [(1, 1, 22), (2, 1, 35), (3, 1, 37)]),
            ('baruch-prophecy', 'ბარუქის წინასწარმეტყველება', 'Baruch Prophecy', 'ბარუქის წინასწარმეტყველება', [(4, 1, 37), (5, 1, 9)]),
        ],
    },
    {
        'book_slug': '1makabelta',
        'book_name_ka': 'I მაკაბელთა',
        'book_name_en': '1 Maccabees',
        'topics': [
            ('maccabees-1', 'I მაკაბელთა', '1 Maccabees', 'წიგნის შინაარსი', [(1, 1, 64), (2, 1, 70), (3, 1, 60)]),
            ('mattathias', 'მათათია', 'Mattathias', 'მათათიას აჯანყება', [(2, 1, 70), (3, 1, 60)]),
            ('judas-maccabeus', 'იუდა მაკაბელი', 'Judas Maccabeus', 'იუდა მაკაბელის ბრძოლები', [(3, 1, 60), (4, 1, 35), (5, 1, 68)]),
            ('antiochus-epiphanes', 'ანტიოქე ეპიფანესი', 'Antiochus Epiphanes', 'ანტიოქეს დევნა', [(1, 10, 64), (6, 1, 17)]),
            ('maccabean-revolt', 'მაკაბელთა აჯანყება', 'Maccabean Revolt', 'მაკაბელთა აჯანყება', [(2, 1, 70), (3, 1, 60), (4, 1, 35)]),
        ],
    },
    {
        'book_slug': '2makabelta',
        'book_name_ka': 'II მაკაბელთა',
        'book_name_en': '2 Maccabees',
        'topics': [
            ('maccabees-2', 'II მაკაბელთა', '2 Maccabees', 'წიგნის შინაარსი', [(1, 1, 36), (2, 1, 23), (3, 1, 40)]),
            ('judas-maccabeus-2', 'იუდა მაკაბელი (II)', 'Judas Maccabeus (2)', 'იუდა მაკაბელის ბრძოლები', [(8, 1, 36), (10, 1, 38), (11, 1, 38)]),
            ('martyrs-maccabees', 'მაკაბელთა მოწამენი', 'Maccabean Martyrs', 'მაკაბელთა მოწამეობრივი სიკვდილი', [(6, 1, 31), (7, 1, 42)]),
        ],
    },
    {
        'book_slug': '3makabelta',
        'book_name_ka': 'III მაკაბელთა',
        'book_name_en': '3 Maccabees',
        'topics': [
            ('maccabees-3', 'III მაკაბელთა', '3 Maccabees', 'წიგნის შინაარსი', [(1, 1, 29), (2, 1, 33), (3, 1, 30)]),
        ],
    },
    {
        'book_slug': '4makabelta',
        'book_name_ka': 'IV მაკაბელთა',
        'book_name_en': '4 Maccabees',
        'topics': [
            ('maccabees-4', 'IV მაკაბელთა', '4 Maccabees', 'წიგნის შინაარსი', [(1, 1, 35), (2, 1, 24), (3, 1, 19)]),
            ('reason-passion', 'გონება და ვნება', 'Reason and Passion', 'გონება იმპერატორი ვნებებისა', [(1, 1, 35), (2, 1, 24), (3, 1, 19)]),
        ],
    },
    {
        'book_slug': '3ezra',
        'book_name_ka': 'III ეზრა',
        'book_name_en': '3 Ezra',
        'topics': [
            ('ezra-3', 'III ეზრა', '3 Ezra', 'წიგნის შინაარსი', [(1, 1, 58), (2, 1, 30), (3, 1, 36)]),
        ],
    },
]


def build_verses_for_chapters(book_slug, chapter_ranges):
    """
    ქმნის მუხლების სიას თავების დიაპაზონებიდან.
    chapter_ranges: [(chapter, vs_start, vs_end), ...]
    """
    verses = []
    for chapter, vs_start, vs_end in chapter_ranges:
        verses.append({
            'book': book_slug,
            'chapter': chapter,
            'vs': vs_start,
            've': vs_end,
        })
    return verses


def main():
    apply = '--apply' in sys.argv

    print("=== აპოკრიფის თემების შექმნა (ეტაპი A) ===")
    print()

    # ჩატვირთვა
    with open(TOPICAL_FILE, 'r', encoding='utf-8') as f:
        ti = json.load(f)

    with open(TOPIC_NAMES_FILE, 'r', encoding='utf-8') as f:
        topic_names_ka = json.load(f)

    print(f"არსებული თემები: {len(ti['topics']):,}")
    print(f"არსებული by_book წიგნები: {len(ti.get('by_book', {}))}")
    print()

    # აპოკრიფის თემების შექმნა
    new_topics = []
    new_topic_names = {}
    topics_added = 0

    for book in APOCRYPHA_BOOKS:
        book_slug = book['book_slug']
        book_name_ka = book['book_name_ka']

        for topic_slug, name_ka, name_en, label, chapter_ranges in book['topics']:
            # შევამოწმოთ არ არსებობს თუ არა ეს თემა
            if topic_slug in ti.get('by_slug', {}):
                print(f"  [გამოტოვება] {topic_slug} უკვე არსებობს")
                continue

            # მუხლების შექმნა
            verses = build_verses_for_chapters(book_slug, chapter_ranges)

            # თემის შექმნა
            topic = {
                'slug': topic_slug,
                'name_en': name_en,
                'name': name_ka,  # ქართული სახელი
                'source': 'apocrypha',
                'see_also': [],
                'entries': [
                    {
                        'label': label,
                        'verses': verses,
                    }
                ],
                'verse_count': sum(v['ve'] - v['vs'] + 1 for v in verses),
            }

            new_topics.append(topic)
            new_topic_names[topic_slug] = name_ka
            topics_added += 1
            print(f"  [დამატება] {topic_slug:25s} {name_ka:25s} ({len(verses)} ენტრი, {topic['verse_count']} მუხლი)")

    print()
    print(f"დასამატებელი თემები: {topics_added}")

    # by_book განახლება - dict სტრუქტურით (იგივე რაც build_by_book_index.py)
    # ეს უნდა მოხდეს მაშინაც კი როცა თემები უკვე არსებობს
    if 'by_book' not in ti:
        ti['by_book'] = {}

    # ჯერ წავშალოთ ძველი list სტრუქტურის აპოკრიფის ენტრი
    for book in APOCRYPHA_BOOKS:
        book_slug = book['book_slug']
        if book_slug in ti['by_book'] and isinstance(ti['by_book'][book_slug], list):
            del ti['by_book'][book_slug]

    # ახლა შევქმნათ dict სტრუქტურით
    # შევაგროვოთ ყველა აპოკრიფის თემა (როგორც ახალი, ისე უკვე არსებული)
    all_apocrypha_topics = {}
    for book in APOCRYPHA_BOOKS:
        for topic_slug, name_ka, name_en, label, chapter_ranges in book['topics']:
            all_apocrypha_topics[topic_slug] = (book['book_slug'], name_en, chapter_ranges)

    for book in APOCRYPHA_BOOKS:
        book_slug = book['book_slug']

        # შევაგროვოთ ამ წიგნის თემები და მუხლები
        book_topics = []
        book_verse_count = 0

        for topic_slug, (ts_book, name_en, chapter_ranges) in all_apocrypha_topics.items():
            if ts_book != book_slug:
                continue

            # ვპოვოთ თემა topics-ში
            topic = None
            for t in ti['topics']:
                if t['slug'] == topic_slug:
                    topic = t
                    break

            if not topic:
                continue

            # ვამოწმოთ ეს თემა ამ წიგნისთვის არის
            verses_in_book = 0
            for entry in topic['entries']:
                for v in entry['verses']:
                    if v['book'] == book_slug:
                        verses_in_book += v['ve'] - v['vs'] + 1

            if verses_in_book > 0:
                book_topics.append({
                    'slug': topic['slug'],
                    'name_en': topic['name_en'],
                    'verses_in_book': verses_in_book,
                })
                book_verse_count += verses_in_book

        # დავალაგოთ verses_in_book-ის მიხედვით (კლებადობით)
        book_topics.sort(key=lambda x: x['verses_in_book'], reverse=True)

        # შევქმნათ book_data dict
        ti['by_book'][book_slug] = {
            'testament': 'old',
            'topic_count': len(book_topics),
            'verse_count': book_verse_count,
            'top_topics': book_topics,
        }

    # დამატება topical_index.json-ში (მხოლოდ ახალი თემები)
    if topics_added > 0:
        ti['topics'].extend(new_topics)

        # by_slug განახლება
        if 'by_slug' not in ti:
            ti['by_slug'] = {}
        for i, t in enumerate(ti['topics']):
            ti['by_slug'][t['slug']] = i

        # by_verse განახლება
        if 'by_verse' not in ti:
            ti['by_verse'] = {}
        for topic in new_topics:
            for entry in topic['entries']:
                for v in entry['verses']:
                    verse_key = f"{v['book']}:{v['chapter']}:{v['vs']}"
                    if verse_key not in ti['by_verse']:
                        ti['by_verse'][verse_key] = []
                    if topic['slug'] not in ti['by_verse'][verse_key]:
                        ti['by_verse'][verse_key].append(topic['slug'])

        # topic_names_ka.json განახლება
        topic_names_ka.update(new_topic_names)

    print()
    print(f"განახლებული თემები: {len(ti['topics']):,}")
    print(f"განახლებული by_book წიგნები: {len(ti['by_book'])}")
    print(f"განახლებული topic_names: {len(topic_names_ka):,}")

    # აპოკრიფის თემების შემოწმება
    print()
    print("=== აპოკრიფის თემები by_book-ში ===")
    apoc_slugs = ['2ezra','tobiti','ivditi','solomoni','ziraqi','epistole','baruqi','1makabelta','2makabelta','3makabelta','4makabelta','3ezra']
    for slug in apoc_slugs:
        bd = ti['by_book'].get(slug, {})
        count = bd.get('topic_count', 0) if isinstance(bd, dict) else 0
        print(f"  {slug:15s}: {count} თემა")

    if apply:
        with open(TOPICAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(ti, f, ensure_ascii=False, indent=2)
        with open(TOPIC_NAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(topic_names_ka, f, ensure_ascii=False, indent=2)
        print()
        print(f"შენახულია: {TOPICAL_FILE}")
        print(f"შენახულია: {TOPIC_NAMES_FILE}")
    else:
        print()
        print("--apply გარეშე: ცვლილებები არ შენახულა")
        print("გასაშვებად: python3 build_apocrypha_topics.py --apply")


if __name__ == '__main__':
    main()
