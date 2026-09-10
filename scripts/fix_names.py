#!/usr/bin/env python3
"""წიგნების სახელების გასწორება verse_index.json და verses.json-ში."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# სწორი სახელები HTML title-ებიდან
CORRECT_NAMES = {
    # ძველი აღთქმა
    "dabadeba": "დაბადება",
    "gamosvla": "გამოსვლა",
    "levianni": "ლევიანნი",
    "ritskhvni": "რიცხვნი",
    "2rjuli": "მეორე რჯული",
    "iesonave": "იესო ნავეს ძე",
    "msajulni": "მსაჯულნი",
    "ruti": "რუთი",
    "1mepeta": "I მეფეთა",
    "2mepeta": "II მეფეთა",
    "3mepeta": "III მეფეთა",
    "4mepeta": "IV მეფეთა",
    "1neshtta": "I ნეშტთა",
    "2neshtta": "II ნეშტთა",
    "1ezra": "I ეზრა",
    "2ezra": "II ეზრა",
    "3ezra": "III ეზრა",
    "neemia": "ნეემია",
    "esteri": "ესთერი",
    "iobi": "იობი",
    "fsalmunni": "ფსალმუნნი",
    "igavni": "იგავნი სოლომონისა",
    "eklesiaste": "ეკლესიასტე",
    "qeba": "ქებათა-ქება სოლომონისა",
    "esaia": "ესაია",
    "ieremia": "იერემია",
    "baruqi": "ბარუქი",
    "igavni": "იგავნი სოლომონისა",
    "ezekieli": "ეზეკიელი",
    "danieli": "დანიელი",
    "osia": "ოსია",
    "amos": "ამოსი",
    "abdia": "აბდია",
    "iona": "იონა",
    "miqa": "მიქა",
    "naumi": "ნაუმი",
    "abakumi": "აბაკუმი",
    "sofonia": "სოფონია",
    "zaqaria": "ზაქარია",
    "malaqia": "მალაქია",
    # არაკანონიკური
    "tobiti": "ტობითი",
    "ivditi": "ივდითი",
    "godeba": "გოდება იერემიასი",
    "epistole": "ეპისტოლე იერემიასი",
    "1makabelta": "I მაკაბელთა",
    "2makabelta": "II მაკაბელთა",
    "3makabelta": "III მაკაბელთა",
    "4makabelta": "IV მაკაბელთა",
    "solomoni": "სიბრძნე სოლომონისა",
    "ziraqi": "სიბრძნე ზირაქისა",
    "angia": "ანგია",
    "ioveli": "იოველი",
    # ახალი აღთქმა
    "mate": "სახარება მათესაგან",
    "markozi": "სახარება მარკოზისაგან",
    "luka": "სახარება ლუკასაგან",
    "ioane": "სახარება იოანესაგან",
    "saqme": "მოციქულთა საქმენი",
    "romaelta": "რომაელთა მიმართ",
    "1korintelta": "I კორინთელთა მიმართ",
    "2korintelta": "II კორინთელთა მიმართ",
    "galatelta": "გალატელთა მიმართ",
    "efeselta": "ეფესელთა მიმართ",
    "filipelta": "ფილიპელთა მიმართ",
    "kolaselta": "კოლასელთა მიმართ",
    "1tesalonikelta": "I თესალონიკელთა მიმართ",
    "2tesalonikelta": "II თესალონიკელთა მიმართ",
    "1timote": "I ტიმოთეს მიმართ",
    "2timote": "II ტიმოთეს მიმართ",
    "tite": "ტიტეს მიმართ",
    "filimoni": "ფილიმონის მიმართ",
    "ebraelta": "ებრაელთა მიმართ",
    "iakobi": "იაკობის ეპისტოლე",
    "1petre": "I პეტრესი",
    "2petre": "II პეტრესი",
    "1ioane": "I იოანესი",
    "2ioane": "II იოანესი",
    "3ioane": "III იოანესი",
    "iuda": "იუდასი",
    "apokalips": "იოანეს გამოცხადება",
}


def fix_file(filepath):
    print(f"მუშაობა: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    for item in data:
        slug = item.get("book_slug", "")
        if slug in CORRECT_NAMES:
            old_name = item.get("book", "")
            new_name = CORRECT_NAMES[slug]
            if old_name != new_name:
                item["book"] = new_name
                changed += 1

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1 if "verses" in filepath else None)

    print(f"  გასწორდა: {changed} ჩანაწერი")
    return changed


def main():
    total = 0
    total += fix_file(os.path.join(DATA_DIR, "verse_index.json"))
    total += fix_file(os.path.join(DATA_DIR, "verses.json"))
    print(f"\nსულ გასწორდა: {total} ჩანაწერი")


if __name__ == "__main__":
    main()
