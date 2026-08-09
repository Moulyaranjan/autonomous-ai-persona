"""
Strict AI Security editorial filter for Ada.

Scoring system (0-100)
======================

  Factor                  Max   Notes
  ─────────────────────── ───   ────────────────────────────────────────────
  AI/technology relevance  20   Broad AI/tech keyword match
  AI Security alignment    40   Explicit security-signal match (hard gate)
  Recency                  20   Age of source article
  Source credibility       10   Known high-quality sources
  Significance             10   Event/significance indicators
  ─────────────────────── ───
  TOTAL                   100

Two hard gates precede the threshold check:

  Gate 1 – AI Security signal gate
      The topic must contain at least one AI Security signal in title or
      summary.  "AI" alone does NOT satisfy this gate.

  Gate 2 – AI / technology relevance gate
      The topic must contain at least one AI/technology keyword.
      Pure generic security articles (no AI context) are rejected here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import settings
from app.models.topic import TopicCandidate


@dataclass
class EditorialDecision:
    topic: TopicCandidate
    decision: str                            # "ACCEPT" | "REJECT"
    score: int                               # 0-100
    reason: str                              # Human-readable explanation
    score_breakdown: dict = field(default_factory=dict)


class EditorialEngine:
    """Deterministic editorial filter for Ada's AI Security persona."""

    # -----------------------------------------------------------------------
    # AI / Technology relevance keywords  (for Factor 1 only).
    # "ai" alone is deliberately included here but NOT in AI_SECURITY_SIGNALS.
    # -----------------------------------------------------------------------
    AI_TECH_KEYWORDS: frozenset[str] = frozenset({
        "ai",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "llm",
        "large language model",
        "generative ai",
        "openai",
        "anthropic",
        "claude",
        "gemini",
        "deepseek",
        "gpt",
        "chatgpt",
        "neural network",
        "robotics",
        "agentic",
        "autonomous agent",
        "open model",
        "transformer",
        "foundation model",
        "language model",
        "agent",
        # Inherently AI-security tech terms also boost AI-tech relevance.
        "jailbreak",
        "prompt injection",
        "adversarial",
        "guardrail",
        "hallucination",
        "model theft",
    })

    # -----------------------------------------------------------------------
    # AI Security signals  (Gate 1 + Factor 2).
    # "ai" alone is intentionally absent from this set.
    # -----------------------------------------------------------------------
    AI_SECURITY_SIGNALS: frozenset[str] = frozenset({
        "security",
        "safety",
        "secure",
        "secure deployment",
        "privacy",
        "vulnerability",
        "vulnerabilities",
        "vulnerable",
        "jailbreak",
        "prompt injection",
        "red team",
        "red-team",
        "red teaming",
        "adversarial",
        "misuse",
        "model misuse",
        "governance",
        "alignment",
        "guardrail",
        "guardrails",
        "authentication",
        "authorization",
        "data leakage",
        "data leak",
        "threat model",
        "threat",
        "incident",
        "cyber",
        "cybersecurity",
        "cyber security",
        "risk",
        "robustness",
        "supply chain",
        "supply-chain",
        "supply-chain security",
        "attack",
        "exploit",
        "breach",
        "malicious",
        "backdoor",
        "poisoning",
        "model theft",
        "evasion",
        "hallucination",
        "audit",
    })

    # -----------------------------------------------------------------------
    # Significance / newsworthiness indicators  (Factor 5).
    # -----------------------------------------------------------------------
    SIGNIFICANCE_KEYWORDS: frozenset[str] = frozenset({
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
        "discovers",
        "discovered",
        "discloses",
        "disclosed",
        "critical",
        "major",
        "first",
        "open source",
        "patch",
        "update",
    })

    # -----------------------------------------------------------------------
    # Credibility scores for known sources  (Factor 4, max 10).
    # -----------------------------------------------------------------------
    SOURCE_CREDIBILITY: dict[str, int] = {
        "Hacker News":    10,
        "arXiv AI":       10,
        "arXiv ML":       10,
        "arXiv CS":       10,
        "GitHub Trending": 8,
    }

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def evaluate(
        self,
        topic: TopicCandidate,
        persona_domain: str,  # kept for API compatibility; AI Security gates are hard-coded
    ) -> EditorialDecision:

        text = f"{topic.title} {topic.summary}".lower()

        # ------------------------------------------------------------------
        # Factor 1: AI / technology relevance  (0–20)
        # ------------------------------------------------------------------
        ai_tech_matched = sorted(
            {kw for kw in self.AI_TECH_KEYWORDS if kw in text}
        )
        ai_tech_score = min(len(ai_tech_matched) * 5, 20)

        reasons: list[str] = []
        if ai_tech_matched:
            reasons.append(
                f"AI relevance detected ({', '.join(ai_tech_matched[:3])})"
            )
        else:
            reasons.append("No AI/technology keywords found")

        # ------------------------------------------------------------------
        # Gate 1: AI Security signal – hard gate
        # A topic with zero AI Security signals is never eligible.
        # ------------------------------------------------------------------
        ai_security_matched = sorted(
            {sig for sig in self.AI_SECURITY_SIGNALS if sig in text}
        )

        if not ai_security_matched:
            reason = (
                f"Rejected (no AI Security signals): '{topic.title}' contains "
                f"none of the required AI Security signals. Generic AI topics "
                f"(story generation, model architecture, trading agents, etc.) "
                f"are not eligible for Ada's AI Security feed. "
                f"Evaluated: {'; '.join(reasons)}"
            )
            return EditorialDecision(
                topic=topic,
                decision="REJECT",
                score=0,
                reason=reason,
                score_breakdown={
                    "ai_tech_relevance": ai_tech_score,
                    "ai_security_alignment": 0,
                    "recency": 0,
                    "source_credibility": 0,
                    "significance": 0,
                    "total": 0,
                    "ai_security_signals": [],
                    "rejection_gate": "no_ai_security_signal",
                },
            )

        # ------------------------------------------------------------------
        # Gate 2: AI / technology relevance – hard gate
        # Security signals without any AI tech context suggest a generic
        # security article unrelated to AI systems.
        # ------------------------------------------------------------------
        if ai_tech_score == 0:
            reason = (
                f"Rejected (no AI tech relevance): '{topic.title}' has "
                f"security signals ({', '.join(ai_security_matched[:3])}) "
                f"but no AI/technology keywords. This appears to be a "
                f"general security topic unrelated to AI systems."
            )
            return EditorialDecision(
                topic=topic,
                decision="REJECT",
                score=0,
                reason=reason,
                score_breakdown={
                    "ai_tech_relevance": 0,
                    "ai_security_alignment": 0,
                    "recency": 0,
                    "source_credibility": 0,
                    "significance": 0,
                    "total": 0,
                    "ai_security_signals": ai_security_matched,
                    "rejection_gate": "no_ai_tech_relevance",
                },
            )

        reasons.append(
            f"AI Security signals matched ({', '.join(ai_security_matched[:4])})"
        )

        # ------------------------------------------------------------------
        # Factor 2: AI Security alignment  (0–40)
        # 1 signal → 20; each additional signal adds 10, capped at 40.
        # ------------------------------------------------------------------
        n = len(ai_security_matched)
        ai_security_score = min(20 + (n - 1) * 10, 40)

        # ------------------------------------------------------------------
        # Factor 3: Recency  (0–20)
        # ------------------------------------------------------------------
        recency_score, recency_label = self._recency_score(topic.published_at)
        reasons.append(recency_label)

        # ------------------------------------------------------------------
        # Factor 4: Source credibility  (0–10)
        # ------------------------------------------------------------------
        sn = topic.source_name or ""
        if sn in self.SOURCE_CREDIBILITY:
            source_credibility_score = self.SOURCE_CREDIBILITY[sn]
        elif "arxiv" in sn.lower():
            source_credibility_score = 10
        elif "github" in sn.lower():
            source_credibility_score = 8
        elif sn:
            source_credibility_score = 5
        else:
            source_credibility_score = 0

        if source_credibility_score > 0:
            reasons.append(
                f"Recognized source ({sn}, credibility {source_credibility_score}/10)"
            )

        # ------------------------------------------------------------------
        # Factor 5: Significance  (0–10)
        # ------------------------------------------------------------------
        sig_matched = sorted(
            {kw for kw in self.SIGNIFICANCE_KEYWORDS if kw in text}
        )
        significance_score = min(len(sig_matched) * 5, 10)
        if sig_matched:
            reasons.append(
                f"Significance indicators ({', '.join(sig_matched[:3])})"
            )

        # ------------------------------------------------------------------
        # Aggregate
        # ------------------------------------------------------------------
        total_score = (
            ai_tech_score
            + ai_security_score
            + recency_score
            + source_credibility_score
            + significance_score
        )

        score_breakdown = {
            "ai_tech_relevance":    ai_tech_score,
            "ai_security_alignment": ai_security_score,
            "recency":              recency_score,
            "source_credibility":   source_credibility_score,
            "significance":         significance_score,
            "total":                total_score,
            "ai_security_signals":  ai_security_matched,
            "recency_label":        recency_label,
        }

        threshold = settings.TOPIC_SCORE_THRESHOLD

        if total_score >= threshold:
            decision = "ACCEPT"
            reason = (
                f"Accepted (score {total_score}/100 ≥ threshold {threshold}). "
                + "; ".join(reasons)
            )
        else:
            decision = "REJECT"
            reason = (
                f"Rejected (score {total_score}/100 < threshold {threshold}). "
                + "; ".join(reasons)
            )

        return EditorialDecision(
            topic=topic,
            decision=decision,
            score=total_score,
            reason=reason,
            score_breakdown=score_breakdown,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _recency_score(
        published_at: datetime | None,
    ) -> tuple[int, str]:
        """Return (score, label) based on article age."""
        if not published_at:
            return 5, "Publication time unavailable (neutral score)"

        now = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        age_hours = (now - published_at).total_seconds() / 3600

        if age_hours < 0:
            return 20, "Future-dated (treated as just published)"
        if age_hours <= 24:
            return 20, "Published within the last 24 hours"
        if age_hours <= 72:
            return 15, "Published within the last 3 days"
        if age_hours <= 168:
            return 8, "Published within the last week"
        return 3, "Older than one week"