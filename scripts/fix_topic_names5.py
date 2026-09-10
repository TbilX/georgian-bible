#!/usr/bin/env python3
"""ფაზა 5: დასაწყისი ჰ-ის მოხსნა ინგლისური ტრანსლიტერაციის ნაშთებიდან."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# სახელები რომლებიც ნამდვილად ჰ-ით იწყება ქართულ ბიბლიურ ტრადიციაში
KEEP_H = {
    "herod", "herod-antipas", "herod-agrippa", "herod-agrippa-i",
    "herod-philip", "herodias", "herodians", "herodion",
    "herod-king", "herod-the-great",
    "hinnom", "hinnom-valley", "valley-of-hinnom",
    "havilah", "hivites", "hivite",
    "hermon", "hermonite", "mount-hermon",
    "hermonites",
    "hagar", "hagarites", "hagarenes",
    "hodesh", "hodijah", "hodaviah",
    "hophni",
    "huppim",
    "hushah", "hushai", "hushathite", "hushim",
    "hurai", "huram", "huri", "hur",
    "hul", "huldah", "hulda",
    "hun", "huppah",
    "huzoth", "huzot",
    "havvoth", "havoth-jair",
    "havilah-land",
    "hena",
    "heres", "hereth", "heresh",
    "hermonites",
    "hauran",
    "haahashtari",  # საეჭვო, მაგრამ დავტოვოთ
    "habaiah", "habaziniah",  # საეჭვო
    "habergeon",
    "habor",
    "hachaliah", "hachilah", "hachmoni",
    "hadad", "hadadezer", "hadadrimmon",
    "hadashah", "hadassah", "hadattah",
    "hadid", "hadlai", "hadoram", "hadrach",
    "hagab", "hagaba", "haggeri", "haggai", "hagi",
    "hagith", "hagrites",
    "hahiroth", "hakatan", "hakkoz", "hakupha",
    "hala", "halah", "halhul",
    "hallal", "hallel", "hallelujah",
    "ham", "haman", "hamath", "hamathite",
    "hammedatha", "hammoth", "hammonah", "hamon",
    "hamor", "hamuel", "hamul", "hamulite", "hamutal",
    "hanan", "hananel", "hanani", "hananiah",
    "hannah", "hanniel", "hanon", "hanun",
    "haphez", "happizzez",
    "hara", "haradah", "haran", "harhas",
    "harheres", "harhur", "harim",
    "harnepher", "harod", "harodite", "harosheth",
    "haruphite", "haruz",
    "hasadiah", "hasenuah",
    "hashabiah", "hashabnah", "hashabneiah",
    "hashem", "hashmonah", "hashub", "hashubah",
    "hashum", "hashupha", "hasrah",
    "hatach",
    "hauran", "havilah", "havit",
    "hazor", "hazor-hadattah",
    "heber", "hebrew", "hebrewess", "hebrews",
    "hed", "hedge", "hedges",
    "heel", "heels",
    "he-goat", "he-goats",
    "heifer", "heifers",
    "helam", "helbah", "helbon",
    "heleb", "heled", "helek", "helekite",
    "helkai", "helkath",
    "hena", "henadad",
    "her", "herald", "herb", "herbs",
    "herd", "herds", "herdsman", "herdsmen",
    "heredity",
    "heresy", "heresies", "heretic", "heretics",
    "hermon", "hermonite",
    "herod", "herodias", "herodians",
    "heron", "herons",
    "hew", "hewn", "hewn-stone",
    "hezro", "hezrai",
    "hiding", "hiding-place",
    "high", "high-day", "high-god", "high-hand",
    "high-mountain", "high-officer",
    "high-priest", "high-priests",
    "high-sea", "high-way", "highways",
    "hilkiah",
    "hill", "hills", "hill-country",
    "hinnom",
    "hired", "hireling", "hirelings",
    "hissing",
    "hittites", "hittite",
    "hivites", "hivite",
    "hoar", "hoary-head",
    "hobab",
    "hodesh", "hodijah", "hodaviah",
    "hoglah",
    "hoist",
    "hold", "holding",
    "hole", "holes",
    "hollow",
    "holiness",
    "holy", "holy-one", "holy-ones",
    "holy-place", "holy-places",
    "holy-spirit", "holy-trinity",
    "home", "homeward",
    "honest", "honesty",
    "honey", "honeycomb",
    "honour", "honoured",
    "hood",
    "hoof", "hoofs",
    "hook", "hooks",
    "hope", "hopes",
    "hor", "hor-hagidgad", "horam",
    "horeb", "hori", "horite", "horites",
    "horn", "horns",
    "hornet",
    "horror",
    "horse", "horses", "horseback",
    "horseman", "horsemen", "horse-leech",
    "hosanna", "hosea",
    "hoshama", "hoshea",
    "hospitable", "hospitality",
    "host", "host-of-heaven", "hosts",
    "hostage", "hostages",
    "house", "houses", "household", "households",
    "house-of-god", "house-of-judgment",
    "house-of-the-father",
    "hovah", "hovi",
    "hukkok", "hul", "huldah",
    "human", "humanity",
    "humbling", "humility",
    "hunger", "hungry",
    "hunting",
    "hur", "hurai", "huram", "huri",
    "hushah", "hushai", "hushathite", "hushim",
    "husband", "husbands",
    "husbandman", "husbandmen",
    "hymn", "hymns",
    "hypocrisy", "hypocrite", "hypocrites",
}


def main():
    print("=== ფაზა 5: დასაწყისი ჰ-ის მოხსნა ===\n")

    with open(os.path.join(DATA_DIR, "topic_names_ka.json"), "r", encoding="utf-8") as f:
        topics = json.load(f)

    fixed = 0
    kept = 0

    for slug, val in topics.items():
        if val.startswith(("I ", "II ", "III ", "IV ")):
            continue

        if not val.startswith("ჰ"):
            continue

        # გადავამოწმოთ არის თუ არა ეს სახელი რომელიც ნამდვილად ჰ-ით იწყება
        if slug in KEEP_H:
            kept += 1
            continue

        # მოვხსნათ დასაწყისი ჰ
        new_val = val[1:]
        # დავამატოთ "ი" ბოლოში თუ არ არის
        if not new_val.endswith(("ი", "ე", "ა", "ო", "უ")) and len(new_val) > 2:
            new_val = new_val + "ი"
        
        if new_val != val:
            topics[slug] = new_val
            fixed += 1

    # შენახვა
    with open(os.path.join(DATA_DIR, "topic_names_ka.json"), "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

    # სტატისტიკა
    remaining = 0
    for val in topics.values():
        if val.startswith(("I ", "II ", "III ", "IV ")):
            continue
        if "ჰ" in val or "ჩ" in val:
            remaining += 1

    print(f"გასწორდა (ჰ მოიხსნა): {fixed}")
    print(f"დატოვებული (ნამდვილი ჰ): {kept}")
    print(f"დარჩენილი პრობლემური: {remaining}")


if __name__ == "__main__":
    main()
