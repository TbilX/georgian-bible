#!/usr/bin/env python3
"""
build_crossrefs.py
==================
cross_references.txt-დან აგებს ინდექსს ჩვენი slug-ებით.

გამოსავალი: data/crossrefs_index.json

გაშვება:
    python build_crossrefs.py
    python build_crossrefs.py --min-votes 5 --stats
"""

import json
import argparse
from collections import defaultdict
from pathlib import Path

# ვერიფიცირებული 66/66 (protestant canon)
OSIS_TO_SLUG = {
    # პენტატექი (5)
    'Gen': 'dabadeba', 'Exod': 'gamosvla', 'Lev': 'levianni',
    'Num': 'ritskhvni', 'Deut': '2rjuli',
    # ისტორიული (12)
    'Josh': 'iesonave', 'Judg': 'msajulni', 'Ruth': 'ruti',
    '1Sam': '1mepeta', '2Sam': '2mepeta',
    '1Kgs': '3mepeta', '2Kgs': '4mepeta',
    '1Chr': '1neshtta', '2Chr': '2neshtta',
    'Ezra': '1ezra', 'Neh': 'neemia', 'Esth': 'esteri',
    # სიბრძნე/პოეზია (5)
    'Job': 'iobi', 'Ps': 'fsalmunni', 'Prov': 'igavni',
    'Eccl': 'eklesiaste', 'Song': 'qeba',
    # წინასწარმეტყველები (17)
    'Isa': 'esaia', 'Jer': 'ieremia', 'Lam': 'godeba',
    'Ezek': 'ezekieli', 'Dan': 'danieli',
    'Hos': 'osia', 'Joel': 'ioveli', 'Amos': 'amos',
    'Obad': 'abdia', 'Jonah': 'iona', 'Mic': 'miqa',
    'Nah': 'naumi', 'Hab': 'abakumi', 'Zeph': 'sofonia',
    'Hag': 'angia', 'Zech': 'zaqaria', 'Mal': 'malaqia',
    # ახალი აღთქმა - სახარებები (4)
    'Matt': 'mate', 'Mark': 'markozi', 'Luke': 'luka', 'John': 'ioane',
    # ისტორიული (1)
    'Acts': 'saqme',
    # პავლეს ეპისტოლეები (13)
    'Rom': 'romaelta',
    '1Cor': '1korintelta', '2Cor': '2korintelta',
    'Gal': 'galatelta', 'Eph': 'efeselta',
    'Phil': 'filipelta', 'Col': 'kolaselta',
    '1Thess': '1tesalonikelta', '2Thess': '2tesalonikelta',
    '1Tim': '1timote', '2Tim': '2timote',
    'Titus': 'tite', 'Phlm': 'filimoni',
    # ზოგადი ეპისტოლეები (8)
    'Heb': 'ebraelta', 'Jas': 'iakobi',
    '1Pet': '1petre', '2Pet': '2petre',
    '1John': '1ioane', '2John': '2ioane', '3John': '3ioane',
    'Jude': 'iuda',
    # გამოცხადება (1)
    'Rev': 'apokalips',
}


