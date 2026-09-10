#!/usr/bin/env python3
"""
deep_audit_tools.py
===================
ხელსაწყო-ფაილების ღრმა ხარისხის აუდიტი.

აუდიტს უტარებს ყველა data/ ფაილს (verses.json-ს არ ეხება - მხოლოდ იკითხება),
აღმოაჩენს:
- დარჩენილ ინგლისურ სიტყვებს
- ტრანსლიტერაციებს
- ბრუნვის შეცდომებს
- ქართულ-ინგლისურ არევს

გამოყენება:
    python3 deep_audit_tools.py
"""

import json
import os
import re
from collections import Counter

DATA_DIR = "data"

# ქართული და ლათინური ასოები
LATIN_RANGE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


def has_latin(text):
    return bool(set(text) & LATIN_RANGE)


def has_georgian(text):
    return bool(re.search(r'[ა-ჰ]', text))


def latin_ratio(text):
    if not text:
        return 0
    latin_count = sum(1 for c in text if c in LATIN_RANGE)
    return latin_count / len(text)


def is_false_positive(text):
    """რაც არ უნდა იქნეს დადგენილი როგორც შეცდომა"""
    patterns = [
        r'^[A-Z]{2,3}\.\d+\.\d+$',           # REF: GEN.1.1
        r'^[A-Z]{2,3}\.\d+\.\d+-\d+$',      # REF: GEN.1.1-2
        r'^[a-z][a-z0-9_-]+$',                # slug
        r'^\d+$',                              # number
        r'^(nave|torrey|tsk|merged)$',         # source
        r'^(old|new)$',                         # testament
        r'^(I{1,3}|IV|V?I{0,3})$',            # რომაული რიცხვები
        r'^(iii|ii|iv|i{1,3}|v?i{0,3})$',     # რომაული რიცხვები lowercase
    ]
    for p in patterns:
        if re.match(p, text):
            return True
    return False


def is_false_positive_field(path):
    """სტრუქტურული ველები, რომლებიც ყოველთვის ინგლისურია"""
    return any(path.endswith(s) for s in [
        '.slug', '.name_en', '.english', '.en',
        '.source', '.type', '.topic', '.book', '.testament',
        '.generated_at', '.version'
    ])


def audit_file(filepath, filename):
    """ერთი ფაილის აუდიტი"""
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            return {"error": f"JSON parse error: {e}"}

    results = {
        "filename": filename,
        "size_kb": os.path.getsize(filepath) / 1024,
        "type": type(data).__name__,
        "total_entries": 0,
        "problems": [],
        "stats": Counter(),
    }

    problems = results["problems"]
    stats = results["stats"]

    def check_value(value, path=""):
        if isinstance(value, str):
            stats["total_strings"] += 1

            if is_false_positive_field(path) or is_false_positive(value):
                return

            # ინგლისური + ქართული არევი
            if has_latin(value) and has_georgian(value):
                lr = latin_ratio(value)
                if lr > 0.3:
                    stats["mixed_high_latin"] += 1
                    if len(problems) < 200:
                        problems.append({
                            "path": path,
                            "type": "mixed_high_latin",
                            "value": value[:200],
                            "latin_ratio": round(lr, 2)
                        })
                elif lr > 0.05:
                    stats["mixed_some_latin"] += 1
                    eng_words = re.findall(r'\b[A-Za-z]{3,}\b', value)
                    eng_words = [w for w in eng_words if not is_false_positive(w)]
                    if eng_words and len(problems) < 200:
                        problems.append({
                            "path": path,
                            "type": "english_words",
                            "value": value[:200],
                            "english": eng_words[:5]
                        })

            # სრულად ინგლისური
            elif has_latin(value) and not has_georgian(value):
                if not is_false_positive(value) and len(value) > 5:
                    stats["fully_english"] += 1
                    if len(problems) < 200:
                        problems.append({
                            "path": path,
                            "type": "fully_english",
                            "value": value[:200]
                        })

            # ტრანსლიტერაციის მაგალითები
            translit_patterns = [
                r'\b(პარაბოლა|მირაკული|ვიზიტი|მაგნიფიკატი|ბენედიქტუსი)\b',
                r'\b(მინისტრი|დისციპული|პროფეტი|აპოსტოლი)\b',
                r'\b(ბაპტიზმი|კომუნიონი|რეზურექცია|ინკარნაცია)\b',
            ]
            for pattern in translit_patterns:
                if re.search(pattern, value):
                    stats["transliteration"] += 1
                    if len(problems) < 200:
                        problems.append({
                            "path": path,
                            "type": "transliteration",
                            "value": value[:200],
                            "match": re.findall(pattern, value)
                        })
                    break

            # ბრუნვის ზოგიერთი შეცდომა
            case_patterns = [
                (r'ეწვევა\s+[ა-ჰ]+ი\b', "dative_missing"),
                (r'კურნავს\s+[ა-ჰ]+ი\b', "dative_missing"),
                (r'ხედავს\s+[ა-ჰ]+ი\b', "dative_missing"),
                (r'ეუბნება\s+[ა-ჰ]+ი\b', "dative_missing"),
                (r'უწოდებს\s+[ა-ჰ]+ი\b', "dative_missing"),
            ]
            for pattern, case_type in case_patterns:
                if re.search(pattern, value):
                    stats[f"case_error_{case_type}"] += 1
                    if len(problems) < 200:
                        problems.append({
                            "path": path,
                            "type": "case_error",
                            "subtype": case_type,
                            "value": value[:200]
                        })
                    break

        elif isinstance(value, dict):
            for k, v in value.items():
                check_value(v, f"{path}.{k}" if path else k)

        elif isinstance(value, list):
            results["total_entries"] = max(results["total_entries"], len(value))
            for i, item in enumerate(value[:2000]):  # 2000 ელემენტამდე
                check_value(item, f"{path}[{i}]")

    check_value(data)
    return results


