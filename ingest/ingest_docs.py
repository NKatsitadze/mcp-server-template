"""Build the search_docs index: uv run python -m ingest.ingest_docs

Every source in ingest/sources.py is chunked, redacted and passed through the secret gate (a flagged
file is skipped whole), and the Chroma collection is replaced only after every embedding succeeded.
Re-run it whenever the sources change, then restart the server.
"""

import sys
from typing import Any

from langchain_core.documents import Document

from example_mcp.docs.store import open_vector_store
from example_mcp.errors import DocsUnavailableError
from example_mcp.settings import ServerSettings, load_env_file
from ingest.documents import source_documents
from ingest.secret_gate import SkippedFile
from ingest.sources import SOURCES, LocalSource

BATCH_SIZE = 100


def store_documents(documents: list[Document], store: Any) -> int:
    """Embed everything first, then replace the collection.

    Resetting before embedding would leave a half-empty index if the embeddings API failed mid-run;
    this way any failure before the reset keeps the previous index. Re-running never duplicates
    vectors and drops chunks of deleted files.
    """
    vectors: list[list[float]] = []
    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start : start + BATCH_SIZE]
        vectors.extend(store.embeddings.embed_documents([document.page_content for document in batch]))
        print(f"   embedded batch {start // BATCH_SIZE + 1}/{(len(documents) - 1) // BATCH_SIZE + 1}")
    store.reset_collection()
    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start : start + BATCH_SIZE]
        store._collection.add(
            ids=[document.id for document in batch],
            embeddings=vectors[start : start + BATCH_SIZE],
            documents=[document.page_content for document in batch],
            metadatas=[document.metadata for document in batch],
        )
    return len(store.get(include=[])["ids"])


def report_skipped(skipped: list[SkippedFile]) -> None:
    """Path and pattern names only: the matched value is never printed."""
    print(f"{'✅' if not skipped else '⚠️'} secret gate: {len(skipped)} file(s) skipped")
    for item in skipped:
        print(f"   ⛔ {item.path}: {', '.join(item.patterns)}")


def collect(sources: tuple[LocalSource, ...]) -> list[Document]:
    """All documents of all sources. A missing source folder stops the run before the index is touched."""
    missing = [source.name for source in sources if not source.root.is_dir()]
    if missing:
        raise FileNotFoundError(f"source folder(s) missing: {', '.join(missing)}")
    documents: list[Document] = []
    skipped: list[SkippedFile] = []
    for source in sources:
        source_docs, source_skipped = source_documents(source)
        print(f"🧩 {source.name}: {len(source_docs)} chunks")
        documents += source_docs
        skipped += source_skipped
    report_skipped(skipped)
    return documents


def main() -> None:
    load_env_file()
    settings = ServerSettings()
    try:
        documents = collect(SOURCES)
        if not documents:
            raise FileNotFoundError("no documents found in any source")
        store = open_vector_store(settings)
        stored = store_documents(documents, store)
    except (FileNotFoundError, DocsUnavailableError) as error:
        print(f"❌ {error}; the index was not changed")
        sys.exit(1)
    mark = "✅" if stored == len(documents) else "❌"
    print(f"{mark} index holds {stored} chunks ({settings.docs_index_dir})")
    if stored != len(documents):
        sys.exit(1)


if __name__ == "__main__":
    main()
