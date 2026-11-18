import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter

from example_mcp.log import redact
from ingest.secret_gate import SkippedFile, find_secrets
from ingest.sources import LocalSource

CHUNK_SIZE = 700
CHUNK_OVERLAP = 70

_MARKDOWN_SPLITTER = MarkdownTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
_TEXT_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_SECTION = re.compile(r"^#{2,6}\s+(.+)$", re.MULTILINE)


def chunks(path: Path, text: str) -> list[str]:
    splitter = _MARKDOWN_SPLITTER if path.suffix == ".md" else _TEXT_SPLITTER
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


def file_context(text: str) -> str:
    """One line added to every chunk of a file: its title. Put the facts people ask about here
    (the endpoint, the error codes it returns...), so a chunk that lost them to splitting still
    carries them; this beats separate summary documents, which take result slots away from answers."""
    match = _TITLE.search(text)
    return match.group(1).strip() if match else "untitled"


def chunk_context(text: str, chunk: str, title: str) -> str:
    """The file title plus the section the chunk starts in ("Users resource > Fields").

    Measured on the example docs: a fields table chunk ranked 8-10 for "which fields does a user
    have" with the title alone, because tables embed poorly and every page mentions "fields"; naming
    the section in the header is what makes it findable."""
    start = text.find(chunk[:80])
    sections = [match.group(1).strip() for match in _SECTION.finditer(text) if match.start() <= max(start, 0)]
    return f"{title} > {sections[-1]}" if start >= 0 and sections else title


def make_document(doc_id: str, citation: str, context: str, body: str, metadata: dict[str, str]) -> Document:
    """The citation header is part of the embedded text, so names match in vector and keyword search
    and the tool can cite it without reading metadata. Ids are stable across re-ingests."""
    return Document(id=doc_id, page_content=f"[{citation}] ({context})\n{body}", metadata=metadata)


def source_documents(source: LocalSource) -> tuple[list[Document], list[SkippedFile]]:
    """Chunk every file of a source. Text is redacted first; a file that still looks like it holds a
    secret (in the file or in any chunk) is skipped whole, reporting only its path and pattern names."""
    documents: list[Document] = []
    skipped: list[SkippedFile] = []
    for path in source.files():
        relative = path.relative_to(source.root).as_posix()
        text = redact(path.read_text(encoding="utf-8", errors="replace")).strip()
        if not text:
            continue
        title = file_context(text)
        file_documents = [
            make_document(
                f"{source.name}:{relative}:{index}",
                f"{source.name} — {relative}",
                chunk_context(text, chunk, title),
                chunk,
                {"source": source.name, "file": relative},
            )
            for index, chunk in enumerate(chunks(path, text))
        ]
        findings = sorted(
            set(find_secrets(text)).union(*(find_secrets(doc.page_content) for doc in file_documents))
        )
        if findings:
            skipped.append(SkippedFile(f"{source.name}/{relative}", tuple(findings)))
            continue
        documents.extend(file_documents)
    return documents, skipped
