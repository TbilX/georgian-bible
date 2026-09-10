#!/usr/bin/env python3
"""
audit_data_files.py
===================
data/ ფაილების სტრუქტურული აუდიტი.

იმოძიერებს:
- რა ტიპისაა (dict/list)
- რამდენი ჩანაწერია
- ზომა
- პირველი 3 ნიმუში
- მთავარი სახელწოდებები

გამოყენება:
    python3 audit_data_files.py
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

FILES = [
    "bible_word_groups.json",
    "crossrefs_index.json",
    "crossrefs_merged.json",
    "crossrefs_tsk.json",
    "lexicon.json",
    "manual_ka.json",
    "typo_report.json",
    "ud_lemma_lexicon.json",
    "verses.json",
    "verse_index.json",
    "crossrefs_tsk.json",
    "topical_index.json",
    "topic_names_ka.json",
    "topic_labels_ka.json",
    "theology_terms_fix.json",
    "label_fixes.json",
]


def format_value(v, max_len=120):
    """მნიშვნელობის მოკლე რეპრეზენტაცია."""
    s = str(v)
    if len(s) > max_len:
        s = s[:max_len] + "..."
    return s


def inspect_file(path):
    """ერთი ფაილის აუდიტი."""
    filename = path.name
    size_bytes = path.stat().st_size
    size_mb = size_bytes / 1024 / 1024

    print(f"\n{'='*70}")
    print(f"📄 {filename}")
    print(f"   ზომა: {size_bytes:,} bytes ({size_mb:.2f} MB)")

    try:
        # დიდი ფაილებისთვის შეზღუდვითი ჩატვირთვა
        if size_mb > 50:
            print("   დიდი ფაილი - იტვირთება სტრუქტურულად...")
            with open(path, "r", encoding="utf-8") as f:
                # პირველი 500 სიმბოლო, რომ დავინახოთ ტიპი
                preview = f.read(500)
            print(f"   პრევიუ: {preview[:200]}")
            # სრულად არ ვტვირთავთ
            print("   ⚠️  50MB+ - სრულად არ ჩაიტვირთა აუდიტისთვის")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"   ❌ ჩატვირთვის შეცდომა: {e}")
        return

    if isinstance(data, dict):
        print(f"   ტიპი: dict, გასაღებები: {len(data):,}")
        keys = list(data.keys())[:3]
        for k in keys:
            v = data[k]
            print(f"   გასაღები '{k}':")
            print(f"      {format_value(v)}")
    elif isinstance(data, list):
        print(f"   ტიპი: list, ელემენტები: {len(data):,}")
        if data:
            for i, item in enumerate(data[:3]):
                print(f"   ელემენტი [{i}]:")
                print(f"      {format_value(item)}")
    elif isinstance(data, str):
        print(f"   ტიპი: string, სიგრძე: {len(data):,}")
        print(f"      {data[:200]}")
    else:
        print(f"   ტიპი: {type(data).__name__}, მნიშვნელობა: {format_value(data)}")


def main():
    print("=== data/ ფაილების სტრუქტურული აუდიტი ===")

    for filename in FILES:
        path = DATA_DIR / filename
        if not path.exists():
            print(f"\n📄 {filename}")
            print("   ❌ ფაილი არ არსებობს")
            continue

        inspect_file(path)


if __name__ == "__main__":
    main()
