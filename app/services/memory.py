import re
from typing import Any
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post


class MemoryService:
    """
    Memory service responsible for preventing an agent from
    publishing the same topic more than once.

    Duplicate detection uses:

    1. Normalized topic title
    2. Normalized source URL

    URL matching is only performed when a URL is supplied.
    This keeps the existing has_seen_topic(agent_id, title)
    interface backward compatible.
    """

    _TRACKING_PARAMETERS = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_title(title: str | None) -> str:
        """
        Normalize a title for reliable duplicate comparison.

        Example:

            "OpenAI Announces New AI Model!"
            ->
            "openai announces new ai model"
        """

        if not title:
            return ""

        normalized = str(title).lower()

        # Replace punctuation with spaces.
        normalized = re.sub(
            r"[^\w\s]",
            " ",
            normalized,
        )

        # Collapse repeated whitespace.
        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip()

    @classmethod
    def _normalize_url(cls, url: str | None) -> str:
        """
        Normalize a URL for duplicate comparison.

        Removes:
        - trailing slash
        - URL fragments
        - common tracking parameters
        - default HTTP/HTTPS ports
        """

        if not url:
            return ""

        url = str(url).strip()

        if not url:
            return ""

        try:
            parts = urlsplit(url)

            scheme = parts.scheme.lower()
            netloc = parts.netloc.lower()

            # Remove default ports.
            if scheme == "http":
                netloc = netloc.replace(":80", "")
            elif scheme == "https":
                netloc = netloc.replace(":443", "")

            path = parts.path.rstrip("/")

            query_parameters = [
                (key, value)
                for key, value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if key.lower() not in cls._TRACKING_PARAMETERS
            ]

            query = urlencode(query_parameters)

            return urlunsplit(
                (
                    scheme,
                    netloc,
                    path,
                    query,
                    "",
                )
            )

        except Exception:
            # Conservative fallback for malformed URLs.
            return url.rstrip("/")

    async def has_seen_topic(
        self,
        agent_id: str,
        title: str,
        url: str | None = None,
    ) -> bool:
        """
        Check whether an agent has already published a topic.

        A topic is considered previously seen when either:

        1. Its normalized title matches a previously published title.
        2. Its normalized URL matches a previously published URL.

        The URL check is only performed when a URL is supplied.

        Args:
            agent_id:
                Agent whose memory is being checked.

            title:
                Topic title.

            url:
                Optional source URL.

        Returns:
            True if the topic has already been published.
            False otherwise.
        """

        normalized_title = self._normalize_title(title)
        normalized_url = self._normalize_url(url)

        # ---------------------------------------------------------------
        # Fetch previously published posts for this agent.
        #
        # We intentionally scope memory to the agent so that two
        # different personas do not share publishing history.
        # ---------------------------------------------------------------

        result = await self.db.execute(
            select(
                Post.topic_title,
                Post.topic_url,
            ).where(
                Post.agent_id == agent_id,
            )
        )

        rows = result.all()

        for existing_title, existing_url in rows:

            # -----------------------------------------------------------
            # Title-based duplicate detection.
            # -----------------------------------------------------------

            existing_normalized_title = self._normalize_title(
                existing_title
            )

            if (
                normalized_title
                and existing_normalized_title
                and normalized_title == existing_normalized_title
            ):
                return True

            # -----------------------------------------------------------
            # URL-based duplicate detection.
            # -----------------------------------------------------------

            if normalized_url:

                existing_normalized_url = self._normalize_url(
                    existing_url
                )

                if (
                    existing_normalized_url
                    and normalized_url == existing_normalized_url
                ):
                    return True

        return False
