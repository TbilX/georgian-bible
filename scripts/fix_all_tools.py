#!/usr/bin/env python3
"""
fix_all_tools.py
================
ხელსაწყო-ფაილებში დარჩენილი ინგლისური root-ების ქართულით ჩანაცვლება.

იყენებს:
- data/topic_names_ka.json (თემატური სახელები)
- data/name_dictionary_ka.json (ზოგადი სახელების ლექსიკონი)
- data/manual_ka.json (ხელით კურირებული)
- data/theology_terms_fix.json (თეოლოგიური ტერმინები)
- data/label_fixes.json (გრამატიკული ფიქსები)

გამოყენება:
    python3 fix_all_tools.py data/topic_labels_ka.json --dry-run
    python3 fix_all_tools.py data/topic_labels_ka.json --apply
"""

import argparse
import json
import re
import shutil
import os
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent / "data"


def genitive_form(nominative):
    """მეტობითი ბრუნვის გენერატორი."""
    if not nominative:
        return nominative
    if nominative.endswith('ის'):
        return nominative
    # უკვე მრავლობითი მეტობითი (თა ბოლო)
    if nominative.endswith('თა'):
        return nominative
    last = nominative[-1]
    if last == 'ი':
        return nominative[:-1] + 'ის'
    if last in ('ე', 'ა'):
        return nominative[:-1] + 'ის'
    if last in ('ო', 'უ'):
        return nominative + 'ს'
    return nominative + 'ის'


def combine_with_suffix(ka, suffix):
    """ქართული სიტყვის შერწყმა ქართულ ნაცვალსახელთან (ში, თან, ზე, დან, ...)."""
    if not ka or not suffix:
        return ka

    # პოსტპოზიციები, რომლებშიც 'ი' იკარგება
    postpositions_drop_i = {'ში', 'თან', 'ზე', 'დან', 'კენ', 'მდე', 'გარეშე', 'ვით'}

    if ka.endswith('ი') and suffix in postpositions_drop_i:
        return ka[:-1] + suffix

    # 'ს' (dative/accusative) ან 'ის' (genitive)
    if suffix == 'ის':
        return genitive_form(ka)
    if suffix == 'ს':
        if ka[-1] in ('ე', 'ა', 'ო', 'უ'):
            return ka + 'ს'
        if ka.endswith('ი'):
            return ka[:-1] + 'ს'
        return ka + 'ს'

    return ka + suffix


