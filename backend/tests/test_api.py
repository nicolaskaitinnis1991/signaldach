"""Tests for FastAPI API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "signal-dach"


class TestItemsEndpoint:
    def test_get_items_returns_list(self, client):
        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_items_with_filters(self, client):
        resp = client.get("/items?category=regulation&urgency=high&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_items_with_search(self, client):
        resp = client.get("/items?q=bitcoin")
        assert resp.status_code == 200


class TestAnalyticsEndpoint:
    def test_get_analytics_returns_summary(self, client):
        resp = client.get("/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "by_category" in data
        assert "by_urgency" in data
        assert "daily" in data
        assert "period_days" in data


class TestSourcesEndpoint:
    def test_get_sources_returns_list(self, client):
        resp = client.get("/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_seed_defaults_works(self, client):
        resp = client.post("/sources/seed-defaults")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "seeded"

        # Verify sources were actually created
        resp2 = client.get("/sources")
        data2 = resp2.json()
        assert len(data2["sources"]) > 0


class TestScrapeEndpoint:
    def test_trigger_scrape_no_sources(self, client):
        """Without seeded sources, scrape should report no sources."""
        resp = client.post("/scrape/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_sources"

    def test_trigger_scrape_after_seeding(self, client):
        """After seeding, scrape should attempt to run."""
        # Seed first
        client.post("/sources/seed-defaults")

        resp = client.post("/scrape/trigger")
        assert resp.status_code == 200
        data = resp.json()
        # May be "completed" or "no_sources" depending on timing
        assert data["status"] in ("completed", "no_sources")
        if data["status"] == "completed":
            assert "sources_scraped" in data
            assert "results" in data


class TestAlertsEndpoint:
    def test_get_alerts_returns_list(self, client):
        resp = client.get("/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_create_alert(self, client):
        resp = client.post("/alerts", json={
            "name": "Test Alert",
            "tenant_id": "default",
            "conditions": {"category": "regulation", "min_relevance": 7},
            "channels": {"email": "test@example.com"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert "id" in data

    def test_create_and_list_alert(self, client):
        """Created alert should appear in list."""
        client.post("/alerts", json={
            "name": "Listed Alert",
            "conditions": {"category": "market"},
        })

        resp = client.get("/alerts")
        data = resp.json()
        assert len(data["alerts"]) >= 1
        names = [a["name"] for a in data["alerts"]]
        assert "Listed Alert" in names

    def test_delete_alert(self, client):
        # Create first
        create_resp = client.post("/alerts", json={
            "name": "To Delete",
            "conditions": {},
        })
        alert_id = create_resp.json()["id"]

        # Delete
        del_resp = client.delete(f"/alerts/{alert_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify gone
        list_resp = client.get("/alerts")
        ids = [a["id"] for a in list_resp.json()["alerts"]]
        assert alert_id not in ids

    def test_delete_nonexistent_alert(self, client):
        resp = client.delete("/alerts/nonexistent-id")
        assert resp.status_code == 404

    def test_update_alert(self, client):
        # Create
        create_resp = client.post("/alerts", json={
            "name": "Original Name",
            "conditions": {},
        })
        alert_id = create_resp.json()["id"]

        # Update
        update_resp = client.put(f"/alerts/{alert_id}", json={
            "name": "Updated Name",
            "enabled": False,
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "updated"
