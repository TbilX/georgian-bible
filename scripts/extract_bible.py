#!/usr/bin/env python3
"""
ბიბლიის მუხლების ექსტრაქცია CHM-დან დეკომპილირებულ HTML ფაილებიდან.
წყარო: source_html/  (პროექტის შიგნით)
შედეგი: data/verses.json — ყველა მუხლი ორ ენაზე (ახალი + ძველი ქართული)
"""
import os
import re
import json
import glob
from html.parser import HTMLParser
from pathlib import Path

SRC = os.path.join(os.path.dirname(__file__), "source_html")
OUT = os.path.join(os.path.dirname(__file__), "data", "verses.json")

# წიგნების ქართული სახელების მაპინგი (ლათინური დირექტორია -> ქართული სახელი)
BOOK_NAMES = {
    # ძველი აღთქმა
    "dabadeba": "დაბადება",
    "gamosvla": "გამოსვლა",
    "levianni": "ლევიანები",
    "ritskhvni": "რიცხვნი",
    "godeba": "გოდება იერემიასი",
    "2rjuli": "მეორე რჯული",
    "iisus": "იესო ნავე",
    "msajulni": "მსაჯულნი",
    "ruti": "რუთი",
    "1mepeta": "I მეფეთა",
    "2mepeta": "II მეფეთა",
    "3mepeta": "III მეფეთა",
    "4mepeta": "IV მეფეთა",
    "1neshtta": "I მატიანე",
    "2neshtta": "II მატიანე",
    "1ezra": "I ეზრა",
    "2ezra": "II ეზრა",
    "3ezra": "III ეზრა",
    "neemia": "ნეემია",
    "esteri": "ესთერი",
    "iobi": "იობი",
    "fsalmunni": "წინასწარმეტყველებანი (ფსალმუნნი)",
    "solomoni": "იგავნი სოლომონისა",
    "eklesiaste": "ეკლესიასტე",
    "qeba": "გალობანი გალობათა",
    "esai": "ესაია",
    "ieremia": "იერემია",
    "baruqi": "ბარუქი",
    "igavni": "იგავნი იერემიასნი",
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
    "aggeos": "აგგეოსი",
    "zaqaria": "ზაქარია",
    "malaqia": "მალაქია",
    # არაკანონიკური
    "tobiti": "ტობითი",
    "ivditi": "იუდითი",
    "1makabelta": "I მაკაბელთა",
    "2makabelta": "II მაკაბელთა",
    "3makabelta": "III მაკაბელთა",
    "4makabelta": "IV მაკაბელთა",
    "iesonave": "იასონ კვირინელის წიგნი",
    "ziraqi": "მანასეს ლოცვა",
    # ახალი აღთქმა
    "mate": "მათე",
    "markozi": "მარკოზი",
    "luka": "ლუკა",
    "ioane": "იოანე",
    "saqme": "მოციქულთა საქმენი",
    "romaelta": "რომაელთა",
    "1korintelta": "I კორინთელთა",
    "2korintelta": "II კორინთელთა",
    "galatelta": "გალატელთა",
    "efeselta": "ეფესელთა",
    "filipelta": "ფილიპელთა",
    "kolaselta": "კოლასელთა",
    "1tesalonikelta": "I თესალონიკელთა",
    "2tesalonikelta": "II თესალონიკელთა",
    "1timote": "I ტიმოთე",
    "2timote": "II ტიმოთე",
    "tite": "ტიტე",
    "filimoni": "ფილიმონი",
    "ebraelta": "ებრაელთა",
    "iakobi": "იაკობი",
    "1petre": "I პეტრე",
    "2petre": "II პეტრე",
    "1ioane": "I იოანე",
    "2ioane": "II იოანე",
    "3ioane": "III იოანე",
    "iuda": "იუდა",
    "apokalips": "გამოცხადება",
}


