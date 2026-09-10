#!/usr/bin/env python3
"""
fix_labels_auto.py
==================
თემატური ენციკლოპედიის label-ების ავტომატური კორექცია.

იყენებს data/label_fixes.json ლექსიკონს:
- term_replacements: უცხო ტერმინების ჩანაცვლება
- preposition_fixes: წინდებულების გამოსწორება
- phrase_fixes: ფრაზების ჩანაცვლება
- book_abbrev_fixes: წიგნების აბრევიატურების ნორმალიზაცია
- cleanup_patterns: დარჩენილი ინგლისური არტიკლების წაშლა

გამოყენება:
    python3 fix_labels_auto.py           # dry-run (შემოწმება)
    python3 fix_labels_auto.py --apply   # შენახვა
"""

import json
import re
import sys
import shutil
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"
FIXES_FILE = DATA_DIR / "label_fixes.json"


def fix_label(label, fixes):
    """ერთი label-ის ავტომატური კორექცია."""
    # წინასწარი ნორმალიზაცია: მრუდი/სხვადასხვა აპოსტროფების გაბჭვillation
    result = label.replace('\u2018', "'").replace('\u2019', "'")\
                  .replace('\u201A', "'").replace('\u201B', "'")\
                  .replace('\u0060', "'")
    changes = []

    # ფაზა 1: ფრაზული ჩანაცვლებები (ყველაზე სპეციფიკური, ჯერ)
    for old, new in fixes.get("phrase_fixes", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"ფრაზა: {old} -> {new}")

    # ფაზა 2: წინდებულების გამოსწორება
    for old, new in fixes.get("preposition_fixes", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"წინდებული: {old} -> {new}")

    # ფაზა 3: ტერმინოლოგიური ჩანაცვლებები (მთელი სიტყვის)
    for old, new in fixes.get("term_replacements", {}).items():
        # მთელი სიტყვის ჩანაცვლება (ქართული word boundary)
        # ქართულში სიტყვის საზღვარი: არა-ქართული ასო ან სტრინგის დასაწყისი/დასასრული
        pattern = r'(?<![ა-ჰ])' + re.escape(old) + r'(?![ა-ჰ])'
        new_result = re.sub(pattern, new, result)
        if new_result != result:
            changes.append(f"ტერმინი: {old} -> {new}")
            result = new_result

    # ფაზა 4: წიგნების აბრევიატურების ნორმალიზაცია
    # "მე ნეშ" -> "I ნეშ", "მე მეფ" -> "I მეფ"
    for old, new in fixes.get("book_abbrev_fixes", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"აბრევიატურა: {old} -> {new}")

    # ფაზა 5: დარჩენილი ინგლისური არტიკლების წაშლა
    # "theის" -> "" (უკვე ფაზა 1-ში გამოსწორდა, მაგრამ დარჩენილი შემთხვევები)
    for old, new in fixes.get("cleanup_patterns", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"გასუფთავება: {old} -> (წაშლა)")

    # ფაზა 5b: სიმბოლოების გასუფთავება (&, ?, ')
    for old, new in fixes.get("symbol_cleanup", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"სიმბოლო: {old!r} -> {new!r}")

    # ფაზა 5c: აპოსტროფების გამოსწორება
    # 'X' -> X-ის (მაგ: 'მარიამი' -> მარიამის)
    for old, new in fixes.get("apostrophe_fixes", {}).items():
        pattern = re.escape(old)
        new_result = re.sub(pattern, new, result)
        if new_result != result:
            changes.append(f"აპოსტროფი: {old} -> {new}")
            result = new_result

    # ფაზა 5d: წინდებულების კონტექსტური გამოსწორება
    # (ხებრონთან?) -> (ხებრონში)
    for old, new in fixes.get("preposition_context_fixes", {}).items():
        if old in result:
            result = result.replace(old, new)
            changes.append(f"წინდებული (კონტექსტი): {old} -> {new}")

    # ფაზა 5d2: წიგნების აბრევიატურების ნორმალიზაცია რეგექსით
    # "მათ 1:1" -> "მათე 1:1" (მხოლოდ როცა რიცხვი მოდის)
    book_patterns = [
        (r'(?<![ა-ჰ])მათ(?=\s+\d)', 'მათე'),
        (r'(?<![ა-ჰ])მარკ(?=\s+\d)', 'მარკოზი'),
        (r'(?<![ა-ჰ])ლუკ(?=\s+\d)', 'ლუკა'),
        (r'(?<![ა-ჰ])იოან(?=\s+\d)', 'იოანე'),
    ]
    for pattern, repl in book_patterns:
        new_result = re.sub(pattern, repl, result)
        if new_result != result:
            result = new_result
            changes.append(f"წიგნი: {pattern} -> {repl}")

    # ფაზა 5e: ბრუნვის შეცდომების ავტომატური გამოსწორება
    # "verb Xი" -> "verb Xს" (ინგლისური nominative -> ქართული dative)
    # მხოლოდ სახელების/არსებითი სახელებისთვის, არა ნაცვალსახელებისთვის/ზედსართავებისთვის
    excluded_words = set(['მისი', 'შენი', 'ჩვენი', 'თქვენი', 'ის', 'ეს', 'რა', 'ვინ',
                         'იგი', 'ისინი', 'აქ', 'იქ', 'აქაც', 'იქაც', 'სხვა', 'საკუთარი',
                         'სულიერი', 'ზოგიერთი', 'ყოველი', 'თითოეული', 'ნაკლები', 'მეტი',
                         'კარგი', 'ცუდი', 'დიდი', 'პატარა', 'ახალი', 'ძველი', 'უკანასკნელი',
                         'პირველი', 'მეორე', 'მესამე', 'უახლესი', 'უძველესი', 'ადამიანი',
                         'კაცი', 'ქალი', 'გოგო', 'ბიჭი', 'ბავშვი', 'ხატოვანი', 'იმის',
                         'ამის', 'მაგის', 'ისეთი', 'ამის', 'მის', 'ასეთი', 'ისეთი', 'უცხო',
                         'ნაცნობი', 'უცნობი', 'მდიდარი', 'ღარიბი', 'ძლიერი', 'სუსტი',
                         'ცოცხალი', 'მკვდარი', 'ჯანმრთელი', 'ავადმყოფი', 'ჭეშმარიტი',
                         'ბევრი', 'ნაკლები', 'საკმარისი', 'საჭირო', 'შესაბამისი', 'შესაფერისი',
                         'საკმაო', 'საგანგებო', 'საგანგებ', 'განსაკუთრებულ', 'აღნიშნულ', 'მოხსენიებულ',
                         'მცდარი', 'წმინდა', 'ცოდული', 'უდანაშაულო', 'უბიწო',
                         'უბიწოების', 'განაჩენის', 'მოცემული', 'გადაცემული', 'აღნიშნული',
                         'განხილული', 'მოხსენიებული', 'გათვალისწინებული', 'განსაკუთრებული',
                         'მოთხოვნილი', 'მითითებული', 'მინიშნებული', 'დამტკიცებული'])
    adjective_endings = ('ური', 'ები', 'ება', 'ობა', 'ობის', 'ების', 'ულ', 'ულ', 'ად', 'ით',
                         'იან', 'ვან', 'მან', 'არ', 'ებრივ', 'ობრივ', 'ურად', 'ებრივად')

    def case_repl(match):
        verb_part = match.group(1)
        word = match.group(2)
        after = match.group(3)

        # გადავამოწმოთ სიტყვა როგორც ნომინატიური ფორმით (word + 'ი')
        # ასევე სტემის სახით (მარტო word)
        full_word = word + 'ი'
        if (full_word in excluded_words or word in excluded_words or
            len(word) <= 2 or
            any(word.endswith(end) for end in adjective_endings) or
            any(full_word.endswith(end) for end in adjective_endings)):
            return match.group(0)

        changes.append(f"ბრუნვა: {full_word} -> {word}ს")
        return f"{verb_part} {word}ს{after}"

    for verb in fixes.get("case_fixes", {}).keys():
        pattern = r'(' + re.escape(verb) + r')\s+([ა-ჰ]+)ი(\s|$|[;:,—\.\(\)\-])'
        new_result = re.sub(pattern, case_repl, result)
        result = new_result

    # ფაზა 6: ზოგადი გასუფთავება
    # ზედმეტი სივრცეები
    result = re.sub(r'  +', ' ', result).strip()
    # " — " შენარჩუნება, მაგრამ ზედმეტი სივრცეები წავშალოთ
    result = re.sub(r'\s+—\s+', ' — ', result)

    # ფაზა 7: "მიმართ" ბოლოში წაშლა (ინგლისური "to" არასწორი თარგმანი)
    # "გამოვლენილი მიმართ —" -> "გამოვლენილი —"
    # "მიმართ —" -> "—"
    if 'მიმართ —' in result:
        result = result.replace('მიმართ —', '—')
        changes.append("გასუფთავება: მიმართ — -> —")
    if result.rstrip().endswith('მიმართ'):
        result = result.rstrip()[:-len('მიმართ')].rstrip()
        changes.append("გასუფთავება: ბოლო მიმართ -> (წაშლა)")

    # ფაზა 8: ზედმეტი სივრცეები ხელახლა
    result = re.sub(r'  +', ' ', result).strip()
    result = re.sub(r'\s+—\s+', ' — ', result)

    return result, changes


