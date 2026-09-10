#!/usr/bin/env python3
"""
fix_apostrophes.py - აპოსტროფების სისტემური გასწორება topic_labels_ka.json-ში.

პრობლემა: ინგლისური "'s" მეტობითი ბრუნვა ვერ გადაითარგმნა სწორად.
მაგ: "God's covenant" → "ღმერთი' აღთქმა" (არასწორი, უნდა იყოს "ღმერთის აღთქმა")

ფიქსი:
1. თუ ორიგინალში არის "’s" ან "'s" ან "’" → ვცვლი აპოსტროფს "ს"-ით (მეტობითი ბრუნვა)
2. თუ ორიგინალში არის "of" → ვცვლი აპოსტროფს "ს"-ით (მეტობითი ბრუნვა)
3. დანარჩენი → ვცვლი აპოსტროფს სივრცით (ფორმატირების შეცდომა)
"""
import json
import re
import os

DATA_DIR = "data"

# ფაილების ჩატვირთვა
with open(os.path.join(DATA_DIR, "topical_index.json"), "r", encoding="utf-8") as f:
    topical = json.load(f)
with open(os.path.join(DATA_DIR, "topic_labels_ka.json"), "r", encoding="utf-8") as f:
    labels_ka = json.load(f)

# ყველა აპოსტროფიანი label-ის პოვნა
apo_entries = []
for topic in topical.get("topics", []):
    for entry in topic.get("entries", []):
        en = entry.get("label", "")
        ka = labels_ka.get(en, "")
        if ka and "'" in ka:
            apo_entries.append((en, ka))

print(f"სულ აპოსტროფიანი: {len(apo_entries)}")

# ფიქსი
changes = 0
details = []

for en, ka in apo_entries:
    new_ka = ka

    # ვპოვნი აპოსტროფის პოზიციას
    # პატერნი: "სიტყვა' სიტყვა" ან "სიტყვა',"
    for m in re.finditer(r"([ა-ჰ]+)'([ ,:])", ka):
        word_before = m.group(1)
        char_after = m.group(2)

        # გადავამოწმოთ ორიგინალურ ინგლისურში რა პატერნია
        # თუ ორიგინალში არის "’s" ან "'s" ან "’" → მეტობითი ბრუნვა
        if "’s " in en or "’s," in en or "’s:" in en or "’s." in en:
            # მეტობითი ბრუნვა: ვცვლი აპოსტროფს "ს"-ით
            new_ka = new_ka[:m.start()] + word_before + "ს" + char_after + new_ka[m.end():]
        elif "’ " in en or "’," in en or "’:" in en:
            # მეტობითი ბრუნვა (მრავლობითი): ვცვლი აპოსტროფს "ს"-ით
            new_ka = new_ka[:m.start()] + word_before + "ს" + char_after + new_ka[m.end():]
        elif re.search(r"\bof\b", en, re.IGNORECASE):
            # "of" მეტობითი ბრუნვა: ვცვლი აპოსტროფს "ს"-ით
            new_ka = new_ka[:m.start()] + word_before + "ს" + char_after + new_ka[m.end():]
        else:
            # სხვა შემთხვევა - ვცვლი აპოსტროფს სივრცით
            new_ka = new_ka[:m.start()] + word_before + " " + char_after + new_ka[m.end():]

    if new_ka != ka:
        labels_ka[en] = new_ka
        changes += 1
        if len(details) < 10:
            details.append((en, ka, new_ka))

print(f"გასწორებული: {changes}")

# შენახვა
with open(os.path.join(DATA_DIR, "topic_labels_ka.json"), "w", encoding="utf-8") as f:
    json.dump(labels_ka, f, ensure_ascii=False, indent=2)
print("შენახულია")

# დეტალები
print(f"\n=== პირველი 10 გასწორება ===")
for en, old, new in details:
    print(f"EN: {en[:80]}")
    print(f"OLD: {old[:80]}")
    print(f"NEW: {new[:80]}")
    print()
