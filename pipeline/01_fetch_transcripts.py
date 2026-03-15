"""
Step 1: Fetch YouTube transcripts for Next '25 sessions.

IMPORTANT: Run this locally — never on a cloud VM.
YouTube blocks datacenter IPs.

Usage:
    python pipeline/01_fetch_transcripts.py              # Fetch P0 only
    python pipeline/01_fetch_transcripts.py --all         # Fetch all priorities
    python pipeline/01_fetch_transcripts.py --video xLDSuXD8Mls  # Fetch one video
"""

import argparse
import json
import sys
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

from pipeline.sources import YOUTUBE_SOURCES, get_sources_by_priority

DATA_DIR = Path(__file__).parent / "data" / "transcripts"


def fetch_transcript(video_id: str) -> list[dict[str, float | str]] | None:
    """Fetch transcript for a single YouTube video.

    Returns list of segments with 'text', 'start', 'duration' fields,
    or None if transcript is unavailable.
    """
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        # Convert FetchedTranscript to list of dicts
        segments = [
            {
                "text": snippet.text,
                "start": snippet.start,
                "duration": snippet.duration,
            }
            for snippet in transcript
        ]
        return segments
    except Exception as e:
        print(f"  ERROR fetching {video_id}: {e}")
        return None


def save_transcript(
    source: dict[str, str | list[str]],
    segments: list[dict[str, float | str]],
) -> Path:
    """Save transcript to JSON file with metadata."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    video_id = str(source["video_id"])
    output = {
        "video_id": video_id,
        "title": source["title"],
        "track": source["track"],
        "speakers": source["speakers"],
        "segment_count": len(segments),
        "segments": segments,
    }

    filepath = DATA_DIR / f"{video_id}.json"
    filepath.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return filepath


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts")
    parser.add_argument("--all", action="store_true", help="Fetch all priorities")
    parser.add_argument("--video", type=str, help="Fetch a single video by ID")
    parser.add_argument("--priority", type=str, default="P0", help="Priority level (P0, P1, P2)")
    args = parser.parse_args()

    if args.video:
        sources = [s for s in YOUTUBE_SOURCES if s["video_id"] == args.video]
        if not sources:
            # Allow fetching arbitrary video IDs not in sources list
            sources = [{"video_id": args.video, "title": args.video, "track": "Unknown", "speakers": [], "priority": "manual"}]
    elif args.all:
        sources = YOUTUBE_SOURCES
    else:
        sources = get_sources_by_priority(args.priority)

    print(f"Fetching transcripts for {len(sources)} video(s)...\n")

    success_count = 0
    fail_count = 0

    for source in sources:
        video_id = source["video_id"]
        title = source["title"]
        print(f"  [{video_id}] {title}...")

        segments = fetch_transcript(str(video_id))
        if segments is None:
            fail_count += 1
            continue

        filepath = save_transcript(source, segments)
        total_duration = sum(float(s["duration"]) for s in segments)
        minutes = total_duration / 60
        print(f"    ✓ {len(segments)} segments, {minutes:.1f} min → {filepath.name}")
        success_count += 1

    print(f"\nDone: {success_count} succeeded, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
