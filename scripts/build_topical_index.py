#!/usr/bin/env python3
"""
build_topical_index.py
======================
Nave's Topical Bible და Torrey's New Topical Textbook-დან
აგებს თემატური ენციკლოპედიის ინდექსს ჩვენი slug-ებით.

წყარო: j86schroeder/topical-bible-search (GitHub)
ფორმატი JSONL (თითო ხაზი ერთი JSON ობიექტი)

გამოსავალი: data/topical_index.json

სტრუქტურა:
{
  "topics": [
    {
      "slug": "aaron",
      "name": "აარონი",           // თემის ქართული სახელი (თარგმანი შემდგომ)
      "name_en": "AARON",
      "source": "nave",
      "see_also": ["priest_high"],
      "entries": [
        {
          "label": "Lineage of",
          "verses": [
            {"book": "gamosvla", "chapter": 6, "vs": 16, "ve": 20},
            ...
          ]
        }
      ],
      "verse_count": 51
    }
  ],
  "by_slug": {
    "aaron": 0,   // index in topics array
    ...
  },
  "by_verse": {
    "gamosvla:6:16": ["aaron", "levites", ...],
    ...
  }
}
"""

import json
from collections import defaultdict
from pathlib import Path

# ინგლისური წიგნის სახელები → ჩვენი slug-ები
BOOK_NAME_TO_SLUG = {
    'Genesis': 'dabadeba', 'Exodus': 'gamosvla', 'Leviticus': 'levianni',
    'Numbers': 'ritskhvni', 'Deuteronomy': '2rjuli',
    'Joshua': 'iesonave', 'Judges': 'msajulni', 'Ruth': 'ruti',
    '1 Samuel': '1mepeta', '2 Samuel': '2mepeta',
    '1 Kings': '3mepeta', '2 Kings': '4mepeta',
    '1 Chronicles': '1neshtta', '2 Chronicles': '2neshtta',
    'Ezra': '1ezra', 'Nehemiah': 'neemia', 'Esther': 'esteri',
    'Job': 'iobi', 'Psalms': 'fsalmunni', 'Proverbs': 'igavni',
    'Ecclesiastes': 'eklesiaste', 'Song of Solomon': 'qeba',
    'Isaiah': 'esaia', 'Jeremiah': 'ieremia', 'Lamentations': 'godeba',
    'Ezekiel': 'ezekieli', 'Daniel': 'danieli',
    'Hosea': 'osia', 'Joel': 'ioveli', 'Amos': 'amos',
    'Obadiah': 'abdia', 'Jonah': 'iona', 'Micah': 'miqa',
    'Nahum': 'naumi', 'Habakkuk': 'abakumi', 'Zephaniah': 'sofonia',
    'Haggai': 'angia', 'Zechariah': 'zaqaria', 'Malachi': 'malaqia',
    'Matthew': 'mate', 'Mark': 'markozi', 'Luke': 'luka', 'John': 'ioane',
    'Acts': 'saqme',
    'Romans': 'romaelta',
    '1 Corinthians': '1korintelta', '2 Corinthians': '2korintelta',
    'Galatians': 'galatelta', 'Ephesians': 'efeselta',
    'Philippians': 'filipelta', 'Colossians': 'kolaselta',
    '1 Thessalonians': '1tesalonikelta', '2 Thessalonians': '2tesalonikelta',
    '1 Timothy': '1timote', '2 Timothy': '2timote',
    'Titus': 'tite', 'Philemon': 'filimoni',
    'Hebrews': 'ebraelta', 'James': 'iakobi',
    '1 Peter': '1petre', '2 Peter': '2petre',
    '1 John': '1ioane', '2 John': '2ioane', '3 John': '3ioane',
    'Jude': 'iuda',
    'Revelation': 'apokalips',
}


