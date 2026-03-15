"""
Step 3: Chunk transcripts into 2-minute windows and embed with text-embedding-005.

Chunking strategy (from PRD):
- 120-second sliding windows
- 15-second overlap between windows
- Chunk prefix: "Session: {title}\\nTrack: {track}\\nSpeakers: {speakers}\\nTranscript:\\n{text}"
- Embedding model: text-embedding-005, 768 dimensions
- Task type: RETRIEVAL_DOCUMENT (for indexing)
- Batch size: 250 chunks per API call

Usage:
    python pipeline/03_chunk_and_embed.py                 # Process all transcripts
    python pipeline/03_chunk_and_embed.py --video xLDSuXD8Mls  # Process one video
    python pipeline/03_chunk_and_embed.py --skip-embed     # Chunk only, no embeddings
"""

import argparse
import json
import os
import time
from pathlib import Path

import vertexai
from dotenv import load_dotenv
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

load_dotenv()

TRANSCRIPTS_DIR = Path(__file__).parent / "data" / "transcripts"
CHUNKS_DIR = Path(__file__).parent / "data" / "chunks"

CHUNK_WINDOW_SECONDS = 120
CHUNK_OVERLAP_SECONDS = 15
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_DIMENSIONS = 768
# text-embedding-005 has a 20K token input limit per batch.
# Each 2-min chunk is ~300-500 tokens with prefix. 20 chunks per batch is safe.
EMBEDDING_BATCH_SIZE = 20


def chunk_transcript(transcript_data: dict) -> list[dict]:
    """Chunk a transcript into 2-minute sliding windows with 15s overlap."""
    segments = transcript_data["segments"]
    video_id = transcript_data["video_id"]
    title = transcript_data["title"]
    track = transcript_data["track"]
    speakers = transcript_data["speakers"]
    speakers_str = ", ".join(speakers) if speakers else "Unknown"

    chunks: list[dict] = []
    step = CHUNK_WINDOW_SECONDS - CHUNK_OVERLAP_SECONDS  # 105 seconds

    # Find total duration
    if not segments:
        return chunks

    last_segment = segments[-1]
    total_duration = float(last_segment["start"]) + float(last_segment["duration"])

    window_start = 0.0
    chunk_index = 0

    while window_start < total_duration:
        window_end = window_start + CHUNK_WINDOW_SECONDS

        # Collect segments in this window
        window_segments = [
            s for s in segments
            if float(s["start"]) >= window_start and float(s["start"]) < window_end
        ]

        if not window_segments:
            window_start += step
            continue

        raw_text = " ".join(str(s["text"]) for s in window_segments)
        start_time = int(window_start)

        # Prefixed text for embedding (gives the model context about the source)
        prefixed_text = (
            f"Session: {title}\n"
            f"Track: {track}\n"
            f"Speakers: {speakers_str}\n"
            f"Transcript:\n{raw_text}"
        )

        youtube_url = f"https://youtube.com/watch?v={video_id}&t={start_time}s"

        chunk = {
            "chunk_id": f"{video_id}_{chunk_index:04d}",
            "source_type": "youtube_transcript",
            "source_id": video_id,
            "title": title,
            "track": track,
            "speakers": speakers,
            "start_time": start_time,
            "youtube_url": youtube_url,
            "raw_text": raw_text,
            "text": prefixed_text,
            "embedding": None,  # Filled in by embed step
        }

        chunks.append(chunk)
        chunk_index += 1
        window_start += step

    return chunks


def embed_chunks(chunks: list[dict], project_id: str, location: str) -> list[dict]:
    """Embed all chunks using text-embedding-005 on Vertex AI."""
    vertexai.init(project=project_id, location=location)

    texts = [c["text"] for c in chunks]
    all_embeddings: list[list[float]] = []

    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

    # Process in batches
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch_texts = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_num = (i // EMBEDDING_BATCH_SIZE) + 1
        total_batches = (len(texts) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
        print(f"    Embedding batch {batch_num}/{total_batches} ({len(batch_texts)} chunks)...")

        inputs = [
            TextEmbeddingInput(text=t, task_type="RETRIEVAL_DOCUMENT")
            for t in batch_texts
        ]
        embeddings = model.get_embeddings(
            inputs,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        all_embeddings.extend([e.values for e in embeddings])

        # Rate limit safety
        if i + EMBEDDING_BATCH_SIZE < len(texts):
            time.sleep(1)

    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding

    return chunks


def save_chunks(video_id: str, chunks: list[dict]) -> Path:
    """Save embedded chunks to JSON file."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CHUNKS_DIR / f"{video_id}_chunks.json"
    filepath.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))
    return filepath


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk and embed transcripts")
    parser.add_argument("--video", type=str, help="Process a single video by ID")
    parser.add_argument("--skip-embed", action="store_true", help="Chunk only, no embeddings")
    args = parser.parse_args()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "next-live-agent")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    # Find transcript files to process
    if args.video:
        transcript_files = list(TRANSCRIPTS_DIR.glob(f"{args.video}.json"))
    else:
        transcript_files = sorted(TRANSCRIPTS_DIR.glob("*.json"))

    if not transcript_files:
        print("No transcript files found. Run 01_fetch_transcripts.py first.")
        return

    print(f"Processing {len(transcript_files)} transcript(s)...\n")

    total_chunks = 0
    for filepath in transcript_files:
        transcript_data = json.loads(filepath.read_text())
        video_id = transcript_data["video_id"]
        title = transcript_data["title"]

        print(f"  [{video_id}] {title}")

        # Chunk
        chunks = chunk_transcript(transcript_data)
        print(f"    → {len(chunks)} chunks")

        if not chunks:
            print("    ⚠ No chunks generated, skipping")
            continue

        # Embed
        if not args.skip_embed:
            chunks = embed_chunks(chunks, project_id, location)
            dim = len(chunks[0]["embedding"]) if chunks[0]["embedding"] else 0
            print(f"    → Embedded ({dim} dimensions)")

        # Save
        output_path = save_chunks(video_id, chunks)
        print(f"    → Saved to {output_path.name}")
        total_chunks += len(chunks)

    print(f"\nDone: {total_chunks} total chunks processed")


if __name__ == "__main__":
    main()
