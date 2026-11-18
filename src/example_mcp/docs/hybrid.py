import re
from collections.abc import Sequence

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Keyword tokens for BM25. Keeps names like `get-group` and `invalid-params` whole (exact-match
    queries), and also adds their parts so `group` alone still matches."""
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(text.casefold()):
        tokens.append(token)
        parts = re.split(r"[-_]", token)
        if len(parts) > 1:
            tokens.extend(parts)
    return tokens


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[str]:
    """Merge ranked id lists: each list contributes 1 / (k + rank). Rank-based, so vector distances
    and BM25 scores never need to be on the same scale."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)
