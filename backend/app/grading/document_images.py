import fitz  # PyMuPDF
from fastapi import HTTPException, status

from app.config import settings

_RENDER_DPI = 150


def file_to_page_images(file_bytes: bytes, content_type: str) -> tuple[list[bytes], str]:
    """Render an uploaded file to one or more page images for vision input.

    PDFs are rendered page-by-page at a fixed DPI (vision models take images, not
    PDF bytes directly), always producing PNG output. An already-an-image upload
    passes through unchanged as a single-page list, keeping its original mime type.

    Returns (images, mime_type_of_those_images).
    """
    if content_type == "application/pdf":
        images: list[bytes] = []
        zoom = _RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                if len(doc) > settings.max_document_pages:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"PDF has too many pages. Maximum allowed is {settings.max_document_pages}.",
                    )
                for page in doc:
                    pixmap = page.get_pixmap(matrix=matrix)
                    images.append(pixmap.tobytes("png"))
        except fitz.FileDataError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF could not be read.",
            ) from exc
        return images, "image/png"

    if content_type.startswith("image/"):
        return [file_bytes], content_type

    raise ValueError(f"Unsupported file type for vision extraction: {content_type}")
