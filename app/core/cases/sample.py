"""Invented, nonclinical fixtures. The pattern is NOT a radiograph."""
import io
import pymupdf
from PIL import Image, ImageDraw

DEMO_MARKER = 'DANDOONJAN_SYNTHETIC_SAMPLE_V1'
DEMO_VERSION = 'demo-review-v2'
DEMO_MODEL = 'mock-evidence-v1'
SAMPLE_TEXT = ('SYNTHETIC Treatment Plan\nTooth 46: RCT recommended\n'
               'Tooth 46: Crown recommended after RCT\n'
               'For software testing only; not clinical evidence.\n')


def is_demo(case):
    return case.demo_visitor is not None


def execution_identity(case):
    from app.config import get_settings
    settings = get_settings()
    return ('mock', DEMO_MODEL) if is_demo(case) else (settings.ai_provider, settings.ai_model_name)


def image_pattern():
    image = Image.new('RGB', (512, 384), '#242424')
    draw = ImageDraw.Draw(image)
    for x in range(32, 480, 32):
        draw.line((x, 48, x, 320), fill=(x // 2, x // 2, x // 2), width=12)
    draw.text((20, 20), 'SYNTHETIC TRANSPORT PATTERN - NOT A RADIOGRAPH', fill='white')
    output = io.BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()


def plan_pdf():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), 'SYNTHETIC Treatment Plan\nTooth 46: RCT recommended\nFor software testing only; not clinical evidence.')
        return doc.tobytes()
