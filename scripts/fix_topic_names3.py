#!/usr/bin/env python3
"""ფაზა 3: დარჩენილი 308 პრობლემური სახელის გასწორება ფონეტიკური წესებით."""
import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def is_georgian_ch_word(val):
    """არის თუ არა ეს ნამდვილი ქართული სიტყვა რომელშიც ჩ ბუნებრივად არის."""
    # თუ შეიცავს ქართულ ფუძეს რომელიც ჩ-ს იყენებს
    georgian_roots = [
        "ჩვენ", "ჩემ", "მორჩილ", "გამორჩევ", "წინასწარგანჩენ",
        "ჩან", "ჩართ", "ჩამო", "ჩასვ", "ჩადგ", "მოწმე",
        "უჩვენ", "გამოჩენ", "შემოწმ", "წარმოჩენ", "მოჩვენ",
        "გადმოჩ", "ჩამკვ", "ჩანაწ", "ჩატარ", "ჩარევ",
        "ჩამორთმევ", "ჩამოწყვეტ", "ჩამოწყობ",
    ]
    for root in georgian_roots:
        if root in val:
            return True
    return False


def fix_name(val):
    """ფონეტიკური გარდაქმნა ერთ სახელზე."""
    new_val = val

    # 1. ბოლო ჰ → ი (ან მოხსნა თუ უკვე ბოლოვდება ხმლით)
    if new_val.endswith("ჰ"):
        new_val = new_val[:-1]
        if not new_val.endswith(("ი", "ე", "ა", "ო", "უ")):
            new_val = new_val + "ი"
    elif new_val.endswith("ჰი"):
        new_val = new_val[:-2] + "ი"

    # 2. ჩ → ქ (მაგრამ არა ქართულ სიტყვებში)
    if "ჩ" in new_val and not is_georgian_ch_word(new_val):
        new_val = new_val.replace("ჩ", "ქ")

    # 3. ჯჰ → ია
    if "ჯჰ" in new_val:
        new_val = new_val.replace("ჯჰ", "ია")

    # 4. ჰ შუაში → მოხსნა (მაგრამ არა დასაწყისში)
    # გამოვტოვოთ შემთხვევები სადაც ჰ ბუნებრივია (იშვიათი)
    if len(new_val) > 1 and "ჰ" in new_val[1:]:
        # შევინახოთ პირველი ასო და დანარჩენიდან მოვხსნათ ჰ
        # მაგრამ გარკვეულ შემთხვევებში ჰ ბუნებრივია (აბიჰუ, ბაალ-ჰამონი)
        # უბრალოდ მოვხსნათ - ქართულ ბიბლიურ ტრადიციაში ჰ იშვიათია
        new_val = new_val[0] + new_val[1:].replace("ჰ", "")

    return new_val


def main():
    print("=== ფაზა 3: დარჩენილი სახელების გასწორება ===\n")

    with open(os.path.join(DATA_DIR, "topic_names_ka.json"), "r", encoding="utf-8") as f:
        topics = json.load(f)

    fixed = 0
    skipped_roman = 0
    unchanged = 0

    for slug, val in topics.items():
        # გამოვტოვოთ რომაული რიცხვები
        if val.startswith(("I ", "II ", "III ", "IV ")):
            skipped_roman += 1
            continue

        # გადავამოწმოთ პრობლემურია თუ არა
        if "ჰ" not in val and "ჩ" not in val and "ჯჰ" not in val:
            continue

        new_val = fix_name(val)
        if new_val != val and len(new_val) >= 2:
            topics[slug] = new_val
            fixed += 1
            print(f"  {slug:45s} '{val}' -> '{new_val}'")
        else:
            unchanged += 1

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
    print(f"გასწორდა: {fixed}")
    print(f"უცვლელი დარჩა: {unchanged}")
    print(f"რომაული რიცხვები (გამოტოვებული): {skipped_roman}")
    print(f"დარჩენილი პრობლემური: {remaining}")


if __name__ == "__main__":
    main()
