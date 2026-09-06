import pytest
from fastapi import HTTPException

from app.core.upload_security import read_validated_upload


class FakeUpload:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def read(self, size: int = -1) -> bytes:
        return self.data[:size]


@pytest.mark.asyncio
async def test_validated_upload_accepts_matching_pdf_signature() -> None:
    data = b"%PDF-1.7" + b"content"

    assert await read_validated_upload(FakeUpload(data), "application/pdf", 100) == data


@pytest.mark.asyncio
async def test_validated_upload_rejects_mismatched_signature() -> None:
    with pytest.raises(HTTPException) as error:
        await read_validated_upload(FakeUpload(b"not a pdf"), "application/pdf", 100)

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_validated_upload_rejects_oversized_files() -> None:
    with pytest.raises(HTTPException) as error:
        await read_validated_upload(FakeUpload(b"%PDF-1.7" + b"x" * 100), "application/pdf", 10)

    assert error.value.status_code == 413
