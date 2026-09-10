#!/usr/bin/env python3
"""
აპლიკაციას უკეთებს data/manual_ka.json-დან ხელით თარგმანებს.
გადაფარავს ტრანსლიტერაციის თარგმანებს უკეთესი ხელით თარგმანებით.

გაშვება: python3 apply_manual.py
ინახავს პროგრესს - გათიშვის შემთხვევაში შეიძლება ხელახლა გაშვება.
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAPPING_FILE = os.path.join(DATA_DIR, "topic_names_ka.json")
MANUAL_FILE = os.path.join(DATA_DIR, "manual_ka.json")


def main():
    if not os.path.exists(MANUAL_FILE):
        print(f"ფაილი არ არსებობს: {MANUAL_FILE}")
        return

    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manual = json.load(f)

    updated = 0
    added = 0
    for slug, ka in manual.items():
        if slug in mapping:
            if mapping[slug] != ka:
                mapping[slug] = ka
                updated += 1
        else:
            mapping[slug] = ka
            added += 1

    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"განახლდა: {updated}, დაემატა: {added}")
    print(f"სულ დაფარული: {len(mapping)}")


if __name__ == "__main__":
    main()
