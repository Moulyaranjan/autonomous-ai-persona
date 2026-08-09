import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.topic import TopicCandidate
from app.services.editorial_engine import EditorialDecision


class PostPublisher:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def publish(
        self,
        agent_id: str,
        topic: TopicCandidate,
        decision: EditorialDecision,
        text: str,
    ) -> Post:

        breakdown = decision.score_breakdown or {}

        ai_security_signals = breakdown.get(
            "ai_security_signals",
            [],
        )

        recency_label = breakdown.get(
            "recency_label",
            "Recency information was not available.",
        )

        source_credibility = breakdown.get(
            "source_credibility",
            0,
        )

        ai_tech_relevance = breakdown.get(
            "ai_tech_relevance",
            0,
        )

        ai_security_alignment = breakdown.get(
            "ai_security_alignment",
            0,
        )

        significance = breakdown.get(
            "significance",
            0,
        )

        # threshold = breakdown.get(
        #     "threshold",
        #     decision.score,
        # )

        if ai_security_signals:
            security_reason = (
                "The topic contains AI Security signals: "
                + ", ".join(ai_security_signals)
                + "."
            )
        else:
            security_reason = (
                "The topic passed the AI Security editorial gate."
            )

        rationale = (
            f"Selected '{topic.title}' because it achieved an "
            f"editorial score of {decision.score}/100 and passed "
            f"Ada's AI Security publishing standards. "
            f"AI/technology relevance contributed "
            f"{ai_tech_relevance}/20 points, while AI Security "
            f"alignment contributed {ai_security_alignment}/40 points. "
            f"{security_reason} "
            f"{recency_label}, making the topic relevant to the "
            f"current publishing cycle. "
            f"The source credibility score was "
            f"{source_credibility}/10 and the significance score was "
            f"{significance}/10. "
            f"The topic was selected from the candidates that passed "
            f"the discovery and editorial filters in this cycle."
        )

        sources = [topic.source_url] if topic.source_url else []

        post = Post(
            agent_id=agent_id,
            topic_title=topic.title,
            topic_url=topic.source_url,
            text=text,
            rationale=rationale,
            sources=json.dumps(sources),
            source_name=topic.source_name,
            source_published_at=topic.published_at,
            editorial_score=decision.score,
            score_breakdown=json.dumps(
                decision.score_breakdown
            ),
        )

        self.db.add(post)

        await self.db.commit()
        await self.db.refresh(post)

        return post