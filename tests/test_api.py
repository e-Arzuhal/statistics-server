import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_statistics.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_analyze_first_contract():
    resp = client.post("/contracts/analyze", json={
        "contract_type": "kira_sozlesmesi",
        "features": ["kira_bedeli", "depozito"],
        "fields": {"kira_bedeli": "15000", "adres": "Kadıköy"},
        "completeness_score": 75.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_type"] == "kira_sozlesmesi"
    assert "record_id" in data
    # First contract: no recommendations (only 1 record, nothing missing from others)
    assert isinstance(data["recommendations"], list)


def test_analyze_builds_recommendations():
    # Insert 10 contracts with 'sozlesme_suresi' to push it above 30% threshold
    for _ in range(10):
        client.post("/contracts/analyze", json={
            "contract_type": "kira_sozlesmesi",
            "features": ["kira_bedeli", "sozlesme_suresi", "depozito"],
            "fields": {},
            "completeness_score": 90.0,
        })

    # Now analyze a contract WITHOUT 'sozlesme_suresi' → should get recommendation
    resp = client.post("/contracts/analyze", json={
        "contract_type": "kira_sozlesmesi",
        "features": ["kira_bedeli"],
        "fields": {},
        "completeness_score": 50.0,
    })
    assert resp.status_code == 200
    data = resp.json()
    feature_names = [r["feature_name"] for r in data["recommendations"]]
    assert "sozlesme_suresi" in feature_names


def test_stats_endpoint():
    client.post("/contracts/analyze", json={
        "contract_type": "hizmet_sozlesmesi",
        "features": ["hizmet_bedeli", "sure"],
        "fields": {},
        "completeness_score": 80.0,
    })
    resp = client.get("/stats/hizmet_sozlesmesi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_type"] == "hizmet_sozlesmesi"
    assert data["total_contracts"] == 1
    feature_names = [f["feature_name"] for f in data["feature_stats"]]
    assert "hizmet_bedeli" in feature_names


def test_stats_empty_type():
    resp = client.get("/stats/nonexistent_type")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contracts"] == 0
    assert data["feature_stats"] == []


def test_recommendations_exclude_present_features():
    # Insert contracts with feature_x at high usage
    for _ in range(5):
        client.post("/contracts/analyze", json={
            "contract_type": "test_type",
            "features": ["feature_x", "feature_y"],
            "fields": {},
        })

    # Analyze contract that already has feature_x → should NOT recommend feature_x
    resp = client.post("/contracts/analyze", json={
        "contract_type": "test_type",
        "features": ["feature_x"],
        "fields": {},
    })
    assert resp.status_code == 200
    data = resp.json()
    feature_names = [r["feature_name"] for r in data["recommendations"]]
    assert "feature_x" not in feature_names
