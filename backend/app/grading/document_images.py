import fitz  # PyMuPDF

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
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                pixmap = page.get_pixmap(matrix=matrix)
                images.append(pixmap.tobytes("png"))
        return images, "image/png"

    if content_type.startswith("image/"):
        return [file_bytes], content_type

    raise ValueError(f"Unsupported file type for vision extraction: {content_type}")
