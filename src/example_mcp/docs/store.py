from typing import Any

from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma

from example_mcp.errors import DocsUnavailableError
from example_mcp.settings import ServerSettings

COLLECTION_NAME = "docs"
INGEST_COMMAND = "uv run python -m ingest.ingest_docs"


def open_vector_store(settings: ServerSettings) -> Chroma:
    """The single place that defines the index: ingest writes and the server reads through it, so
    both always use the same collection, directory and embedding model.

    Every way the embedding provider can fail to start (missing key, provider package not installed,
    unknown provider) becomes a DocsUnavailableError that says what to fix, never a crash.
    """
    provider = settings.embedding_model.partition(":")[0]
    try:
        embeddings: Any = init_embeddings(settings.embedding_model)
    except ImportError as error:
        raise DocsUnavailableError(
            f"search_docs is disabled: the '{provider}' embeddings package is not installed "
            f"(uv add langchain-{provider})."
        ) from error
    except Exception as error:
        raise DocsUnavailableError(
            f"search_docs is disabled: could not start the '{provider}' embeddings "
            f"({type(error).__name__}). Check EMBEDDING_MODEL and the provider's API key in .env."
        ) from error
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(settings.docs_index_dir),
    )
