from __future__ import annotations

from ..schemas import FeatureRecommendation
from ..config import get_settings

settings = get_settings()


def _jaccard(a: set, b: set) -> float:
    """Jaccard benzerliği: |A∩B| / |A∪B|. Her iki küme boşsa 1.0 döner."""
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


def compute_recommendations(
    current_features: list[str],
    feature_counts: dict[str, int],
    total: int,
    threshold: float | None = None,
    top_n: int | None = None,
) -> list[FeatureRecommendation]:
    """
    Frequency-based recommendations:
    - Features used in >= threshold% of same-type contracts
    - NOT already present in the current contract
    """
    if total == 0:
        return []

    threshold = threshold if threshold is not None else settings.recommendation_threshold
    top_n = top_n if top_n is not None else settings.recommendation_top_n

    current_set = set(current_features)
    candidates = []

    for feature_name, count in feature_counts.items():
        if feature_name in current_set:
            continue

        usage_pct = (count / total) * 100
        if usage_pct >= threshold:
            candidates.append(
                FeatureRecommendation(
                    feature_name=feature_name,
                    usage_percentage=round(usage_pct, 1),
                    count=count,
                    total=total,
                    message=f"Bu alan benzer sözleşmelerin %{round(usage_pct, 1)}'inde yer alıyor. Eklemeyi düşünebilirsiniz.",
                    reason=f"statistical_frequency:{round(usage_pct, 1)}%_of_{total}_contracts",
                )
            )

    candidates.sort(key=lambda r: r.usage_percentage, reverse=True)
    return candidates[:top_n]


def compute_jaccard_recommendations(
    current_features: list[str],
    all_records: list[list[str]],
    threshold: float | None = None,
    top_n: int | None = None,
) -> list[FeatureRecommendation]:
    """
    Jaccard-weighted collaborative filtering:
    Her geçmiş sözleşme için Jaccard(mevcut, geçmiş) hesaplanır;
    özellik puanları bu benzerlik ağırlığıyla biriktirilir.
    Yüksek benzerlikli sözleşmelerin özelliklerine daha fazla ağırlık verilir.

    Dezavantaj: O(n * m) karmaşıklık, büyük veri setlerinde yavaşlayabilir.
    Pratik sınır: max 1000 kayıt işlenir.
    """
    if not all_records:
        return []

    threshold = threshold if threshold is not None else settings.recommendation_threshold
    top_n = top_n if top_n is not None else settings.recommendation_top_n

    current_set = set(current_features)
    weighted_scores: dict[str, float] = {}
    total_weight: float = 0.0

    # En fazla 1000 kayıt işle
    for record_features in all_records[:1000]:
        record_set = set(record_features)
        sim = _jaccard(current_set, record_set)
        total_weight += sim
        for feature in record_set:
            if feature not in current_set:
                weighted_scores[feature] = weighted_scores.get(feature, 0.0) + sim

    if total_weight == 0:
        return []

    total = len(all_records)
    candidates = []
    for feature_name, score in weighted_scores.items():
        normalized_pct = round((score / total_weight) * 100, 1)
        if normalized_pct >= threshold:
            candidates.append(
                FeatureRecommendation(
                    feature_name=feature_name,
                    usage_percentage=normalized_pct,
                    count=int(score),
                    total=total,
                    message=f"Benzer sözleşmelerde sıkça tercih edilen bu alan, profilinize %{normalized_pct} uyum gösteriyor.",
                    reason=f"jaccard_weighted_frequency:{normalized_pct}%_similarity_weighted",
                )
            )

    candidates.sort(key=lambda r: r.usage_percentage, reverse=True)
    return candidates[:top_n]
