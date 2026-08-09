"""
Unified Topic Discovery Aggregator.

Combines topic candidates from:

1. RSS feeds
2. Hacker News
3. GitHub Trending
4. arXiv

Each source module is responsible for fetching and
normalizing its own data.

This module coordinates all sources, removes duplicate
topics, and scores the remaining candidates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .rss import fetch_all_rss_topics
from .hackernews import fetch_hackernews_topics
from .github_trending import fetch_github_trending_topics
from .arxiv import fetch_arxiv_topics
from .deduplicator import deduplicate_topics
from .scorer import select_topics

from app.core.config import settings


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback limits (used only if settings values are absent or zero)
# ---------------------------------------------------------------------------

DEFAULT_RSS_LIMIT = 10
DEFAULT_HACKERNEWS_LIMIT = 30
DEFAULT_GITHUB_LIMIT = 25
DEFAULT_ARXIV_LIMIT = 20

DEFAULT_SCORE_THRESHOLD = 50


# ---------------------------------------------------------------------------
# Unified topic discovery
# ---------------------------------------------------------------------------

async def fetch_all_topics(
    rss_limit: int | None = None,
    hackernews_limit: int | None = None,
    github_limit: int | None = None,
    arxiv_limit: int | None = None,
    score_threshold: int = DEFAULT_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    # Use settings as authoritative source; fall back to module defaults.
    rss_limit = rss_limit or settings.RSS_LIMIT or DEFAULT_RSS_LIMIT
    hackernews_limit = hackernews_limit or settings.HACKERNEWS_LIMIT or DEFAULT_HACKERNEWS_LIMIT
    github_limit = github_limit or settings.GITHUB_LIMIT or DEFAULT_GITHUB_LIMIT
    arxiv_limit = arxiv_limit or settings.ARXIV_LIMIT or DEFAULT_ARXIV_LIMIT
    """
    Fetch topics from all discovery sources concurrently.

    Pipeline:

        RSS
        Hacker News
        GitHub Trending
        arXiv
             ↓
        Aggregation
             ↓
        Deduplication
             ↓
        Topic Scoring
             ↓
        Selected Topics

    Args:
        rss_limit:
            Maximum number of topics fetched from each RSS source.

        hackernews_limit:
            Maximum number of Hacker News topics.

        github_limit:
            Maximum number of GitHub Trending topics.

        arxiv_limit:
            Maximum number of arXiv topics.

        score_threshold:
            Minimum score required for a topic to be selected.

    Returns:
        List of selected and scored topic candidates.
    """

    logger.info("Starting unified topic discovery.")

    try:

        # ---------------------------------------------------------------
        # RSS is SYNCHRONOUS.
        #
        # fetch_all_rss_topics() returns a list directly.
        # Therefore execute it in a background thread.
        # ---------------------------------------------------------------

        rss_task = asyncio.to_thread(
            fetch_all_rss_topics,
            limit_per_source=rss_limit,
        )

        # ---------------------------------------------------------------
        # These services are ASYNCHRONOUS.
        # ---------------------------------------------------------------

        hackernews_task = fetch_hackernews_topics(
            limit=hackernews_limit,
        )

        github_task = fetch_github_trending_topics(
            limit=github_limit,
        )

        arxiv_task = fetch_arxiv_topics(
            limit=arxiv_limit,
        )

        # ---------------------------------------------------------------
        # Run all four discovery sources concurrently.
        # ---------------------------------------------------------------

        results = await asyncio.gather(
            rss_task,
            hackernews_task,
            github_task,
            arxiv_task,
            return_exceptions=True,
        )

        # ---------------------------------------------------------------
        # Source names corresponding to results above.
        # ---------------------------------------------------------------

        source_names = [
            "RSS",
            "Hacker News",
            "GitHub Trending",
            "arXiv",
        ]

        all_topics: list[dict[str, Any]] = []

        # ---------------------------------------------------------------
        # Process results from each source.
        # ---------------------------------------------------------------

        for source_name, result in zip(
            source_names,
            results,
        ):

            # -----------------------------------------------------------
            # One source may have failed.
            # -----------------------------------------------------------

            if isinstance(result, Exception):

                logger.error(
                    "%s discovery failed: %s",
                    source_name,
                    result,
                )

                continue

            # -----------------------------------------------------------
            # Every discovery service should return a list.
            # -----------------------------------------------------------

            if not isinstance(result, list):

                logger.warning(
                    "%s returned unexpected data type: %s",
                    source_name,
                    type(result).__name__,
                )

                continue

            # -----------------------------------------------------------
            # Add topics to unified collection.
            # -----------------------------------------------------------

            logger.info(
                "%s returned %d topics.",
                source_name,
                len(result),
            )

            all_topics.extend(result)

        # ---------------------------------------------------------------
        # Deduplicate AFTER all four sources have been processed.
        # ---------------------------------------------------------------

        logger.info(
            "Collected %d topics from all discovery sources.",
            len(all_topics),
        )

        unique_topics = deduplicate_topics(
            all_topics
        )

        logger.info(
            "Deduplication completed. "
            "Collected=%d, unique=%d, duplicates_removed=%d",
            len(all_topics),
            len(unique_topics),
            len(all_topics) - len(unique_topics),
        )

        # ---------------------------------------------------------------
        # Score and select topics.
        # ---------------------------------------------------------------

        selected_topics = select_topics(
            unique_topics,
            threshold=score_threshold,
        )

        logger.info(
            "Topic selection completed. "
            "Unique=%d, selected=%d, rejected=%d",
            len(unique_topics),
            len(selected_topics),
            len(unique_topics) - len(selected_topics),
        )

        return selected_topics

    except Exception:

        logger.exception(
            "Unexpected error during unified topic discovery."
        )

        return []


# ---------------------------------------------------------------------------
# Local test entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Run the complete unified topic discovery pipeline locally.
    """

    topics = await fetch_all_topics()

    print(
        f"\nFound {len(topics)} selected topics.\n"
    )

    for index, topic in enumerate(
        topics,
        start=1,
    ):

        print(
            f"## Topic {index}"
        )

        print(
            f"Title: {topic.get('title', '')}"
        )

        print(
            f"Source: {topic.get('source', '')}"
        )

        print(
            f"Score: {topic.get('score', 0)}"
        )

        print(
            f"Breakdown: {topic.get('score_breakdown', {})}"
        )

        print(
            f"URL: {topic.get('url', '')}"
        )

        print(
            "-" * 80
        )


# ---------------------------------------------------------------------------
# Script execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    asyncio.run(main())