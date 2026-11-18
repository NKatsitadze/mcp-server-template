from typing import Any

import pytest
from langchain_core.documents import Document

from example_mcp.docs.hybrid import reciprocal_rank_fusion, tokenize
from example_mcp.docs.search import RESULTS, DocsSearch
from example_mcp.docs.store import open_vector_store
from example_mcp.errors import DocsUnavailableError
from example_mcp.settings import ServerSettings

ERRORS_ID = "knowledge:errors.md:0"
TODOS_ID = "knowledge:todos.md:0"
USERS_ID = "knowledge:users.md:0"
CHUNKS = {
    ERRORS_ID: "[knowledge — errors.md] (Errors)\nunknown id returns 404 with {}",
    TODOS_ID: "[knowledge — todos.md] (Todos)\nfilter with userId and completed",
    USERS_ID: "[knowledge — users.md] (Users)\nthe allowlist hides email and phone",
}


class FakeStore:
    def __init__(self, vector_order: list[str], chunks: dict[str, str] = CHUNKS, fail: bool = False) -> None:
        self.vector_order = vector_order
        self.chunks = chunks
        self.fail = fail
        self.loads = 0

    def get(self, include: list[str]) -> dict[str, Any]:
        self.loads += 1
        ids = list(self.chunks)
        return {
            "ids": ids,
            "documents": [self.chunks[i] for i in ids],
            "metadatas": [{"file": i} for i in ids],
        }

    def similarity_search(self, query: str, k: int) -> list[Document]:
        if self.fail:
            raise ConnectionError("provider down")
        return [Document(id=doc_id, page_content=self.chunks[doc_id]) for doc_id in self.vector_order[:k]]


@pytest.fixture
def docs_settings(settings: ServerSettings, tmp_path) -> ServerSettings:
    return settings.model_copy(update={"docs_index_dir": tmp_path})


def make_search(docs_settings: ServerSettings, store: FakeStore) -> DocsSearch:
    return DocsSearch(docs_settings, store_factory=lambda _settings: store)


def test_tokenize_keeps_names_whole_and_adds_their_parts() -> None:
    assert tokenize("Filter by user_id on /todos-list") == [
        "filter",
        "by",
        "user_id",
        "user",
        "id",
        "on",
        "todos-list",
        "todos",
        "list",
    ]


def test_rrf_rewards_agreement_between_rankings() -> None:
    assert reciprocal_rank_fusion([["a", "b"], ["b", "c"]]) == ["b", "a", "c"]
    assert reciprocal_rank_fusion([]) == []


async def test_keyword_only_hit_is_still_returned(docs_settings) -> None:
    """Vector search misses the chunk with the exact name; BM25 must bring it in."""
    results = await make_search(docs_settings, FakeStore(vector_order=[USERS_ID])).search("userId filter")

    assert TODOS_ID in [doc.id for doc in results]


async def test_chunk_found_by_both_rankers_comes_first(docs_settings) -> None:
    results = await make_search(docs_settings, FakeStore(vector_order=[USERS_ID, ERRORS_ID])).search("404")

    assert results[0].id == ERRORS_ID


async def test_results_are_capped_and_index_loads_once(docs_settings) -> None:
    store = FakeStore(vector_order=list(CHUNKS))
    search = make_search(docs_settings, store)

    await search.search("todos")
    results = await search.search("todos")

    assert len(results) <= RESULTS
    assert store.loads == 1


async def test_missing_index_dir_explains_how_to_ingest(settings, tmp_path) -> None:
    missing = settings.model_copy(update={"docs_index_dir": tmp_path / "nope"})

    with pytest.raises(DocsUnavailableError, match=r"ingest\.ingest_docs"):
        await make_search(missing, FakeStore([])).search("x")


async def test_empty_index_explains_how_to_ingest(docs_settings) -> None:
    with pytest.raises(DocsUnavailableError, match="empty"):
        await make_search(docs_settings, FakeStore([], chunks={})).search("x")


async def test_embedding_failure_becomes_docs_error(docs_settings) -> None:
    with pytest.raises(DocsUnavailableError, match="ConnectionError"):
        await make_search(docs_settings, FakeStore([], fail=True)).search("x")


def test_store_without_provider_key_is_unavailable_not_a_crash(docs_settings) -> None:
    with pytest.raises(DocsUnavailableError, match="API key"):
        open_vector_store(docs_settings)


def test_store_with_unknown_provider_is_unavailable(docs_settings) -> None:
    unknown = docs_settings.model_copy(update={"embedding_model": "nosuchprovider:model"})

    with pytest.raises(DocsUnavailableError, match="nosuchprovider"):
        open_vector_store(unknown)


def test_store_with_key_opens(docs_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    store = open_vector_store(docs_settings)

    assert store._collection.name == "docs"
