#!/usr/bin/env python3
"""
fix_labels_ai.py
================
AI-ს გამოყენება რთული/კონტექსტური label-ების კორექციისთვის.

⚠️  საჭიროებს API key-ს: ANTHROPIC_API_KEY (ან OPENAI_API_KEY, თუ ხელით შეცვლით)

მიდგომა:
    1. იმოძებნება საეჭვო label-ები identify_bad_labels.py-ს მსგავსი ევრისტიკით
    2. AI-ს ეგზავნება batch-ად (20-30 label)
    3. პასუხები იწმინდება და ინახება
    4. შეცდომის შემთხვევაში - ავტომატური retry და/ან გადარჩენა

გამოყენება:
    export ANTHROPIC_API_KEY="..."
    python3 fix_labels_ai.py --test 100       # 100 label-ის ტესტი (~$0.20)
    python3 fix_labels_ai.py --run 500        # 500 label-ის batch
    python3 fix_labels_ai.py --all            # ყველა საეჭვო

რეკომენდაცია:
    ჯერ --test 100, შემდეგ --all (ან --run N თითოეულ ნაწილად)
"""

import json
import re
import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

# === კონფიგურაცია ===
DATA_DIR = Path(__file__).parent / "data"
LABELS_FILE = DATA_DIR / "topic_labels_ka.json"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Default: Anthropic. შეცვალეთ თუ OpenAI/Gemini გინდათ.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic").lower()
MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-5-20250929")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "20"))
MAX_RETRIES = 3
RETRY_DELAY = 5  # წამი


# === საეჭვო label-ების იდენტიფიკაცია ===
SUSPICIOUS_PATTERNS = [
    # ბრუნვის შეცდომები (ზმნა + ნომინატიური)
    (r"\b(ეწვევა|კურნავს|ხედავს|აძლევს|ბრძანებს|ეუბნება|ეცხადება|"
     r"მოკლავს|აირჩევს|მოაქვს|იხილავს|მიიღებს|ეძებს|ხსნის|აღადგენს|"
     r"ფარავს|იცავს|ამცნობს|მართავს|ინახავს|დებს|აყენებს|აძევებს|"
     r"ჰკითხავს|კრძალავს|განაჩენს|აგდებს|აქცევს|იჭერს|აწვდის)\s+[ა-ჰ]+ი\b",
     "ბრუნვის შეცდომა"),

    # უცხოური ტერმინები
    (r"\b(მაგნიფიკატი|ბენედიქტუსი|ვიზიტი|პარაბოლა|მირაკული|მაგები|"
     r"პროფეტი|აპოსტოლი|მინისტრი|დისციპულ|კომისია|დეპუტატი|პრეზიდენტი)\b",
     "უცხო ტერმინი"),

    # ინგლისური სიტყვა/სახელი
    (r"[A-Za-z]{3,}", "ინგლისური სიტყვა"),

    # წინდებულის არასწორი ფორმა
    (r"\([ა-ჰ]+თან\?\)", "თან? კონტექსტში"),
    (r"\([ა-ჰ]+თან\)$", "თან კონტექსტში"),
    (r"\bდან\s+[ა-ჰ]+ი\b", "დან წინდებული"),
    (r"\bმიერ\s+[ა-ჰ]+ი\b", "მიერ წინდებული"),

    # აპოსტროფები
    (r"'[ა-ჰ]+'", "აპოსტროფები"),
    (r"[ა-ჰ]+'ს\b", "აპოსტროფი ს"),

    # კითხვის/გაურკვევლობის ნიშნები
    (r"\?\)", "?)"),
    (r"\([ა-ჰ]+\?", "(X?"),
]


