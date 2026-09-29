import io
import pytest
from PIL import Image, PngImagePlugin


def test_image_metadata_removed_and_original_preserved():
    from app.ai.multimodal import prepare_image
    buf = io.BytesIO()
    meta = PngImagePlugin.PngInfo()
    meta.add_text('patient', 'PRIVATE_CANARY')
    Image.new('RGB', (100, 100), 'white').save(buf, format='PNG', pnginfo=meta)
    original = buf.getvalue()
    result = prepare_image(original)
    assert b'PRIVATE_CANARY' not in result
    assert b'PRIVATE_CANARY' in original
    assert Image.open(io.BytesIO(result)).size == (100, 100)


def test_pdf_pages_are_bounded():
    import pymupdf
    from app.ai.multimodal import prepare_pdf
    with pymupdf.open() as doc:
        for _ in range(9):
            doc.new_page()
        with pytest.raises(ValueError, match='PAGE_LIMIT'):
            prepare_pdf(doc.tobytes())


def test_invalid_image_is_safe():
    from app.ai.multimodal import prepare_image
    with pytest.raises(ValueError, match='IMAGE_INVALID'):
        prepare_image(b'PRIVATE_CANARY')
