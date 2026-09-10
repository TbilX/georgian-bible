#!/usr/bin/env python3
"""
root_translations_ka.json-ის კონტექსტუალური აუდიტი.
თითოეული თარგმანისთვის პოულობს ბიბლიურ კონტექსტს და აჩვენებს
საეჭვო შემთხვევებს გადასამოწმებლად.
"""
import json
import re
import os

DATA_DIR = "data"

# ბიბლიის ჩატვირთვა
with open(os.path.join(DATA_DIR, "verses.json"), "r", encoding="utf-8") as f:
    VERSES = json.load(f)

# წიგნის slug -> ქართული აბრევიატურა
SLUG_TO_KA = {
    "dabadeba": "დაბ", "gamosvla": "გამ", "levianni": "ლევ", "ritskhvni": "რიც",
    "msajulni": "მსა", "iesonave": "იენ", "martyrebelni": "მარ", "ruti": "რუთ",
    "1mepeta": "I მეფ", "2mepeta": "II მეფ", "3mepeta": "III მეფ", "4mepeta": "IV მეფ",
    "1neshtta": "I ნეშ", "2neshtta": "II ნეშ", "ezraieli": "ეზრ", "neemia": "ნეე",
    "esteri": "ესთ", "iobi": "იობ", "fsalmunni": "ფსა", "tilebi": "იგა",
    "qeba": "ქებ", "eklesiaste": "ეკლ", "solomoni": "ქებ-წ",
    "esaia": "ესა", "ieremia": "იერ", "baruqi": "ბარ", "klalebi": "წრ",
    "ezekieli": "ეზე", "danieli": "დან", "osia": "ოსი", "ioveli": "იოე",
    "amos": "ამო", "abdia": "აბდ", "iona": "იონ", "miqa": "მიქ",
    "naumi": "ნაუ", "abakumi": "აბა", "zefania": "ზეფ", "aggeos": "აგ",
    "zakharia": "ზაქ", "malaqia": "მალ",
    "mate": "მათე", "markozi": "მარ", "luka": "ლუკა", "ioane": "იოა",
    "saqme": "საქ", "romaelta": "რომ", "1korintelta": "I კორ", "2korintelta": "II კორ",
    "galatelta": "გალ", "efeselta": "ეფე", "filipelta": "ფილ", "kolaselta": "კოლ",
    "1tesalonikelta": "I თეს", "2tesalonikelta": "II თეს", "1timote": "I ტიმ",
    "2timote": "II ტიმ", "tite": "ტიტ", "filimoni": "ფილ", "ebraelta": "ებრ",
    "iakobi": "იაკ", "1petre": "I პეტ", "2petre": "II პეტ", "1ioane": "I იოა",
    "2ioane": "II იოა", "3ioane": "III იოა", "iuda": "იუდ", "apokalips": "გამ",
}

# მუხლების ინდექსი (book_slug:chapter:verse -> text)
VERSE_INDEX = {}
for v in VERSES:
    key = f"{v.get('book_slug')}:{v.get('chapter')}:{v.get('verse')}"
    VERSE_INDEX[key] = v.get("new", "")


def get_verse_text(book_slug, chapter, verse):
    return VERSE_INDEX.get(f"{book_slug}:{chapter}:{verse}", "")


# topic_labels_ka.json-ის ჩატვირთვა
with open(os.path.join(DATA_DIR, "topic_labels_ka.json"), "r", encoding="utf-8") as f:
    LABELS = json.load(f)

# root_translations_ka.json-ის ჩატვირთვა
with open(os.path.join(DATA_DIR, "root_translations_ka.json"), "r", encoding="utf-8") as f:
    ROOT_TRANS = json.load(f)["root_translations"]


# რეფერენსის პარსინგი: "მათე 27:57,58; მარ 15:43-45"
# აბრევიატურა -> slug-ის რუკა
KA_ABBR_TO_SLUG = {v: k for k, v in SLUG_TO_KA.items() if v}


def parse_refs_from_label(label):
    """label-დან რეფერენსების გამოღება."""
    refs = []
    # პატერნი: აბრევიატურა თავი:მუხლი
    pattern = re.compile(r'([IVX]+\s+)?([ა-ჰ]+)\s+(\d+):(\d+)(?:[-,](\d+))?')
    for m in pattern.finditer(label):
        prefix = (m.group(1) or "").strip()
        abbr = m.group(2)
        chapter = int(m.group(3))
        verse = int(m.group(4))
        verse_end = m.group(5)
        if verse_end:
            verse_end = int(verse_end)
        # slug-ის პოვნა
        full_abbr = (prefix + " " + abbr).strip() if prefix else abbr
        slug = KA_ABBR_TO_SLUG.get(full_abbr) or KA_ABBR_TO_SLUG.get(abbr)
        if slug:
            refs.append((slug, chapter, verse, verse_end))
    return refs


