from fastapi import HTTPException, UploadFile, status


_SUPPORTED_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"BM",
    b"II*\x00",
    b"MM\x00*",
)


async def read_validated_upload(file: UploadFile, content_type: str, max_bytes: int) -> bytes:
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File is too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.",
        )

    if content_type == "application/pdf":
        valid_signature = data.startswith(b"%PDF-")
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        valid_signature = data.startswith(b"PK\x03\x04")
    elif content_type.startswith("image/"):
        valid_signature = any(data.startswith(signature) for signature in _SUPPORTED_IMAGE_SIGNATURES)
        if content_type == "image/webp":
            valid_signature = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    else:
        valid_signature = False

    if not valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file content does not match its declared type.",
        )

    return data
