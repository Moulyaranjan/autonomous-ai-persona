from datetime import datetime, timedelta, timezone

from app.models.topic import TopicCandidate
from app.services.editorial_engine import (
    EditorialDecision,
    EditorialEngine,
)


def test_editorial_relevant_ai_security_topic_is_accepted():
    """
    A topic with both AI relevance and an explicit AI Security
    signal should be accepted when recent and credible.
    """

    engine = EditorialEngine()

    candidate = TopicCandidate(
        title="Researchers discover prompt injection vulnerability in AI agents",
        summary=(
            "Security researchers identified a prompt injection attack "
            "that can manipulate autonomous AI agents."
        ),
        source_url="https://example.com/ai-agent-security",
        source_name="Hacker News",
        published_at=(
            datetime.now(timezone.utc)
            - timedelta(hours=2)
        ),
    )

    decision = engine.evaluate(
        candidate,
        persona_domain="AI Security",
    )

    assert decision.decision == "ACCEPT"
    assert decision.score >= 60

    assert "AI Security" in decision.reason
    assert "ai_security_alignment" in decision.score_breakdown
    assert "ai_security_signals" in decision.score_breakdown

    assert decision.score_breakdown["ai_security_alignment"] > 0


def test_editorial_generic_ai_topic_is_rejected():
    """
    Generic AI news must NOT be accepted merely because it
    contains AI-related keywords.

    Example:
        OpenAI releases a new language model

    This has AI relevance but no meaningful AI Security signal.
    """

    engine = EditorialEngine()

    candidate = TopicCandidate(
        title="OpenAI releases a new language model",
        summary=(
            "OpenAI announced a new language model with improved "
            "reasoning and general-purpose capabilities."
        ),
        source_url="https://example.com/openai-new-model",
        source_name="Hacker News",
        published_at=(
            datetime.now(timezone.utc)
            - timedelta(hours=2)
        ),
    )

    decision = engine.evaluate(
        candidate,
        persona_domain="AI Security",
    )

    assert decision.decision == "REJECT"

    assert decision.score == 0

    assert decision.score_breakdown["rejection_gate"] == (
        "no_ai_security_signal"
    )

    assert decision.score_breakdown["ai_security_alignment"] == 0

    assert "no AI Security signals" in decision.reason


def test_editorial_generic_security_topic_is_rejected():
    """
    A generic cybersecurity topic without AI context must also
    be rejected.
    """

    engine = EditorialEngine()

    candidate = TopicCandidate(
        title="Critical cybersecurity vulnerability discovered",
        summary=(
            "Security researchers discovered a major vulnerability "
            "in enterprise software."
        ),
        source_url="https://example.com/security-vulnerability",
        source_name="Hacker News",
        published_at=(
            datetime.now(timezone.utc)
            - timedelta(hours=4)
        ),
    )

    decision = engine.evaluate(
        candidate,
        persona_domain="AI Security",
    )

    assert decision.decision == "REJECT"

    assert decision.score == 0

    assert decision.score_breakdown["rejection_gate"] == (
        "no_ai_tech_relevance"
    )


def test_editorial_rejects_irrelevant_topic():
    """
    Completely unrelated topics must be rejected.
    """

    engine = EditorialEngine()

    candidate = TopicCandidate(
        title="Baking Sourdough Bread: A Beginner's Guide",
        summary=(
            "Learn how to make delicious sourdough bread at home."
        ),
        source_url="https://example.com/sourdough",
        source_name="FoodBlog",
        published_at=(
            datetime.now(timezone.utc)
            - timedelta(hours=10)
        ),
    )

    decision = engine.evaluate(
        candidate,
        persona_domain="AI Security",
    )

    assert decision.decision == "REJECT"

    assert decision.score == 0

    assert "Rejected" in decision.reason
