"""Resume validation: size, extension allowlist, and content sniffing (a renamed .exe must fail)."""

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

import magic
from fastapi import UploadFile

PDF_MIME = "application/pdf"
DOC_MIME = "application/msword"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# extension → (canonical MIME stored on the lead, MIME types libmagic may report for it)
ALLOWED: dict[str, tuple[str, frozenset[str]]] = {
    ".pdf": (PDF_MIME, frozenset({PDF_MIME})),
    ".doc": (
        DOC_MIME,
        frozenset({DOC_MIME, "application/x-ole-storage", "application/CDFV2", "application/vnd.ms-office"}),
    ),
    # libmagic often only sees a generic zip in the first bytes; the zip is then checked for Word parts.
    ".docx": (DOCX_MIME, frozenset({DOCX_MIME, "application/zip"})),
}

SNIFF_BYTES = 8192


class ResumeRejected(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidResume:
    data: bytes
    filename: str
    extension: str
    mime: str


def _display_name(raw: str | None) -> str:
    # Display only — never used as a path. Drop any directory part and control chars.
    name = PurePath((raw or "").replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:255] or "resume"


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


async def validate_resume(upload: UploadFile, max_bytes: int) -> ValidResume:
    # 1. Size. The request-level Content-Length check in the router rejects huge bodies before
    #    parsing; here, read at most max_bytes + 1 so an oversized part is never fully buffered.
    if upload.size is not None and upload.size > max_bytes:
        raise ResumeRejected(f"File is too large (max {max_bytes // (1024 * 1024)} MB)", 413)
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ResumeRejected(f"File is too large (max {max_bytes // (1024 * 1024)} MB)", 413)
    if not data:
        raise ResumeRejected("File is empty")

    # 2. Extension allowlist.
    filename = _display_name(upload.filename)
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED:
        raise ResumeRejected("Resume must be a PDF, DOC, or DOCX file", 415)
    canonical_mime, sniff_ok = ALLOWED[extension]

    # 3. Content sniffing: the bytes must agree with the extension.
    sniffed = magic.from_buffer(data[:SNIFF_BYTES], mime=True)
    if sniffed not in sniff_ok or (extension == ".docx" and not _is_docx(data)):
        raise ResumeRejected("File contents don't match a PDF, DOC, or DOCX document", 415)

    return ValidResume(data=data, filename=filename, extension=extension, mime=canonical_mime)
