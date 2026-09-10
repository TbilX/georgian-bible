#!/usr/bin/env python3
"""
analyze_duplicates.py
=====================
გამოიკვლევს 189 დუბლიკატ მუხლს verse_index.json-ში.

გაშვება:
    python analyze_duplicates.py
    python analyze_duplicates.py --full   (სრული სია)
"""

import json
import argparse
from collections import defaultdict


def analyze_duplicates(show_full=False):
    with open('data/verse_index.json', 'r', encoding='utf-8') as f:
        verse_index = json.load(f)

    seen_keys = defaultdict(list)
    for i, vi in enumerate(verse_index):
        key = f"{vi['book_slug']}:{vi['chapter']}:{vi['verse']}"
        seen_keys[key].append(i)

    duplicates = {k: v for k, v in seen_keys.items() if len(v) > 1}

    print(f"სულ მუხლი: {len(verse_index)}")
    print(f"უნიკალური გასაღები: {len(seen_keys)}")
    print(f"დუბლირებული გასაღებები: {len(duplicates)}")
    print(f"დაკარგული მუხლი (ბოლო იმარჯვებს): {len(verse_index) - len(seen_keys)}")

    # დუბლიკატები წიგნების მიხედვით
    books_with_dups = defaultdict(int)
    for key in duplicates:
        book = key.split(':')[0]
        books_with_dups[book] += 1

    print("\n=== დუბლიკატები წიგნების მიხედვით ===")
    for book, count in sorted(books_with_dups.items(), key=lambda x: -x[1]):
        print(f"  {book}: {count}")

    # ტექსტების შედარება: იდენტური თუ განსხვავებული
    identical = 0
    different = 0
    different_examples = []

    for key, indices in duplicates.items():
        texts_new = [verse_index[i].get('new', '') for i in indices]
        texts_old = [verse_index[i].get('old', '') for i in indices]

        # შევადაროთ როგორც new, ასევე old
        if texts_new[0] == texts_new[1] and texts_old[0] == texts_old[1]:
            identical += 1
        else:
            different += 1
            if len(different_examples) < 20:
                different_examples.append((key, indices, texts_new, texts_old))

    print(f"\n=== ტექსტების შედარება ===")
    print(f"იდენტური დუბლიკატები (same text): {identical}")
    print(f"განსხვავებული დუბლიკატები (diff text): {different}")

    # განსხვავებული დუბლიკატების დეტალური ანალიზი
    if different_examples:
        print(f"\n=== განსხვავებული დუბლიკატების მაგალითები (პირველი {len(different_examples)}) ===")
        for key, indices, texts_new, texts_old in different_examples:
            print(f"\n--- {key} ---")
            for j, idx in enumerate(indices):
                vi = verse_index[idx]
                print(f"  [{j}] idx={idx}, file={vi.get('file', '?')}")
                print(f"      new: {texts_new[j][:100]}...")
                if texts_old[j]:
                    print(f"      old: {texts_old[j][:100]}...")

    # იდენტური დუბლიკატების მაგალითებიც
    if identical > 0:
        print(f"\n=== იდენტური დუბლიკატების მაგალითები (პირველი 5) ===")
        count = 0
        for key, indices in duplicates.items():
            texts_new = [verse_index[i].get('new', '') for i in indices]
            texts_old = [verse_index[i].get('old', '') for i in indices]
            if texts_new[0] == texts_new[1] and texts_old[0] == texts_old[1]:
                print(f"\n--- {key} ---")
                for j, idx in enumerate(indices):
                    vi = verse_index[idx]
                    print(f"  [{j}] idx={idx}, file={vi.get('file', '?')}")
                    print(f"      new: {texts_new[j][:100]}...")
                count += 1
                if count >= 5:
                    break

    # სრული სია თუ --full
    if show_full and different > 0:
        print(f"\n\n=== სრული სია განსხვავებული დუბლიკატების ({different}) ===")
        for key, indices in duplicates.items():
            texts_new = [verse_index[i].get('new', '') for i in indices]
            texts_old = [verse_index[i].get('old', '') for i in indices]
            if texts_new[0] != texts_new[1] or texts_old[0] != texts_old[1]:
                print(f"  {key}")
                for j, idx in enumerate(indices):
                    print(f"    [{j}] {texts_new[j][:80]}")

    # file გასაღების ანალიზი - სად არის დუბლიკატები
    print(f"\n=== file წყაროების ანალიზი ===")
    file_pairs = defaultdict(int)
    for key, indices in duplicates.items():
        files = tuple(sorted(set(verse_index[i].get('file', '?') for i in indices)))
        file_pairs[files] += 1
    for files, cnt in sorted(file_pairs.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cnt}x: {files}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='სრული სია განსხვავებული დუბლიკატების')
    args = parser.parse_args()
    analyze_duplicates(show_full=args.full)
