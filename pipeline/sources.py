"""Content sources for the Next '25 knowledge base."""

YOUTUBE_SOURCES: list[dict[str, str | list[str]]] = [
    {
        "video_id": "xLDSuXD8Mls",
        "title": "Developer Keynote — Google Cloud Next '25",
        "track": "Keynote",
        "speakers": ["Jeanine Banks", "Jason Bender", "Logan Kilpatrick"],
        "priority": "P0",
    },
    {
        "video_id": "Md4Fs-Zc3tg",
        "title": "Opening Keynote (Full) — Google Cloud Next '25",
        "track": "Keynote",
        "speakers": ["Thomas Kurian", "Sundar Pichai"],
        "priority": "P0",
    },
    {
        "video_id": "zgrOwow_uTQ",
        "title": "Introducing the Agent Development Kit (ADK)",
        "track": "ADK",
        "speakers": [],
        "priority": "P0",
    },
    {
        "video_id": "dwgmfSOZNoQ",
        "title": "Keynote 10-Minute Highlights — Google Cloud Next '25",
        "track": "Keynote",
        "speakers": [],
        "priority": "P0",
    },
    {
        "video_id": "44C8u0CDtSo",
        "title": "Getting Started with ADK",
        "track": "ADK",
        "speakers": [],
        "priority": "P1",
    },
    {
        "video_id": "5ZmaWY7UX6k",
        "title": "Getting Started with ADK Tools",
        "track": "ADK",
        "speakers": [],
        "priority": "P1",
    },
    {
        "video_id": "EFhzfeEPF8o",
        "title": "ADK: Orchestrating AI Agents (DEVcember)",
        "track": "ADK",
        "speakers": [],
        "priority": "P1",
    },
    {
        "video_id": "h9Lueiqo89E",
        "title": "ADK Community Call — January 2026",
        "track": "ADK",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "cXDr4RYJxK0",
        "title": "ADK Community Call — February 2026",
        "track": "ADK",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "3v8SRiS8xcQ",
        "title": "Salesforce — Agentforce + A2A Protocol",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "J2iOiEwCZEw",
        "title": "Verizon — AI Customer Agents",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "SLyuYxBvHhE",
        "title": "Deutsche Bank — DB Lumina",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "_w1FgKv1IlI",
        "title": "Nevada DETR — Appeals Assistant",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "o9VdzkhiOW8",
        "title": "Reddit — Reddit Answers with Gemini",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "ijGmXAy4oj4",
        "title": "Jensen Huang — Gemini on NVIDIA",
        "track": "Keynote",
        "speakers": ["Jensen Huang"],
        "priority": "P2",
    },
    {
        "video_id": "imd-Vx9hhu0",
        "title": "Intuit — AI Tax Preparation",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "qEhrg5-NOzk",
        "title": "Mercado Libre — Vertex AI Search",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
    {
        "video_id": "tl20Hswfy9A",
        "title": "Honeywell — Gemini Product Development",
        "track": "Customer Story",
        "speakers": [],
        "priority": "P2",
    },
]

BLOG_SOURCES: list[dict[str, str]] = [
    {
        "url": "https://cloud.google.com/blog/topics/google-cloud-next/google-cloud-next-2025-wrap-up",
        "title": "Google Cloud Next 2025 Wrap-Up — All 231 Announcements",
        "track": "Announcements",
    },
    {
        "url": "https://cloud.google.com/blog/topics/google-cloud-next/developer-keynote-recap-next25",
        "title": "Next '25 Developer Keynote Recap",
        "track": "Keynote",
    },
    {
        "url": "https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/",
        "title": "ADK Official Announcement",
        "track": "ADK",
    },
    {
        "url": "https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/",
        "title": "Agent2Agent (A2A) Protocol Announcement",
        "track": "A2A",
    },
    {
        "url": "https://cloud.google.com/blog/topics/google-cloud-next/next25-day-1-recap",
        "title": "Next '25 Day 1 Recap",
        "track": "Announcements",
    },
    {
        "url": "https://cloud.google.com/blog/products/ai-machine-learning/google-agentspace-agent-driven-enterprise",
        "title": "Google Agentspace — Agent-Driven Enterprise",
        "track": "Agentspace",
    },
    {
        "url": "https://cloud.google.com/blog/products/ai-machine-learning/build-and-manage-multi-system-agents-vertex-ai",
        "title": "Build and Manage Multi-System Agents with Vertex AI",
        "track": "Agent Engine",
    },
    {
        "url": "https://blog.google/technology/ai/google-cloud-next-2025-sundar-pichai-keynote/",
        "title": "Sundar Pichai Keynote Recap",
        "track": "Keynote",
    },
]


def get_sources_by_priority(priority: str) -> list[dict[str, str | list[str]]]:
    """Filter YouTube sources by priority level."""
    return [s for s in YOUTUBE_SOURCES if s["priority"] == priority]