def parse_single(ref_str):
    """'Gen.1.1' -> ('dabadeba', 1, 1) ან None"""
    parts = ref_str.strip().split('.')
    if len(parts) != 3:
        return None
    slug = OSIS_TO_SLUG.get(parts[0])
    if not slug:
        return None
    try:
        return (slug, int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def parse_target(ref_str):
    """
    'John.1.1'          -> {book, chapter, vs, ve}
    'John.1.1-John.1.3' -> {book, chapter, vs, ve}
    """
    if '-' in ref_str:
        left, right = ref_str.split('-', 1)
        start = parse_single(left)
        end = parse_single(right)
        if not start:
            return None
        if end and start[0] == end[0] and start[1] == end[1]:
            return {'book': start[0], 'chapter': start[1],
                    'vs': start[2], 've': end[2]}
        else:
            # თუ range სცილდება ერთ თავს, ვიღებთ მხოლოდ დასაწყისს
            return {'book': start[0], 'chapter': start[1],
                    'vs': start[2], 've': start[2]}
    else:
        p = parse_single(ref_str)
        if p:
            return {'book': p[0], 'chapter': p[1], 'vs': p[2], 've': p[2]}
        return None


def build(input_path, output_path, min_votes=1, verbose=False):
    index = defaultdict(list)
    total = 0
    matched = 0
    skipped_from = defaultdict(int)
    skipped_to = defaultdict(int)

    with open(input_path, 'r', encoding='utf-8') as f:
        header = f.readline()
        for line in f:
            total += 1
            parts = line.strip().split('\t')
            if len(parts) < 3:
                continue

            from_ref, to_ref, votes_str = parts[0], parts[1], parts[2]

            try:
                votes = int(votes_str)
            except ValueError:
                continue

            if votes < min_votes:
                continue

            from_p = parse_single(from_ref)
            to_p = parse_target(to_ref)

            if not from_p:
                osis = from_ref.split('.')[0] if '.' in from_ref else from_ref
                skipped_from[osis] += 1
                continue

            if not to_p:
                osis = to_ref.split('.')[0] if '.' in to_ref else to_ref
                skipped_to[osis] += 1
                continue

            key = f"{from_p[0]}:{from_p[1]}:{from_p[2]}"
            index[key].append({**to_p, 'votes': votes})
            matched += 1

    # votes-ით დალაგება, კლებადი
    for key in index:
        index[key].sort(key=lambda x: -x['votes'])

    print(f"\n=== შედეგი ===")
    print(f"სულ ხაზი: {total:,}")
    print(f"წარმატებით: {matched:,} ({100*matched/total:.1f}%)")
    print(f"უნიკალური წყარო მუხლი: {len(index):,}")

    if skipped_from:
        total_skipped_from = sum(skipped_from.values())
        print(f"\nგამოტოვებული FROM (მაპინგში არ არის): {total_skipped_from:,}")
        if verbose:
            for osis, cnt in sorted(skipped_from.items(), key=lambda x: -x[1])[:10]:
                print(f"  {osis}: {cnt:,}")

    if skipped_to:
        total_skipped_to = sum(skipped_to.values())
        print(f"გამოტოვებული TO (მაპინგში არ არის): {total_skipped_to:,}")
        if verbose:
            for osis, cnt in sorted(skipped_to.items(), key=lambda x: -x[1])[:10]:
                print(f"  {osis}: {cnt:,}")

    # სტატისტიკა votes-ის მიხედვით
    all_votes = []
    for refs in index.values():
        for r in refs:
            all_votes.append(r['votes'])
    all_votes.sort()
    if all_votes:
        print(f"\n=== Votes სტატისტიკა ===")
        print(f"მინიმალური: {all_votes[0]}")
        print(f"მედიანა: {all_votes[len(all_votes)//2]}")
        print(f"მაქსიმალური: {all_votes[-1]}")
        print(f"საშუალო: {sum(all_votes)/len(all_votes):.1f}")

    # წიგნების დაფარვა
    books_with_refs = set()
    for key in index:
        book = key.split(':')[0]
        books_with_refs.add(book)
    print(f"\nწიგნები რომელთაც აქვთ cross-refs: {len(books_with_refs)}/66")

    if verbose:
        # დავამატოთ სრული სია რომელ წიგნებს აქვთ/არ აქვთ
        all_canonical_slugs = set(OSIS_TO_SLUG.values())
        with_refs = books_with_refs & all_canonical_slugs
        without_refs = all_canonical_slugs - books_with_refs
        print(f"\nწიგნები რომელთაც აქვთ cross-refs ({len(with_refs)}):")
        for s in sorted(with_refs):
            print(f"  {s}")
        if without_refs:
            print(f"\nწიგნები რომელთაც არ აქვთ cross-refs ({len(without_refs)}):")
            for s in sorted(without_refs):
                print(f"  {s}")

    # შენახვა
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dict(index), f, ensure_ascii=False, separators=(',', ':'))

    size_mb = Path(output_path).stat().st_size / 1024 / 1024
    print(f"\nშენახულია: {output_path} ({size_mb:.1f} მბ)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/crossrefs/cross_references.txt')
    parser.add_argument('--output', default='data/crossrefs_index.json')
    parser.add_argument('--min-votes', type=int, default=1)
    parser.add_argument('--stats', action='store_true',
                       help='დეტალური სტატისტიკა გამოტოვებული OSIS-ების შესახებ')
    args = parser.parse_args()

    build(args.input, args.output, args.min_votes, verbose=args.stats)


if __name__ == '__main__':
    main()