def run_full_audit():
    """ყველა ფაილის აუდიტი"""
    files = [
        "bible_word_groups.json",
        "crossrefs_index.json",
        "crossrefs_merged.json",
        "crossrefs_tsk.json",
        "label_fixes.json",
        "lexicon.json",
        "manual_ka.json",
        "theology_terms_fix.json",
        "topic_labels_ka.json",
        "topic_names_ka.json",
        "topical_index.json",
        "typo_report.json",
        "ud_lemma_lexicon.json",
        "verse_index.json",
        # verses.json არ ეხება - გამოტოვება
    ]

    all_results = {}

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  {filename}: არ არსებობს")
            continue

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"\n  შემოწმება: {filename} ({size_mb:.1f} MB)")

        result = audit_file(filepath, filename)
        all_results[filename] = result

        if "error" in result:
            print(f"    შეცდომა: {result['error']}")
        else:
            stats = result["stats"]
            total_problems = len(result["problems"])
            print(f"    strings: {stats.get('total_strings', 0):,}")
            print(f"    პრობლემები: {total_problems}")
            for k, v in sorted(stats.items()):
                if k != "total_strings" and v > 0:
                    print(f"      {k}: {v}")

    # რეპორტის შენახვა
    report_path = os.path.join(DATA_DIR, "quality_audit_report.json")
    serializable = {}
    for fname, result in all_results.items():
        serializable[fname] = {
            "size_kb": round(result.get("size_kb", 0), 1),
            "total_entries": result.get("total_entries"),
            "problem_count": len(result.get("problems", [])),
            "stats": dict(result.get("stats", {})),
            "sample_problems": result.get("problems", [])[:20]
        }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

    print(f"\n\nრეპორტი შენახულია: {report_path}")

    # ჯამური სტატისტიკა
    print("=" * 60)
    print("ჯამური სტატისტიკა:")
    total_problems = sum(len(r.get("problems", []))
                        for r in all_results.values()
                        if "error" not in r)
    print(f"  სულ პრობლემა: {total_problems}")

    ranked = sorted(
        ((fname, r) for fname, r in all_results.items() if "error" not in r),
        key=lambda x: len(x[1].get("problems", [])),
        reverse=True
    )
    print("\nფაილები პრობლემების მიხედვით:")
    for fname, result in ranked:
        count = len(result.get("problems", []))
        if count > 0:
            print(f"  {fname}: {count} პრობლემა")


if __name__ == "__main__":
    print("ხელსაწყო-ფაილების ხარისხის ღრმა აუდიტი")
    print("=" * 60)
    run_full_audit()
