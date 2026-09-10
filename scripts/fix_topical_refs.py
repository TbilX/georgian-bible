#!/usr/bin/env python3
"""
fix_topical_refs.py
===================
თემატური ენციკლოპედიის რეფერენსების კორექცია:
1. ფსალმუნების ებრაული -> LXX (ქართული) ნუმერაციის კონვერტაცია
2. მუხლების დიაპაზონის შემოჭრა (clip) რეალურ მაქსიმუმამდე (მონაცემთა შეცდომების გასწორება)
3. by_verse ინდექსის ხელახლა აგება

გამოყენება:
    python3 fix_topical_refs.py           # კორექცია + შემოწმება
    python3 fix_topical_refs.py --apply   # კორექცია + შენახვა
"""

import json
import sys
import os
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TOPICAL_FILE = DATA_DIR / "topical_index.json"
VERSE_INDEX_FILE = DATA_DIR / "verse_index.json"


def load_verse_index():
    """ქართული ბიბლიის მუხლების ინდექსის ჩატვირთვა."""
    with open(VERSE_INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_chapter_max_verses(verse_index):
    """თითო წიგნის თითო თავის მაქსიმალური მუხლის ნომერი."""
    max_verses = defaultdict(lambda: defaultdict(int))
    for v in verse_index:
        max_verses[v["book_slug"]][v["chapter"]] = max(
            max_verses[v["book_slug"]][v["chapter"]],
            v["verse"],
        )
    return max_verses


def build_bible_verse_set(verse_index):
    """ქართული ბიბლიის მუხლების სეტი (book, chapter, verse)."""
    verses = set()
    for v in verse_index:
        verses.add((v["book_slug"], v["chapter"], v["verse"]))
    return verses


# === ფსალმუნების ებრაული -> LXX კონვერტაცია ===
# წყარო: https://en.wikipedia.org/wiki/Psalms#Numbering
#
# ებრაული (Masoretic) -> LXX (Septuagint, ქართული ბიბლია)
#
# ფსალმუნები 1-8: იდენტურია
# ფსალმუნი 9+10 (ებრ.) -> ფსალმუნი 9 (LXX)
# ფსალმუნები 11-113 (ებრ.) -> 10-112 (LXX)
# ფსალმუნი 114+115 (ებრ.) -> ფსალმუნი 113 (LXX)
# ფსალმუნი 116 (ებრ.) -> ფსალმუნი 114+115 (LXX)
# ფსალმუნები 117-146 (ებრ.) -> 116-145 (LXX)
# ფსალმუნი 147 (ებრ.) -> ფსალმუნი 146+147 (LXX)
# ფსალმუნები 148-150: იდენტურია

# LXX ფსალმუნი 9-ის მუხლების რაოდენობა (ქართული ბიბლიის მიხედვით)
# ებრაული 9-ს აქვს 20 მუხლი, ებრაული 10-ს 18 -> სულ 38
# LXX 9-ს აქვს 39 მუხლი (დამატებით 1 - სათაური ან განსხვავებული დაყოფა)
# ებრაული 10:1 -> LXX 9:22 (offset 21, რადგან LXX 9-ს აქვს 21-ე მუხლამდე ებრაული 9-ის შინაარსი + დამატებითი მუხლი)

HEBREW_PSALM_9_COUNT = 20  # ებრაული ფსალმუნი 9-ის მუხლები
LXX_PSALM_9_OFFSET = HEBREW_PSALM_9_COUNT + 1  # 21 (LXX 9-ს აქვს დამატებითი მუხლი)

HEBREW_PSALM_114_COUNT = 8  # ებრაული ფსალმუნი 114-ის მუხლები
HEBREW_PSALM_116_SPLIT = 9  # ებრაული 116:1-9 -> LXX 114, 116:10+ -> LXX 115
HEBREW_PSALM_147_SPLIT = 11  # ებრაული 147:1-11 -> LXX 146, 147:12+ -> LXX 147

# === მალაქიას კონვერტაცია ===
# ებრაული მალაქია თავი 4 (6 მუხლი) -> LXX მალაქია თავი 3:19-24
# ქართულ ბიბლიაში მალაქიას 3 თავია (LXX), ებრაული თავი 4 = LXX თავი 3:19-24
MALACHI_HEB_CH4_TO_LXX_CH3 = 3
MALACHI_HEB_CH4_OFFSET = 18  # ებრ. 4:1 -> LXX 3:19 (1+18=19)

# === ნეემიას კონვერტაცია ===
# ებრაული ნეემია 4:18-23 -> LXX ნეემია 4:33-38 (offset +15)
# ქართულ ბიბლიაში ნეემია 4-ს აქვს მუხლები 1-17, 33-38 (18-32 გამოტოვებულია)
NEHEMIAH_CH4_OFFSET = 15  # ებრ. 4:18 -> LXX 4:33
NEHEMIAH_CH4_START = 18   # დასაწყისი ებრაული მუხლი რომელსაც სჭირდება კონვერტაცია


def hebrew_to_lxx_psalm(heb_ch, heb_vs):
    """ებრაული ფსალმუნის რეფერენსი -> LXX (ქართული) ნუმერაცია.

    აბრუნებს (lxx_ch, lxx_vs) ან None თუ კონვერტაცია შეუძლებელია.
    თუ მუხლის დიაპაზონი გადადის ერთ LXX თავიდან მეორეში, აბრუნებს (lxx_ch1, lxx_vs1, lxx_ch2, lxx_vs2).
    """
    # ფსალმუნები 1-8: იდენტურია
    if heb_ch <= 8:
        return (heb_ch, heb_vs)

    # ფსალმუნი 9 (ებრ.) -> ფსალმუნი 9 (LXX), პირდაპირ
    if heb_ch == 9:
        return (9, heb_vs)

    # ფსალმუნი 10 (ებრ.) -> ფსალმუნი 9 (LXX), offset
    if heb_ch == 10:
        return (9, heb_vs + LXX_PSALM_9_OFFSET)

    # ფსალმუნები 11-113 (ებრ.) -> 10-112 (LXX)
    if 11 <= heb_ch <= 113:
        return (heb_ch - 1, heb_vs)

    # ფსალმუნი 114 (ებრ.) -> ფსალმუნი 113 (LXX)
    if heb_ch == 114:
        return (113, heb_vs)

    # ფსალმუნი 115 (ებრ.) -> ფსალმუნი 113 (LXX), offset
    if heb_ch == 115:
        return (113, heb_vs + HEBREW_PSALM_114_COUNT)

    # ფსალმუნი 116 (ებრ.) -> ფსალმუნი 114 ან 115 (LXX)
    if heb_ch == 116:
        if heb_vs <= HEBREW_PSALM_116_SPLIT:
            return (114, heb_vs)
        else:
            return (115, heb_vs - HEBREW_PSALM_116_SPLIT)

    # ფსალმუნები 117-146 (ებრ.) -> 116-145 (LXX)
    if 117 <= heb_ch <= 146:
        return (heb_ch - 1, heb_vs)

    # ფსალმუნი 147 (ებრ.) -> ფსალმუნი 146 ან 147 (LXX)
    if heb_ch == 147:
        if heb_vs <= HEBREW_PSALM_147_SPLIT:
            return (146, heb_vs)
        else:
            return (147, heb_vs - HEBREW_PSALM_147_SPLIT)

    # ფსალმუნები 148-150: იდენტურია
    if 148 <= heb_ch <= 150:
        return (heb_ch, heb_vs)

    # ფსალმუნი 151 (მხოლოდ LXX-ში, ებრაულში არ არის)
    return None


def convert_psalm_verse_range(book, ch, vs, ve):
    """ფსალმუნის მუხლის დიაპაზონის კონვერტაცია.

    აბრუნებს list of (chapter, vs, ve) კონვერტირებული დიაპაზონების.
    თუ დიაპაზონი გადადის ერთ LXX თავიდან მეორეში, იყოფა.
    """
    if book != "fsalmunni":
        return [(ch, vs, ve)]

    # თუ დიაპაზონი ერთ ებრაულ თავშია
    result_start = hebrew_to_lxx_psalm(ch, vs)
    result_end = hebrew_to_lxx_psalm(ch, ve)

    if result_start is None or result_end is None:
        return [(ch, vs, ve)]  # ვერ გადავცვალეთ, დავტოვოთ როგორცაა

    start_ch, start_vs = result_start
    end_ch, end_vs = result_end

    # თუ ორივე ერთ LXX თავშია
    if start_ch == end_ch:
        return [(start_ch, start_vs, end_vs)]

    # თუ დიაპაზონი გადადის თავებს შორის (მაგ: ებრ. 116:5-12 -> LXX 114:5 + 115:1-3)
    # ვპოულობთ საზღვარს
    if ch == 116 and start_ch == 114 and end_ch == 115:
        # ებრ. 116:vs-9 -> LXX 114:vs-9, ებრ. 116:10-ve -> LXX 115:1-(ve-9)
        parts = []
        if vs <= HEBREW_PSALM_116_SPLIT:
            parts.append((114, vs, HEBREW_PSALM_116_SPLIT))
        if ve > HEBREW_PSALM_116_SPLIT:
            parts.append((115, 1, ve - HEBREW_PSALM_116_SPLIT))
        return parts

    if ch == 147 and start_ch == 146 and end_ch == 147:
        # ებრ. 147:vs-11 -> LXX 146:vs-11, ებრ. 147:12-ve -> LXX 147:1-(ve-11)
        parts = []
        if vs <= HEBREW_PSALM_147_SPLIT:
            parts.append((146, vs, HEBREW_PSALM_147_SPLIT))
        if ve > HEBREW_PSALM_147_SPLIT:
            parts.append((147, 1, ve - HEBREW_PSALM_147_SPLIT))
        return parts

    # სხვა შემთხვევა (უნდა არ მოხდეს, მაგრამ სიფრთხილისთვის)
    return [(start_ch, start_vs, end_vs)]


def clip_verse_range(book, ch, vs, ve, max_verses):
    """მუხლის დიაპაზონის შემოჭრა რეალურ მაქსიმუმამდე.

    აბრუნებს (ch, vs, ve) ან None თუ თავი არ არსებობს.
    """
    ch_max = max_verses.get(book, {}).get(ch, 0)
    if ch_max == 0:
        return None  # თავი არ არსებობს ქართულ ბიბლიაში
    if vs > ch_max:
        return None  # დასაწყისი მუხლი არ არსებობს
    # შემოვჭრათ დასრულება
    ve = min(ve, ch_max)
    return (ch, vs, ve)


def fix_topical_index(topical_index, max_verses, bible_verses):
    """თემატური ინდექსის კორექცია.

    აბრუნებს (fixed_index, stats_dict).
    """
    stats = {
        "psalm_converted": 0,
        "psalm_split": 0,
        "clipped": 0,
        "dropped_no_chapter": 0,
        "dropped_no_verse": 0,
        "total_verses_before": 0,
        "total_verses_after": 0,
    }

    topics = topical_index["topics"]
    verse_to_topics = defaultdict(set)

    for topic in topics:
        new_entries = []
        for entry in topic.get("entries", []):
            new_verses = []
            for v in entry.get("verses", []):
                book = v["book"]
                ch = v["chapter"]
                vs = v["vs"]
                ve = v["ve"]
                stats["total_verses_before"] += 1

                # ნაბიჯი 1: ფსალმუნების კონვერტაცია ებრაული -> LXX
                if book == "fsalmunni":
                    converted = convert_psalm_verse_range(book, ch, vs, ve)
                    if len(converted) > 1:
                        stats["psalm_split"] += 1
                    if converted[0] != (ch, vs, ve):
                        stats["psalm_converted"] += 1
                    # დავამატოთ ყველა კონვერტირებული ნაწილი
                    for conv_ch, conv_vs, conv_ve in converted:
                        # ნაბიჯი 2: შემოჭრა
                        clipped = clip_verse_range(book, conv_ch, conv_vs, conv_ve, max_verses)
                        if clipped is None:
                            stats["dropped_no_chapter"] += 1
                            continue
                        clip_ch, clip_vs, clip_ve = clipped
                        if clip_ve < clip_vs:
                            stats["dropped_no_verse"] += 1
                            continue
                        if (clip_ch, clip_vs, clip_ve) != (conv_ch, conv_vs, conv_ve):
                            stats["clipped"] += 1
                        new_verses.append({
                            "book": book,
                            "chapter": clip_ch,
                            "vs": clip_vs,
                            "ve": clip_ve,
                        })
                        stats["total_verses_after"] += 1
                        # by_verse ინდექსი
                        for vv in range(clip_vs, clip_ve + 1):
                            verse_to_topics[f"{book}:{clip_ch}:{vv}"].add(topic["slug"])
                    continue

                # ნაბიჯი 1b: მალაქიას კონვერტაცია ებრაული თავი 4 -> LXX თავი 3
                if book == "malaqia" and ch == 4:
                    stats["psalm_converted"] += 1  # ვიყენებთ იმავე სტატისტიკას
                    new_ch = MALACHI_HEB_CH4_TO_LXX_CH3
                    new_vs = vs + MALACHI_HEB_CH4_OFFSET
                    new_ve = ve + MALACHI_HEB_CH4_OFFSET
                    clipped = clip_verse_range(book, new_ch, new_vs, new_ve, max_verses)
                    if clipped is None:
                        stats["dropped_no_chapter"] += 1
                        continue
                    clip_ch, clip_vs, clip_ve = clipped
                    if clip_ve < clip_vs:
                        stats["dropped_no_verse"] += 1
                        continue
                    new_verses.append({
                        "book": book,
                        "chapter": clip_ch,
                        "vs": clip_vs,
                        "ve": clip_ve,
                    })
                    stats["total_verses_after"] += 1
                    for vv in range(clip_vs, clip_ve + 1):
                        verse_to_topics[f"{book}:{clip_ch}:{vv}"].add(topic["slug"])
                    continue

                # ნაბიჯი 1c: ნეემიას კონვერტაცია ებრ. 4:18+ -> LXX 4:33+
                # დიაპაზონები რომლებიც გადაკვეთენ საზღვარს (vs<18, ve>=18) იყოფა
                if book == "neemia" and ch == 4 and ve >= NEHEMIAH_CH4_START:
                    stats["psalm_converted"] += 1
                    parts = []
                    if vs < NEHEMIAH_CH4_START:
                        # ნაწილი 1: vs-დან 17-მდე (ნორმალური)
                        parts.append((ch, vs, NEHEMIAH_CH4_START - 1))
                        # ნაწილი 2: 18+15-დან ve+15-მდე (კონვერტირებული)
                        parts.append((ch, NEHEMIAH_CH4_START + NEHEMIAH_CH4_OFFSET,
                                      ve + NEHEMIAH_CH4_OFFSET))
                    else:
                        # მთლიანად კონვერტირებული
                        parts.append((ch, vs + NEHEMIAH_CH4_OFFSET,
                                      ve + NEHEMIAH_CH4_OFFSET))
                    for part_ch, part_vs, part_ve in parts:
                        clipped = clip_verse_range(book, part_ch, part_vs, part_ve, max_verses)
                        if clipped is None:
                            stats["dropped_no_chapter"] += 1
                            continue
                        clip_ch, clip_vs, clip_ve = clipped
                        if clip_ve < clip_vs:
                            stats["dropped_no_verse"] += 1
                            continue
                        new_verses.append({
                            "book": book,
                            "chapter": clip_ch,
                            "vs": clip_vs,
                            "ve": clip_ve,
                        })
                        stats["total_verses_after"] += 1
                        for vv in range(clip_vs, clip_ve + 1):
                            verse_to_topics[f"{book}:{clip_ch}:{vv}"].add(topic["slug"])
                    continue

                # ნაბიჯი 2: არა-ფსალმუნი წიგნები - მხოლოდ შემოჭრა
                clipped = clip_verse_range(book, ch, vs, ve, max_verses)
                if clipped is None:
                    stats["dropped_no_chapter"] += 1
                    continue
                clip_ch, clip_vs, clip_ve = clipped
                if clip_ve < clip_vs:
                    stats["dropped_no_verse"] += 1
                    continue
                if (clip_ch, clip_vs, clip_ve) != (ch, vs, ve):
                    stats["clipped"] += 1
                new_verses.append({
                    "book": book,
                    "chapter": clip_ch,
                    "vs": clip_vs,
                    "ve": clip_ve,
                })
                stats["total_verses_after"] += 1
                # by_verse ინდექსი
                for vv in range(clip_vs, clip_ve + 1):
                    verse_to_topics[f"{book}:{clip_ch}:{vv}"].add(topic["slug"])

            if new_verses:
                new_entries.append({
                    "label": entry.get("label", ""),
                    "verses": new_verses,
                })

        topic["entries"] = new_entries
        # გადავთვალოთ verse_count
        topic["verse_count"] = sum(len(e["verses"]) for e in new_entries)

    # by_verse ინდექსის ხელახლა აგება
    by_verse = {}
    for key, slugs in verse_to_topics.items():
        by_verse[key] = sorted(slugs)

    topical_index["by_verse"] = by_verse

    # by_slug ინდექსი უცვლელია (თემების რაოდენობა არ შეიცვალა)

    # match rate შემოწმება
    match_count = 0
    total_refs = 0
    for key in by_verse.keys():
        parts = key.split(":")
        book = parts[0]
        ch = int(parts[1])
        vs = int(parts[2])
        total_refs += 1
        if (book, ch, vs) in bible_verses:
            match_count += 1

    stats["match_rate"] = match_count / total_refs * 100 if total_refs > 0 else 100
    stats["by_verse_count"] = len(by_verse)
    stats["total_refs"] = total_refs
    stats["matched_refs"] = match_count

    return topical_index, stats


def main():
    apply = "--apply" in sys.argv

    print("=== თემატური ენციკლოპედიის რეფერენსების კორექცია ===")
    print()

    # მონაცემების ჩატვირთვა
    print("ქართული ბიბლიის ინდექსის ჩატვირთვა...")
    verse_index = load_verse_index()
    max_verses = build_chapter_max_verses(verse_index)
    bible_verses = build_bible_verse_set(verse_index)
    print(f"  მუხლები: {len(bible_verses):,}")

    print("თემატური ინდექსის ჩატვირთვა...")
    with open(TOPICAL_FILE, "r", encoding="utf-8") as f:
        topical_index = json.load(f)
    print(f"  თემები: {len(topical_index['topics']):,}")
    print(f"  by_verse: {len(topical_index['by_verse']):,}")
    print()

    # კორექციამდე მატჩის შემოწმება
    old_match = 0
    old_total = 0
    for key in topical_index["by_verse"].keys():
        parts = key.split(":")
        book = parts[0]
        ch = int(parts[1])
        vs = int(parts[2])
        old_total += 1
        if (book, ch, vs) in bible_verses:
            old_match += 1
    old_rate = old_match / old_total * 100 if old_total > 0 else 100
    print(f"კორექციამდე: {old_match}/{old_total} = {old_rate:.1f}%")
    print()

    # კორექცია
    print("კორექციის შესრულება...")
    fixed_index, stats = fix_topical_index(topical_index, max_verses, bible_verses)

    print()
    print("=== შედეგები ===")
    print(f"  ფსალმუნის კონვერტირებული რეფერენსი: {stats['psalm_converted']}")
    print(f"  ფსალმუნის გაყოფილი დიაპაზონი: {stats['psalm_split']}")
    print(f"  შემოჭრილი დიაპაზონი: {stats['clipped']}")
    print(f"  გამოტოვებული (თავი არ არსებობს): {stats['dropped_no_chapter']}")
    print(f"  გამოტოვებული (მუხლი არ არსებობს): {stats['dropped_no_verse']}")
    print(f"  მუხლის რეფერენსი კორექციამდე: {stats['total_verses_before']}")
    print(f"  მუხლის რეფერენსი კორექციის შემდეგ: {stats['total_verses_after']}")
    print()
    print(f"  by_verse ზომა: {stats['by_verse_count']:,}")
    print(f"  მატჩი: {stats['matched_refs']}/{stats['total_refs']} = {stats['match_rate']:.1f}%")
    print()

    if stats["match_rate"] < 99.0:
        print("ყურადღება: მატჩი 99%-ზე ნაკლებია. ვნახოთ დარჩენილი პრობლემები:")
        remaining = []
        for key in fixed_index["by_verse"].keys():
            parts = key.split(":")
            book = parts[0]
            ch = int(parts[1])
            vs = int(parts[2])
            if (book, ch, vs) not in bible_verses:
                remaining.append((book, ch, vs))
        from collections import Counter
        rem_by_book = Counter(b for b, c, v in remaining)
        for book, cnt in rem_by_book.most_common(10):
            print(f"    {book}: {cnt}")

    if apply:
        # სარეზერვო ასლი
        backup = TOPICAL_FILE.with_suffix(".json.bak2")
        print(f"\nსარეზერვო ასლი: {backup}")
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(topical_index, f, ensure_ascii=False)

        print(f"შენახვა: {TOPICAL_FILE}")
        with open(TOPICAL_FILE, "w", encoding="utf-8") as f:
            json.dump(fixed_index, f, ensure_ascii=False)
        print("შენახულია.")
    else:
        print("\n--apply გარეშე: ცვლილებები არ შენახულა.")
        print("გასაშვებად: python3 fix_topical_refs.py --apply")


if __name__ == "__main__":
    main()
