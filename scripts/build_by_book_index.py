#!/usr/bin/env python3
"""
build_by_book_index.py
======================
by_book ინდექსის აგება topical_index.json-ში.

სტრუქტურა:
{
  "by_book": {
    "dabadeba": {
      "testament": "old",
      "topic_count": 342,
      "verse_count": 1250,
      "top_topics": [
        {"slug": "creation", "name_en": "CREATION", "verses_in_book": 45},
        ...
      ]
    },
    ...
  }
}

გამოყენება:
    python3 build_by_book_index.py           # შემოწმება
    python3 build_by_book_index.py --apply   # შენახვა
"""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TOPICAL_FILE = DATA_DIR / "topical_index.json"

# წიგნების კატეგორიზაცია (server.py-დან ასლი)
OLD_TESTAMENT_ORDER = [
    "dabadeba", "gamosvla", "levianni", "ritskhvni", "2rjuli",
    "iesonave", "msajulni", "ruti",
    "1mepeta", "2mepeta", "3mepeta", "4mepeta",
    "1neshtta", "2neshtta", "1ezra", "neemia",
    "2ezra", "tobiti", "ivditi", "esteri",
    "iobi", "fsalmunni", "igavni", "eklesiaste", "qeba",
    "solomoni", "ziraqi",
    "esaia", "ieremia", "godeba", "epistole", "baruqi",
    "ezekieli", "danieli",
    "osia", "ioveli", "amos", "abdia", "iona", "miqa",
    "naumi", "abakumi", "sofonia", "angia", "zaqaria", "malaqia",
    "1makabelta", "2makabelta", "3makabelta", "4makabelta", "3ezra",
]

NEW_TESTAMENT_ORDER = [
    "mate", "markozi", "luka", "ioane", "saqme",
    "romaelta", "1korintelta", "2korintelta", "galatelta",
    "efeselta", "filipelta", "kolaselta",
    "1tesalonikelta", "2tesalonikelta",
    "1timote", "2timote", "tite", "filimoni",
    "ebraelta", "iakobi", "1petre", "2petre",
    "1ioane", "2ioane", "3ioane", "iuda", "apokalips",
]

NONCANONICAL_BOOKS = {
    "2ezra", "3ezra", "tobiti", "ivditi", "solomoni", "ziraqi",
    "baruqi", "epistole", "1makabelta", "2makabelta", "3makabelta", "4makabelta",
}


def get_testament(book_slug):
    """წიგნის აღთქმის განსაზღვრა."""
    if book_slug in NEW_TESTAMENT_ORDER:
        return "new"
    if book_slug in NONCANONICAL_BOOKS:
        return "apocrypha"
    return "old"


def build_by_book(topical_index):
    """by_book ინდექსის აგება."""
    topics = topical_index.get("topics", [])
    by_slug = topical_index.get("by_slug", {})

    # წიგნის მიხედვით თემების და მუხლების დათვლა
    book_topics = defaultdict(lambda: {
        "topic_slugs": set(),
        "verse_count": 0,
        "topic_verse_counts": Counter(),  # slug -> verse count in this book
    })

    for topic in topics:
        slug = topic["slug"]
        for entry in topic.get("entries", []):
            for v in entry.get("verses", []):
                book = v["book"]
                book_topics[book]["topic_slugs"].add(slug)
                book_topics[book]["verse_count"] += 1
                book_topics[book]["topic_verse_counts"][slug] += 1

    # სტრუქტურის ფორმირება
    by_book = {}
    for book_slug, data in book_topics.items():
        testament = get_testament(book_slug)

        # top_topics - დალაგებული მუხლების რაოდენობის მიხედვით
        top_topics = []
        for slug, count in data["topic_verse_counts"].most_common(20):
            idx = by_slug.get(slug)
            name_en = topics[idx]["name_en"] if idx is not None else slug
            top_topics.append({
                "slug": slug,
                "name_en": name_en,
                "verses_in_book": count,
            })

        by_book[book_slug] = {
            "testament": testament,
            "topic_count": len(data["topic_slugs"]),
            "verse_count": data["verse_count"],
            "top_topics": top_topics,
        }

    return by_book


def main():
    apply = "--apply" in sys.argv

    print("=== by_book ინდექსის აგება ===")
    print()

    print("თემატური ინდექსის ჩატვირთვა...")
    with open(TOPICAL_FILE, "r", encoding="utf-8") as f:
        topical_index = json.load(f)
    print(f"  თემები: {len(topical_index['topics']):,}")
    print(f"  by_verse: {len(topical_index['by_verse']):,}")
    print()

    print("by_book ინდექსის აგება...")
    by_book = build_by_book(topical_index)
    print(f"  წიგნები: {len(by_book)}")
    print()

    # სტატისტიკა აღთქმის მიხედვით
    by_testament = defaultdict(int)
    for book, data in by_book.items():
        by_testament[data["testament"]] += 1
    print("წიგნები აღთქმის მიხედვით:")
    for testament, count in sorted(by_testament.items()):
        print(f"  {testament}: {count} წიგნი")
    print()

    # ტოპ 10 წიგნი თემების რაოდენობის მიხედვით
    print("ტოპ 10 წიგნი თემების რაოდენობის მიხედვით:")
    sorted_books = sorted(by_book.items(), key=lambda x: -x[1]["topic_count"])
    for book, data in sorted_books[:10]:
        print(f"  {book}: {data['topic_count']} თემა, {data['verse_count']} მუხლი ({data['testament']})")
    print()

    if apply:
        topical_index["by_book"] = by_book
        print(f"შენახვა: {TOPICAL_FILE}")
        with open(TOPICAL_FILE, "w", encoding="utf-8") as f:
            json.dump(topical_index, f, ensure_ascii=False)
        print("შენახულია.")
    else:
        print("--apply გარეშე: ცვლილებები არ შენახულა.")
        print("გასაშვებად: python3 build_by_book_index.py --apply")


if __name__ == "__main__":
    main()
