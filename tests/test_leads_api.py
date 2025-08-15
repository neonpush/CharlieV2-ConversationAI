from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoints():
    r = client.get("/health/healthz")
    assert r.status_code == 200
    r = client.get("/health/readyz")
    # Ready may be 503 in local without DB; just assert it returns JSON
    assert r.headers.get("content-type", "").startswith("application/json")


def test_create_lead_requires_secret():
    r = client.post("/api/leads/", json={})
    assert r.status_code == 401


def test_store_transcript_requires_secret():
    r = client.post("/api/leads/1/transcript", json={"leadId": "1", "transcript": "hi"})
    assert r.status_code == 401


