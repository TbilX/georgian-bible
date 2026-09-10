#!/usr/bin/env python3
"""
fix_systematic_labels.py
========================
სისტემური შეცდომების გასწორება topic_labels_ka.json-ში.

სკრიპტი გადაამოწმებს ყველა 42,531 label-ს და გაასწორებს
ცხადად არასწორ თარგმანებს კონტექსტის გათვალისწინებით.

გამოყენება:
    python3 fix_systematic_labels.py              # მშრალი გაშვება
    python3 fix_systematic_labels.py --apply      # შენახვა
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"


def apply_fixes(labels):
    """
    ახდენს სისტემური შეცდომების გასწორებას.
    აბრუნებს (fixed_count, fixes_list) - სია ცვლილებებისა.
    """
    fixes = []

    for en_label, ka_label in list(labels.items()):
        original = ka_label
        en_lower = en_label.lower()
        new_ka = ka_label

        # ==========================================
        # ფიქსი 1: სამღვდელო → საწმიდარი (SANCTUARY)
        # ==========================================
        if 'სამღვდელო' in new_ka:
            # მხოლოდ როცა ინგლისურში არის SANCTUARY
            if 'SANCTUARY' in en_label.upper() or 'sanctuary' in en_lower:
                new_ka = new_ka.replace('სამღვდელო', 'საწმიდარი')

        # ==========================================
        # ფიქსი 2: ხასხასი → ხასიათი (character)
        # ==========================================
        if 'ხასხასი' in new_ka:
            if 'character' in en_lower:
                new_ka = new_ka.replace('ხასხასი', 'ხასიათი')

        # ==========================================
        # ფიქსი 3: წვეული → გამოწვეული (summoned)
        # ==========================================
        if 'წვეული' in new_ka:
            if 'summon' in en_lower:
                new_ka = new_ka.replace('წვეული', 'გამოწვეული')

        # ==========================================
        # ფიქსი 4: შედეგიანი → შედეგი (consequent)
        # ==========================================
        if 'შედეგიანი' in new_ka:
            if 'consequent' in en_lower:
                new_ka = new_ka.replace('შედეგიანი დაცემაზე', 'დაცემის შედეგი')
                new_ka = new_ka.replace('შედეგიანი', 'შედეგი')

        # ==========================================
        # ფიქსი 5: ეწვევა → ესტუმრა (visits - წარსული)
        # ==========================================
        if 'ეწვევა' in new_ka:
            if 'visit' in en_lower:
                # მოგვები ეწვევა → ესტუმრნენ (მრავლობითი)
                if 'მოგვები' in new_ka or 'მოციქულნი' in new_ka or 'მწყემსები' in new_ka:
                    new_ka = new_ka.replace('ეწვევა', 'ესტუმრნენ')
                else:
                    new_ka = new_ka.replace('ეწვევა', 'ესტუმრა')

        # ==========================================
        # ფიქსი 6: ჩანს → გამოეცხადება (appears to)
        # ==========================================
        if 'ჩანს ' in new_ka:
            if 'appears to' in en_lower or 'appeared to' in en_lower:
                # "ანგელოზი ჩანს მარიამს" → "ანგელოზი გამოეცხადება მარიამს"
                new_ka = new_ka.replace('ჩანს ', 'გამოეცხადება ')

        # ==========================================
        # ფიქსი 7: წოდებული → ეწოდება (Called X)
        # ==========================================
        # "Called ARABAH" → "ეწოდება არაბა"
        # "Also called SACAR" → "ასევე ეწოდება საქარი"
        # მაგრამ "წოდებული" როგორც ზედსართავი ზოგჯერ სწორია
        if new_ka.startswith('წოდებული '):
            if en_label.strip().startswith('Called ') or en_label.strip().startswith('.Called '):
                # ვნახოთ მეორე სიტყვა - თუ ეს არის სახელი (დიდი ასოთი)
                rest = new_ka[len('წოდებული '):]
                if rest and rest[0].isupper() or rest[0] == '"':
                    new_ka = 'ეწოდება ' + rest

        if 'ასევე წოდებული ' in new_ka:
            if 'also called' in en_lower:
                new_ka = new_ka.replace('ასევე წოდებული ', 'ასევე ეწოდება ')

        # ==========================================
        # ფიქსი 8: მეტობითი ბრუნვა "სახლი X" → "X-ის სახლი"
        # ==========================================
        # "სახლი ღმერთი" → "ღმერთის სახლი"
        # "სახლი უფალი" → "უფლის სახლი"
        # "სახლი ლოცვა" → "ლოცვის სახლი"
        # "სახლი ქრისტეს" → "ქრისტეს სახლი" (უკვე გენიტივია)
        genitive_map = {
            'სახლი ღმერთი ': 'ღმერთის სახლი ',
            'სახლი უფალი ': 'უფლის სახლი ',
            'სახლი ლოცვა ': 'ლოცვის სახლი ',
            'სახლი ქრისტეს ': 'ქრისტეს სახლი ',
            'სახლი დავითის ': 'დავითის სახლი ',
        }
        for old, new in genitive_map.items():
            if old in new_ka:
                new_ka = new_ka.replace(old, new)

        # ==========================================
        # ფიქსი 9: "ადგილები" (places - კონტექსტის მიხედვით)
        # ==========================================
        # "Places pot of manna" → "დააბრძანა მანნას ქვაბი"
        # მხოლოდ ცხადად არასწორი შემთხვევები
        if 'ადგილები ქვაბი' in new_ka:
            if 'places pot' in en_lower or 'places the pot' in en_lower:
                new_ka = new_ka.replace('ადგილები ქვაბი', 'დააბრძანა ქვაბი')

        # ==========================================
        # ფიქსი 10: "არის გაკეთებული" → "გაკეთებულია"
        # მხოლოდ სრული სიტყვის შემთხვევაში (სივრცე ან დასაწყისი)
        # ==========================================
        # "არის გაკეთებული" უნდა იყოს ცალკე სიტყვა, არა ნაწილი სხვა სიტყვის
        if ' არის გაკეთებული ' in new_ka:
            new_ka = new_ka.replace(' არის გაკეთებული ', ' გაკეთებულია ')
        elif new_ka.startswith('არის გაკეთებული '):
            new_ka = 'გაკეთებულია ' + new_ka[len('არის გაკეთებული '):]
        elif new_ka.endswith(' არის გაკეთებული'):
            new_ka = new_ka[:-len(' არის გაკეთებული')] + ' გაკეთებულია'
        elif new_ka == 'არის გაკეთებული':
            new_ka = 'გაკეთებულია'

        if ' არის მოცემული ' in new_ka:
            new_ka = new_ka.replace(' არის მოცემული ', ' მოცემულია ')
        elif new_ka.startswith('არის მოცემული '):
            new_ka = 'მოცემულია ' + new_ka[len('არის მოცემული '):]
        elif new_ka.endswith(' არის მოცემული'):
            new_ka = new_ka[:-len(' არის მოცემული')] + ' მოცემულია'

        if ' არის წარდგენილი ' in new_ka:
            new_ka = new_ka.replace(' არის წარდგენილი ', ' წარადგინეს ')
        elif new_ka.startswith('არის წარდგენილი '):
            new_ka = 'წარადგინეს ' + new_ka[len('არის წარდგენილი '):]
        elif new_ka.endswith(' არის წარდგენილი'):
            new_ka = new_ka[:-len(' არის წარდგენილი')] + ' წარადგინეს'

        # ==========================================
        # ფიქსი 11: "აკეთებს არ" - არასწორი თარგმანი "does not"
        # "Does not understand" ითარგმნება "არ ესმის", არა "არ აკეთებს გაიგე"
        # ეს ფიქსი ძალიან რისკიანია - გამოვრიცხავთ
        # ==========================================
        # არ ვეხებით - "აკეთებს არ" არის სიტყვა-სიტყვით თარგმანი მაგრამ
        # მისი ავტომატური გასწორება უფრო მეტ ზიანს აყენებს

        # ==========================================
        # ფიქსი 12: "თელააბედს" → "ელისაბედს" (Elisabeth)
        # ==========================================
        if 'თელააბედს' in new_ka:
            if 'elisabeth' in en_lower or 'elizabeth' in en_lower:
                new_ka = new_ka.replace('თელააბედს', 'ელისაბედს')

        # ==========================================
        # ფიქსი 13: ინგლისური სიტყვების წაშლა (ცხადი შემთხვევები)
        # ==========================================
        # "Jerის" → "იერის" (არასწორი სახელის ფუძე)
        new_ka = re.sub(r'Jerის', 'იერის', new_ka)

        # ==========================================
        # ფიქსი 14: "მისს" → "მის" (არასწორი მეტობითი)
        # ==========================================
        new_ka = re.sub(r'მისს ', 'მის ', new_ka)

        # ცვლილების შენახვა
        if new_ka != original:
            labels[en_label] = new_ka
            fixes.append((en_label[:60], original[:60], new_ka[:60]))

    return len(fixes), fixes


def main():
    apply = '--apply' in sys.argv

    print("=== სისტემური შეცდომების გასწორება ===")
    print()

    with open(LABELS_FILE, 'r', encoding='utf-8') as f:
        labels = json.load(f)

    print(f"სულ label: {len(labels):,}")
    print()

    fixed_count, fixes = apply_fixes(labels)

    # დაჯგუფება ფიქსის ტიპის მიხედვით
    print(f"გასწორდა: {fixed_count} label")
    print()

    # ნიმუშები
    if fixes:
        print("=== ნიმუშები (before/after) ===")
        for en, old, new in fixes[:40]:
            print(f"  EN: {en}")
            print(f"  OLD: {old}")
            print(f"  NEW: {new}")
            print()

        if len(fixes) > 40:
            print(f"  ... და კიდევ {len(fixes) - 40} ფიქსი")

    if apply:
        with open(LABELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"\nშენახულია: {LABELS_FILE}")
    else:
        print(f"\n--apply გარეშე: ცვლილებები არ შენახულა")
        print("გასაშვებად: python3 fix_systematic_labels.py --apply")


if __name__ == '__main__':
    main()