def find_bible_context_for_root(eng_root):
    """პოულობს ბიბლიურ კონტექსტს root-ისთვის."""
    # ვპოვნი label-ებს სადაც ეს root გამოიყენება
    contexts = []
    for key, val in LABELS.items():
        if not isinstance(val, str):
            continue
        if re.search(r'\b' + re.escape(eng_root) + r'\b', val, re.IGNORECASE):
            # რეფერენსების გამოღება
            refs = parse_refs_from_label(val)
            bible_verses = []
            for slug, ch, vs, ve in refs[:2]:  # პირველი 2 რეფერენსი
                text = get_verse_text(slug, ch, vs)
                if text:
                    bible_verses.append({
                        "ref": f"{SLUG_TO_KA.get(slug, slug)} {ch}:{vs}",
                        "text": text[:200]
                    })
            contexts.append({
                "label_key": key[:80],
                "label_value": val[:120],
                "bible_verses": bible_verses
            })
            if len(contexts) >= 3:
                break
    return contexts


def main():
    print(f"სულ root-ები: {len(ROOT_TRANS)}")
    print()

    # საეჭვო კატეგორიები
    suspicious_categories = {
        "ზედსართავი სახელები": [
            "insatiable", "plenteous", "censorious", "voracious", "avaricious",
            "vindictive", "malignant", "crafty", "agile", "gallant", "pompous",
            "populous", "multitudinous", "fusible", "malleable", "compact",
            "complicated", "burnished", "grisled", "speckled", "spotted",
            "distrustful", "delusion", "disquiet", "unsocial", "unstable",
            "irrational", "imprudent", "improvident", "inexperience",
            "helpless", "abased", "depopulated", "tedious", "fading",
            "fleeting", "trackless", "undeviating", "uninterrupted",
            "unsatisfying", "unreservedly", "voracious", "violent",
        ],
        "ზმნები": [
            "assuages", "devour", "banish", "crush", "overturns", "overwhelm",
            "perpetrate", "conceive", "punishes", "relieves", "ponders",
            "inspects", "scorning", "silenced", "massacred", "slaughtered",
            "stormed", "sweeping", "rushing", "stacking", "levelled",
            "digging", "fishing", "trading", "hedging", "manuring",
            "fertilising", "enlightening", "regenerating", "aunticating",
            "cruises", "binders", "reapers", "feeling", "penetrating",
            "cheerfully", "industriously", "fearlessly", "readily",
            "winking", "whispering", "babbling", "itching", "defaming",
            "disinterestedness", "restraint", "retirement", "observation",
            "eventide", "everywhere", "immediate", "weekly", "monthly",
        ],
        "ცხოველები/მცენარეები": [
            "earthworm", "horseleech", "nighthawk", "hart", "crocodiles",
            "conies", "aloe", "chestnut", "teil", "thickets", "rushes",
            "gourds", "cucumbers", "onions", "leeks", "fitches", "mulberry",
            "bricks", "helmets", "javelins", "lances", "boxes", "footstools",
            "ponds", "vales", "quicksands",
        ],
        "რელიგიური/მაგიური": [
            "necromancers", "soothsayers", "enchanters", "charmers",
            "apocalypse", "christianity", "mercury", "preciousness",
            "sonorousness", "joyfulness", "cleanness", "impurity",
            "frowardness", "quarrelsomeness", "literature",
        ],
        "ფიზიკური/მატერიალური": [
            "fusibility", "fusible", "malleable", "burnished", "compact",
            "complicated", "levelled", "stacking", "hedging", "manuring",
            "digging", "fishing", "trading", "traffickers", "chapmen",
            "reapers", "binders", "boxes", "bricks", "helmets",
        ],
    }

    for category, roots in suspicious_categories.items():
        print(f"\n{'='*70}")
        print(f"=== {category} ({len(roots)}) ===")
        print(f"{'='*70}\n")

        for eng in sorted(roots):
            if eng not in ROOT_TRANS:
                continue
            ka = ROOT_TRANS[eng]
            contexts = find_bible_context_for_root(eng)

            print(f"--- {eng} -> {ka} ---")
            for ctx in contexts[:2]:
                print(f"  label: {ctx['label_value']}")
                for bv in ctx["bible_verses"][:1]:
                    print(f"  ბიბლია {bv['ref']}: {bv['text']}")
            print()


if __name__ == "__main__":
    main()
