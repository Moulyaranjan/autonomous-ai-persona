"""
Topic Scoring and Selection Service.

This module evaluates discovered technology topics and assigns
a publication score.

The scorer is intentionally deterministic at this stage so that
the discovery pipeline can be tested without requiring an LLM.

Pipeline position:

    Discovery Sources
          ↓
       Aggregator
          ↓
      Deduplicator
          ↓
         Scorer
          ↓
    Selected Topics
"""

from __future__ import annotations

import logging
import re
from typing import Any


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SELECTION_THRESHOLD = 50


# ---------------------------------------------------------------------------
# Relevance keywords
# ---------------------------------------------------------------------------

# Keywords indicating strong AI / technology relevance.
HIGH_RELEVANCE_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "llm",
    "large language model",
    "agent",
    "ai agent",
    "robotics",
    "computer vision",
    "natural language processing",
    "nlp",
    "neural network",
    "openai",
    "anthropic",
    "gemini",
    "chatgpt",
    "gpt",
    "claude",
    "cuda",
    "gpu",
    "quantum computing",
    "cybersecurity",
    "cyber security",
    "developer tool",
    "software",
    "technology",
}


# ---------------------------------------------------------------------------
# Significance keywords
# ---------------------------------------------------------------------------

# Keywords indicating a potentially significant technology event.
#
# Security-related terms are included because vulnerabilities, attacks,
# exploits, prompt injection, jailbreaks, and security incidents are
# important technology developments. This does NOT make the scorer
# persona-specific; EditorialEngine remains responsible for deciding
# whether a topic actually fits the active persona.
SIGNIFICANCE_KEYWORDS = {
    "launch",
    "launched",
    "release",
    "released",
    "announces",
    "announced",
    "introduces",
    "introduced",
    "new",
    "breakthrough",
    "research",
    "study",
    "acquisition",
    "funding",
    "security",
    "cybersecurity",
    "cyber",
    "vulnerability",
    "vulnerabilities",
    "attack",
    "attacks",
    "exploit",
    "exploits",
    "jailbreak",
    "jailbreaks",
    "prompt injection",
    "model security",
    "security flaw",
    "security flaws",
    "data breach",
    "breach",
    "incident",
    "update",
    "major",
    "critical",
    "first",
    "open source",
    "opensource",
}


# ---------------------------------------------------------------------------
# Audience interest keywords
# ---------------------------------------------------------------------------

# Keywords indicating strong audience interest.
INTEREST_KEYWORDS = {
    "chatgpt",
    "gpt",
    "gemini",
    "claude",
    "openai",
    "anthropic",
    "google",
    "github",
    "ai agent",
    "agents",
    "llm",
    "robotics",
    "cybersecurity",
    "gpu",
    "developer",
    "open source",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _clean_text(value: Any) -> str:
    """Convert a value into normalized searchable text."""

    if value is None:
        return ""

    text = str(value)

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def _topic_text(topic: dict[str, Any]) -> str:
    """Combine important topic fields into searchable text."""

    title = _clean_text(topic.get("title", ""))
    summary = _clean_text(topic.get("summary", ""))

    tags = topic.get("tags", [])

    if isinstance(tags, list):
        tag_text = " ".join(
            _clean_text(tag)
            for tag in tags
        )
    else:
        tag_text = _clean_text(tags)

    return f"{title} {summary} {tag_text}".strip()


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

def _calculate_relevance_score(topic: dict[str, Any]) -> int:
    """
    Calculate AI/technology relevance.

    Maximum score: 30.
    """

    text = _topic_text(topic)

    score = 0

    matched_keywords: set[str] = set()

    for keyword in HIGH_RELEVANCE_KEYWORDS:
        if keyword in text:
            matched_keywords.add(keyword)

    # Reward multiple relevant signals.
    score += min(len(matched_keywords) * 5, 25)

    # Strong source-specific relevance.
    source = _clean_text(
        topic.get(
            "source",
            topic.get("source_name", ""),
        )
    )

    if source in {
        "openai",
        "google ai",
        "anthropic",
        "arxiv",
        "github trending",
        "hacker news",
    }:
        score += 5

    return min(score, 30)


# ---------------------------------------------------------------------------
# Significance scoring
# ---------------------------------------------------------------------------

def _calculate_significance_score(topic: dict[str, Any]) -> int:
    """
    Calculate how significant the topic appears.

    Maximum score: 25.

    Security-related developments such as vulnerabilities,
    attacks, exploits, jailbreaks, prompt injection, and
    critical incidents are treated as meaningful technology
    events without making this scorer persona-specific.
    """

    text = _topic_text(topic)

    matched = sum(
        1
        for keyword in SIGNIFICANCE_KEYWORDS
        if keyword in text
    )

    return min(matched * 5, 25)


# ---------------------------------------------------------------------------
# Audience interest scoring
# ---------------------------------------------------------------------------

def _calculate_interest_score(topic: dict[str, Any]) -> int:
    """
    Calculate potential audience interest.

    Maximum score: 25.
    """

    text = _topic_text(topic)

    matched = sum(
        1
        for keyword in INTEREST_KEYWORDS
        if keyword in text
    )

    return min(matched * 5, 25)


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

def _calculate_recency_score(topic: dict[str, Any]) -> int:
    """
    Calculate a basic recency score.

    The discovery services already provide published_at.

    Maximum score: 20.

    Invalid or missing timestamps receive a neutral score.
    """

    published_at = topic.get("published_at")

    if not published_at:
        return 10

    try:
        from datetime import datetime, timezone

        timestamp = str(published_at)

        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"

        published = datetime.fromisoformat(timestamp)

        if published.tzinfo is None:
            published = published.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)

        age_hours = (
            now - published
        ).total_seconds() / 3600

        if age_hours < 0:
            return 20

        if age_hours <= 24:
            return 20

        if age_hours <= 72:
            return 15

        if age_hours <= 168:
            return 10

        if age_hours <= 720:
            return 5

        return 0

    except (ValueError, TypeError, OverflowError):
        logger.warning(
            "Unable to parse published_at: %s",
            published_at,
        )

        return 10


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_topic(topic: dict[str, Any]) -> dict[str, Any]:
    """
    Score one topic.

    Returns a copy of the original topic with scoring metadata.

    Total score:

        relevance    = 30
        significance = 25
        interest     = 25
        recency      = 20

        TOTAL        = 100
    """

    relevance = _calculate_relevance_score(topic)

    significance = _calculate_significance_score(topic)

    interest = _calculate_interest_score(topic)

    recency = _calculate_recency_score(topic)

    total_score = (
        relevance
        + significance
        + interest
        + recency
    )

    scored_topic = dict(topic)

    scored_topic["score"] = total_score

    scored_topic["score_breakdown"] = {
        "relevance": relevance,
        "significance": significance,
        "interest": interest,
        "recency": recency,
    }

    return scored_topic


