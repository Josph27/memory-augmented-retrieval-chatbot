from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | {".pdf"}


class DocumentLoaderError(RuntimeError):
    """Raised when a local document file cannot be loaded."""


@dataclass(frozen=True)
class LoadedDocument:
    """Plain text loaded from a local file with source metadata."""

    title: str
    text: str
    source: str
    metadata: dict


class TextDocumentIndexer(Protocol):
    """Protocol for document backends that can index loaded text."""

    def index_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ):
        """Index one plain-text document."""
        ...


def load_document_file(path: str | Path, encoding: str = "utf-8") -> LoadedDocument:
    """Load a supported local file into text for document-memory indexing."""
    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise DocumentLoaderError(f"Document file does not exist: {file_path}")
    if not file_path.is_file():
        raise DocumentLoaderError(f"Document path is not a file: {file_path}")

    extension = file_path.suffix.lower()
    if extension in SUPPORTED_TEXT_EXTENSIONS:
        return load_text_file(file_path, encoding=encoding)
    if extension == ".pdf":
        return load_pdf_file(file_path)

    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise DocumentLoaderError(
        f"Unsupported document extension {extension!r}. Supported extensions: {supported}"
    )


def load_text_file(path: Path, encoding: str = "utf-8") -> LoadedDocument:
    """Load a UTF-8 text or markdown file."""
    try:
        text = path.read_text(encoding=encoding)
    except UnicodeDecodeError as error:
        msg = f"Could not decode {path} with encoding {encoding!r}."
        raise DocumentLoaderError(msg) from error
    return LoadedDocument(
        title=path.stem,
        text=text,
        source="file",
        metadata=base_file_metadata(path, loader_name="path_read_text"),
    )


def load_pdf_file(path: Path) -> LoadedDocument:
    """Load PDF text with a mature PDF library when one is installed."""
    try:
        text, page_count, loader_name = load_pdf_with_pypdf(path)
    except DocumentLoaderError:
        try:
            text, page_count, loader_name = load_pdf_with_pymupdf(path)
        except DocumentLoaderError as error:
            msg = (
                "PDF loading requires pypdf or PyMuPDF. Install one of them to index PDF files."
            )
            raise DocumentLoaderError(msg) from error

    metadata = base_file_metadata(path, loader_name=loader_name)
    metadata["page_count"] = page_count
    return LoadedDocument(
        title=path.stem,
        text=text,
        source="file",
        metadata=metadata,
    )


def load_pdf_with_pypdf(path: Path) -> tuple[str, int, str]:
    """Load PDF text through pypdf if available."""
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception as error:
        raise DocumentLoaderError("pypdf is unavailable.") from error

    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(text for text in page_texts if text), len(reader.pages), "pypdf"


def load_pdf_with_pymupdf(path: Path) -> tuple[str, int, str]:
    """Load PDF text through PyMuPDF if available."""
    try:
        import fitz  # type: ignore[import-not-found]
    except Exception as error:
        raise DocumentLoaderError("PyMuPDF is unavailable.") from error

    with fitz.open(path) as document:
        page_texts = [page.get_text().strip() for page in document]
        page_count = document.page_count
    return "\n\n".join(text for text in page_texts if text), page_count, "pymupdf"


def base_file_metadata(path: Path, loader_name: str) -> dict:
    """Return common file metadata for loaded documents."""
    return {
        "file_path": str(path),
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "loader_name": loader_name,
        "source": "file",
    }


def index_loaded_document(loaded: LoadedDocument, indexer: TextDocumentIndexer):
    """Index one loaded document through the configured document backend."""
    return indexer.index_text_document(
        title=loaded.title,
        text=loaded.text,
        source=loaded.source,
        metadata=loaded.metadata,
    )


def index_file_document(path: str | Path, indexer: TextDocumentIndexer):
    """Load and index one local document file."""
    return index_loaded_document(load_document_file(path), indexer)
