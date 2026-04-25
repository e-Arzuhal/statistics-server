"""
Unit tests for statistics-server recommendation engine.
No DB, no HTTP — pure function tests.
"""
import pytest
from app.services.recommendation import compute_recommendations, compute_jaccard_recommendations, _jaccard
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


# ---------------------------------------------------------------------------
# _jaccard (yardımcı fonksiyon)
# ---------------------------------------------------------------------------

class TestJaccardHelper:

    def test_both_empty_returns_one(self):
        assert _jaccard(set(), set()) == 1.0

    def test_identical_sets_returns_one(self):
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == pytest.approx(1.0)

    def test_no_overlap_returns_zero(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_partial_overlap(self):
        # |{a,b} ∩ {b,c}| / |{a,b} ∪ {b,c}| = 1/3
        result = _jaccard({"a", "b"}, {"b", "c"})
        assert result == pytest.approx(1 / 3, abs=0.001)

    def test_one_empty_other_nonempty_returns_zero(self):
        assert _jaccard(set(), {"a", "b"}) == pytest.approx(0.0)
        assert _jaccard({"a", "b"}, set()) == pytest.approx(0.0)

    def test_subset_relationship(self):
        # {a} ⊂ {a,b,c} → |{a}| / |{a,b,c}| = 1/3
        result = _jaccard({"a"}, {"a", "b", "c"})
        assert result == pytest.approx(1 / 3, abs=0.001)


# ---------------------------------------------------------------------------
# compute_jaccard_recommendations
# ---------------------------------------------------------------------------

class TestComputeJaccardRecommendations:

    def test_empty_records_returns_empty(self):
        result = compute_jaccard_recommendations(
            current_features=["kira_bedeli"],
            all_records=[],
        )
        assert result == []

    def test_already_present_features_not_recommended(self):
        result = compute_jaccard_recommendations(
            current_features=["kira_bedeli", "depozito"],
            all_records=[["kira_bedeli", "depozito", "sozlesme_suresi"]],
            threshold=0.0,
        )
        names = [r.feature_name for r in result]
        assert "kira_bedeli" not in names
        assert "depozito" not in names
        assert "sozlesme_suresi" in names

    def test_no_overlap_zero_weight_returns_empty(self):
        # Mevcut sözleşme ile geçmiş kayıtlar tamamen farklı → Jaccard=0 → total_weight=0
        result = compute_jaccard_recommendations(
            current_features=["a", "b"],
            all_records=[["c", "d"], ["e", "f"]],
            threshold=0.0,
        )
        assert result == []

    def test_higher_similarity_record_weighted_more(self):
        # İki geçmiş kayıt: biri mevcut ile tam örtüşüyor, diğeri hiç örtüşmüyor
        # "depozito" sadece benzer kayıtta var → önerilmeli
        # "yabanciAlan" sadece benzer olmayan kayıtta var → önerilmemeli (weight=0)
        result = compute_jaccard_recommendations(
            current_features=["kira_bedeli", "sozlesme_suresi"],
            all_records=[
                ["kira_bedeli", "sozlesme_suresi", "depozito"],   # Jaccard=2/3 benzer
                ["x", "y", "yabanciAlan"],                         # Jaccard=0 benzer değil
            ],
            threshold=0.0,
        )
        names = [r.feature_name for r in result]
        assert "depozito" in names
        assert "yabanciAlan" not in names

    def test_results_sorted_by_percentage_descending(self):
        result = compute_jaccard_recommendations(
            current_features=["a"],
            all_records=[
                ["a", "b", "c", "d"],
                ["a", "b"],
                ["a", "b", "c"],
            ],
            threshold=0.0,
        )
        percentages = [r.usage_percentage for r in result]
        assert percentages == sorted(percentages, reverse=True)

    def test_top_n_limits_output(self):
        result = compute_jaccard_recommendations(
            current_features=["a"],
            all_records=[["a", f"feature_{i}"] for i in range(20)],
            threshold=0.0,
            top_n=3,
        )
        assert len(result) <= 3

    def test_1000_record_limit_applied(self):
        # 1500 kayıt → sadece ilk 1000'i işlemeli; hata vermemeli
        records = [["kira_bedeli", f"f_{i}"] for i in range(1500)]
        result = compute_jaccard_recommendations(
            current_features=["kira_bedeli"],
            all_records=records,
            threshold=0.0,
            top_n=5,
        )
        assert isinstance(result, list)

    def test_reason_field_identifies_jaccard_source(self):
        result = compute_jaccard_recommendations(
            current_features=["kira_bedeli"],
            all_records=[["kira_bedeli", "depozito"]],
            threshold=0.0,
        )
        assert len(result) >= 1
        assert "jaccard" in result[0].reason

    def test_threshold_filters_low_similarity_features(self):
        # threshold=80 → düşük ağırlıklı özellikler elenecek
        result = compute_jaccard_recommendations(
            current_features=["a"],
            all_records=[
                ["a", "b"],   # Jaccard=0.5
                ["c", "d"],   # Jaccard=0.0
            ],
            threshold=80.0,
        )
        # "b" düşük ağırlıkla önerilmeyecek kadar küçük
        assert result == []
