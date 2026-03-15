"""
Step 4: Upload embedded chunks to Firestore.

Uploads each chunk as a document in the 'session_chunks' collection.
The embedding field uses Firestore's native Vector type.

Usage:
    python pipeline/04_ingest_firestore.py                     # Ingest all chunks
    python pipeline/04_ingest_firestore.py --video xLDSuXD8Mls  # Ingest one video
    python pipeline/04_ingest_firestore.py --clear              # Clear collection first
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

load_dotenv()

CHUNKS_DIR = Path(__file__).parent / "data" / "chunks"
COLLECTION = "session_chunks"
BATCH_SIZE = 400  # Firestore batch write limit is 500


def clear_collection(db: firestore.Client) -> int:
    """Delete all documents in the session_chunks collection."""
    docs = db.collection(COLLECTION).list_documents()
    count = 0
    batch = db.batch()
    for doc in docs:
        batch.delete(doc)
        count += 1
        if count % BATCH_SIZE == 0:
            batch.commit()
            batch = db.batch()
            print(f"    Deleted {count} documents...")
    if count % BATCH_SIZE != 0:
        batch.commit()
    return count


def ingest_chunks(db: firestore.Client, chunks: list[dict]) -> int:
    """Upload chunks to Firestore using batch writes."""
    collection_ref = db.collection(COLLECTION)
    count = 0
    batch = db.batch()

    for chunk in chunks:
        if chunk.get("embedding") is None:
            print(f"    ⚠ Skipping {chunk['chunk_id']} — no embedding")
            continue

        doc_ref = collection_ref.document(chunk["chunk_id"])
        doc_data = {
            "source_type": chunk["source_type"],
            "source_id": chunk["source_id"],
            "title": chunk["title"],
            "track": chunk["track"],
            "speakers": chunk["speakers"],
            "start_time": chunk["start_time"],
            "youtube_url": chunk["youtube_url"],
            "raw_text": chunk["raw_text"],
            "text": chunk["text"],
            "embedding": Vector(chunk["embedding"]),
        }

        batch.set(doc_ref, doc_data)
        count += 1

        if count % BATCH_SIZE == 0:
            batch.commit()
            batch = db.batch()
            print(f"    Uploaded {count} documents...")

    if count % BATCH_SIZE != 0:
        batch.commit()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest chunks to Firestore")
    parser.add_argument("--video", type=str, help="Ingest chunks for a single video")
    parser.add_argument("--clear", action="store_true", help="Clear collection before ingesting")
    args = parser.parse_args()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent")
    db = firestore.Client(project=project_id)

    if args.clear:
        print("Clearing session_chunks collection...")
        deleted = clear_collection(db)
        print(f"  Deleted {deleted} documents\n")

    # Find chunk files
    if args.video:
        chunk_files = list(CHUNKS_DIR.glob(f"{args.video}_chunks.json"))
    else:
        chunk_files = sorted(CHUNKS_DIR.glob("*_chunks.json"))

    if not chunk_files:
        print("No chunk files found. Run 03_chunk_and_embed.py first.")
        return

    print(f"Ingesting {len(chunk_files)} chunk file(s)...\n")

    total_uploaded = 0
    for filepath in chunk_files:
        chunks = json.loads(filepath.read_text())
        video_id = chunks[0]["source_id"] if chunks else filepath.stem
        title = chunks[0]["title"] if chunks else "Unknown"

        print(f"  [{video_id}] {title} ({len(chunks)} chunks)")
        uploaded = ingest_chunks(db, chunks)
        print(f"    ✓ Uploaded {uploaded} documents")
        total_uploaded += uploaded

    print(f"\nDone: {total_uploaded} total documents uploaded to Firestore")


if __name__ == "__main__":
    main()
