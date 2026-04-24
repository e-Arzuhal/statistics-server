"""
Integration tests for statistics-server HTTP endpoints.
Uses in-memory SQLite so no external DB is required.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAnalyzeEndpoint:
    def _payload(self, contract_type="kira_sozlesmesi", features=None, score=75.0):
        return {
            "contract_type": contract_type,
            "features": features or ["kira_bedeli", "depozito"],
            "fields": {"kira_bedeli": "15000"},
            "completeness_score": score,
        }

    def test_analyze_returns_200_and_record_id(self, client):
        resp = client.post("/contracts/analyze", json=self._payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["record_id"] >= 1
        assert data["contract_type"] == "kira_sozlesmesi"

    def test_analyze_stats_summary_totals(self, client):
        client.post("/contracts/analyze", json=self._payload())
        resp = client.post("/contracts/analyze", json=self._payload())
        data = resp.json()
        assert data["stats_summary"]["total_contracts"] == 2

    def test_recommendations_after_history(self, client):
        client.post("/contracts/analyze", json=self._payload(
            features=["kira_bedeli", "depozito", "sozlesme_suresi"], score=90.0
        ))
        resp = client.post("/contracts/analyze", json=self._payload(
            features=["kira_bedeli"], score=60.0
        ))
        rec_names = [r["feature_name"] for r in resp.json()["recommendations"]]
        assert any(n in rec_names for n in ["depozito", "sozlesme_suresi"])

    def test_different_types_dont_mix(self, client):
        client.post("/contracts/analyze", json=self._payload(
            contract_type="kira_sozlesmesi", features=["depozito"], score=50.0
        ))
        resp = client.post("/contracts/analyze", json=self._payload(
            contract_type="is_sozlesmesi", features=[], score=0.0
        ))
        rec_names = [r["feature_name"] for r in resp.json()["recommendations"]]
        assert "depozito" not in rec_names


class TestStatsEndpoint:
    def test_stats_empty(self, client):
        resp = client.get("/stats/kira_sozlesmesi")
        assert resp.status_code == 200
        assert resp.json()["total_contracts"] == 0

    def test_stats_usage_percentage(self, client):
        for _ in range(2):
            client.post("/contracts/analyze", json={
                "contract_type": "is_sozlesmesi",
                "features": ["ucret"],
                "fields": {},
                "completeness_score": None,
            })
        client.post("/contracts/analyze", json={
            "contract_type": "is_sozlesmesi",
            "features": ["ucret", "deneme_suresi"],
            "fields": {},
            "completeness_score": None,
        })
        resp = client.get("/stats/is_sozlesmesi")
        data = resp.json()
        ucret = next(f for f in data["feature_stats"] if f["feature_name"] == "ucret")
        assert ucret["usage_percentage"] == pytest.approx(100.0)
        deneme = next(f for f in data["feature_stats"] if f["feature_name"] == "deneme_suresi")
        assert deneme["usage_percentage"] == pytest.approx(33.3, abs=0.5)
