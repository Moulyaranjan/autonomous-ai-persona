import uuid

import pytest

from app.database.database import (
    AsyncSessionLocal,
    Base,
    engine,
    run_migrations,
)
from app.models.post import Post
from app.services.memory import MemoryService


@pytest.mark.asyncio
async def test_memory_has_seen_topic_by_normalized_title():
    """
    Memory should recognize a previously published topic even
    when the new title differs only by capitalization or punctuation.
    """

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        agent_id = f"test-agent-title-{uuid.uuid4()}"

        post = Post(
            agent_id=agent_id,
            topic_title="OpenAI Announces New AI Security Model!",
            topic_url="https://example.com/security-model",
            text="Sample post content",
            rationale="Sample rationale",
            sources='["https://example.com/security-model"]',
        )

        db.add(post)
        await db.commit()

        memory = MemoryService(db)

        # Same topic with different capitalization/punctuation.
        assert await memory.has_seen_topic(
            agent_id=agent_id,
            title="openai announces new ai security model",
            url="https://example.com/different-url",
        ) is True


@pytest.mark.asyncio
async def test_memory_has_seen_topic_by_normalized_url():
    """
    Memory should recognize a previously published topic when
    the same URL is provided with tracking parameters.
    """

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        agent_id = f"test-agent-url-{uuid.uuid4()}"

        post = Post(
            agent_id=agent_id,
            topic_title="Prompt Injection Attack Against AI Agents",
            topic_url="https://example.com/prompt-injection",
            text="Sample post content",
            rationale="Sample rationale",
            sources='["https://example.com/prompt-injection"]',
        )

        db.add(post)
        await db.commit()

        memory = MemoryService(db)

        # Same URL with a tracking parameter.
        assert await memory.has_seen_topic(
            agent_id=agent_id,
            title="Completely Different Title",
            url=(
                "https://example.com/prompt-injection"
                "?utm_source=twitter"
            ),
        ) is True


@pytest.mark.asyncio
async def test_memory_different_agent_isolated():
    """
    Memory must remain isolated between agents.
    """

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        agent_id = f"test-agent-a-{uuid.uuid4()}"
        other_agent_id = f"test-agent-b-{uuid.uuid4()}"

        title = f"Unique AI Security Research {uuid.uuid4()}"

        post = Post(
            agent_id=agent_id,
            topic_title=title,
            topic_url="https://example.com/research",
            text="Sample post content",
            rationale="Sample rationale",
            sources='["https://example.com/research"]',
        )

        db.add(post)
        await db.commit()

        memory = MemoryService(db)

        assert await memory.has_seen_topic(
            agent_id=agent_id,
            title=title,
            url="https://example.com/research",
        ) is True

        assert await memory.has_seen_topic(
            agent_id=other_agent_id,
            title=title,
            url="https://example.com/research",
        ) is False


@pytest.mark.asyncio
async def test_memory_unseen_topic_returns_false():
    """
    A genuinely new topic should not be considered previously seen.
    """

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:

        agent_id = f"test-agent-new-{uuid.uuid4()}"

        memory = MemoryService(db)

        assert await memory.has_seen_topic(
            agent_id=agent_id,
            title="Brand New AI Security Research",
            url="https://example.com/new-research",
        ) is False

