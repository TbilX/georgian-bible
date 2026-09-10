#!/usr/bin/env python3
"""
apply_name_fixes.py
===================
data/name_dictionary_ka.json-ის გამოყენება topic_labels_ka.json-ის
ინგლისური სახელების/სიტყვების გასწორებისთვის.

გამოყენება:
    python3 apply_name_fixes.py           # dry-run
    python3 apply_name_fixes.py --apply   # შენახვა
"""

import json
import re
import sys
import shutil
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"
DICT_FILE = DATA_DIR / "name_dictionary_ka.json"


def fix_label_with_dict(label, dictionary):
    """ერთი label-ის გასწორება ლექსიკონით."""
    result = label
    changes = []

    # ვეძებთ ინგლისურ სიტყვებს (მხოლოდ A-Z, 3+ სიმბოლო)
    words = re.findall(r"[A-Za-z]{3,}", result)
    for word in words:
        word_lower = word.lower()
        if word_lower in dictionary:
            ka = dictionary[word_lower]
            # word boundary-ით ჩანაცვლება
            pattern = r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])"
            new_result = re.sub(pattern, ka, result)
            if new_result != result:
                changes.append(f"{word} -> {ka}")
                result = new_result

    return result, changes


def main():
    apply = "--apply" in sys.argv

    print("=== ინგლისური სახელების ჩანაცვლება label-ებში ===")

    with open(LABELS_FILE, "r", encoding="utf-8") as f:
        labels = json.load(f)

    with open(DICT_FILE, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    print(f"  სულ label: {len(labels):,}")
    print(f"  ლექსიკონი: {len(dictionary):,} წოლი\n")

    changed_count = 0
    change_words = Counter()
    samples = []

    for key, label in labels.items():
        new_label, changes = fix_label_with_dict(label, dictionary)
        if new_label != label:
            changed_count += 1
            for c in changes:
                word = c.split(" -> ")[0]
                change_words[word] += 1
            if len(samples) < 20:
                samples.append((label[:75], new_label[:75], changes))
            labels[key] = new_label

    print(f"შეიცვალა: {changed_count:,} / {len(labels):,} ({changed_count/len(labels)*100:.1f}%)")
    print()

    print("Top 20 ყველაზე ხშირად ჩანაცვლებული:")
    for word, count in change_words.most_common(20):
        print(f"  {word}: {count}")
    print()

    print("ნიმუშები:")
    for old, new, changes in samples:
        print(f"  {old}")
        print(f"    -> {new}")
        print(f"    [{', '.join(changes)}]")
        print()

    # აუდიტი
    remaining = 0
    remaining_words = Counter()
    for label in labels.values():
        words = re.findall(r"[A-Za-z]{3,}", label)
        for w in words:
            # გამოვრიცხოთ რომაული რიცხვები II, III, IV
            if w not in ["III", "II", "IV"]:
                remaining += 1
                remaining_words[w] += 1

    print(f"დარჩენილი ინგლისური შემთხვევები: {remaining}")
    print(f"დარჩენილი უნიკალური სიტყვები: {len(remaining_words)}")
    print()
    print("Top 20 დარჩენილი:")
    for w, c in remaining_words.most_common(20):
        print(f"  {w}: {c}")

    if apply:
        bak = LABELS_FILE.with_suffix(".json.bak2")
        shutil.copy2(LABELS_FILE, bak)
        print(f"\nსარეზერვო ასლი: {bak}")
        with open(LABELS_FILE, "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"შენახულია: {LABELS_FILE}")
    else:
        print("\n--apply გარეშე: ცვლილებები არ შენახულა.")


if __name__ == "__main__":
    main()