class VerseExtractor(HTMLParser):
    """HTML პარსერი — ამოიღებს მუხლებს ცხრილის უჯრედებიდან.

    HTML სტრუქტურა (4 სვეტი):
      სვეტი 0: ახალი ქართულის მუხლის ნომერი (შეიძლება იყოს ცარიელი)
      სვეტი 1: ახალი ქართულის ტექსტი (შეიძლება იყოს ცარიელი)
      სვეტი 2: ძველი ქართულის მუხლის ნომერი (შეიძლება იყოს ცარიელი)
      სვეტი 3: ძველი ქართულის ტექსტი (შეიძლება იყოს ცარიელი)

    სამი შემთხვევა:
      1. ნორმალური: ორივე ენას აქვს ნომერი და ტექსტი (ნომრები შეიძლება განსხვავდებოდეს)
      2. მხოლოდ ძველი: ახალი ცარიელია, ძველს აქვს ნომერი და ტექსტი
         → მიემატება წინა მუხლის old ველს (პარალელური ნუმერაციის აცდენა)
      3. მხოლოდ ახალი: ახალს აქვს ნომერი და ტექსტი, ძველი ცარიელია
         → იქმნება მუხლი new ტექსტით, old=""
    """

    def __init__(self):
        super().__init__()
        self.verses = []  # [(num, text_new, text_old), ...]
        self.book_title = ""
        self.chapter_title = ""
        self.in_td = False
        self.current_cell = ""
        self.cells = []  # მიმდინარე რიგის უჯრედები (პოზიციის შენარჩუნებით)
        self.in_h1 = False
        self.in_h2 = False
        self.h1_text = ""
        self.h2_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.in_td = True
            self.current_cell = ""
        elif tag == "h1":
            self.in_h1 = True
            self.h1_text = ""
        elif tag == "h2":
            self.in_h2 = True
            self.h2_text = ""

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
            # ყოველთვის ვამატებთ უჯრედს, მათ შორის ცარიელსაც
            # (პოზიციის შენარჩუნება კრიტიკულია)
            text = self.current_cell.strip()
            self.cells.append(text)
        elif tag == "tr":
            # რიგი დასრულდა — ვამუშავებთ
            self._process_row()
            self.cells = []
        elif tag == "h1":
            self.in_h1 = False
            self.book_title = self.h1_text.strip()
        elif tag == "h2":
            self.in_h2 = False
            self.chapter_title = self.h2_text.strip()

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data
        elif self.in_h1:
            self.h1_text += data
        elif self.in_h2:
            self.h2_text += data

    def _process_row(self):
        """უჯრედების რიგის დამუშავება პოზიციის მიხედვით.

        ფორმატი 4 უჯრედით (სტანდარტული):
          [num_new, text_new, num_old, text_old]

        ფორმატი 3 უჯრედით (ერთიანი ნომერი):
          [num, text_new, text_old]

        Header რიგები (2 უჯრედი ან 3 უჯრედი ტექსტით) არ შეიცავს მუხლებს.
        """
        cells = self.cells

        # ფორმატი 4 უჯრედით: [num_new, text_new, num_old, text_old]
        if len(cells) >= 4:
            num_new_str = cells[0]
            text_new = cells[1]
            num_old_str = cells[2]
            text_old = cells[3]

            # შემთხვევა 1: ახალ ქართულს აქვს მუხლის ნომერი
            if num_new_str:
                try:
                    num = int(num_new_str)
                except ValueError:
                    return
                # თუ ძველი ქართულის რიგმა უკვე შექმნა ეს მუხლი
                # (new='', old='text') → განვაახლოთ new ველი
                # ან თუ ორივე ენას აქვს ტექსტი (ნარატიული ხიდი) → შევუერთოთ
                existing = None
                for v in reversed(self.verses):
                    if v["num"] == num:
                        existing = v
                        break
                if existing:
                    if not existing["new"]:
                        existing["new"] = text_new
                    elif text_new:
                        existing["new"] += " " + text_new
                    if not existing["old"]:
                        existing["old"] = text_old
                    elif text_old:
                        existing["old"] += " " + text_old
                else:
                    self.verses.append({
                        "num": num,
                        "new": text_new,
                        "old": text_old,
                    })
            # შემთხვევა 2: ახალი ცარიელია
            else:
                # 2a: ძველს აქვს საკუთარი ნომერი
                if num_old_str:
                    try:
                        num = int(num_old_str)
                    except ValueError:
                        return
                    # თუ ეს ნომერი უკვე არსებობს (ახალმა ქართულმა შექმნა)
                    # → მივამატოთ old ტექსტი არსებულ მუხლს
                    existing = None
                    for v in reversed(self.verses):
                        if v["num"] == num:
                            existing = v
                            break
                    if existing:
                        if existing["old"]:
                            existing["old"] += " " + text_old
                        else:
                            existing["old"] = text_old
                    else:
                        # ახალი მუხლი ძველი ქართულის ნომრით
                        self.verses.append({
                            "num": num,
                            "new": "",
                            "old": text_old,
                        })
                # 2b: ძველს არ აქვს ნომერი, მაგრამ აქვს ტექსტი → გაგრძელება
                elif text_old:
                    if self.verses:
                        prev = self.verses[-1]
                        if prev["old"]:
                            prev["old"] += " " + text_old
                        else:
                            prev["old"] = text_old

        # ფორმატი 3 უჯრედით: [num, text_new, text_old]
        elif len(cells) == 3:
            num_str = cells[0]
            text_new = cells[1]
            text_old = cells[2]

            # თუ პირველი უჯრედი არ არის რიცხვი — header რიგი
            if not num_str:
                return
            try:
                num = int(num_str)
            except ValueError:
                return
            self.verses.append({
                "num": num,
                "new": text_new,
                "old": text_old,
            })


