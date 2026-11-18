import asyncio
import threading
from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from example_mcp.docs.hybrid import reciprocal_rank_fusion, tokenize
from example_mcp.docs.store import INGEST_COMMAND, open_vector_store
from example_mcp.errors import DocsUnavailableError
from example_mcp.log import get_logger
from example_mcp.settings import ServerSettings

VECTOR_CANDIDATES = 10
KEYWORD_CANDIDATES = 10
# How many excerpts the model gets. Re-measure on YOUR corpus before changing it: for a set of real
# questions, find the rank of the first chunk that holds the answer, and keep a slot or two of slack.
# Too few drops answers; too many buries them and costs tokens on every call.
RESULTS = 4

logger = get_logger("docs")


class DocsSearch:
    """Hybrid search: vector (meaning) + BM25 (exact names such as `userId` or `/todos`), merged with
    reciprocal rank fusion. Loads lazily on first use, so the server starts even without an index."""

    def __init__(
        self,
        settings: ServerSettings,
        store_factory: Callable[[ServerSettings], Any] = open_vector_store,
    ) -> None:
        self._settings = settings
        self._store_factory = store_factory
        self._load_lock = threading.Lock()
        self._store: Any = None
        self._documents: dict[str, Document] = {}
        self._ids: list[str] = []
        self._bm25: BM25Okapi | None = None

    async def search(self, query: str) -> list[Document]:
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: str) -> list[Document]:
        self._ensure_loaded()
        assert self._bm25 is not None
        try:
            vector_ids = [
                doc.id for doc in self._store.similarity_search(query, k=VECTOR_CANDIDATES) if doc.id
            ]
        except Exception as error:
            raise DocsUnavailableError(f"Embedding the query failed ({type(error).__name__}).") from error
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(self._ids)), key=lambda index: scores[index], reverse=True)
        keyword_ids = [self._ids[index] for index in ranked[:KEYWORD_CANDIDATES] if scores[index] > 0]
        fused = reciprocal_rank_fusion([vector_ids, keyword_ids])
        return [self._documents[doc_id] for doc_id in fused if doc_id in self._documents][:RESULTS]

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            if self._bm25 is not None:
                return
            if not self._settings.docs_index_dir.exists():
                raise DocsUnavailableError(f"The docs index does not exist yet. Run: {INGEST_COMMAND}")
            store = self._store_factory(self._settings)
            data = store.get(include=["documents", "metadatas"])
            if not data["ids"]:
                raise DocsUnavailableError(f"The docs index is empty. Run: {INGEST_COMMAND}")
            self._documents = {
                doc_id: Document(id=doc_id, page_content=text, metadata=metadata or {})
                for doc_id, text, metadata in zip(
                    data["ids"], data["documents"], data["metadatas"], strict=True
                )
            }
            self._ids = list(self._documents)
            self._bm25 = BM25Okapi([tokenize(self._documents[doc_id].page_content) for doc_id in self._ids])
            self._store = store
            logger.info("Loaded %d doc chunks for search_docs", len(self._ids))
