import pytest


@pytest.mark.asyncio
async def test_create_session(client):
    response = await client.post("/sessions", json={"tenant_id": "test-tenant"})
    assert response.status_code == 201
    data = response.json()
    assert data["tenant_id"] == "test-tenant"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_session(client):
    # Create first
    create_resp = await client.post("/sessions", json={})
    session_id = create_resp.json()["id"]

    # Retrieve
    get_resp = await client.get(f"/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    response = await client.get("/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