# === PROMPT-ები ===
SYSTEM_PROMPT = """შენ ხარ ქართული ბიბლიური ტექსტების პროფესიონალი რედაქტორი. გაქვს გამოცდილება საქართველოს საპატრიარქოს გამოცემებთან და თანამედროვე ქართული ბიბლიის რედაქციასთან.

მოცემულია ბიბლიური თემატური ენციკლოპედიის label-ები. ისინი ინგლისურიდან მანქანურადაა ნათარგმნი და შეიცვალა ქართულად, მაგრამ კონტექსტური გრამატიკის, წინდებულების, სიტყვათა წყობისა და ზოგიერთი სახელის თარგმანის შეცდომებია.

შენი ამოცანა: გამოასწორო თითოეული label ისე, რომ იყოს ბუნებრივი, გასაგები ქართული, რომელიც შეესაბამება ბიბლიურ კონტექსტს.

მკაცრი წესები:
1. გამოასწორე ბრუნვები (მოქმედებითი/მიცემითი/ვითარებითი) - ქართული გრამატიკის მიხედვით.
2. გამოასწორე წინდებულები: (ხებრონთან?) → (ხებრონში), (ბეთლემთან) → (ბეთლემში), (იერიხონთან) → (იერიხოსთან).
3. გამოასწორე სიტყვათა წყობა - ქართული, არა ინგლისური წყობით.
4. თარგმნე დარჩენილი ინგლისური სახელები/სიტყვები ქართული ტრადიციული ტრანსლიტერაციით (არიმათია, იოქტანი, ცელოფხადი და ა.შ.).
5. უცხოური ტერმინები ჩაანაცვლე: მაგნიფიკატი → საგალობელი, პარაბოლა → იგავი, მირაკული → სასწაული, მაგები → მოგვები.
6. აპოსტროფები 'X' შეცვალე ბუნებრივი მეტობითი ბრუნვით (მაგ: 'მარიამი' → მარიამის).
7. კითხვის ნიშნები (X?) წაშალე, თუ უბრალოდ გაურკვევლობას აღნიშნავს.
8. შეინარჩუნე ბიბლიური მუხლის რეფერენსი (მაგ: "მათ 3:11" → "მათე 3:11").
9. შეინარჩუნე შინაარსი. არა დაამატო ახალი ინფორმაცია.

წიგნების ნორმალური ფორმები:
მათ → მათე, მარკ → მარკოზი, ლუკ → ლუკა, იოან → იოანე
I ნეშ → 1 ნეშტთა, II მეფ → 2 მეფეთა, III მეფ → 3 მეფეთა

ტერმინოლოგია:
მოციქული, წინასწარმეტყველი, იგავი, სასწაული, საგალობელი, მოგვები, ნათლისღება

მხოლოდ გამოსწორებული label-ები დააბრუნე, სულ ნომრით."""

FEW_SHOT_EXAMPLES = """მაგალითები:

INPUT: 1. მარიამი ეწვევა ელისაბედი ლუკ 1:39-45
OUTPUT: 1. მარიამი ეწვევა ელისაბედს, ლუკა 1:39-45

INPUT: 2. 'მარიამი' საგალობელი (ხებრონთან?) ლუკ 1:46-55
OUTPUT: 2. მარიამის საგალობელი (ხებრონში), ლუკა 1:46-55

INPUT: 3. მოგვები (ბრძენნი კაცნი აღმოსავლეთიდან) ვიზიტი (ბეთლემთან) მათ 2:1-12
OUTPUT: 3. მოგვების (აღმოსავლელი ბრძენების) მოსვლა ბეთლემში, მათე 2:1-12

INPUT: 4. იესო კურნავს ბრმა (იერიხონთან) მარკ 10:46-52
OUTPUT: 4. იესო კურნავს ბრმას იერიხოსთან, მარკოზი 10:46-52

INPUT: 5. ანგელოზი გაბრიელი ჩანს მარიამს (ნაზარეთთან) ლუკ 1:26-38
OUTPUT: 5. ანგელოზი გაბრიელი ეცხადება მარიამს ნაზარეთში, ლუკა 1:26-38
"""


