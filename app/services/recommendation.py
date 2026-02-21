from ..schemas import FeatureRecommendation
from ..config import get_settings

settings = get_settings()


def compute_recommendations(
    current_features: list[str],
    feature_counts: dict[str, int],
    total: int,
    threshold: float | None = None,
    top_n: int | None = None,
) -> list[FeatureRecommendation]:
    """
    Recommend features that:
    - Are used in >= threshold% of contracts of the same type
    - Are NOT already present in the current contract
    """
    if total == 0:
        return []

    threshold = threshold if threshold is not None else settings.recommendation_threshold
    top_n = top_n if top_n is not None else settings.recommendation_top_n

    current_set = set(current_features)
    candidates = []

    for feature_name, count in feature_counts.items():
        if feature_name in current_set:
            continue  # already present, skip

        usage_pct = (count / total) * 100
        if usage_pct >= threshold:
            candidates.append(
                FeatureRecommendation(
                    feature_name=feature_name,
                    usage_percentage=round(usage_pct, 1),
                    count=count,
                    total=total,
                    message=f"Bu alan benzer sözleşmelerin %{round(usage_pct, 1)}'inde yer alıyor. Eklemeyi düşünebilirsiniz.",
                )
            )

    # Sort by usage_percentage descending, take top N
    candidates.sort(key=lambda r: r.usage_percentage, reverse=True)
    return candidates[:top_n]
