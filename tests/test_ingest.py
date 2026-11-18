from pathlib import Path
from typing import Any

import pytest
from langchain_core.documents import Document

from ingest.documents import file_context, source_documents
from ingest.ingest_docs import collect, store_documents
from ingest.secret_gate import find_secrets
from ingest.sources import SOURCES, LocalSource

KNOWLEDGE = SOURCES[0]


def fake_secret() -> str:
    # Assembled at runtime so this file itself never matches the gate.
    return "api_key = '" + "a1" * 12 + "'"


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        (fake_secret(), "key-literal"),
        ("password: 'hunter22'", "password-literal"),
        ("postgres://user:" + "pw@db:5432/x", "credentialed-uri"),
        ("Authorization: Bearer " + "x" * 30, "bearer-token"),
        ("sk-" + "A" * 30, "provider-key"),
        ("-----BEGIN RSA " + "PRIVATE KEY-----", "private-key"),
    ],
)
def test_gate_catches_credentials(text: str, pattern: str) -> None:
    assert pattern in find_secrets(text)


@pytest.mark.parametrize(
    "text", ["apiKey: 'string'", "Authorization: Bearer <token>", "password: str", "GET /users/1"]
)
def test_gate_lets_ordinary_docs_through(text: str) -> None:
    assert find_secrets(text) == []


def test_every_knowledge_page_passes_the_gate() -> None:
    pages = KNOWLEDGE.files()

    assert len(pages) >= 8
    for page in pages:
        assert find_secrets(page.read_text(encoding="utf-8")) == [], page.name


def test_knowledge_gives_enough_chunks_with_citations() -> None:
    documents, skipped = source_documents(KNOWLEDGE)

    assert skipped == []
    assert len(documents) >= 15
    assert len({document.id for document in documents}) == len(documents)
    for document in documents:
        assert document.page_content.startswith("[knowledge — ")


def test_chunk_ids_are_stable_across_runs() -> None:
    first, _ = source_documents(KNOWLEDGE)
    second, _ = source_documents(KNOWLEDGE)

    assert [document.id for document in first] == [document.id for document in second]


def test_file_with_a_secret_is_skipped_whole(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("# Fine\nnothing to see", encoding="utf-8")
    (tmp_path / "bad.md").write_text(f"# Config\n{fake_secret()}", encoding="utf-8")

    documents, skipped = source_documents(LocalSource("t", tmp_path, ("*.md",)))

    assert {document.metadata["file"] for document in documents} == {"ok.md"}
    assert [(item.path, item.patterns) for item in skipped] == [("t/bad.md", ("key-literal",))]


def test_title_is_carried_in_every_chunk_header(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Todos resource\n\n" + "word " * 600, encoding="utf-8")

    documents, _ = source_documents(LocalSource("t", tmp_path, ("*.md",)))

    assert len(documents) > 1
    assert all(document.page_content.startswith("[t — a.md] (Todos resource)") for document in documents)
    assert file_context("no title here") == "untitled"


def test_chunk_header_names_the_section_it_starts_in(tmp_path: Path) -> None:
    text = "# Users\n\nintro\n\n## Fields\n\n" + "| a | b |\n" * 120 + "\n## Errors\n\n404 for unknown ids"
    (tmp_path / "u.md").write_text(text, encoding="utf-8")

    documents, _ = source_documents(LocalSource("t", tmp_path, ("*.md",)))
    headers = [document.page_content.splitlines()[0] for document in documents]

    assert "[t — u.md] (Users > Fields)" in headers
    assert headers[-1] == "[t — u.md] (Users > Errors)"


def test_missing_source_folder_stops_before_the_index(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing"):
        collect((LocalSource("gone", tmp_path / "nope", ("*.md",)),))


class FakeEmbeddings:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise ConnectionError("provider down")
        return [[0.0] for _ in texts]


class FakeChroma:
    def __init__(self, fail: bool = False) -> None:
        self.embeddings = FakeEmbeddings(fail)
        self.events: list[str] = []
        self.ids: list[str] = ["old"]
        self._collection = self

    def reset_collection(self) -> None:
        self.events.append("reset")
        self.ids = []

    def add(self, ids: list[str], **_: Any) -> None:
        self.events.append("add")
        self.ids += ids

    def get(self, include: list[str]) -> dict[str, Any]:
        return {"ids": self.ids}


DOCS = [Document(id=f"d{index}", page_content="x") for index in range(3)]


def test_store_embeds_everything_before_resetting() -> None:
    store = FakeChroma()

    assert store_documents(DOCS, store) == 3
    assert store.events == ["reset", "add"]


def test_failed_embedding_keeps_the_old_index() -> None:
    store = FakeChroma(fail=True)

    with pytest.raises(ConnectionError):
        store_documents(DOCS, store)
    assert store.ids == ["old"]
    assert store.events == []