def needs_ai_review(label):
    """დაადგინოს საჭიროებს თუ არა AI-ს კორექციას."""
    for pattern, reason in SUSPICIOUS_PATTERNS:
        if re.search(pattern, label):
            return True, reason
    return False, None


def load_client():
    """ინიციალიზაცია AI კლიენტის."""
    if AI_PROVIDER == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            print("გთხოვთ დააყენოთ anthropic: pip install anthropic")
            sys.exit(1)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("არასწორი: ANTHROPIC_API_KEY გარემოს ცვლადი ცარიელია.")
            print("export ANTHROPIC_API_KEY='...'")
            sys.exit(1)
        return Anthropic()

    elif AI_PROVIDER == "openai":
        try:
            import openai
        except ImportError:
            print("გთხოვთ დააყენოთ openai: pip install openai")
            sys.exit(1)

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("არასწორი: OPENAI_API_KEY გარემოს ცვლადი ცარიელია.")
            sys.exit(1)
        openai.api_key = api_key
        return openai

    else:
        print(f"უცნობი AI_PROVIDER: {AI_PROVIDER}")
        print("მხარდაჭერილია: anthropic, openai")
        sys.exit(1)


def fix_batch_with_anthropic(labels_batch, client):
    """Anthropic API-ს გამოყენებით batch-ის კორექცია."""
    numbered = "\n".join([f"{i+1}. {label}" for i, label in enumerate(labels_batch)])

    prompt = f"""გამოასწორე შემდეგი label-ები (თითოეული ცალკე ხაზზე, დანომრილი).
დააბრუნე გამოსწორებული ვერსიები იმავე ფორმატით (ნომერი + წერტილი + გამოსწორებული ტექსტი).

{numbered}

გამოსწორებული:"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLES,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")


def fix_batch_with_openai(labels_batch, client):
    """OpenAI API-ს გამოყენებით batch-ის კორექცია."""
    numbered = "\n".join([f"{i+1}. {label}" for i, label in enumerate(labels_batch)])

    prompt = f"""გამოასწორე შემდეგი label-ები (თითოეული ცალკე ხაზზე, დანომრილი).
დააბრუნე გამოსწორებული ვერსიები იმავე ფორმატით (ნომერი + წერტილი + გამოსწორებული ტექსტი).

{numbered}

გამოსწორებული:"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLES},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise Exception(f"OpenAI API error: {e}")


def parse_batch_response(text, expected_count):
    """AI-ს პასუხის დანომრილი ხაზების პარსინგი."""
    if not text:
        return None

    lines = text.split("\n")
    fixed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^\d+\.\s*(.+)$", line)
        if match:
            fixed.append(match.group(1).strip().strip('"'))

    # თუ რაოდენობა არ ემთხვევა, სცადეთ როგორც თავისუფალი ტექსტის
    # ყოველი ხაზი მაგივრად
    if len(fixed) != expected_count:
        fixed = [l.strip().strip('"') for l in lines if l.strip()]

    if len(fixed) != expected_count:
        return None
    return fixed


def validate_fix(original, fixed):
    """გადამოწმება რომ AI-მ არ "გადაწვა" label."""
    # რეფერენსი უნდა შენარჩუნდეს
    orig_refs = re.findall(r"\d+:\d+(?:-\d+)?", original)
    fixed_refs = re.findall(r"\d+:\d+(?:-\d+)?", fixed)
    if orig_refs != fixed_refs:
        return False, "რეფერენსი შეიცვალა"

    # სიგრძე არ უნდა შეიცვალოს რადიკალურად
    if len(fixed) < len(original) * 0.4 or len(fixed) > len(original) * 2.5:
        return False, "სიგრძის რადიკალური ცვლილება"

    # უნდა შეიცავდეს ქართულ ასოებს
    georgian_chars = sum(1 for c in fixed if "ა" <= c <= "ჰ")
    if georgian_chars < len(fixed) * 0.3:
        return False, "ცოტა ქართული ასო"

    return True, "OK"


