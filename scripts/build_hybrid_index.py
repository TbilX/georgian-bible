#!/usr/bin/env python3
"""
Hybrid Search ინდექსის აგება — "ნულოვანი აცდენის" არქიტექტურა.

სამი ფენა:
1. BM25 (ლექსიკური) — ზუსტი სიტყვების პოვნა
2. LaBSE Dense Embedding (სემანტიკური) — აზრით პოვნა, 109 ენა (ქართული ჩათვლით)
3. Cross-Encoder Reranking — საბოლოო ზუსტი რანჟირება

შედეგი:
  data/embeddings_labse.npz    — LaBSE embeddings (768-dim)
  data/bm25_index.pkl          — BM25 ინდექსი
  data/verse_index.json        — მუხლების მეტამონაცემები (უკვე გვაქვს)
"""
import os
import json
import pickle
import numpy as np
from rank_bm25 import BM25Okapi

# CPU-ზე გაშვება — GPU არ აყვება LaBSE-ს
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VERSES_FILE = os.path.join(DATA_DIR, "verses.json")
LABSE_FILE = os.path.join(DATA_DIR, "embeddings_labse.npz")
BM25_FILE = os.path.join(DATA_DIR, "bm25_index.pkl")

# LaBSE — 109 ენა, ქართული ჩათვლით, 768 განზომილება
# უკეთესია ქართულისთვის ვიდრე MiniLM
MODEL_NAME = "LaBSE"


def tokenize_georgian(text):
    """
    სუფთა ტოკენიზაცია ბიბლიის ტექსტისთვის.
    - მხოლოდ ქართული ასოები (Mkhedruli)
    - lowercase
    - არანაირი დამახინჯება (არა წინასწარი stemming)
    - ციფრები, პუნქტუაცია, ლათინური — არ შედის
    """
    import re
    text = text.lower()
    # მხოლოდ ქართული ასოები: U+10D0-U+10FF (Mkhedruli)
    tokens = re.findall(r'[ა-ჰ]+', text)
    return [t for t in tokens if len(t) >= 1]


def main():
    # მუხლების ჩატვირთვა
    print(f"მუხლების ჩატვირთვა: {VERSES_FILE}")
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        verses = json.load(f)
    print(f"  სულ: {len(verses):,} მუხლი")

    # ტექსტების მომზადება
    texts = []
    for v in verses:
        new = v.get("new", "").strip()
        old = v.get("old", "").strip()
        combined = new
        if old and old != new:
            combined += " " + old
        texts.append(combined)

    # === ფენა 1: BM25 ინდექსი ===
    print(f"\n=== ფენა 1: BM25 ინდექსი ===")
    print("ტოკენიზაცია...")
    tokenized = [tokenize_georgian(t) for t in texts]
    print("BM25 ინდექსის აგება...")
    bm25 = BM25Okapi(tokenized)
    print(f"  მზადაა! {len(tokenized):,} დოკუმენტი")

    # შენახვა
    with open(BM25_FILE, "wb") as f:
        pickle.dump(bm25, f)
    print(f"  შენახულია: {BM25_FILE} ({os.path.getsize(BM25_FILE)/1024/1024:.1f} MB)")

    # === ფენა 2: LaBSE Dense Embeddings ===
    print(f"\n=== ფენა 2: LaBSE Dense Embeddings ===")
    print(f"მოდელის ჩატვირთვა: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_embedding_dimension() if hasattr(model, 'get_embedding_dimension') else 768
    print(f"  განზომილება: {dim}")

    print(f"\nEmbeddings-ის გამოთვლა {len(texts):,} ტექსტისთვის (CPU, შესაძლოა 10-15 წუთი)...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
        device="cpu",
    )
    print(f"  მზადაა: shape={embeddings.shape}, dtype={embeddings.dtype}")

    # შენახვა
    print(f"შენახვა: {LABSE_FILE}")
    np.savez_compressed(LABSE_FILE, embeddings=embeddings)
    print(f"  ზომა: {os.path.getsize(LABSE_FILE)/1024/1024:.1f} MB")

    print("\n=== მზადაა! ===")
    print(f"BM25: {BM25_FILE}")
    print(f"LaBSE: {LABSE_FILE} ({embeddings.shape})")
    print(f"მუხლები: {len(verses):,}")
    print("\nშემდეგი ნაბიჯი: გაუშვით server.py (განახლებული)")


if __name__ == "__main__":
    main()
