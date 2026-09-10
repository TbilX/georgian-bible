#!/usr/bin/env python3
"""
fix_topic_names.py
==================
თემატური ენციკლოპედიის სათაურების ქართული თარგმანის გასწორება.

იყენებს data/theology_terms_fix.json ხელით კურირებულ ლექსიკონს
საღვთისმეტყველო ტერმინების სწორი ქართული თარგმანებისთვის.

გამოყენება:
    python3 fix_topic_names.py           # შემოწმება (dry-run)
    python3 fix_topic_names.py --apply   # შენახვა
"""

import json
import sys
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
NAMES_FILE = DATA_DIR / "topic_names_ka.json"
FIX_FILE = DATA_DIR / "theology_terms_fix.json"


def main():
    apply = "--apply" in sys.argv

    print("=== თემის სათაურების ქართული თარგმანის გასწორება ===")
    print()

    # ჩატვირთვა
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        names_ka = json.load(f)
    print(f"  არსებული თარგმანები: {len(names_ka):,}")

    with open(FIX_FILE, "r", encoding="utf-8") as f:
        fix_dict = json.load(f)
    # _comment გასაღები გამოვრიცხოთ
    fix_dict = {k: v for k, v in fix_dict.items() if not k.startswith("_")}
    print(f"  ფიქსის ლექსიკონი: {len(fix_dict)} ტერმინი")
    print()

    # გასწორება
    fixed = 0
    changed = []
    added = []

    for slug, correct_ka in fix_dict.items():
        old_ka = names_ka.get(slug, "")
        if old_ka == correct_ka:
            continue
        if old_ka:
            changed.append((slug, old_ka, correct_ka))
        else:
            added.append((slug, correct_ka))
        names_ka[slug] = correct_ka
        fixed += 1

    print(f"  გასწორდა: {len(changed)}")
    print(f"  დაემატა: {len(added)}")
    print(f"  ჯამში ცვლილება: {fixed}")
    print()

    if changed:
        print("ცვლილებები:")
        for slug, old, new in changed:
            print(f"  {slug}: {old} -> {new}")

    if added:
        print()
        print("დამატებული:")
        for slug, new in added:
            print(f"  {slug}: -> {new}")

    print()

    # დამატებითი აუდიტი - საეჭვო ტრანსლიტერაციები
    latin_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    bad_suffixes = ["ცია", "სია", "ზმი", "იზმი"]

    suspicious = []
    with open(DATA_DIR / "topical_index.json", "r", encoding="utf-8") as f:
        index = json.load(f)

    for t in index["topics"]:
        slug = t["slug"]
        name_en = t.get("name_en", "")
        name_ka = names_ka.get(slug, "")

        if not name_ka:
            suspicious.append((slug, name_en, "[აკლია]", "აკლია"))
            continue

        if any(c in latin_chars for c in name_ka):
            suspicious.append((slug, name_en, name_ka, "ლათინური ასოები"))
            continue

        for suffix in bad_suffixes:
            if name_ka.endswith(suffix):
                suspicious.append((slug, name_en, name_ka, f"ტრანსლიტერაცია: -{suffix}"))
                break

    print(f"დარჩენილი საეჭვო თარგმანები: {len(suspicious)}")
    if suspicious:
        print("  (ზოგიერთი სწორია - მაგ: ეკლესია, კასია, ასია)")
        for slug, en, ka, reason in suspicious[:20]:
            print(f"  {en} -> {ka} ({reason})")

    print()

    if apply:
        # სარეზერვო ასლი
        bak = NAMES_FILE.with_suffix(".json.bak")
        shutil.copy2(NAMES_FILE, bak)
        print(f"სარეზერვო ასლი: {bak}")

        with open(NAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(names_ka, f, ensure_ascii=False, indent=2)
        print(f"შენახულია: {NAMES_FILE}")
    else:
        print("--apply გარეშე: ცვლილებები არ შენახულა.")
        print("გასაშვებად: python3 fix_topic_names.py --apply")


if __name__ == "__main__":
    main()
