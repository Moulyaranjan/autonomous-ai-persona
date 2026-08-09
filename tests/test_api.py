import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.database import Base, engine, run_migrations


@pytest.mark.asyncio
async def test_init_and_feed_api():
    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Initialize Agent
        init_res = await client.post(
            "/api/agent/init",
            json={
                "persona": {
                    "name": "Ada",
                    "domain": "AI Security",
                }
            },
        )

        assert init_res.status_code == 200

        data = init_res.json()

        assert "agentId" in data

        agent_id = data["agentId"]

        assert len(agent_id) > 0

        # 2. Retrieve Feed
        feed_res = await client.get(
            f"/api/agent/feed?agentId={agent_id}"
        )

        assert feed_res.status_code == 200

        feed_data = feed_res.json()

        assert "posts" in feed_data
        assert isinstance(feed_data["posts"], list)

        # 3. Test Invalid Agent ID Feed
        bad_res = await client.get(
            "/api/agent/feed?agentId=invalid-id-xyz"
        )

        assert bad_res.status_code == 404