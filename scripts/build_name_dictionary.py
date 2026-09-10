#!/usr/bin/env python3
"""
build_name_dictionary.py
========================
ინგლისური -> ქართული სახელების ლექსიკონის აგება ლოკალური რესურსებისგან.

წყაროები:
- data/topic_names_ka.json (თემატური სახელების ქართული თარგმანი)
- data/manual_ka.json (ხელით კურირებული ქართული)
- data/lexicon.json (ლექსიკონი - თუ აქვს EN->KA mapping)
- data/verses.json (ბიბლიის ტექსტი - კონტექსტისთვის)

გამოყენება:
    python3 build_name_dictionary.py
"""

import json
import re
import os
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def is_good_ka(value):
    """თარგმანი ითვლება სწორად, თუ არ შეიცავს ლათინურ ასოებს."""
    if not value or not isinstance(value, str):
        return False
    return not re.search(r'[A-Za-z]', value)


def build_dictionary():
    """კომბინირებული ლექსიკონის აგება."""
    dictionary = {}
    sources = Counter()

    # წყარო 1: topic_names_ka.json
    with open(DATA_DIR / "topic_names_ka.json", "r", encoding="utf-8") as f:
        topic_names = json.load(f)

    with open(DATA_DIR / "topical_index.json", "r", encoding="utf-8") as f:
        topical = json.load(f)

    for topic in topical["topics"]:
        slug = topic.get("slug", "")
        if not slug:
            continue
        name_ka = topic_names.get(slug, "")
        if not is_good_ka(name_ka):
            continue

        # რამდენიმე form: lowercase, capitalized, original
        en_forms = [slug, slug.lower(), slug.title()]
        for en in en_forms:
            if en not in dictionary or sources[en] == "topic_names":
                dictionary[en] = name_ka
                sources[en] = "topic_names"

    # წყარო 2: manual_ka.json
    with open(DATA_DIR / "manual_ka.json", "r", encoding="utf-8") as f:
        manual = json.load(f)

    for en, ka in manual.items():
        if not is_good_ka(ka):
            continue
        en_key = en.lower().strip()
        if en_key not in dictionary:
            dictionary[en_key] = ka
            sources[en_key] = "manual_ka"

    # წყარო 3: lexicon.json (სცადეთ)
    # lexicon.json 87MB-ია, შესაძლოა იტვირთოს? სცადეთ გასაღების იტერაცია
    try:
        with open(DATA_DIR / "lexicon.json", "r", encoding="utf-8") as f:
            lexicon = json.load(f)
        # მხოლოდ პირველი 1000 ელემენტის შემოწმება დროის/მეხსიერების ეკონომიისთვის
        count = 0
        for word, info in lexicon.items():
            if not isinstance(info, dict):
                continue
            # ვეძებთ ინგლისურ დადგენილებას
            en = info.get("en") or info.get("english") or info.get("translation")
            ka = info.get("ka") or info.get("georgian") or word
            if en and ka and is_good_ka(ka):
                en_key = en.lower().strip()
                if en_key not in dictionary:
                    dictionary[en_key] = ka
                    sources[en_key] = "lexicon"
            count += 1
            if count >= 1000:
                break
    except Exception as e:
        print(f"lexicon.json ჩატვირთვის გამოტოვება: {e}")

    print(f"=== ლექსიკონი აშენებულია ===")
    print(f"სულ წოლები: {len(dictionary):,}")
    print(f"  topic_names: {sum(1 for s in sources.values() if s == 'topic_names')}")
    print(f"  manual_ka: {sum(1 for s in sources.values() if s == 'manual_ka')}")
    print(f"  lexicon: {sum(1 for s in sources.values() if s == 'lexicon')}")

    # შევინახოთ
    out_path = DATA_DIR / "name_dictionary_ka.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)
    print(f"შენახულია: {out_path}")

    return dictionary


def main():
    build_dictionary()


if __name__ == "__main__":
    main()
