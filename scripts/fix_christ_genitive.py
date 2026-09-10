#!/usr/bin/env python3
"""
ქრისტე-ს მეტობითი ბრუნვის კონტექსტუალური გასწორება.
ინგლისური label-ების მიხედვით განსაზღვრავს:
- "of Christ" / "Christ's" → ქრისტეს (მეტობითი)
- "Christ" (სახელობითი) → ქრისტე (რჩება)
"""
import json
import re

DATA_DIR = "data"

with open(f"{DATA_DIR}/topical_index.json", "r", encoding="utf-8") as f:
    TOPICAL = json.load(f)

with open(f"{DATA_DIR}/topic_labels_ka.json", "r", encoding="utf-8") as f:
    LABELS_KA = json.load(f)


def is_genitive_context(en_label):
    """განსაზღვრავს არის თუ არა ინგლისური label-ში Christ მეტობით ბრუნვაში."""
    # "Christ's" - ყოველთვის მეტობითი
    if re.search(r"Christ's\b", en_label):
        return True
    # "of Christ" - მეტობითი
    if re.search(r"\bof Christ\b", en_label, re.IGNORECASE):
        return True
    # "of Jesus Christ" / "of the Christ"
    if re.search(r"\bof (?:Jesus |the )?Christ\b", en_label, re.IGNORECASE):
        return True
    return False


def main():
    # ვაგროვებთ ყველა ინგლისურ label-ს რომელთა ქართული თარგმანიც შეიცავს "ქრისტე "
    # (სივრცით - ე.ი. არ არის ბოლოში)
    changes = 0
    for topic in TOPICAL.get("topics", []):
        for entry in topic.get("entries", []):
            en_label = entry.get("label", "")
            if not en_label:
                continue
            ka_label = LABELS_KA.get(en_label)
            if not ka_label:
                continue
            if "ქრისტე " not in ka_label:
                continue

            if is_genitive_context(en_label):
                # მეტობითი: ქრისტე -> ქრისტეს
                new_ka = ka_label.replace("ქრისტე ", "ქრისტეს ")
                if new_ka != ka_label:
                    LABELS_KA[en_label] = new_ka
                    changes += 1

    print(f"მეტობითი ბრუნვის გასწორებები: {changes}")

    # შენახვა
    with open(f"{DATA_DIR}/topic_labels_ka.json", "w", encoding="utf-8") as f:
        json.dump(LABELS_KA, f, ensure_ascii=False, indent=2)
    print("შენახულია")

    # ნიმუშები
    samples = [
        "Type of Christ Ro 5:14",
        "A title of Christ Re 1:8,11; 21:6; 22:13",
        "Of the body of Christ Mt 26:26; Ac 20:7; 1Co 11:23,24",
        "Of Christ Ps 118:22; Isa 28:16; Mt 21:42; Mr 12:10; Lu 20:17; Ac 4:11; 1Co 3:11; Eph 2:20; 1Pe 2:6",
        "Witness of Christ's resurrection 1Co 15:7",
        "Christ claims the first place in Mt 10:37; Lu 14:26",
        "Christ called Heb 2:10",
        "Christ Jesus Ac 19:4; Ro 3:24; 8:1; 1Co 1:2,30; Heb 3:1; 1Pe 5:10,14",
    ]
    print()
    print("=== ნიმუშები ===")
    for s in samples:
        if s in LABELS_KA:
            print(f"  EN: {s[:80]}")
            print(f"  KA: {LABELS_KA[s][:100]}")
            print()


if __name__ == "__main__":
    main()
