#!/usr/bin/env python3
"""ფაზა 4: სტატისტიკური ამოღება მუხლებიდან დარჩენილი სახელებისთვის."""
import json
import os
import re
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_verse_texts():
    with open(os.path.join(DATA_DIR, "verses.json"), "r", encoding="utf-8") as f:
        verses = json.load(f)
    verse_lookup = {}
    for v in verses:
        key = (v["book_slug"], v["chapter"], v["verse"])
        verse_lookup[key] = v.get("new", "")
    return verse_lookup


def extract_name_from_verses(slug, topical, verse_lookup, current_name):
    """სტატისტიკური ამოღება: ვპოვებთ სახელს მუხლებიდან."""
    topic = next((t for t in topical["topics"] if t["slug"] == slug), None)
    if not topic:
        return None

    all_verses = []
    for entry in topic.get("entries", []):
        for ref in entry.get("verses", []):
            key = (ref["book"], ref["chapter"], ref["vs"])
            text = verse_lookup.get(key, "")
            if text:
                all_verses.append(text)

    if not all_verses:
        return None

    # ამჟამინდელი სახელის ფუძე (ჰ-ის გარეშე)
    current_root = current_name.replace("ჰ", "").replace("ი", "")
    if len(current_root) < 3:
        return None

    # ვეძებთ სიტყვებს რომლებიც ჰგავს ფუძეს
    word_counts = Counter()
    for text in all_verses[:100]:
        words = re.findall(r"[ა-ჰ]{3,}", text)
        for w in words:
            # ფუძის შედარება
            w_root = w.rstrip("ისმთშიგადნლრ")
            if len(w_root) >= 3 and w_root[:3] == current_root[:3]:
                word_counts[w] += 1

    if not word_counts:
        return None

    # ყველაზე ხშირი ფორმა
    best = word_counts.most_common(1)[0][0]
    # გადავამოწმოთ რომ არ არის საერთო სიტყვა
    common_words = {
        "რომ", "იყო", "ხოლო", "მისი", "უფალი", "ღმერთი", "იესო",
        "ქრისტე", "ისრაელ", "იერუსალიმ", "დავით", "მოსე",
        "აბრაამ", "იაკობ", "ისააკ", "სოლომონ", "საული",
        "ესავ", "იოსებ", "იოანე", "პეტრე", "პავლე",
    }
    if best in common_words:
        return None

    return best


def main():
    print("=== ფაზა 4: სტატისტიკური ამოღება ===\n")

    with open(os.path.join(DATA_DIR, "topic_names_ka.json"), "r", encoding="utf-8") as f:
        topics = json.load(f)

    with open(os.path.join(DATA_DIR, "topical_index.json"), "r", encoding="utf-8") as f:
        topical = json.load(f)

    verse_lookup = load_verse_texts()

    fixed = 0
    not_found = 0

    for slug, val in topics.items():
        if val.startswith(("I ", "II ", "III ", "IV ")):
            continue

        # მხოლოდ პრობლემური
        if "ჰ" not in val and "ჩ" not in val:
            continue

        # სტატისტიკური ამოღება
        suggested = extract_name_from_verses(slug, topical, verse_lookup, val)
        if suggested and suggested != val and len(suggested) >= 3:
            topics[slug] = suggested
            fixed += 1
            print(f"  [სტატისტიკა] {slug:45s} '{val}' -> '{suggested}'")
        else:
            not_found += 1

    # შენახვა
    with open(os.path.join(DATA_DIR, "topic_names_ka.json"), "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

    # სტატისტიკა
    remaining = 0
    for val in topics.values():
        if val.startswith(("I ", "II ", "III ", "IV ")):
            continue
        if "ჰ" in val or "ჩ" in val:
            remaining += 1

    print(f"\n=== შედეგი ===")
    print(f"სტატისტიკით გასწორდა: {fixed}")
    print(f"ვერ მოიძებნა: {not_found}")
    print(f"დარჩენილი პრობლემური: {remaining}")


if __name__ == "__main__":
    main()
