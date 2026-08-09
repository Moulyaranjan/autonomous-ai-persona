from sqlalchemy.ext.asyncio import AsyncSession

from app.services.editorial_engine import EditorialEngine
from app.services.memory import MemoryService
from app.services.topic_adapter import adapt_topic
from services.topic_discovery.aggregator import fetch_all_topics


class AgentEngine:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.editorial_engine = EditorialEngine()
        self.memory = MemoryService(db)

    async def discover_and_select(
        self,
        agent_id: str,
        persona_domain: str,
    ):
        raw_topics = await fetch_all_topics()

        topics = [
            adapt_topic(topic)
            for topic in raw_topics
            if topic.get("selected", True)
        ]

        decisions = []

        for topic in topics:

            # -----------------------------------------------------------
            # Memory check
            # -----------------------------------------------------------

            already_seen = await self.memory.has_seen_topic(
                agent_id=agent_id,
                title=topic.title,
                url=topic.source_url,
            )

            if already_seen:
                continue

            # -----------------------------------------------------------
            # Editorial judgment
            # -----------------------------------------------------------

            decision = self.editorial_engine.evaluate(
                topic=topic,
                persona_domain=persona_domain,
            )

            decisions.append(decision)

        # ---------------------------------------------------------------
        # Highest scoring acceptable topic first
        # ---------------------------------------------------------------

        accepted = [
            decision
            for decision in decisions
            if decision.decision == "ACCEPT"
        ]

        accepted.sort(
            key=lambda decision: decision.score,
            reverse=True,
        )

        return accepted