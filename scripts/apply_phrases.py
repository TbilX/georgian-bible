#!/usr/bin/env python3
"""
ამატებს ხელით თარგმანებს მრავალსიტყვიანი ფრაზებისთვის manual_ka.json-ში
და შემდეგ ინახავს topic_names_ka.json-ში.
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAPPING_FILE = os.path.join(DATA_DIR, "topic_names_ka.json")
MANUAL_FILE = os.path.join(DATA_DIR, "manual_ka.json")

# მრავალსიტყვიანი ფრაზების ხელით თარგმანი
PHRASES = {
    # "X, The" → უბრალოდ სახელი (უკვე სწორია ბევრი, მაგრამ ზოგიერთი გასასწორებელია)
    "affections-the": "გრძნობანი",
    "blessed-the": "ნეტარნი",
    "deluge-the": "წარღვნა",
    "ear-the": "ყური",
    "eye-the": "თვალი",
    "hair-the": "თმა",
    "heart-the": "გული",
    "moon-the": "მთვარე",
    "rich-the": "მდიდარნი",
    "sick-the": "სნაურნი",
    "stars-the": "ვარსკვლავნი",
    "sword-the": "მახვილი",
    "lot-the": "წილისყდა",

    # ტომები - "X, the Tribe Of" → "ტომი X"
    "asher-the-tribe-of": "აშერის ტომი",
    "benjamin-tribe-of": "ბენიამინის ტომი",
    "dan-the-tribe-of": "დანის ტომი",
    "ephraim-tribe-of": "ეფრემის ტომი",
    "gad-the-tribe-of": "გადის ტომი",
    "issachar-the-tribe-of": "ისაქარის ტომი",
    "judah-the-tribe-of": "იუდას ტომი",
    "manasseh-the-tribe-of": "მანასეს ტომი",
    "naphtali-the-tribe-of": "ნაფთალის ტომი",
    "reuben-the-tribe-of": "რუბენის ტომი",
    "simeon-the-tribe-of": "სიმეონის ტომი",
    "zebulun-the-tribe-of": "ზებულუნის ტომი",
    "tribes-of-israel-the": "ისრაელის ტომები",

    # ხალხები - "X, The" → მრავლობითი
    "amalekites-the": "ამალეკელები",
    "ammonites-the": "ამონელები",
    "amorites-the": "ამორელები",
    "anakim-the": "ანაკიმები",
    "canaanites-the": "ქანაანელები",
    "edomites-the": "ედომელები",
    "ishmaelites-the": "იშმაელები",
    "kenites-the": "კენიტები",
    "sidonians-the": "სიდონელები",
    "pharisees-the": "ფარისევლები",
    "sadducees-the": "სადუკელები",
    "rephaim-or-giants-the": "რეფაიმები (გიგანტები)",

    # სამართლებრივი ფრაზები
    "actions-at-law": "სასამართლო დავები",
    "adjudication-at-law": "სასამართლო გადაწყვეტილება",
    "change-of-venue": "სასამართლო შეცვლა",
    "damages-and-compensation": "ზიანი და კომპენსაცია",
    "malfeasance-in-office": "თანამდებობის ბოროტად გამოყენება",
    "majority-and-minority-reports": "უმრავლესობის და უმცირესობის ანგარიშები",

    # რელიგიური ფრაზები
    "afflicted-duty-toward-the": "მწუხარეთა მოვალეობა",
    "affliction-prayer-under": "ლოცვა განსაცდელში",
    "amusements-and-pleasures-worldly": "ამქვეყნიური გართობა და სიამოვნებანი",
    "amusements-and-worldly-pleasures": "ამქვეყნიური გართობა და სიამოვნებანი",
    "arts-of-the": "ხელოვნებანი",
    "atoms-of-matter": "მატერიის ატომები",
    "avenger-of-blood": "სისხლის აღმბერავი",
    "beauty-and-bands": "მშვენიერება და ბორკენები",
    "boring-the-ear": "ყურის გახვრეტა",
    "calf-of-gold": "ოქროს კრავი",
    "calves-of-jeroboam": "იერობოამის კრავები",
    "capital-and-labor": "კაპიტალი და შრომა",
    "castor-and-pollux": "კასტორი და პოლუქსი",
    "charmers-and-charming": "მომხიბლავნი და მოხიბლვა",
    "cities-of-refuge":  "თავშესაფრის ქალაქები",
    "coat-of-mail": "ჯავშანი",
    "aquila-and-priscilla": "აკილა და პრისკილა",
    "decision-valley-of": "გადაწყვეტილების ველი",
    "fall-of-man": "კაცის დაცემა",
    "fight-of-faith": "რწმენის ბრძოლა",
    "forgiveness-of-injuries": "შეურაცხყოფის მიტევება",
    "house-of-god": "ღვთის სახლი",
    "humiliation-and-self-affliction": "დამდაბლება და თავის გასაცდელი",
    "hyke-or-upper-garment": "ზედა სამოსი (ჰიკე)",
    "macedonian-empire-the": "მაკედონიის იმპერია",
    "olives-mount-of": "ზეთისხილის მთა",
    "paschal-lamb-typical-nature-of": "პასექის კრავის ტიპური ბუნება",
    "scape-goat-the": "გამოსყიდვის თხა",
    "temple-the-second": "მეორე ტაძარი",
    "titles-and-names-of-ministers": "მსახურთა სახელები და წოდებანი",
    "titles-and-names-of-the-devil": "ეშმაკის სახელები და წოდებანი",
    "vail-or-veil": "ფარდა",
    "vail-the-sacred": "საკურთხეველი ფარდა",
    "walls-of-the-cities": "ქალაქთა კედლები",
    "bow-the": "მშვილდი",
}


def main():
    # წაიკითხოს არსებული manual_ka.json
    manual = {}
    if os.path.exists(MANUAL_FILE):
        with open(MANUAL_FILE, "r", encoding="utf-8") as f:
            manual = json.load(f)

    # დავამატოთ ახალი ფრაზები
    added = 0
    updated = 0
    for slug, ka in PHRASES.items():
        if slug in manual:
            if manual[slug] != ka:
                manual[slug] = ka
                updated += 1
        else:
            manual[slug] = ka
            added += 1

    # შევინახოთ manual_ka.json
    with open(MANUAL_FILE, "w", encoding="utf-8") as f:
        json.dump(manual, f, ensure_ascii=False, indent=2)
    print(f"manual_ka.json: დაემატა {added}, განახლდა {updated}")

    # გადავატაროთ apply_manual.py-ის ლოგიკა
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    updated = 0
    added = 0
    for slug, ka in PHRASES.items():
        if slug in mapping:
            if mapping[slug] != ka:
                mapping[slug] = ka
                updated += 1
        else:
            mapping[slug] = ka
            added += 1

    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"topic_names_ka.json: განახლდა {updated}, დაემატა {added}")


if __name__ == "__main__":
    main()