def main():
    apply = "--apply" in sys.argv

    print("=== Label-ების ავტომატური კორექცია ===")
    print()

    # ჩატვირთვა
    with open(LABELS_FILE, "r", encoding="utf-8") as f:
        labels = json.load(f)
    print(f"  სულ label: {len(labels):,}")

    with open(FIXES_FILE, "r", encoding="utf-8") as f:
        fixes = json.load(f)
    # _comment გამოვრიცხოთ
    fixes = {k: v for k, v in fixes.items() if not k.startswith("_")}
    total_fixes = sum(len(v) for v in fixes.values())
    print(f"  ფიქსის წესები: {total_fixes}")
    print()

    # კორექცია
    changed_count = 0
    change_types = Counter()
    samples = []

    for key, label in labels.items():
        new_label, changes = fix_label(label, fixes)
        if new_label != label:
            changed_count += 1
            for c in changes:
                change_types[c.split(":")[0]] += 1
            if len(samples) < 20:
                samples.append((key[:30], label[:60], new_label[:60], changes))
            labels[key] = new_label

    print(f"  შეიცვალა: {changed_count:,} / {len(labels):,} ({changed_count/len(labels)*100:.1f}%)")
    print()

    print("ცვლილებების ტიპები:")
    for ctype, count in change_types.most_common():
        print(f"  {ctype}: {count}")
    print()

    print("ცვლილებების ნიმუშები (პირველი 20):")
    for key, old, new, changes in samples:
        print(f"  {old}")
        print(f"    -> {new}")
        print(f"    [{', '.join(changes)}]")
        print()

    # დარჩენილი პრობლემების აუდიტი
    print("=== დარჩენილი პრობლემების აუდიტი ===")
    remaining = {
        "უცხო_ტერმინი": 0,
        "დან_წინდებული": 0,
        "მიერ_წინდებული": 0,
        "თან_წინდებული": 0,
        "მიმართ_ბოლოში": 0,
        "ინგლისური_სიტყვა": 0,
        "მე_ნეშ_პრეფიქსი": 0,
        "the_არტიკლი": 0,
    }

    foreign_terms = ["მაგნიფიკატი", "ვიზიტი", "მინისტრი", "პარაბოლა", "მირაკული",
                     "მაგები", "პროფეტი", "აპოსტოლი", "ფუნქცია", "დიზაინი",
                     "მოდელი", "სიმბოლო", "კომუნიკაცია", "ვალუტა"]

    for key, label in labels.items():
        for term in foreign_terms:
            if term in label.lower():
                remaining["უცხო_ტერმინი"] += 1
                break

        if re.search(r'(?<![ა-ჰ])დან [ა-ჰ]+', label):
            remaining["დან_წინდებული"] += 1
        if re.search(r'(?<![ა-ჰ])მიერ [ა-ჰ]+', label):
            remaining["მიერ_წინდებული"] += 1
        if re.search(r'(?<![ა-ჰ])თან [ა-ჰ]+', label):
            remaining["თან_წინდებული"] += 1
        if label.rstrip().endswith('მიმართ') or ' მიმართ —' in label:
            remaining["მიმართ_ბოლოში"] += 1
        if re.search(r'[a-zA-Z]{3,}', label) and not re.search(r'\b(III|II|IV)\b', label):
            remaining["ინგლისური_სიტყვა"] += 1
        if 'მე ნეშ' in label or 'მე მეფ' in label or 'მე კორ' in label or 'მე პეტ' in label or 'მე ტიმ' in label or 'მე იოა' in label or 'მე თეს' in label:
            remaining["მე_ნეშ_პრეფიქსი"] += 1
        if re.search(r'(?<![a-zA-Z])the(?![a-zA-Z])', label, re.IGNORECASE):
            remaining["the_არტიკლი"] += 1

    for cat, count in remaining.items():
        print(f"  {cat}: {count}")

    print()

    if apply:
        # სარეზერვო ასლი
        bak = LABELS_FILE.with_suffix(".json.bak")
        shutil.copy2(LABELS_FILE, bak)
        print(f"სარეზერვო ასლი: {bak}")

        with open(LABELS_FILE, "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)
        print(f"შენახულია: {LABELS_FILE}")
    else:
        print("--apply გარეშე: ცვლილებები არ შენახულა.")
        print("გასაშვებად: python3 fix_labels_auto.py --apply")


if __name__ == "__main__":
    main()
