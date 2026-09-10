#!/usr/bin/env python3
"""
discover_mapping.py
===================
verse_index.json-დან და cross_references.txt-დან
ამოიღებს ყველა უნიკალურ წიგნის იდენტიფიკატორს
და გამოიტანს მზა OSIS_TO_SLUG მაპინგის ჩონჩხს.

გაშვება:
    python discover_mapping.py
"""

import json
from collections import OrderedDict


def discover():
    # 1. verse_index.json-დან ყველა უნიკალური slug და სახელი
    with open('data/verse_index.json', 'r', encoding='utf-8') as f:
        verses = json.load(f)

    slug_to_name = OrderedDict()
    for v in verses:
        s = v['book_slug']
        if s not in slug_to_name:
            slug_to_name[s] = v.get('book', s)

    # 2. cross_references.txt-დან ყველა უნიკალური OSIS წიგნის აბრევიატურა
    osis_books = set()
    with open('data/crossrefs/cross_references.txt', 'r', encoding='utf-8') as f:
        header = f.readline()
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 2:
                continue
            for ref_str in [parts[0], parts[1]]:
                for single_ref in ref_str.split('-'):
                    dot_parts = single_ref.strip().split('.')
                    if dot_parts:
                        book_part = dot_parts[0]
                        osis_books.add(book_part)

    osis_sorted = sorted(osis_books)

    print(f"verse_index.json: {len(slug_to_name)} წიგნი")
    print(f"cross_references.txt: {len(osis_sorted)} OSIS აბრევიატურა")

    print("\n\n=== რეალური slugs (verse_index.json) ===\n")
    for i, (slug, name) in enumerate(slug_to_name.items(), 1):
        print(f"  {i:>3}. {slug:<30} {name}")

    print("\n\n=== OSIS აბრევიატურები (cross_references.txt) ===\n")
    for i, osis in enumerate(osis_sorted, 1):
        print(f"  {i:>3}. {osis}")

    # 3. მზა Python dict-ის ჩონჩხი
    print("\n\n=== შესავსები მაპინგი (დააკოპირე და შეავსე) ===\n")
    print("OSIS_TO_SLUG = {")
    for osis in osis_sorted:
        print(f"    '{osis}': '',  # ???")
    print("}")

    print("\n\n=== შესავსები უკუ მაპინგი (slug -> book_name) ===\n")
    print("SLUG_TO_NAME = {")
    for slug, name in slug_to_name.items():
        print(f"    '{slug}': '{name}',")
    print("}")


if __name__ == '__main__':
    discover()
