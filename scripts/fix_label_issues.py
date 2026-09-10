#!/usr/bin/env python3
"""
fix_label_issues.py
===================
ცხადი შეცდომების გასწორება topic_labels_ka.json-ში.

ეტაპი 4 (ნაწილობრივ): ცხადი შეცდომების გასწორება
- დუბლირებული სიტყვები (მაგ: "წესი წესი" -> "წესი")
- "არის გაკეთებული" -> "გახდა" (is made)
- "არის მოცემული" -> "მოცემული" (is given)

გამოყენება:
    python3 fix_label_issues.py              # მშრალი გაშვება
    python3 fix_label_issues.py --apply      # შენახვა
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"
TOPICAL_FILE = DATA_DIR / "topical_index.json"


def fix_duplicate_words(ka_label):
    """
    შლის დუბლირებულ სიტყვებს.
    მაგ: "წესი წესი" -> "წესი"
    მაგ: "მათე მათე" -> "მათე"
    """
    words = ka_label.split()
    if len(words) < 2:
        return ka_label, False

    new_words = [words[0]]
    for i in range(1, len(words)):
        prev = new_words[-1].rstrip(',.;:')
        curr = words[i].rstrip(',.;:')
        # თუ იგივე სიტყვაა (პუნქტუაციის გარეშე) და სიგრძე > 3, არ დავამატოთ
        if prev == curr and len(curr) > 3:
            continue
        new_words.append(words[i])

    if len(new_words) != len(words):
        return ' '.join(new_words), True
    return ka_label, False


def fix_is_made(ka_label):
    """
    'არის გაკეთებული' -> 'გახდა' (is made / became)
    მაგ: 'ხვდება მოსეს და არის გაკეთებული მოლაპარაკე' -> 'ხვდება მოსეს და გახდა მოლაპარაკე'
    """
    if 'არის გაკეთებული' in ka_label:
        new = ka_label.replace('არის გაკეთებული', 'გახდა')
        return new, True
    return ka_label, False


def fix_is_given(ka_label):
    """
    'არის მოცემული' -> 'მოცემული' (is given)
    მაგ: 'არის მოცემული ღმერთის მიერ' -> 'მოცემული ღმერთის მიერ'
    """
    if 'არის მოცემული' in ka_label:
        new = ka_label.replace('არის მოცემული', 'მოცემული')
        return new, True
    return ka_label, False


def fix_of_reference(ka_label, en_label):
    """
    'X of [ref]' სტრუქტურის გასწორება.
    თუ ორიგინალი მთავრდება 'of'-ით რეფერენსამდე, თარგმანი უნდა იყოს 'X - [ref]'
    მაგ: 'წარმოშობა გამ 6:16' -> 'წარმოშობა - გამ 6:16'

    მაგრამ ეს მხოლოდ მაშინ როცა 'of' არ არის მეტობითი ბრუნვა.
    """
    # ვამოწმოთ თუ ორიგინალი არის "X of [ref]" სტრუქტურის
    # ანუ ბოლო სიტყვა "of"-ის წინ არის ბიბლიური აბრევიატურა
    BIBLE_ABBR = {'Ge','Ex','Le','Nu','De','Jos','Jdg','Ru','1Sa','2Sa','1Ki','2Ki',
                  '1Ch','2Ch','Ezr','Ne','Es','Job','Ps','Pr','Ec','So','Isa','Jer',
                  'La','Eze','Da','Ho','Joe','Am','Ob','Jon','Mic','Na','Hab','Zep',
                  'Hag','Zec','Mal','Mt','Mr','Lu','Joh','Ac','Ro','1Co','2Co','Ga',
                  'Eph','Php','Col','1Th','2Th','1Ti','2Ti','Tit','Phm','Heb','Jas',
                  '1Pe','2Pe','1Jo','2Jo','3Jo','Jude','Re'}

    # ვპოვოთ რეფერენსი ორიგინალში
    ref_pattern = re.compile(
        r'\s+(' + '|'.join(re.escape(a) for a in BIBLE_ABBR) + r')\s+\d+'
    )
    m = ref_pattern.search(en_label)
    if not m:
        return ka_label, False

    # ტექსტი რეფერენსამდე
    text_before = en_label[:m.start()].strip()
    # თუ მთავრდება "of"-ით, ეს არის "X of [ref]" სტრუქტურა
    if not text_before.endswith(' of') and not text_before.endswith(' Of'):
        return ka_label, False

    # ახლა ვნახოთ ქართულ თარგმანში - თუ არ არის "-" რეფერენსის წინ
    # ვპოვოთ რეფერენსი ქართულში
    ka_abbr_values = {'დაბ','გამ','ლევ','რიც','მრჟ','იენ','მსჯ','რუთ',
                      'I მეფ','II მეფ','I მეფე','II მეფე','III მეფ','IV მეფ',
                      'I ნეშ','II ნეშ','ეზრ','ნეე','ესთ','იობ','ფსა','იგავ',
                      'ეკლ','ქებ','ესა','იერ','გოდ','ეზე','დანი','ოსი','იოვ',
                      'ამო','აბდ','იონ','მიქ','ნაუ','აბა','სოფ','ანგ','ზაყ',
                      'მალ','მათ','მარ','ლუკ','იოა','საქ','რომ','I კორ','II კორ',
                      'გალ','ეფე','ფილ','კოლ','I თეს','II თეს','I ტიმ','II ტიმ',
                      'ტიტ','ფილმ','ებრ','იაკ','I პეტ','II პეტ','I იოა','II იოა',
                      'III იოა','იუდ','გამო'}

    # უფრო მარტივი მიდგომა: თუ ქართულში არ არის "- [ref]" ფორმატი
    # და რეფერენსი პირდაპირ ერთვის ტექსტს, დავამატოთ "-"
    # მაგრამ ეს რთულია რადგან ქართული აბრევიატურები სხვადასხვანაირად არიან

    # მარტივი შემოწმება: თუ ტექსტი მთავრდება სიტყვით (არა "-ის"/"-ს")
    # და მას მოსდევს რეფერენსი, დავამატოთ "-"
    # მაგრამ ეს შეიძლება იყოს ცუდი რადგან ზოგიერთი შემთხვევა სწორია

    return ka_label, False


def main():
    apply = '--apply' in sys.argv

    print("=== ცხადი შეცდომების გასწორება (ეტაპი 4) ===")
    print()

    with open(LABELS_FILE, 'r', encoding='utf-8') as f:
        labels = json.load(f)

    with open(TOPICAL_FILE, 'r', encoding='utf-8') as f:
        ti = json.load(f)

    # შევქმნათ label-ების სია ორიგინალური ინგლისურით
    en_labels = set()
    for t in ti['topics']:
        for e in t.get('entries', []):
            en_labels.add(e.get('label', ''))

    print(f"სულ label: {len(labels):,}")
    print()

    fixed_dup = 0
    fixed_made = 0
    fixed_given = 0
    samples = []

    for key, ka in list(labels.items()):
        if key not in en_labels:
            continue

        original = ka
        new_ka = ka

        # 1. დუბლირებული სიტყვები
        new_ka, changed = fix_duplicate_words(new_ka)
        if changed:
            fixed_dup += 1
            if len(samples) < 10:
                samples.append(('dub', key, original, new_ka))

        # 2. "არის გაკეთებული" -> "გახდა" (მხოლოდ როცა არ არის "made of")
        # "made of" = "დამზადებული ...-ისგან", არა "გახდა"
        # ვამოწმოთ: თუ "გაკეთებული"-ს მოსდევს "ორის"/"სამის"/"ოქროს"/"ვერცხლის" და ა.შ. = made of
        if 'არის გაკეთებული' in new_ka:
            # ვამოწმოთ თუ არ არის "made of" კონტექსტი
            after_made = new_ka.split('არის გაკეთებული', 1)
            if len(after_made) > 1:
                next_words = after_made[1].strip()[:20]
                # "made of" კონტექსტი: ორის, სამის, ოქროს, ვერცხლის, ხის, ქვის
                if not any(w in next_words for w in ['ორის', 'სამის', 'ოქროს', 'ვერცხლის', 'ხის', 'ქვის']):
                    new_ka, changed = fix_is_made(new_ka)
                    if changed:
                        fixed_made += 1
                        if len(samples) < 15:
                            samples.append(('made', key, original, new_ka))

        # 3. "არის მოცემული"
        new_ka, changed = fix_is_given(new_ka)
        if changed:
            fixed_given += 1
            if len(samples) < 20:
                samples.append(('given', key, original, new_ka))

        if new_ka != original:
            labels[key] = new_ka

    total_fixed = fixed_dup + fixed_made + fixed_given
    print(f"გასწორებული: {total_fixed}")
    print(f"  დუბლირებული სიტყვები: {fixed_dup}")
    print(f"  'არის გაკეთებული': {fixed_made}")
    print(f"  'არის მოცემული': {fixed_given}")
    print()

    if samples:
        print("=== ნიმუშები ===")
        for issue, en, old, new in samples[:15]:
            print(f"  [{issue}] EN: {en[:60]}")
            print(f"         OLD: {old[:60]}")
            print(f"         NEW: {new[:60]}")
            print()

    if apply:
        with open(LABELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"შენახულია: {LABELS_FILE}")
    else:
        print("--apply გარეშე: ცვლილებები არ შენახულა")


if __name__ == '__main__':
    main()
