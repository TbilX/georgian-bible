#!/usr/bin/env python3
"""
root_translations_ka.json-ის კონტექსტუალური ვალიდაცია
ბიბლიის თანამედროვე ქართული თარგმანის გამოყენებით.

თითოეული საეჭვო root-ისთვის:
1. პოულობს topical_index.json-იდან ინგლისურ label-ს
2. პოულობს ბიბლიურ მუხლს (თანამედროვე ქართული)
3. აჩვენებს შედარებას: ინგლისური root -> ქართული თარგმანი vs ბიბლიური კონტექსტი
"""
import json
import re
import os

DATA_DIR = "data"

# ბიბლიის ჩატვირთვა
with open(os.path.join(DATA_DIR, "verses.json"), "r", encoding="utf-8") as f:
    VERSES = json.load(f)

VERSE_INDEX = {}
for v in VERSES:
    key = f"{v.get('book_slug')}:{v.get('chapter')}:{v.get('verse')}"
    VERSE_INDEX[key] = v.get("new", "")


# ინგლისური აბრევიატურა -> ქართული slug
EN_ABBR_TO_SLUG = {
    "Ge": "dabadeba", "Ex": "gamosvla", "Le": "levianni", "Nu": "ritskhvni",
    "De": "msajulni", "Jos": "iesonave", "Jdg": "martyrebelni", "Ru": "ruti",
    "1Sa": "1mepeta", "2Sa": "2mepeta", "1Ki": "3mepeta", "2Ki": "4mepeta",
    "1Ch": "1neshtta", "2Ch": "2neshtta", "Ezr": "ezraieli", "Ne": "neemia",
    "Es": "esteri", "Job": "iobi", "Ps": "fsalmunni", "Pr": "tilebi",
    "Ec": "eklesiaste", "So": "qeba", "Isa": "esaia", "Jer": "ieremia",
    "La": "klalebi", "Eze": "ezekieli", "Da": "danieli", "Ho": "osia",
    "Joe": "ioveli", "Am": "amos", "Ob": "abdia", "Jon": "iona",
    "Mic": "miqa", "Na": "naumi", "Hab": "abakumi", "Zep": "zefania",
    "Hag": "aggeos", "Zec": "zakharia", "Mal": "malaqia",
    "Mt": "mate", "Mr": "markozi", "Lu": "luka", "Joh": "ioane",
    "Ac": "saqme", "Ro": "romaelta", "1Co": "1korintelta", "2Co": "2korintelta",
    "Ga": "galatelta", "Eph": "efeselta", "Php": "filipelta", "Col": "kolaselta",
    "1Th": "1tesalonikelta", "2Th": "2tesalonikelta", "1Ti": "1timote",
    "2Ti": "2timote", "Tit": "tite", "Phm": "filimoni", "Heb": "ebraelta",
    "Jas": "iakobi", "1Pe": "1petre", "2Pe": "2petre", "1Jo": "1ioane",
    "2Jo": "2ioane", "3Jo": "3ioane", "Jude": "iuda", "Re": "apokalips",
}


def parse_en_refs(label):
    """ინგლისურ label-დან რეფერენსების გამოღება."""
    refs = []
    # პატერნი: აბრევიატურა თავი:მუხლი
    pattern = re.compile(r'\b([A-Z][a-z]{1,3})(?:\s*\d+)?:\s*(\d+)(?:[-,](\d+))?\s*(\d+)?')
    for m in pattern.finditer(label):
        abbr = m.group(1)
        if abbr in EN_ABBR_TO_SLUG:
            chapter = int(m.group(2))
            verse = m.group(4) or m.group(3)
            if verse:
                verse = int(verse)
                refs.append((EN_ABBR_TO_SLUG[abbr], chapter, verse))
    return refs


def get_verse_text(book_slug, chapter, verse):
    return VERSE_INDEX.get(f"{book_slug}:{chapter}:{verse}", "")


# topical_index.json-ის ჩატვირთვა
with open(os.path.join(DATA_DIR, "topical_index.json"), "r", encoding="utf-8") as f:
    TOPICAL = json.load(f)

# topic_labels_ka.json
with open(os.path.join(DATA_DIR, "topic_labels_ka.json"), "r", encoding="utf-8") as f:
    LABELS_KA = json.load(f)

# root_translations
with open(os.path.join(DATA_DIR, "root_translations_ka.json"), "r", encoding="utf-8") as f:
    ROOT_TRANS = json.load(f)["root_translations"]


# ყველა root-ისთვის ვპოვნი ინგლისურ label-ს და ბიბლიურ კონტექსტს
def find_context_for_root(eng_root):
    """პოულობს ბიბლიურ კონტექსტს root-ისთვის."""
    results = []
    for topic in TOPICAL.get("topics", []):
        for entry in topic.get("entries", []):
            en_label = entry.get("label", "")
            if not en_label:
                continue
            if re.search(r'\b' + re.escape(eng_root) + r'\b', en_label, re.IGNORECASE):
                ka_label = LABELS_KA.get(en_label, "")
                refs = parse_en_refs(en_label)
                bible_verses = []
                for slug, ch, vs in refs[:2]:
                    text = get_verse_text(slug, ch, vs)
                    if text:
                        bible_verses.append({
                            "ref": f"{slug} {ch}:{vs}",
                            "text": text[:250]
                        })
                if bible_verses or ka_label:
                    results.append({
                        "en_label": en_label[:120],
                        "ka_label": ka_label[:120],
                        "bible_verses": bible_verses
                    })
                if len(results) >= 2:
                    return results
    return results


def main():
    # ყველა root-ის შემოწმება
    print(f"სულ root-ები: {len(ROOT_TRANS)}")
    print()

    # ვამოწმებთ ყველა root-ს ბიბლიური კონტექსტით
    issues = []
    for eng in sorted(ROOT_TRANS.keys()):
        ka = ROOT_TRANS[eng]
        contexts = find_context_for_root(eng)
        if not contexts:
            continue

        # ვაჩვენებთ კონტექსტს
        for ctx in contexts:
            bible_text = ""
            if ctx["bible_verses"]:
                bible_text = ctx["bible_verses"][0]["text"]

            print(f"=== {eng} -> {ka} ===")
            print(f"  EN: {ctx['en_label']}")
            print(f"  KA: {ctx['ka_label']}")
            if bible_text:
                print(f"  ბიბლია: {bible_text}")
            print()

    print(f"\n{'='*70}")
    print(f"ყველა root ბიბლიური კონტექსტით ნაჩვენებია")


if __name__ == "__main__":
    main()
