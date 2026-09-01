"""Pure search indexing and fuzzy scoring helpers."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata


_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SearchDocument:
    key: str
    name: str
    category: str
    panel_labels: tuple[str, ...] = ()
    source_names: tuple[str, ...] = ()
    group_name: str = ""

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.name,
                self.category,
                *self.panel_labels,
                *self.source_names,
                self.group_name,
            )
        )


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return _SEPARATOR_RE.sub(" ", ascii_text.casefold()).strip()


def score_document(query: str, document: SearchDocument) -> float:
    """Return a deterministic fuzzy score in the 0..1 range."""

    query_norm = normalize_text(query)
    if not query_norm:
        return 1.0

    name = normalize_text(document.name)
    category = normalize_text(document.category)
    haystack = normalize_text(document.searchable_text)

    if query_norm == name or query_norm == category:
        return 1.0
    if name.startswith(query_norm) or category.startswith(query_norm):
        return 0.96
    if query_norm in name or query_norm in category:
        return 0.92
    if query_norm in haystack:
        return 0.86

    query_tokens = query_norm.split()
    haystack_tokens = haystack.split()
    token_score = _token_similarity(query_tokens, haystack_tokens)
    sequence_score = SequenceMatcher(None, query_norm, name or category).ratio()
    subsequence_score = (
        0.74
        if _is_subsequence(query_norm.replace(" ", ""), haystack.replace(" ", ""))
        else 0.0
    )

    return min(1.0, max(token_score, sequence_score * 0.82, subsequence_score))


def rank_documents(
    query: str,
    documents: list[SearchDocument],
    *,
    limit: int | None = None,
    minimum_score: float = 0.36,
) -> list[SearchDocument]:
    ranked = [
        (score_document(query, document), normalize_text(document.name), document)
        for document in documents
    ]
    ranked = [item for item in ranked if item[0] >= minimum_score]
    ranked.sort(key=lambda item: (-item[0], item[1], item[2].key))

    results = [item[2] for item in ranked]
    return results if limit is None else results[:limit]


def _token_similarity(query_tokens: list[str], haystack_tokens: list[str]) -> float:
    if not query_tokens or not haystack_tokens:
        return 0.0

    scores = []
    for query_token in query_tokens:
        best = max(
            SequenceMatcher(None, query_token, haystack_token).ratio()
            for haystack_token in haystack_tokens
        )
        scores.append(best)

    return (sum(scores) / len(scores)) * 0.9


def _is_subsequence(needle: str, haystack: str) -> bool:
    iterator = iter(haystack)
    return all(char in iterator for char in needle)