def process_batch(batch_items, client, labels, fixed_count, failed_count):
    """ერთი batch-ის დამუშავება."""
    keys = [k for k, v, r in batch_items]
    values = [v for k, v, r in batch_items]

    for attempt in range(MAX_RETRIES):
        try:
            if AI_PROVIDER == "anthropic":
                raw = fix_batch_with_anthropic(values, client)
            else:
                raw = fix_batch_with_openai(values, client)

            fixed = parse_batch_response(raw, len(values))
            if fixed is None:
                raise Exception("პასუხის პარსინგი ვერ მოხერხდა")

            ok_count = 0
            for key, old, new in zip(keys, values, fixed):
                valid, reason = validate_fix(old, new)
                if valid:
                    if new != old:
                        labels[key] = new
                        fixed_count[0] += 1
                        if fixed_count[0] <= 20:
                            print(f"  ✓ {old[:65]}")
                            print(f"    → {new[:65]}")
                    ok_count += 1
                else:
                    print(f"  ⚠️ ვალიდაცია ვერ გაიარა ({reason}): {old[:50]}")

            if ok_count == len(values):
                return
            else:
                raise Exception(f"batch validation: {ok_count}/{len(values)}")

        except Exception as e:
            print(f"  ⚠️ მცდელობა {attempt + 1}/{MAX_RETRIES} ვერ გაიარა: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                failed_count[0] += len(values)


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # სარეზერვო ასლი
    backup_path = OUTPUT_DIR / f"topic_labels_ka.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy2(LABELS_FILE, backup_path)
    print(f"სარეზერვო ასლი: {backup_path}")

    # ჩატვირთვა
    with open(LABELS_FILE, "r", encoding="utf-8") as f:
        labels = json.load(f)
    print(f"სულ label: {len(labels):,}")

    # საეჭვოების იდენტიფიკაცია
    to_fix = []
    for key, label in labels.items():
        need, reason = needs_ai_review(label)
        if need:
            to_fix.append((key, label, reason))
    print(f"საეჭვო label-ები: {len(to_fix)}")

    # რაოდენობის ლიმიტი
    limit = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 100
        print(f"ტესტ რეჟიმი: პირველი {limit} label")
    elif "--run" in sys.argv:
        idx = sys.argv.index("--run")
        limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 500
        print(f"ბეტა რეჟიმი: პირველი {limit} label")
    elif "--all" in sys.argv:
        limit = len(to_fix)
        print(f"სრული რეჟიმი: {limit} label")
    else:
        print("\nმიუთითეთ ერთ-ერთი:")
        print("  --test N   # N label-ის ტესტი")
        print("  --run N    # N label-ის batch")
        print("  --all      # ყველა საეჭვო")
        sys.exit(1)

    to_fix = to_fix[:limit]

    # AI კლიენტი
    client = load_client()

    # Processing
    fixed_count = [0]
    failed_count = [0]

    for i in range(0, len(to_fix), BATCH_SIZE):
        batch = to_fix[i:i + BATCH_SIZE]
        print(f"\n[{i+1}-{i+len(batch)} / {len(to_fix)}]")
        process_batch(batch, client, labels, fixed_count, failed_count)

        # შენახვა ყოველ 500-ზე
        if (i // BATCH_SIZE) % 25 == 0 and i > 0:
            with open(LABELS_FILE, "w", encoding="utf-8") as f:
                json.dump(labels, f, ensure_ascii=False, indent=2)
            print(f"  💾 შენახულია: {fixed_count[0]} შეცვლილი")

        # Rate limiting
        time.sleep(0.5)

    # საბოლოო შენახვა
    with open(LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"დასრულდა:")
    print(f"  ✓ გასწორდა: {fixed_count[0]}")
    print(f"  ✗ ვერ გასწორდა: {failed_count[0]}")
    print(f"  სარეზერვო: {backup_path}")


if __name__ == "__main__":
    main()
