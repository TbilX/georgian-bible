#!/usr/bin/env python3
"""
AI ძიების ინდექსის აგება.
ყველა მუხლს ვაქცივებთ (embedding) multilingual მოდელით.
შედეგი: data/embeddings.npz + data/verse_index.json
"""
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
VERSES_FILE = os.path.join(DATA_DIR, "verses.json")
EMBEDDINGS_FILE = os.path.join(DATA_DIR, "embeddings.npz")
INDEX_FILE = os.path.join(DATA_DIR, "verse_index.json")

# მოდელი: მრავალენოვანი, მსუბუქი, კარგად მუშაობს ქართულზე
# paraphrase-multilingual-MiniLM-L12-v2 — 384 განზომილება, სწრაფი
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def main():
    # მუხლების ჩატვირთვა
    print(f"მუხლების ჩატვირთვა: {VERSES_FILE}")
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        verses = json.load(f)
    print(f"  სულ: {len(verses):,} მუხლი")

    # ტექსტების მომზადება — ვაერთებთ ორ ენას უკეთესი ძიებისთვის
    # ფორმატი: "ახალი ქართული: ... ძველი ქართული: ..."
    texts = []
    for v in verses:
        new = v.get("new", "").strip()
        old = v.get("old", "").strip()
        # ვაერთებთ — ასე ძიება მუშაობს ორივე ენაზე
        combined = f"{new}"
        if old and old != new:
            combined += f" [ძველი: {old}]"
        texts.append(combined)

    # მოდელის ჩატვირთვა
    print(f"\nმოდელის ჩატვირთვა: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print(f"  განზომილება: {model.get_sentence_embedding_dimension()}")

    # Embeddings-ის გამოთვლა (batch-ებად)
    print(f"\nEmbeddings-ის გამოთვლა {len(texts):,} ტექსტისთვის...")
    batch_size = 256
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # cosine similarity-სთვის
    )
    print(f"  მზადაა: shape={embeddings.shape}, dtype={embeddings.dtype}")

    # შენახვა
    print(f"\nშენახვა: {EMBEDDINGS_FILE}")
    np.savez_compressed(EMBEDDINGS_FILE, embeddings=embeddings)
    print(f"  ზომა: {os.path.getsize(EMBEDDINGS_FILE) / 1024 / 1024:.1f} MB")

    # მარტივი ინდექსი (მუხლის ID -> მეტამონაცემები)
    # ეს საჭიროა სწრაფი ძიებისთვის
    index = []
    for i, v in enumerate(verses):
        index.append({
            "id": i,
            "book": v["book"],
            "book_slug": v["book_slug"],
            "chapter": v["chapter"],
            "verse": v["verse"],
            "testament": v["testament"],
            "new": v["new"],
            "old": v["old"],
        })

    print(f"შენახვა: {INDEX_FILE}")
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    print(f"  ზომა: {os.path.getsize(INDEX_FILE) / 1024 / 1024:.1f} MB")

    print("\n=== მზადაა! ===")
    print(f"მუხლები: {len(verses):,}")
    print(f"Embeddings: {embeddings.shape}")
    print(f"მოდელი: {MODEL_NAME}")


if __name__ == "__main__":
    main()
