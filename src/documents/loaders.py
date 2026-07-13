from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


MAX_PDF_PAGES = 512
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


def load_document_file(
    path: str | Path,
    encoding: str = "utf-8",
    display_name: str | None = None,
) -> LoadedDocument:
    """Load a supported local file into text for document-memory indexing."""
    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise DocumentLoaderError(f"Document file does not exist: {file_path}")
    if not file_path.is_file():
        raise DocumentLoaderError(f"Document path is not a file: {file_path}")

    display_path = Path(display_name) if display_name else file_path
    extension = display_path.suffix.lower()
    if extension in SUPPORTED_TEXT_EXTENSIONS:
        return load_text_file(file_path, encoding=encoding, display_name=display_name)
    if extension == ".pdf":
        return load_pdf_file(file_path, display_name=display_name)

    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise DocumentLoaderError(
        f"Unsupported document extension {extension!r}. Supported extensions: {supported}"
    )


def load_text_file(
    path: Path,
    encoding: str = "utf-8",
    display_name: str | None = None,
) -> LoadedDocument:
    """Load a UTF-8 text or markdown file."""
    try:
        text = path.read_text(encoding=encoding)
    except UnicodeDecodeError as error:
        msg = f"Could not decode {path} with encoding {encoding!r}."
        raise DocumentLoaderError(msg) from error
    return LoadedDocument(
        title=display_stem(path, display_name),
        text=text,
        source="file",
        metadata=base_file_metadata(path, loader_name="path_read_text", display_name=display_name),
    )


def normalize_pdf_text(text: str, page_count: int) -> str:
    """Normalize PDF-extracted text for chunking: fix line breaks, strip artifacts."""
    lines = text.split("\n")

    # Strip standalone page numbers
    lines = [line for line in lines if line.strip() and not re.fullmatch(r"\d{1,4}", line.strip())]

    # Remove repeated header/footer lines (appear on ≥50% of pages)
    if page_count >= 3:
        threshold = max(page_count // 2, 2)
        line_counts = Counter(lines)
        repeated = {line for line, count in line_counts.items() if count >= threshold}
        lines = [line for line in lines if line not in repeated]

    # Collapse single newlines within paragraphs, keep paragraph breaks
    # PDFs produce one line per visual line, not per paragraph.
    # Strategy: join all lines with \n, then collapse single \n to space,
    # and coalesce runs of \n into \n\n paragraph breaks.
    joined = "\n".join(lines)
    # Replace single newline (text\ntext) with space
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", joined)
    # Coalesce multiple newlines into double paragraph breaks
    normalized = re.sub(r"\n{2,}", "\n\n", normalized)

    return normalized.strip()


def load_pdf_file(path: Path, display_name: str | None = None) -> LoadedDocument:
    """Load PDF text with a mature PDF library when one is installed."""
    try:
        text, page_count, loader_name = load_pdf_with_pypdf(path)
    except DocumentLoaderError:
        try:
            text, page_count, loader_name = load_pdf_with_pymupdf(path)
        except DocumentLoaderError as error:
            msg = "PDF loading requires pypdf or PyMuPDF. Install one of them to index PDF files."
            raise DocumentLoaderError(msg) from error

    if page_count > MAX_PDF_PAGES:
        raise DocumentLoaderError(
            f"PDF has {page_count} pages (max {MAX_PDF_PAGES}). "
            "Split the document into smaller files."
        )

    if not text.strip():
        raise DocumentLoaderError(
            "No extractable text found. This may be a scanned/image PDF. Try OCR before indexing."
        )

    text = normalize_pdf_text(text, page_count)

    metadata = base_file_metadata(path, loader_name=loader_name, display_name=display_name)
    metadata["page_count"] = page_count
    return LoadedDocument(
        title=display_stem(path, display_name),
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


def base_file_metadata(path: Path, loader_name: str, display_name: str | None = None) -> dict:
    """Return common file metadata for loaded documents."""
    display_path = Path(display_name) if display_name else path
    return {
        "file_path": str(path),
        "file_name": display_path.name,
        "file_extension": display_path.suffix.lower(),
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


def index_file_document(
    path: str | Path,
    indexer: TextDocumentIndexer,
    display_name: str | None = None,
):
    """Load and index one local document file."""
    return index_loaded_document(load_document_file(path, display_name=display_name), indexer)


def display_stem(path: Path, display_name: str | None = None) -> str:
    """Return the original upload stem when provided, otherwise the filesystem stem."""
    return Path(display_name).stem if display_name else path.stem
