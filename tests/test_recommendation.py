"""
Unit tests for statistics-server recommendation engine.
No DB, no HTTP — pure function tests.
"""
import pytest
from app.services.recommendation import compute_recommendations
from app.schemas import FeatureRecommendation


def _make_counts(*features: str) -> dict[str, int]:
    return {f: 1 for f in features}


class TestComputeRecommendations:

    def test_returns_empty_when_no_history(self):
        result = compute_recommendations(
            current_features=[],
            feature_counts={},
            total=0,
        )
        assert result == []

    def test_recommends_missing_common_feature(self):
        # "depozito" kullanılıyor ama mevcut sözleşmede yok
        result = compute_recommendations(
            current_features=["kira_bedeli"],
            feature_counts={"kira_bedeli": 10, "depozito": 9},
            total=10,
            threshold=30.0,
        )
        names = [r.feature_name for r in result]
        assert "depozito" in names
        assert "kira_bedeli" not in names  # zaten mevcut, önerilmez

    def test_does_not_recommend_below_threshold(self):
        result = compute_recommendations(
            current_features=[],
            feature_counts={"nadir_alan": 1},
            total=100,
            threshold=30.0,
        )
        assert result == []  # %1 kullanım, eşiğin altında

    def test_results_sorted_by_usage_descending(self):
        result = compute_recommendations(
            current_features=[],
            feature_counts={"a": 5, "b": 9, "c": 7},
            total=10,
            threshold=30.0,
        )
        pcts = [r.usage_percentage for r in result]
        assert pcts == sorted(pcts, reverse=True)

    def test_top_n_limits_results(self):
        counts = {f"feature_{i}": 10 for i in range(20)}
        result = compute_recommendations(
            current_features=[],
            feature_counts=counts,
            total=10,
            threshold=30.0,
            top_n=3,
        )
        assert len(result) <= 3

    def test_reason_field_contains_percentage(self):
        result = compute_recommendations(
            current_features=[],
            feature_counts={"sozlesme_suresi": 8},
            total=10,
            threshold=30.0,
        )
        assert len(result) == 1
        assert "80.0%" in result[0].reason
        assert "10" in result[0].reason

    def test_all_features_present_returns_empty(self):
        result = compute_recommendations(
            current_features=["a", "b", "c"],
            feature_counts={"a": 10, "b": 10, "c": 10},
            total=10,
            threshold=30.0,
        )
        assert result == []

    def test_usage_percentage_calculation(self):
        result = compute_recommendations(
            current_features=[],
            feature_counts={"alan": 3},
            total=10,
            threshold=30.0,
        )
        assert len(result) == 1
        assert result[0].usage_percentage == pytest.approx(30.0, abs=0.1)
        assert result[0].count == 3
        assert result[0].total == 10