def clean_text(text):
    """ტექსტის გასუფთავება."""
    # ზედმეტი ცარიელი სივრცეები
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_chapter(filepath, book_slug, book_name, chapter_num, testament):
    """ერთი თავის ფაილის დამუშავება."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"  შეცდომა {filepath}: {e}")
        return []

    parser = VerseExtractor()
    try:
        parser.feed(html)
    except Exception as e:
        print(f"  პარსინგის შეცდომა {filepath}: {e}")
        return []

    verses = []
    for v in parser.verses:
        text_new = clean_text(v["new"])
        text_old = clean_text(v["old"])
        if not text_new and not text_old:
            continue
        verses.append({
            "book_slug": book_slug,
            "book": book_name,
            "chapter": chapter_num,
            "verse": v["num"],
            "testament": testament,
            "new": text_new,
            "old": text_old,
            "file": os.path.relpath(filepath, SRC),
        })
    return verses


def main():
    all_verses = []
    stats = {"books": 0, "chapters": 0, "verses": 0}

    for testament, dirname in [("old", "dzveli"), ("new", "akhali")]:
        test_dir = os.path.join(SRC, dirname)
        if not os.path.isdir(test_dir):
            continue
        print(f"\n=== {testament == 'old' and 'ძველი აღთქმა' or 'ახალი აღთქმა'} ===")

        books = sorted(os.listdir(test_dir))
        for book_slug in books:
            book_dir = os.path.join(test_dir, book_slug)
            if not os.path.isdir(book_dir):
                continue
            book_name = BOOK_NAMES.get(book_slug, book_slug)
            print(f"  {book_name} ({book_slug})...")

            # ვპოვნით თავების ფაილებს
            chapter_files = glob.glob(os.path.join(book_dir, "*.htm"))
            chapter_files.sort(key=lambda f: _chapter_sort_key(f, book_slug))

            for cf in chapter_files:
                # თავის ნომერი ფაილის სახელიდან
                basename = os.path.basename(cf)
                m = re.search(r"-(\d+)\.htm$", basename)
                if m:
                    chapter_num = int(m.group(1))
                elif basename == f"{book_slug}.htm":
                    # ერთფაილიანი წიგნი (მაგ: 2ioane.htm, iuda.htm) — თავი 1
                    chapter_num = 1
                else:
                    continue

                verses = extract_chapter(cf, book_slug, book_name, chapter_num, testament)
                all_verses.extend(verses)
                stats["chapters"] += 1
                stats["verses"] += len(verses)
            stats["books"] += 1

    # შენახვა
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_verses, f, ensure_ascii=False, indent=1)

    print(f"\n=== სტატისტიკა ===")
    print(f"წიგნები: {stats['books']}")
    print(f"თავები: {stats['chapters']}")
    print(f"მუხლები: {stats['verses']}")
    print(f"ფაილი: {OUT}")
    print(f"ზომა: {os.path.getsize(OUT) / 1024 / 1024:.1f} MB")


def _chapter_sort_key(filepath, book_slug):
    """თავების სორტირება ნომრით."""
    basename = os.path.basename(filepath)
    m = re.search(r"-(\d+)\.htm$", basename)
    if m:
        return int(m.group(1))
    # ერთფაილიანი წიგნი — თავი 1
    if basename == f"{book_slug}.htm":
        return 1
    return 0


if __name__ == "__main__":
    main()