# ---------------------------------------------------------------------------
# Topic selection
# ---------------------------------------------------------------------------

def select_topics(
    topics: list[dict[str, Any]],
    threshold: int = DEFAULT_SELECTION_THRESHOLD,
) -> list[dict[str, Any]]:
    """
    Score and select topics suitable for publication.

    Args:
        topics:
            Deduplicated topic candidates.

        threshold:
            Minimum score required for selection.

    Returns:
        Topics whose score meets or exceeds the threshold,
        sorted from highest score to lowest score.
    """

    if not topics:
        logger.info("No topics received for scoring.")
        return []

    if threshold < 0 or threshold > 100:
        logger.warning(
            "Invalid scoring threshold: %d. "
            "Using default threshold=%d.",
            threshold,
            DEFAULT_SELECTION_THRESHOLD,
        )

        threshold = DEFAULT_SELECTION_THRESHOLD

    logger.info(
        "Starting topic scoring. Input topics=%d, threshold=%d",
        len(topics),
        threshold,
    )

    scored_topics: list[dict[str, Any]] = []

    for topic in topics:
        try:
            scored_topic = score_topic(topic)

            if scored_topic["score"] >= threshold:
                scored_topic["selected"] = True
                scored_topics.append(scored_topic)

            else:
                # Keep the decision visible if this module is
                # later used for debugging or analytics.
                scored_topic["selected"] = False

        except Exception:
            logger.exception(
                "Failed to score topic: %s",
                topic.get("title", "Unknown"),
            )

    # Highest-scoring topics first.
    scored_topics.sort(
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    logger.info(
        "Topic scoring completed. "
        "Input=%d, selected=%d, rejected=%d",
        len(topics),
        len(scored_topics),
        len(topics) - len(scored_topics),
    )

    return scored_topics


# ---------------------------------------------------------------------------
# Local test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    test_topics = [
        {
            "title": "OpenAI releases a new AI model",
            "summary": (
                "OpenAI announced a new large language model "
                "with improved reasoning capabilities."
            ),
            "url": "https://example.com/openai-model",
            "source": "OpenAI",
            "published_at": "2026-08-08T10:00:00Z",
            "tags": ["ai", "openai", "llm"],
        },
        {
            "title": (
                "Critical prompt injection vulnerability "
                "discovered in AI agents"
            ),
            "summary": (
                "Researchers identified a new prompt injection "
                "attack affecting autonomous AI agents."
            ),
            "url": "https://example.com/ai-security",
            "source": "OpenAI",
            "published_at": "2026-08-08T10:00:00Z",
            "tags": ["ai", "security"],
        },
        {
            "title": "Local weather report",
            "summary": (
                "Weather conditions are expected to remain stable."
            ),
            "url": "https://example.com/weather",
            "source": "Example",
            "published_at": "2026-08-08T09:00:00Z",
            "tags": ["weather"],
        },
    ]

    selected = select_topics(test_topics)

    print(f"\nSelected topics: {len(selected)}\n")

    for topic in selected:
        print(f"Title: {topic['title']}")
        print(f"Score: {topic['score']}")
        print(f"Breakdown: {topic['score_breakdown']}")
        print(f"Selected: {topic['selected']}")
        print("-" * 80)