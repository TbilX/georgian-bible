#!/usr/bin/env python3
"""
ბიბლიის ტექსტური და ტიპოგრაფიული შეცდომების ავტომატური დეტექტორი
================================================================
იყენებს სიხშირულ ანალიზს, ლევენშტეინის მანძილს (Levenshtein Distance)
და რეგულარულ გამოსახულებებს შეცდომების აღმოსაჩენად.

გაშვება: python3 find_typos.py
შედეგი: data/typo_report.json + კონსოლის ანგარიში

უსაფრთხოა — არ ცვლის მონაცემებს, მხოლოდ ანგარიშს ქმნის.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================================
#  დამხმარე ფუნქციები
# ============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """გამოითვლის ორ სიტყვას შორის ასოების განსხვავებას (მანძილს)."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def extract_words(text: str) -> list:
    """ტექსტიდან ამოიღებს მხოლოდ ქართულ სიტყვებს (მხედრული + არქაული)."""
    if not text:
        return []
    pattern = r'[ა-ჰჱჲჳჴჵ]+'
    return re.findall(pattern, text.lower())


# ============================================================================
#  მთავარი სკანირება
# ============================================================================

def scan_for_typos():
    print("=" * 70)
    print("  ბიბლიის ტექსტური და ტიპოგრაფიული შეცდომების ავტომატური დეტექტორი")
    print("=" * 70)

    data_dir = Path("data")
    index_file = data_dir / "verse_index.json"

    if not index_file.exists():
        print(f"❌ ფაილი ვერ მოიძებნა: {index_file}")
        sys.exit(1)

    # მონაცემების ჩატვირთვა
    print("\n📖 მონაცემების ჩატვირთვა...")
    with open(index_file, 'r', encoding='utf-8') as f:
        verses = json.load(f)

    print(f"   სულ მუხლები: {len(verses):,}")

    # 1. სიტყვების სიხშირის დათვლა
    print("\n📊 სიტყვების სიხშირის დათვლა...")
    freq_new = Counter()
    freq_old = Counter()
    word_locations_new = defaultdict(list)
    word_locations_old = defaultdict(list)

    for v in verses:
        ref = f"{v['book']} {v['chapter']}:{v['verse']}"
        words_new = extract_words(v.get('new', ''))
        words_old = extract_words(v.get('old', ''))
        freq_new.update(words_new)
        freq_old.update(words_old)
        for w in set(words_new):
            word_locations_new[w].append(ref)
        for w in set(words_old):
            word_locations_old[w].append(ref)

    print(f"   ახალი ქართული: {len(freq_new):,} უნიკალური სიტყვა, {sum(freq_new.values()):,} სულ")
    print(f"   ძველი ქართული: {len(freq_old):,} უნიკალური სიტყვა, {sum(freq_old.values()):,} სულ")

    # 2. სავარაუდო ტიპოგრაფიული შეცდომები (Frequency=1, Levenshtein=1)
    print("\n🔍 1. სავარაუდო ტიპოგრაფიული შეცდომების ძებნა...")
    print("   (სიტყვა 1-ხელ გვხვდება, მაგრამ 1 ასოთი განსხვავდება ხშირი სიტყვისგან)")

    suspects_new = find_typo_suspects(freq_new, word_locations_new, 'new')
    suspects_old = find_typo_suspects(freq_old, word_locations_old, 'old')

    print(f"   ნაპოვნია ახალ ქართულში: {len(suspects_new)}")
    print(f"   ნაპოვნია ძველ ქართულში: {len(suspects_old)}")

    # 3. ტექნიკური შეცდომების სკანირება
    print("\n🔍 2. ტექნიკური და OCR შეცდომების ძებნა...")
    formatting_errors = find_formatting_errors(verses)
    print(f"   ნაპოვნია: {len(formatting_errors)} ტექნიკური ხარვეზი")

    # 4. OCR პატერნები
    print("\n🔍 3. ცნობილი OCR/ტიპოგრაფიული პატერნების ძებნა...")
    ocr_errors = find_ocr_patterns(verses)
    print(f"   ნაპოვნია: {len(ocr_errors)}")

    # 5. ანგარიშის გამოტანა
    print("\n" + "=" * 70)
    print("  შედეგები")
    print("=" * 70)

    all_suspects = suspects_new + suspects_old

    if all_suspects:
        print(f"\n📍 სავარაუდო ტიპოგრაფიული შეცდომები (სიხშირე=1, მანძილი=1):")
        print(f"   {'სავარაუდო':<25} → {'სწორი ვარიანტი':<25} {'სიხშირე':>8} {'ტექსტი':>6} {'მუხლი'}")
        print("   " + "-" * 90)
        for item in sorted(all_suspects, key=lambda x: -x['frequent_count']):
            loc = item['locations'][0] if item['locations'] else '?'
            print(f"   {item['suspect']:<23} → {item['suggested']:<23} {item['frequent_count']:>8}x {item['text_type']:>6} {loc}")

    if formatting_errors:
        print(f"\n📍 ტექნიკური ხარვეზები (პირველი 20):")
        for item in formatting_errors[:20]:
            print(f"   [{item['ref']}] {item['issue']}")
            if item.get('snippet'):
                print(f"      ტექსტი: \"{item['snippet']}\"")

    if ocr_errors:
        print(f"\n📍 OCR პატერნები (პირველი 20):")
        for item in ocr_errors[:20]:
            print(f"   [{item['ref']}] {item['issue']}")
            if item.get('snippet'):
                print(f"      ტექსტი: \"{item['snippet']}\"")

    # 6. შედეგების შენახვა JSON-ად
    report = {
        'summary': {
            'total_verses': len(verses),
            'unique_words_new': len(freq_new),
            'unique_words_old': len(freq_old),
            'typo_suspects_new': len(suspects_new),
            'typo_suspects_old': len(suspects_old),
            'formatting_errors': len(formatting_errors),
            'ocr_errors': len(ocr_errors),
        },
        'typo_suspects_new': suspects_new,
        'typo_suspects_old': suspects_old,
        'formatting_errors': formatting_errors,
        'ocr_errors': ocr_errors,
    }

    report_path = data_dir / "typo_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 სრული ანგარიში შენახულია: {report_path}")
    print(f"   სულ სავარაუდო შეცდომა: {len(all_suspects) + len(formatting_errors) + len(ocr_errors)}")