class ToolFixer:
    def __init__(self):
        self.dictionaries = {}
        self.label_fixes = {}
        self.load_dictionaries()

    def load_dictionaries(self):
        files = {
            "topic_names": DATA_DIR / "topic_names_ka.json",
            "name_dict": DATA_DIR / "name_dictionary_ka.json",
            "manual_ka": DATA_DIR / "manual_ka.json",
            "theology": DATA_DIR / "theology_terms_fix.json",
            "label_fixes": DATA_DIR / "label_fixes.json",
            "root_trans": DATA_DIR / "root_translations_ka.json",
        }

        for key, path in files.items():
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self.dictionaries[key] = json.load(f)
            else:
                self.dictionaries[key] = {}

        self.label_fixes = self.dictionaries.get("label_fixes", {})
        self.root_trans = self.dictionaries.get("root_trans", {}).get("root_translations", {})

    def lookup(self, word):
        """ინგლისური სიტყვის ძებნა ყველა ლექსიკონში."""
        lower = word.lower().strip()

        # 0. root_translations (ახალი ლექსიკონი დარჩენილი root-ებისთვის)
        if lower in self.root_trans:
            return self.root_trans[lower]

        # 1. topic_names (ზუზტი slug)
        topic_names = self.dictionaries.get("topic_names", {})
        if lower in topic_names:
            return topic_names[lower]

        # 2. name_dictionary
        name_dict = self.dictionaries.get("name_dict", {})
        if lower in name_dict:
            return name_dict[lower]

        # 3. manual_ka
        manual = self.dictionaries.get("manual_ka", {})
        if lower in manual:
            return manual[lower]

        # 4. theology_terms_fix
        theology = self.dictionaries.get("theology", {})
        if lower in theology:
            return theology[lower]

        # 5. გადიდებული/პატარა ასოების ვარიაციები
        variants = [
            lower,
            word.lower(),
            word.title(),
            word.upper(),
        ]

        for d in [topic_names, name_dict, manual, theology]:
            for v in variants:
                if v in d:
                    return d[v]

        return None

    def apply_term_fixes(self, text):
        """label_fixes.json-ის term_replacements გამოყენება."""
        result = text
        for old, new in self.label_fixes.get("term_replacements", {}).items():
            if old in result:
                result = result.replace(old, new)
        return result

    def apply_phrase_fixes(self, text):
        """label_fixes.json-ის phrase_fixes გამოყენება."""
        result = text
        for old, new in self.label_fixes.get("phrase_fixes", {}).items():
            if old in result:
                result = result.replace(old, new)
        return result

    def fix_english_in_text(self, text):
        """ინგლისური root-ების ძებნა და ჩანაცვლება."""
        if not isinstance(text, str) or not text:
            return text

        # regex: ინგლისური ასოები, შემდეგ ქართული ნაცვალსახელი
        pattern = re.compile(r'([A-Za-z]{3,})([ა-ჰ]*)')

        result = text
        # ვეძებთ ყველა დამთხვევას (თავიდან ბოლომდი)
        # რადგან ჩანაცვლება ცვლის სიგრძეს, გამოვიყენებთ finditer-ს და ახალგანლაგებულად
        for match in list(pattern.finditer(text))[::-1]:
            word = match.group(1)
            suffix = match.group(2)
            ka = self.lookup(word)
            if ka:
                replacement = combine_with_suffix(ka, suffix)
                result = result[:match.start()] + replacement + result[match.end():]

        return result

    def fix_apostrophes(self, text):
        """ქართული სიტყვის შემდეგ ' -> მეტობითი, გარდა postposition-ებისა."""
        # postposition ფუძეები და function words
        postposition_suffixes = {
            'ში', 'ზე', 'დან', 'თან', 'კენ', 'მდე', 'გარეშე',
            'ვით', 'ად', 'მიერ', 'გამო', 'თვის', 'შორის', 'ბოლოს',
            'წინ', 'უკან', 'ქვეშ', 'მიმართ', 'გარეშე', 'ვინ', 'რომ',
            'რადგან', 'თუ', 'სად'
        }

        pattern = re.compile(r"([ა-ჰ]+)'(?=\s|$|[,.;:\-—()])")

        def repl(m):
            word = m.group(1)
            # თუ სიტყვა მთავრდება postposition-ის ნაწილით, უბრალოდ წავშალოთ '
            if any(word.endswith(s) for s in postposition_suffixes):
                return word
            # თუ function word (მიერ, შორის, მიმართ და ა.შ.) - ასევე წავშალოთ
            if word in postposition_suffixes:
                return word
            return genitive_form(word)

        return pattern.sub(repl, text)

    def fix_text(self, text):
        """უნივერსალური ტექსტის გამოსწორება."""
        if not isinstance(text, str):
            return text

        # 1. ინგლისური root-ების ჩანაცვლება (უსაფრთხო)
        result = self.fix_english_in_text(text)

        return result

    def fix_recursive(self, data):
        """რეკურსიულად გამოსწორება."""
        if isinstance(data, str):
            return self.fix_text(data)
        elif isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                new_dict[k] = self.fix_recursive(v)
            return new_dict
        elif isinstance(data, list):
            return [self.fix_recursive(item) for item in data]
        return data

    def fix_file(self, filepath, dry_run=False, max_changes=10):
        """ერთი ფაილის გამოსწორება."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        fixed_data = self.fix_recursive(data)

        # სტრიქონების დათვლა
        changes = 0
        samples = []

        def compare(old, new, path=""):
            nonlocal changes
            if isinstance(old, str) and isinstance(new, str):
                if old != new:
                    changes += 1
                    if len(samples) < max_changes:
                        samples.append((path, old[:100], new[:100]))
                return
            if isinstance(old, dict) and isinstance(new, dict):
                for k in old:
                    compare(old[k], new.get(k, old[k]), f"{path}.{k}" if path else k)
            elif isinstance(old, list) and isinstance(new, list):
                for i, (o, n) in enumerate(zip(old, new)):
                    compare(o, n, f"{path}[{i}]")

        compare(data, fixed_data)

        if not dry_run and changes > 0:
            bak = filepath.with_suffix(filepath.suffix + ".bak2")
            shutil.copy2(filepath, bak)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(fixed_data, f, ensure_ascii=False, indent=2)
            print(f"  სარეზერვო: {bak}")
            print(f"  შენახულია: {filepath}")

        print(f"  შეცვლილი string-ები: {changes}")
        for path, old, new in samples:
            print(f"    {path}")
            print(f"      {old} -> {new}")

        return fixed_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="JSON ფაილის გზა")
    parser.add_argument("--dry-run", action="store_true", help="არ შეინახო")
    parser.add_argument("--max-samples", type=int, default=20)
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ფაილი არ არსებობს: {filepath}")
        return

    fixer = ToolFixer()
    print(f"=== {filepath.name} ===")
    fixer.fix_file(filepath, dry_run=args.dry_run, max_changes=args.max_samples)


if __name__ == "__main__":
    main()