def load_jsonl(path):
    """JSONL ფაილის ჩატვირთვა."""
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_topical_index(nave_dir, torrey_dir, output_path):
    """თემატური ინდექსის აგება."""

    all_topics = []
    topic_slug_map = {}  # slug -> index
    verse_to_topics = defaultdict(set)  # verse_key -> set of topic slugs

    for source_name, source_dir in [('nave', nave_dir), ('torrey', torrey_dir)]:
        print(f"\n=== {source_name.upper()} ===")

        # თემების ჩატვირთვა
        topics = load_jsonl(Path(source_dir) / 'topics.jsonl')
        entries = load_jsonl(Path(source_dir) / 'entries.jsonl')
        assertions = load_jsonl(Path(source_dir) / 'assertions.jsonl')

        print(f"  თემები: {len(topics):,}")
        print(f"  ენტრიები: {len(entries):,}")
        print(f"  რეფერენსები: {len(assertions):,}")

        # assertions-ის დაჯგუფება entry-ის მიხედვით
        entry_assertions = defaultdict(list)
        for a in assertions:
            entry_assertions[a['entryId']].append(a)

        # entries-ის დაჯგუფება topic-ის მიხედვით
        topic_entries = defaultdict(list)
        for e in entries:
            topic_entries[e['topicId']].append(e)

        # თემების დამუშავება
        matched_refs = 0
        unmatched_refs = 0

        for topic in topics:
            topic_id = topic['id']
            topic_slug = topic['sourceTopicSlug']
            topic_name_en = topic['sourceTopic']

            # see_also slug-ების მომზადება
            see_also = []
            for ref in topic.get('seeAlso', []):
                # გადავიყვანოთ დიდი ასოებიდან slug-ად
                see_also.append(ref.lower().replace(' ', '_').replace(',', ''))

            # ენტრიების შეგროვება
            topic_entries_list = []
            topic_verse_count = 0

            for entry in topic_entries.get(topic_id, []):
                entry_label = entry.get('rawText', '').strip()
                # რეფერენსების ამოღება assertions-დან
                entry_verses = []
                for a in entry_assertions.get(entry['id'], []):
                    book_name = a.get('book', '')
                    slug = BOOK_NAME_TO_SLUG.get(book_name)
                    if not slug:
                        unmatched_refs += 1
                        continue

                    vs = a.get('verseStart') or 0
                    ve = a.get('verseEnd') or vs
                    chapter = a.get('chapterStart') or 0

                    if vs == 0:
                        unmatched_refs += 1
                        continue

                    entry_verses.append({
                        'book': slug,
                        'chapter': chapter,
                        'vs': vs,
                        've': ve,
                    })
                    # verse_to_topics ინდექსი
                    for v in range(vs, ve + 1):
                        verse_to_topics[f"{slug}:{chapter}:{v}"].add(topic_slug)

                    matched_refs += 1
                    topic_verse_count += 1

                if entry_verses:
                    topic_entries_list.append({
                        'label': entry_label,
                        'verses': entry_verses,
                    })

            # თემის დამატება
            if topic_entries_list:
                topic_obj = {
                    'slug': topic_slug,
                    'name_en': topic_name_en,
                    'name': topic_name_en,  # ქართული თარგმანი შემდგომ
                    'source': source_name,
                    'see_also': see_also,
                    'entries': topic_entries_list,
                    'verse_count': topic_verse_count,
                }
                topic_slug_map[topic_slug] = len(all_topics)
                all_topics.append(topic_obj)

        print(f"  დამთხვევა: {matched_refs:,}")
        print(f"  გამოტოვებული: {unmatched_refs:,}")

    # სტატისტიკა
    total_verses = sum(len(v) for v in verse_to_topics.values())
    print(f"\n=== სრული შედეგი ===")
    print(f"  თემები: {len(all_topics):,}")
    print(f"  მუხლები თემებით: {len(verse_to_topics):,}")
    print(f"  თემა-მუხლი კავშირი: {total_verses:,}")

    # ტოპ თემები მუხლების რაოდენობის მიხედვით
    sorted_topics = sorted(all_topics, key=lambda x: -x['verse_count'])
    print(f"\n=== ტოპ 20 თემა ===")
    for t in sorted_topics[:20]:
        print(f"  {t['name_en']:30s} {t['verse_count']:5,} მუხლი")

    # შენახვა
    output = {
        'topics': all_topics,
        'by_slug': topic_slug_map,
        'by_verse': {k: sorted(v) for k, v in verse_to_topics.items()},
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_mb = Path(output_path).stat().st_size / 1024 / 1024
    print(f"\nშენახულია: {output_path} ({size_mb:.1f} მბ)")


if __name__ == '__main__':
    build_topical_index(
        nave_dir='data/topical/nave',
        torrey_dir='data/topical/torrey',
        output_path='data/topical_index.json',
    )
