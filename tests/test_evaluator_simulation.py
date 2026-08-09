import asyncio
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.database import Base, engine, run_migrations
from app.services.scheduler import run_agent_cycle, stop_agent


@pytest.mark.asyncio
async def test_hackathon_evaluator_simulation():
    """
    Locally simulates the Hackathon Evaluator workflow:

    1. Initialize agent via POST /api/agent/init
    2. Receive agentId
    3. Run cycle 1 explicitly
    4. GET /api/agent/feed?agentId=... and assert API contract compliance
    5. Run cycle 2 explicitly
    6. GET /api/agent/feed?agentId=... again
    7. Verify previous posts remain available
    8. Verify post IDs remain unique
    """

    print(
        "\n[EVALUATOR SIMULATION] Step 1: Initializing DB schema...",
        flush=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:

        # ------------------------------------------------------------
        # Step 2: Initialize agent
        #
        # IMPORTANT:
        # Mock start_agent so the real autonomous scheduler does not
        # start in the background. This test manually controls cycles.
        # ------------------------------------------------------------

        print(
            "[EVALUATOR SIMULATION] Step 2: Calling POST /api/agent/init...",
            flush=True,
        )

        with patch("app.api.v1.routes.agent.start_agent"):

            init_res = await client.post(
                "/api/agent/init",
                json={
                    "persona": {
                        "name": "Ada",
                        "domain": "AI Security",
                    }
                },
            )

        assert init_res.status_code == 200, (
            f"Init failed: {init_res.text}"
        )

        data = init_res.json()

        assert "agentId" in data, (
            "agentId missing from response"
        )

        agent_id = data["agentId"]

        assert len(agent_id) > 0

        print(
            f"[EVALUATOR SIMULATION] Received agentId: {agent_id}",
            flush=True,
        )

        # ------------------------------------------------------------
        # Step 3: Run Cycle 1 explicitly
        # ------------------------------------------------------------

        print(
            "[EVALUATOR SIMULATION] Step 3: Executing Cycle 1...",
            flush=True,
        )

        await run_agent_cycle(
            agent_id=agent_id,
            persona_name="Ada",
            persona_domain="AI Security",
        )

        # ------------------------------------------------------------
        # Step 4: Retrieve feed after Cycle 1
        # ------------------------------------------------------------

        print(
            "[EVALUATOR SIMULATION] Step 4: Calling GET /api/agent/feed...",
            flush=True,
        )

        feed_res1 = await client.get(
            f"/api/agent/feed?agentId={agent_id}"
        )

        assert feed_res1.status_code == 200, (
            f"Feed failed: {feed_res1.text}"
        )

        feed1 = feed_res1.json()

        assert "posts" in feed1, (
            "'posts' key missing from feed response"
        )

        posts1 = feed1["posts"]

        assert isinstance(posts1, list)

        print(
            f"[EVALUATOR SIMULATION] Feed returned "
            f"{len(posts1)} post(s) after Cycle 1.",
            flush=True,
        )

        # ------------------------------------------------------------
        # Validate first post if one was generated
        # ------------------------------------------------------------

        if len(posts1) > 0:

            post = posts1[0]

            assert "id" in post and len(post["id"]) > 0, (
                "Post ID missing"
            )

            assert "createdAt" in post and len(post["createdAt"]) > 0, (
                "createdAt missing"
            )

            assert "text" in post and len(post["text"]) > 0, (
                "text missing"
            )

            assert "rationale" in post and len(post["rationale"]) > 0, (
                "rationale missing"
            )

            assert "sources" in post and isinstance(
                post["sources"],
                list,
            ), "sources missing or not a list"

            assert len(post["sources"]) > 0, (
                "sources list is empty"
            )

            print(
                f"   - Post ID: {post['id']}"
            )

            print(
                f"   - Timestamp: {post['createdAt']}"
            )

            print(
                f"   - Rationale: "
                f"{post['rationale'][:80]}..."
            )

            print(
                f"   - Sources: {post['sources']}"
            )

        # ------------------------------------------------------------
        # Step 5: Run Cycle 2 explicitly
        # ------------------------------------------------------------

        print(
            "[EVALUATOR SIMULATION] Step 5: Executing Cycle 2...",
            flush=True,
        )

        await run_agent_cycle(
            agent_id=agent_id,
            persona_name="Ada",
            persona_domain="AI Security",
        )

        # ------------------------------------------------------------
        # Step 6: Retrieve feed again
        # ------------------------------------------------------------

        print(
            "[EVALUATOR SIMULATION] Step 6: "
            "Calling GET /api/agent/feed again...",
            flush=True,
        )

        feed_res2 = await client.get(
            f"/api/agent/feed?agentId={agent_id}"
        )

        assert feed_res2.status_code == 200, (
            f"Second feed request failed: {feed_res2.text}"
        )

        feed2 = feed_res2.json()

        assert "posts" in feed2

        posts2 = feed2["posts"]

        assert isinstance(posts2, list)

        print(
            f"[EVALUATOR SIMULATION] Feed returned "
            f"{len(posts2)} post(s) after Cycle 2.",
            flush=True,
        )

        # ------------------------------------------------------------
        # Ensure previous posts remain available
        # ------------------------------------------------------------

        if len(posts1) > 0:

            post1_ids = {
                post["id"]
                for post in posts1
            }

            post2_ids = {
                post["id"]
                for post in posts2
            }

            assert post1_ids.issubset(post2_ids), (
                "Previous posts disappeared from feed!"
            )

        # ------------------------------------------------------------
        # Ensure every post has a unique ID
        # ------------------------------------------------------------

        all_ids = [
            post["id"]
            for post in posts2
        ]

        assert len(all_ids) == len(set(all_ids)), (
            "Duplicate post IDs found in feed!"
        )

        # ------------------------------------------------------------
        # Cleanup
        # ------------------------------------------------------------

        stop_agent(agent_id)

    print(
        "\n[EVALUATOR SIMULATION] SUCCESS: "
        "All evaluator checks passed!\n",
        flush=True,
    )

