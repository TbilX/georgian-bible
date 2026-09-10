#!/usr/bin/env python3
"""
Bible Word Grouper — ბიბლიის სიტყვების დაჯგუფება ფუძეების მიხედვით.

სამი ფენა:
1. UD ლექსიკონი (ხელით ვერიფიცირებული, 100% ზუსტი)
2. საერთო პრეფიქსის ანალიზი (მექანიკური, საიმედო)
3. LaBSE ემბედინგები + პრეფიქსი (სემანტიკური + ფორმალური)

შედეგი:
  data/bible_word_groups.json — ჯგუფები და word_to_group მაპინგი
"""
import os
import json
import re
import numpy as np
from collections import defaultdict


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VERSES_FILE = os.path.join(DATA_DIR, "verses.json")
UD_LEXICON_FILE = os.path.join(DATA_DIR, "ud_lemma_lexicon.json")
LABSE_FILE = os.path.join(DATA_DIR, "embeddings_labse.npz")
OUTPUT_FILE = os.path.join(DATA_DIR, "bible_word_groups.json")


def clean_tokenize(text):
    """სუფთა ტოკენიზაცია — მხოლოდ ქართული ასოები."""
    text = text.lower()
    return re.findall(r'[ა-ჰ]+', text)


class BibleWordGrouper:
    """
    ბიბლიის სიტყვების დაჯგუფება ფუძეების მიხედვით.
    არა ლემატიზაცია (სიტყვა -> ლემა),
    არამედ ჯგუფება (სიტყვა -> ჯგუფის ყველა წევრი).
    """

    def __init__(self, ud_lexicon):
        self.ud_lexicon = ud_lexicon
        self.groups = defaultdict(set)      # ლემა -> {ფორმა1, ფორმა2, ...}
        self.word_to_group = {}             # ფორმა -> ლემა

    def step1_ud_groups(self):
        """ფენა 1: UD ლექსიკონიდან ჯგუფები (100% ზუსტი)."""
        for word_form, lemma in self.ud_lexicon.items():
            self.groups[lemma].add(word_form)
            self.groups[lemma].add(lemma)
            self.word_to_group[word_form] = lemma
            self.word_to_group[lemma] = lemma

        print(f"  UD-დან: {len(self.groups)} ჯგუფი, "
              f"{len(self.word_to_group)} სიტყვა დაფარულია")

    def step2_prefix_groups(self, all_words,
                            min_prefix_ratio=0.82,
                            min_prefix_len=5,
                            max_group_size=30,
                            max_length_diff=4):
        """
        ფენა 2: საერთო პრეფიქსით ჯგუფება.

        უფრო მკაცრი პირობები:
        - min_prefix_ratio=0.8 (80% — ადრე 70% იყო)
        - min_prefix_len=5 (5 ასო — ადრე 4 იყო)
        - max_group_size=30 (არანაკლებ 30 ფორმა)
        - max_length_diff=4 (სიტყვების სიგრძის სხვაობა არ უნდა აღემატებოდეს 4-ს)
          ეს ხელს უშლის "ძე" (2) და "ძებდა" (6) დაჯგუფებას

        მთავარი ცვლილება: ანალიზი მოიცავს ყველა სიტყვას,
        არა მხოლოდ დაუფარავს. ეს უზრუნველყოფს, რომ UD სიტყვები
        და მათი ფორმები ერთ ჯგუფში მოექცენ.
        """
        # ყველა სიტყვა, არა მხოლოდ uncovered
        all_sorted = sorted(all_words)

        # Union-Find სტრუქტურა ყველა სიტყვისთვის
        parent = {w: w for w in all_words}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                # UD ლემას პრიორიტეტი აქვს
                px_ud = px in self.word_to_group
                py_ud = py in self.word_to_group
                if px_ud and not py_ud:
                    parent[py] = px
                elif py_ud and not px_ud:
                    parent[px] = py
                elif px_ud and py_ud:
                    # ორივე UD-შია — UD ლემების მიხედვით
                    lx = self.word_to_group[px]
                    ly = self.word_to_group[py]
                    if lx == ly:
                        # იგივე ლემა — ვაერთიანებთ
                        if len(px) <= len(py):
                            parent[py] = px
                        else:
                            parent[px] = py
                    # სხვა ლემა — არ ვაერთიანებთ (ცრუ-დადებითია)
                else:
                    # უფრო მოკლე სიტყვა ხდება ფუძე
                    if len(px) <= len(py):
                        parent[py] = px
                    else:
                        parent[px] = py

        for i, word1 in enumerate(all_sorted):
            for j in range(i + 1, min(i + 50, len(all_sorted))):
                word2 = all_sorted[j]

                prefix = self._common_prefix(word1, word2)
                # დინამიური min_prefix_len — მოკლე სიტყვებისთვის (≤5) უფრო დაბალი
                # რადგან max_length_diff=4 უკვე ხელს უშლის ცრუ-დადებითებს
                min_len_words = min(len(word1), len(word2))
                dynamic_min_prefix = min(min_prefix_len, max(3, min_len_words - 1))
                if len(prefix) < dynamic_min_prefix:
                    break  # ანბანურად შორს წავედით

                # სიგრძის სხვაობის ფილტრი — ხელს უშლის ცრუ-დადებითებს
                if abs(len(word1) - len(word2)) > max_length_diff:
                    continue

                # ფარდობა — ორივე სიტყვის საშუალო სიგრძით
                # ეს ხელს უშლის მოკლე სიტყვას (მაგ "მეფ") იყოს ხიდი
                # გრძელ სიტყვებს შორის (მაგ "მეფარე", "მეფაყათი")
                avg_len = (len(word1) + len(word2)) / 2
                if len(prefix) / avg_len >= min_prefix_ratio:
                    union(word1, word2)

        # Union-Find-დან ჯგუფების აგება
        raw_groups = defaultdict(set)
        for w in all_words:
            root = find(w)
            raw_groups[root].add(w)

        # ცრუ-დადებითი ჯგუფების ფილტრაცია — ზედმეტად დიდი ჯგუფები
        filtered_groups = {}
        split_count = 0
        for root, forms in raw_groups.items():
            if len(forms) > max_group_size:
                # დიდი ჯგუფი — ვანაწილებთ სიგრძის მიხედვით
                by_length = defaultdict(set)
                for f in forms:
                    by_length[len(f)].add(f)

                # მეზობელი სიგრძეების გაერთიანება (±2)
                processed = set()
                for length in sorted(by_length.keys()):
                    if length in processed:
                        continue
                    group = set(by_length[length])
                    processed.add(length)
                    for dl in range(length + 1, length + 3):
                        if dl in by_length:
                            group.update(by_length[dl])
                            processed.add(dl)
                    if len(group) > 1:
                        # ფუძე = ყველაზე მოკლე
                        root2 = min(group, key=len)
                        filtered_groups[root2] = group
                    else:
                        sole = list(group)[0]
                        filtered_groups[sole] = {sole}
                split_count += 1
            else:
                filtered_groups[root] = forms

        if split_count:
            print(f"    დაყოფილი {split_count} ზედმეტად დიდი ჯგუფი")

        # სრული გადაკეთება — ყველა ჯგუფი თავიდან აგება
        self.groups = defaultdict(set)
        self.word_to_group = {}

        for root, forms in filtered_groups.items():
            # ვპოულობთ UD ლემას ამ ჯგუფში
            ud_lemma = None
            for form in forms:
                if form in self.ud_lexicon:
                    ud_lemma = self.ud_lexicon[form]
                    break

            if ud_lemma:
                # UD ლემას ვიყენებთ
                self.groups[ud_lemma].update(forms)
                for form in forms:
                    self.word_to_group[form] = ud_lemma
            else:
                # არანაირი UD — ვიყენებთ ყველაზე მოკლე ფორმას
                lemma = min(forms, key=len)
                self.groups[lemma].update(forms)
                for form in forms:
                    self.word_to_group[form] = lemma

        covered_now = len([w for w in all_words if w in self.word_to_group])
        print(f"  პრეფიქსით: {len(self.groups)} ჯგუფი, "
              f"{covered_now}/{len(all_words)} სიტყვა დაფარულია "
              f"({covered_now/len(all_words)*100:.1f}%)")

    def step3_embedding_groups(self, all_words, embeddings, verse_texts,
                                similarity_threshold=0.90,
                                min_common_prefix=5,
                                min_prefix_ratio=0.7):
        """
        ფენა 3: LaBSE ემბედინგებით ჯგუფება.

        პირობა (სამივე ერთდროულად!):
        1. cosine similarity >= 0.90 (სემანტიკურად ახლოა)
        2. საერთო პრეფიქსი >= 5 ასო (ფორმალურადაც ახლოა)
        3. პრეფიქსი >= 70% მოკლე სიტყვის სიგრძისა
        """
        # ჯერ ვაგებთ სიტყვის ემბედინგებს მუხლების ემბედინგებიდან
        # მაგრამ უკეთესია სიტყვის ემბედინგები ცალკე გამოვთვალოთ
        # ამიტომ ვიყენებთ მარტივ მიდგომას: სიტყვის ემბედინგი = 
        # საშუალო ემბედინგი მუხლებისა, სადაც ეს სიტყვა გვხვდება

        from collections import defaultdict
        word_to_verse_idxs = defaultdict(list)
        for i, text in enumerate(verse_texts):
            tokens = set(clean_tokenize(text))
            for t in tokens:
                word_to_verse_idxs[t].append(i)

        # სიტყვის ემბედინგი = საშუალო მუხლის ემბედინგი
        word_embeddings = {}
        uncovered = [w for w in all_words if w not in self.word_to_group]

        print(f"  სიტყვის ემბედინგების გამოთვლა {len(uncovered)} სიტყვისთვის...")
        for w in uncovered:
            idxs = word_to_verse_idxs.get(w, [])
            if idxs:
                word_embeddings[w] = embeddings[idxs].mean(axis=0)

        if not word_embeddings:
            print("  ყველა სიტყვა უკვე დაფარულია!")
            return

        # ემბედინგების მატრიცა
        words_list = list(word_embeddings.keys())
        emb_arr = np.array([word_embeddings[w] for w in words_list])
        norms = np.linalg.norm(emb_arr, axis=1, keepdims=True)
        emb_normed = emb_arr / (norms + 1e-8)

        # ბლოკებად დამუშავება
        batch_size = 1000
        new_groups = defaultdict(set)

        for start in range(0, len(words_list), batch_size):
            end = min(start + batch_size, len(words_list))
            batch = emb_normed[start:end]
            sims = batch @ emb_normed.T

            for i, word1 in enumerate(words_list[start:end]):
                if word1 in self.word_to_group:
                    continue

                high_sim_indices = np.where(sims[i] >= similarity_threshold)[0]

                for idx in high_sim_indices:
                    if idx == start + i:
                        continue
                    word2 = words_list[idx]

                    prefix = self._common_prefix(word1, word2)
                    min_len = min(len(word1), len(word2))
                    if (len(prefix) >= min_common_prefix and
                        len(prefix) / min_len >= min_prefix_ratio):
                        shorter = word1 if len(word1) <= len(word2) else word2
                        new_groups[shorter].add(word1)
                        new_groups[shorter].add(word2)

            if (start // batch_size + 1) % 5 == 0:
                print(f"    {start + batch_size}/{len(words_list)}")

        # UD და პრეფიქს ჯგუფებთან შერწყმა
        for lemma, forms in new_groups.items():
            existing_lemma = None
            for form in forms:
                if form in self.word_to_group:
                    existing_lemma = self.word_to_group[form]
                    break

            if existing_lemma:
                self.groups[existing_lemma].update(forms)
                for form in forms:
                    self.word_to_group[form] = existing_lemma
            else:
                self.groups[lemma].update(forms)
                for form in forms:
                    self.word_to_group[form] = lemma

        covered_now = len([w for w in all_words if w in self.word_to_group])
        print(f"  ემბედინგებით: {len(self.groups)} ჯგუფი, "
              f"{covered_now}/{len(all_words)} სიტყვა დაფარულია "
              f"({covered_now/len(all_words)*100:.1f}%)")

    def _common_prefix(self, s1, s2):
        """ორი სტრინგის საერთო პრეფიქსი."""
        prefix = []
        for c1, c2 in zip(s1, s2):
            if c1 == c2:
                prefix.append(c1)
            else:
                break
        return "".join(prefix)

    def step4_manual_corrections(self, all_words):
        """
        ფენა 4: ხელით კორექტირება — ცნობილი ცრუ-დადებითების გამოსწორება.

        ბიბლია დახურული კორპუსია, ამიტომ შეგვიძლია ზუსტი
        კორექტირება ცნობილი შემთხვევებისთვის.
        """
        # ცნობილი ცრუ-დადებითები — სიტყვა რომელიც არ უნდა იყოს ჯგუფში
        # format: {სიტყვა: არასწორი_ჯგუფი, ...}
        # ეს სიტყვები გამოირჩევა თავისი საკუთარ ჯგუფში
        exclusions = {
            # "მოსე" (Moses) → "მოსელი" (newcomer) — სხვა სიტყვა
            "მოსელი": "მოსე",
            "მოსელნი": "მოსე",
            "მოსელსა": "მოსე",
            "მოსერო": "მოსე",
            "მოსეროთში": "მოსე",
            # "მამა" (father) → "მამავ" — სხვა ფუძე
            "მამავ": "მამა",
        }

        removed = 0
        for word, wrong_lemma in exclusions.items():
            if word in self.word_to_group:
                current_lemma = self.word_to_group[word]
                if current_lemma == wrong_lemma:
                    # გამოვიღოთ ჯგუფიდან
                    self.groups[current_lemma].discard(word)
                    # გავხადოთ ცალკე ჯგუფი
                    self.groups[word] = {word}
                    self.word_to_group[word] = word
                    removed += 1

        if removed:
            print(f"  ხელით კორექტირება: {removed} ცრუ-დადებითი გამოსწორდა")

    def get_search_expansion(self, query_word):
        """
        ძიებისთვის: მომხმარებელი წერს "უფალი" ->
        ვაბრუნებთ ყველა ფორმას: {უფალი, უფალმა, უფლის, ...}
        """
        query_lower = query_word.lower()
        if query_lower in self.word_to_group:
            lemma = self.word_to_group[query_lower]
            return self.groups[lemma]
        return {query_lower}

    def save(self, path):
        data = {
            "groups": {k: sorted(v) for k, v in self.groups.items()},
            "word_to_group": self.word_to_group
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  შენახულია: {path} ({len(self.groups)} ჯგუფი)")

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        obj = cls(ud_lexicon={})
        obj.groups = {k: set(v) for k, v in data["groups"].items()}
        obj.word_to_group = data["word_to_group"]
        return obj


def main():
    print("=== Bible Word Grouper ===\n")

    # მუხლების ჩატვირთვა
    print("მუხლების ჩატვირთვა...")
    with open(VERSES_FILE, encoding="utf-8") as f:
        verses = json.load(f)
    print(f"  {len(verses):,} მუხლი")

    # UD ლექსიკონი
    print("\nUD ლექსიკონის ჩატვირთვა...")
    with open(UD_LEXICON_FILE, encoding="utf-8") as f:
        ud_lexicon = json.load(f)
    print(f"  {len(ud_lexicon)} სიტყვა")

    # ყველა უნიკალური სიტყვა
    print("\nუნიკალური სიტყვების ამოღება...")
    all_words = set()
    verse_texts = []
    for v in verses:
        new = v.get("new") or ""
        old = v.get("old") or ""
        combined = new + " " + old
        verse_texts.append(combined)
        all_words.update(clean_tokenize(combined))
    all_words = sorted(all_words)
    print(f"  {len(all_words):,} უნიკალური სიტყვა")

    # LaBSE ემბედინგები
    print("\nLaBSE ემბედინგების ჩატვირთვა...")
    if os.path.exists(LABSE_FILE):
        data = np.load(LABSE_FILE)
        embeddings = data["embeddings"]
        print(f"  shape: {embeddings.shape}")
    else:
        embeddings = None
        print("  არ არსებობს — ვტოვებთ step3-ს")

    # ჯგუფების აგება
    grouper = BibleWordGrouper(ud_lexicon)

    print("\n=== ფენა 1: UD ჯგუფები ===")
    grouper.step1_ud_groups()

    print("\n=== ფენა 2: პრეფიქსის ჯგუფები ===")
    grouper.step2_prefix_groups(all_words)

    if embeddings is not None:
        print("\n=== ფენა 3: LaBSE ემბედინგები ===")
        grouper.step3_embedding_groups(all_words, embeddings, verse_texts)

    print("\n=== ფენა 4: ხელით კორექტირება ===")
    grouper.step4_manual_corrections(all_words)

    # სტატისტიკა
    covered = len([w for w in all_words if w in grouper.word_to_group])
    multi_groups = {k: v for k, v in grouper.groups.items() if len(v) > 1}

    print(f"\n=== შედეგი ===")
    print(f"  ჯგუფები: {len(grouper.groups):,}")
    print(f"  2+ ფორმიანი ჯგუფები: {len(multi_groups):,}")
    print(f"  დაფარული სიტყვები: {covered:,}/{len(all_words):,} "
          f"({covered/len(all_words)*100:.1f}%)")

    # ბიბლიური სიტყვების შემოწმება
    print(f"\n=== ბიბლიური სიტყვების შემოწმება ===")
    test_words = ["უფალი", "ღმერთი", "იესო", "ქრისტე", "მოსე",
                  "სული", "სიყვარული", "სასუფეველი", "მამა", "ძე",
                  "თქვა", "წარვიდა", "მოვიდა", "ხალხი", "მეფე"]
    for w in test_words:
        forms = grouper.get_search_expansion(w)
        if len(forms) > 1:
            print(f"  {w} ({len(forms)} ფორმა): {', '.join(sorted(forms)[:10])}")
        else:
            print(f"  {w}: მხოლოდ ზუსტი ფორმა")

    # შენახვა
    print(f"\n=== შენახვა ===")
    grouper.save(OUTPUT_FILE)


if __name__ == "__main__":
    main()