GEORGIAN_LETTERS = list('აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰჱჲჳჴჵ')


def generate_edit_distance_1(word):
    """გამოითვლის ყველა ვარიანტს, რომელიც 1 ასოთი განსხვავდება მოცემული სიტყვისგან.
    ბევრად უფრო სწრაფია ვიდრე Levenshtein-ის ყველა წყვილზე გამოთვლა."""
    variants = set()
    # 1. ჩანაცვლება (substitution)
    for i in range(len(word)):
        for c in GEORGIAN_LETTERS:
            if c != word[i]:
                variants.add(word[:i] + c + word[i+1:])
    # 2. წაშლა (deletion)
    for i in range(len(word)):
        variants.add(word[:i] + word[i+1:])
    # 3. ჩასმა (insertion)
    for i in range(len(word) + 1):
        for c in GEORGIAN_LETTERS:
            variants.add(word[:i] + c + word[i:])
    return variants


def find_typo_suspects(freq, word_locations, text_type):
    """პოულობს სიტყვებს, რომლებიც 1-ხელ გვხვდება და 1 ასოთი განსხვავდება ხშირი სიტყვისგან.
    ალგორითმი: გამოითვლის იშვიათი სიტყვის ყველა 1-მანძილიან ვარიანტს და ამოწმებს
    არის თუ არა რომელიმე მათგანი ხშირ სიტყვათა სიაში. O(L*33) თითო სიტყვაზე."""
    suspects = []

    frequent_set = {w: c for w, c in freq.items() if c >= 15}
    rare_words = [w for w, c in freq.items() if c == 1 and len(w) >= 4]

    for rare_word in rare_words:
        variants = generate_edit_distance_1(rare_word)
        best_match = None
        best_freq = 0
        for variant in variants:
            if variant in frequent_set:
                fv = frequent_set[variant]
                if fv > best_freq:
                    best_match = variant
                    best_freq = fv
        if best_match:
            suspects.append({
                'suspect': rare_word,
                'suggested': best_match,
                'frequent_count': best_freq,
                'text_type': text_type,
                'locations': word_locations.get(rare_word, []),
            })

    return suspects


