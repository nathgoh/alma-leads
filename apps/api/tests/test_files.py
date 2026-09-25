import io

import pytest
from fastapi import UploadFile

from app.leads.files import DOC_MIME, DOCX_MIME, PDF_MIME, ResumeRejected, validate_resume
from tests.conftest import DOC_BYTES, EXE_BYTES, PDF_BYTES, make_docx

MAX = 1024 * 1024


def upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=name, size=len(data))


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [("cv.pdf", PDF_BYTES, PDF_MIME), ("cv.DOC", DOC_BYTES, DOC_MIME), ("cv.docx", make_docx(), DOCX_MIME)],
)
async def test_accepts_allowed_documents(name: str, data: bytes, mime: str) -> None:
    result = await validate_resume(upload(name, data), MAX)
    assert result.mime == mime
    assert result.data == data


async def test_renamed_exe_is_rejected() -> None:
    with pytest.raises(ResumeRejected) as exc:
        await validate_resume(upload("cv.pdf", EXE_BYTES), MAX)
    assert exc.value.status_code == 415


async def test_plain_zip_named_docx_is_rejected() -> None:
    buf = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("payload.txt", "not a word document")
    with pytest.raises(ResumeRejected):
        await validate_resume(upload("cv.docx", buf.getvalue()), MAX)


async def test_disallowed_extension_is_rejected() -> None:
    with pytest.raises(ResumeRejected) as exc:
        await validate_resume(upload("cv.txt", b"hello"), MAX)
    assert exc.value.status_code == 415


async def test_oversized_file_is_rejected() -> None:
    with pytest.raises(ResumeRejected) as exc:
        await validate_resume(upload("cv.pdf", PDF_BYTES + b"0" * MAX), MAX)
    assert exc.value.status_code == 413


async def test_empty_file_is_rejected() -> None:
    with pytest.raises(ResumeRejected):
        await validate_resume(upload("cv.pdf", b""), MAX)


async def test_path_components_are_stripped_from_display_name() -> None:
    result = await validate_resume(upload("../../etc/passwd/..\\evil.pdf", PDF_BYTES), MAX)
    assert result.filename == "evil.pdf"
