#!/usr/bin/env python3
"""
build_tsk_crossrefs.py
======================
TSKe (Treasury of Scripture Knowledge, Enhanced) ბაზიდან აგებს
cross-references ინდექსს ჩვენი slug-ებით.

TSKe არის 1800-იან წლებში თეოლოგების მიერ შედგენილი, გაფართოებული
ბაზა 670,000+ ჯაჭვით. ეს არის "ოქროს სტანდარტი" ბიბლიური კვლევისთვის.

გამოსავალი: data/crossrefs_tsk.json

სტრუქტურა:
{
  "dabadeba:1:1": [
    {
      "book": "igavni", "chapter": 8, "vs": 22, "ve": 24,
      "topic": "beginning", "type": "thematic", "source": "tsk"
    },
    ...
  ]
}
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# TSKe შემოკლებები → ჩვენი slug-ები
# განსხვავდება OSIS-ისგან (მაგ: Ge არა Gen, Mt არა Matt)
TSK_TO_SLUG = {
    # პენტატექი
    'Ge': 'dabadeba', 'Ex': 'gamosvla', 'Lev': 'levianni',
    'Nu': 'ritskhvni', 'Deut': '2rjuli',
    # ისტორიული
    'Josh': 'iesonave', 'Judg': 'msajulni', 'Ruth': 'ruti',
    '1Sa': '1mepeta', '2Sa': '2mepeta',
    '1Ki': '3mepeta', '2Ki': '4mepeta',
    '1Ch': '1neshtta', '2Ch': '2neshtta',
    'Ezra': '1ezra', 'Neh': 'neemia', 'Esth': 'esteri',
    # სიბრძნე/პოეზია
    'Job': 'iobi', 'Ps': 'fsalmunni', 'Pr': 'igavni',
    'Ec': 'eklesiaste', 'Song': 'qeba',
    # წინასწარმეტყველები
    'Isa': 'esaia', 'Jer': 'ieremia', 'Lam': 'godeba',
    'Eze': 'ezekieli', 'Dan': 'danieli',
    'Hos': 'osia', 'Joel': 'ioveli', 'Amos': 'amos',
    'Obad': 'abdia', 'Jon': 'iona', 'Mic': 'miqa',
    'Na': 'naumi', 'Hab': 'abakumi', 'Zeph': 'sofonia',
    'Hag': 'angia', 'Zech': 'zaqaria', 'Mal': 'malaqia',
    # ახალი აღთქმა - სახარებები
    'Mt': 'mate', 'Mk': 'markozi', 'Lk': 'luka', 'Jn': 'ioane',
    # ისტორიული
    'Ac': 'saqme',
    # პავლეს ეპისტოლეები
    'Ro': 'romaelta',
    '1Co': '1korintelta', '2Co': '2korintelta',
    'Gal': 'galatelta', 'Eph': 'efeselta',
    'Php': 'filipelta', 'Col': 'kolaselta',
    '1Th': '1tesalonikelta', '2Th': '2tesalonikelta',
    '1Ti': '1timote', '2Ti': '2timote',
    'Titus': 'tite', 'Phlm': 'filimoni',
    # ზოგადი ეპისტოლეები
    'He': 'ebraelta', 'Jas': 'iakobi',
    '1Pe': '1petre', '2Pe': '2petre',
    '1Jn': '1ioane', '2Jn': '2ioane', '3Jn': '3ioane',
    'Jude': 'iuda',
    # გამოცხადება
    'Rev': 'apokalips',
}

# დამატებითი შემოკლებები რომლებიც შეიძლება გამოყენებული იყოს
TSK_EXTRA = {
    '1Chr': '1neshtta', '2Chr': '2neshtta',
    '1Sam': '1mepeta', '2Sam': '2mepeta',
    '1Kgs': '3mepeta', '2Kgs': '4mepeta',
    'Gen': 'dabadeba', 'Exod': 'gamosvla',
    'Num': 'ritskhvni', 'Deu': '2rjuli',
    'Pss': 'fsalmunni', 'Psalm': 'fsalmunni',
    'Prov': 'igavni', 'Ecc': 'eklesiaste',
    'Cant': 'qeba', 'Sng': 'qeba',
    'Ezek': 'ezekieli', 'Ezr': '1ezra',
    'Ne': 'neemia', 'Est': 'esteri',
    'Jsh': 'iesonave', 'Jdg': 'msajulni',
    'Rth': 'ruti', 'Jb': 'iobi',
    'Prv': 'igavni', 'Eccl': 'eklesiaste',
    'Sgs': 'qeba', 'Is': 'esaia',
    'Jr': 'ieremia', 'Je': 'ieremia',
    'La': 'godeba', 'Lm': 'godeba',
    'Dn': 'danieli', 'Da': 'danieli',
    'Ho': 'osia', 'Joe': 'ioveli',
    'Am': 'amos', 'Ob': 'abdia',
    'Jnh': 'iona', 'Mc': 'miqa',
    'Na': 'naumi', 'Nb': 'naumi',
    'Hb': 'abakumi', 'Ha': 'abakumi',
    'Zp': 'sofonia', 'Zeph': 'sofonia',
    'Hg': 'angia', 'Zc': 'zaqaria',
    'Ml': 'malaqia', 'Ma': 'malaqia',
    'Mt': 'mate', 'Mat': 'mate',
    'Mr': 'markozi', 'Mar': 'markozi',
    'Lu': 'luka', 'Luk': 'luka',
    'Joh': 'ioane', 'Jn': 'ioane',
    'Act': 'saqme', 'Ac': 'saqme',
    'Rom': 'romaelta', 'Ro': 'romaelta',
    '1Cor': '1korintelta', '2Cor': '2korintelta',
    'Ga': 'galatelta', 'Eph': 'efeselta',
    'Ephes': 'efeselta', 'Phil': 'filipelta',
    'Phl': 'filipelta', 'Col': 'kolaselta',
    '1Thess': '1tesalonikelta', '2Thess': '2tesalonikelta',
    '1Tim': '1timote', '2Tim': '2timote',
    'Ti': 'tite', 'Phm': 'filimoni',
    'Phlm': 'filimoni', 'Heb': 'ebraelta',
    'Jms': 'iakobi', 'Ja': 'iakobi',
    '1Pet': '1petre', '2Pet': '2petre',
    '1Jo': '1ioane', '2Jo': '2ioane', '3Jo': '3ioane',
    'Jud': 'iuda', 'Jd': 'iuda',
    'Re': 'apokalips', 'Rev': 'apokalips',
    'Apoc': 'apokalips',
    # დამატებითი TSKe შემოკლებები
    'De': '2rjuli',
    'Jos': 'iesonave',
    'Tit': 'tite',
    'Ru': 'ruti',
    'Philem': 'filimoni',
}

# გავაერთიანოთ ორივე მაპინგი
ALL_TSK = {**TSK_TO_SLUG, **TSK_EXTRA}


def parse_source_ref(line):
    """{Ge 1:1} -> ('dabadeba', 1, 1) ან None"""
    m = re.match(r'^\{(\w+)\s+(\d+):(\d+)\}$', line.strip())
    if not m:
        return None
    book_abbr, chap, verse = m.group(1), int(m.group(2)), int(m.group(3))
    slug = ALL_TSK.get(book_abbr)
    if not slug:
        return None
    return (slug, chap, verse)


def parse_target_ref(ref_str):
    """
    'Pr_8:22-24' -> {'book': 'igavni', 'chapter': 8, 'vs': 22, 've': 24}
    'Pr_8:22'    -> {'book': 'igavni', 'chapter': 8, 'vs': 22, 've': 22}
    """
    ref_str = ref_str.strip()
    # ფორმატი: Book_Chap:Verse ან Book_Chap:Verse-Verse
    m = re.match(r'^(\w+)_(\d+):(\d+)(?:-(\d+))?$', ref_str)
    if not m:
        return None
    book_abbr = m.group(1)
    chap = int(m.group(2))
    vs = int(m.group(3))
    ve = int(m.group(4)) if m.group(4) else vs
    slug = ALL_TSK.get(book_abbr)
    if not slug:
        return None
    return {'book': slug, 'chapter': chap, 'vs': vs, 've': ve}


def parse_reciprocal_ref(line):
    """
    'Ge_2:1 - Thus' -> {'book': 'dabadeba', 'chapter': 2, 'vs': 1, 've': 1, 'note': 'Thus'}
    """
    # მოვიცილოთ " - text" ნაწილი
    m = re.match(r'^(\w+)_(\d+):(\d+)(?:-(\d+))?\s*-\s*(.*)$', line.strip())
    if not m:
        # შესაძლოა არ აქვს note
        m2 = re.match(r'^(\w+)_(\d+):(\d+)(?:-(\d+))?$', line.strip())
        if not m2:
            return None
        m = m2
        note = ''
    else:
        note = m.group(5) if m.group(5) else ''

    book_abbr = m.group(1)
    chap = int(m.group(2))
    vs = int(m.group(3))
    ve = int(m.group(4)) if m.group(4) else vs
    slug = ALL_TSK.get(book_abbr)
    if not slug:
        return None
    return {'book': slug, 'chapter': chap, 'vs': vs, 've': ve, 'note': note}


def parse_tske(input_path, output_path):
    """TSKe ფაილის პარსინგი და ინდექსის აგება."""

    index = defaultdict(list)
    total_refs = 0
    matched_refs = 0
    skipped_refs = 0
    unknown_books = set()

    current_source = None  # (slug, chap, verse)
    current_topic = None   # თემატური სათაური
    in_reciprocal = False  # reciprocal სექციაში ვართ თუ არა

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            stripped = line.strip()

            # ცარიელი ხაზი - გამოტოვება
            if not stripped:
                continue

            # წყარო მუხლი: {Ge 1:1}
            if stripped.startswith('{') and stripped.endswith('}'):
                src = parse_source_ref(stripped)
                if src:
                    current_source = src
                    current_topic = None
                    in_reciprocal = False
                else:
                    # უცნობი წიგნი - გამოტოვება
                    abbr = re.match(r'\{(\w+)', stripped)
                    if abbr:
                        unknown_books.add(abbr.group(1))
                    current_source = None
                continue

            # როცა წყარო არ არის დადგენილი - გამოტოვება
            if current_source is None:
                continue

            # Reciprocal სექციის დასაწყისი
            if stripped == 'Reciprocal:':
                in_reciprocal = True
                current_topic = 'reciprocal'
                continue

            # თემატური სათაური: "beginning"
            if stripped.startswith('"') and stripped.endswith('"') and not in_reciprocal:
                current_topic = stripped[1:-1]  # მოვიცილოთ ბრჭყალები
                continue

            # დაკავშირებული მუხლების ხაზი
            # ფორმატი: Book_Chap:Verse, Book_Chap:Verse ან Book_Chap:Verse-Verse

            if in_reciprocal:
                # Reciprocal: Book_Chap:Verse - note
                ref = parse_reciprocal_ref(stripped)
                if ref:
                    src_key = f"{current_source[0]}:{current_source[1]}:{current_source[2]}"
                    index[src_key].append({
                        'book': ref['book'],
                        'chapter': ref['chapter'],
                        'vs': ref['vs'],
                        've': ref['ve'],
                        'topic': 'reciprocal',
                        'type': 'reciprocal',
                        'source': 'tsk',
                        'note': ref.get('note', ''),
                    })
                    matched_refs += 1
                else:
                    skipped_refs += 1
                    # უცნობი წიგნის შემოკლების ამოღება
                    abbr_m = re.match(r'^(\w+)_', stripped)
                    if abbr_m:
                        unknown_books.add(abbr_m.group(1))
            else:
                # ჩვეულებრივი თემატური ჯაჭვი
                # ხაზი შეიძლება შეიცავდეს მრავალ რეფერენსს, მძიმით გამოყოფილი
                # მაგრამ მძიმი არის მხოლოდ ერთ ხაზში, არა მრავალ ხაზში
                # თითო ხაზი შეიძლება შეიცავდეს ერთ ან მრავალ რეფერენსს
                parts = stripped.split(',')
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    ref = parse_target_ref(part)
                    if ref:
                        src_key = f"{current_source[0]}:{current_source[1]}:{current_source[2]}"
                        index[src_key].append({
                            'book': ref['book'],
                            'chapter': ref['chapter'],
                            'vs': ref['vs'],
                            've': ref['ve'],
                            'topic': current_topic or 'general',
                            'type': 'thematic',
                            'source': 'tsk',
                        })
                        matched_refs += 1
                    else:
                        skipped_refs += 1
                        abbr_m = re.match(r'^(\w+)_', part)
                        if abbr_m:
                            unknown_books.add(abbr_m.group(1))

            total_refs += 1

    # დედუპლიკაცია - თუ იგივე მუხლი რამდენჯერმე არის სხვადასხვა თემით,
    # დავტოვოთ ყველა, მაგრამ არა ზუსტად იგივე (წიგნი+თავი+მუხლი+თემა)
    for key in index:
        seen = set()
        unique = []
        for ref in index[key]:
            ref_id = f"{ref['book']}:{ref['chapter']}:{ref['vs']}:{ref['ve']}:{ref['topic']}"
            if ref_id not in seen:
                seen.add(ref_id)
                unique.append(ref)
        index[key] = unique

    # სტატისტიკა
    total_chains = sum(len(v) for v in index.values())
    thematic = sum(1 for v in index.values() for r in v if r['type'] == 'thematic')
    reciprocal = sum(1 for v in index.values() for r in v if r['type'] == 'reciprocal')

    print(f"\n=== TSKe პარსინგის შედეგი ===")
    print(f"წყარო მუხლები: {len(index):,}")
    print(f"სულ ჯაჭვი: {total_chains:,}")
    print(f"  თემატური: {thematic:,}")
    print(f"  ორმხრივი (reciprocal): {reciprocal:,}")
    print(f"დამთხვევა: {matched_refs:,}")
    print(f"გამოტოვებული: {skipped_refs:,}")

    if unknown_books:
        print(f"\nუცნობი შემოკლებები ({len(unknown_books)}):")
        for abbr in sorted(unknown_books)[:20]:
            print(f"  {abbr}")

    # თემატური კატეგორიების სტატისტიკა
    from collections import Counter
    topics = Counter()
    for refs in index.values():
        for r in refs:
            topics[r['topic']] += 1
    print(f"\n=== ტოპ 10 თემატური კატეგორია ===")
    for topic, count in topics.most_common(10):
        print(f"  {topic}: {count:,}")

    # შენახვა
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dict(index), f, ensure_ascii=False, separators=(',', ':'))

    size_mb = Path(output_path).stat().st_size / 1024 / 1024
    print(f"\nშენახულია: {output_path} ({size_mb:.1f} მბ)")

    return index


if __name__ == '__main__':
    input_path = 'data/crossrefs/tske_raw.txt'
    output_path = 'data/crossrefs_tsk.json'
    parse_tske(input_path, output_path)