def find_formatting_errors(verses):
    """პოულობს ტექნიკურ ხარვეზებს: ლათინური ასოები, ორმაგი ჰაერები, პუნქტუაცია."""
    errors = []

    for v in verses:
        ref = f"{v['book']} {v['chapter']}:{v['verse']}"
        text_new = v.get('new', '') or ''
        text_old = v.get('old', '') or ''

        # ა) ლათინური ასოები ქართულ ტექსტში
        for label, text in [('ახალი', text_new), ('ძველი', text_old)]:
            latin = re.findall(r'[a-zA-Z]+', text)
            if latin:
                errors.append({
                    'ref': ref,
                    'issue': f"ლათინური ასოები ({label}): {latin}",
                    'snippet': text[:80],
                })

        # ბ) ორმაგი ჰაერები
        for label, text in [('ახალი', text_new), ('ძველი', text_old)]:
            if '  ' in text:
                errors.append({
                    'ref': ref,
                    'issue': f"ორმაგი ჰაერი ({label})",
                    'snippet': text[:80],
                })

        # გ) ციფრები ტექსტში
        for label, text in [('ახალი', text_new), ('ძველი', text_old)]:
            digits = re.findall(r'[0-9]+', text)
            if digits:
                errors.append({
                    'ref': ref,
                    'issue': f"ციფრები ტექსტში ({label}): {digits}",
                    'snippet': text[:80],
                })

        # დ) სასვენი ნიშანი ჰაერის გარეშე
        for label, text in [('ახალი', text_new), ('ძველი', text_old)]:
            bad_punct = re.findall(r'[ა-ჰჱჲჳჴჵ][\.,;:!?][ა-ჰჱჲჳჴჵ]', text)
            if bad_punct:
                errors.append({
                    'ref': ref,
                    'issue': f"სასვენი ნიშანი ჰაერის გარეშე ({label}): {bad_punct[:3]}",
                    'snippet': text[:80],
                })

    return errors


def find_ocr_patterns(verses):
    """პოულობს ცნობილ OCR/ტიპოგრაფიულ პატერნებს."""
    errors = []

    for v in verses:
        ref = f"{v['book']} {v['chapter']}:{v['verse']}"
        text_new = v.get('new', '') or ''

        # სიტყვები რომლებიც ბოლოვდება ღ-ით (არანორმალური ახალ ქართულში)
        words = extract_words(text_new)
        for w in words:
            if len(w) >= 3 and w.endswith('ღ'):
                errors.append({
                    'ref': ref,
                    'issue': f"სიტყვა ბოლოვდება 'ღ'-ით: '{w}'",
                    'snippet': text_new[:80],
                })

        # ზედმეტი ასოების გამეორება (მაგ: "ააა", "ეეე")
        repeats = re.findall(r'([ა-ჰ])\1{2,}', text_new)
        if repeats:
            errors.append({
                'ref': ref,
                'issue': f"ასოს ზედმეტი გამეორება: {repeats}",
                'snippet': text_new[:80],
            })

    return errors


if __name__ == '__main__':
    scan_for_typos()
