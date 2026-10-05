"""Generated nonclinical pixels/PDF/text only, owned offline HTTP transport."""
import base64
import hashlib
import io
import json
from types import SimpleNamespace

import httpx
import pymupdf
import pytest
from PIL import Image, PngImagePlugin

from app.ai.multimodal import bundle, provider_bundle, prepare_image, prepare_pdf
from app.ai.providers import OpenRouterProvider


def artifact(ref, data, mime, text=None):
    return SimpleNamespace(public_id=ref, sha256=hashlib.sha256(data).hexdigest(),
        detected_mime_type=mime, document_role='previous_report', text_content=text,
        original_filename='PRIVATE_FILENAME', storage_key='PRIVATE_PATH')


def picture(fmt='PNG'):
    out = io.BytesIO()
    image = Image.new('RGB', (80, 40), 'blue')
    if fmt == 'PNG':
        metadata = PngImagePlugin.PngInfo(); metadata.add_text('patient', 'PRIVATE_METADATA')
        image.save(out, fmt, pnginfo=metadata)
    else:
        exif = Image.Exif(); exif[270] = 'PRIVATE_METADATA'; exif[274] = 6
        image.save(out, fmt, exif=exif)
    return out.getvalue()


@pytest.mark.parametrize('fmt,mime', [('PNG','image/png'), ('JPEG','image/jpeg')])
def test_real_image_parts_are_decodable_and_minimized(case, fmt, mime):
    original = picture(fmt)
    source = artifact('ART_PRIVATE', original, mime)
    local = bundle(case, artifacts=[source], read_artifact=lambda a: original)
    outbound, mapping = provider_bundle(local)
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'model': 'synthetic/fixed', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', offline_handler=handler)
    provider.review(outbound)
    parts = seen[0]['messages'][1]['content']
    image_part = next(p for p in parts if p['type'] == 'image_url')
    prefix, encoded = image_part['image_url']['url'].split(',', 1)
    assert prefix == 'data:image/jpeg;base64'
    data = base64.b64decode(encoded, validate=True)
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == 'JPEG' and max(image.size) <= 1600
        assert not image.getexif() and 'icc_profile' not in image.info
        assert image.size == ((40,80) if fmt == 'JPEG' else (80,40))
    assert hashlib.sha256(original).hexdigest() == source.sha256
    serialized = json.dumps(seen)
    assert all(s not in serialized for s in ('PRIVATE_FILENAME','PRIVATE_PATH','PRIVATE_METADATA','ART_PRIVATE',case.public_id))
    assert provider.dispatch_accounting.snapshot()[-1]['image_bearing'] is True


def pdf(pages=2):
    with pymupdf.open() as doc:
        for index in range(pages):
            page = doc.new_page(width=200, height=200)
            page.draw_rect(page.rect, color=None, fill=(1,0,0) if index % 2 == 0 else (0,1,0))
            page.insert_text((10,20), 'SYNTHETIC - NOT CLINICAL')
        return doc.tobytes()


def test_pdf_visual_pages_have_separate_exact_sources(case):
    data = pdf()
    source = artifact('ART_PDF', data, 'application/pdf', 'EXTRACTED_TEXT_PRIVATE')
    local = bundle(case, artifacts=[source], read_artifact=lambda a: data)
    pages = [s for s in local['sources'] if s['artifact_id']]
    assert [(s['source_ref'],s['page']) for s in pages] == [('ART_PDF:page:1',1),('ART_PDF:page:2',2)]
    assert len(local['images']) == 2
    for index, item in enumerate(local['images']):
        with Image.open(io.BytesIO(base64.b64decode(item['data']))) as image:
            r,g,b = image.getpixel((100,100))
            assert (r > g) if index == 0 else (g > r)
    # PDF text is the legacy extraction input; review uses rendered visuals.
    assert all(t['text'] != 'EXTRACTED_TEXT_PRIVATE' for t in local['text'])
    outbound, _ = provider_bundle(local)
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'model':'synthetic/fixed','choices':[
            {'finish_reason':'stop','message':{'content':'{}'}}]})
    OpenRouterProvider('OFFLINE_TEST_ONLY','synthetic/fixed',offline_handler=handler).review(outbound)
    parts = seen[0]['messages'][1]['content']
    actual = [p for p in parts if p['type']=='image_url']
    markers = [p['text'][8:] for p in parts if p['type']=='text' and p['text'].startswith('Source: ')]
    descriptors = [s for s in outbound['sources'] if s['representation']=='PDF_PAGE']
    assert len(actual) == 2 and markers == [s['source_ref'] for s in descriptors]
    with pytest.raises(ValueError): prepare_pdf(pdf(9))


def test_text_partial_coverage_is_explicit(case):
    text = 'متن ساختگی ' * 2500
    data = text.encode()
    local = bundle(case, artifacts=[artifact('ART_TEXT',data,'text/plain',text)], read_artifact=lambda a:data)
    assert len(local['text'][-1]['text']) == 20000
    coverage = local['coverage']['ART_TEXT:text']
    assert coverage['representation'] == 'TEXT' and coverage['partial'] is True
    assert coverage['original_characters'] == len(text)
    outbound, _ = provider_bundle(local)
    descriptor = next(s for s in outbound['sources'] if s['label'].startswith('document-'))
    assert descriptor['partial'] is True


def test_corrupted_original_cannot_use_old_hash(case):
    original = picture()
    source = artifact('ART_BAD',original,'image/png')
    with pytest.raises(ValueError): bundle(case, artifacts=[source], read_artifact=lambda a:picture('JPEG'))


def test_duplicate_source_inventory_fails_before_aliasing():
    local = {'sources':[{'source_ref':'same','kind':'DOCUMENT_EXTRACTED'},
        {'source_ref':'same','kind':'PATIENT_REPORTED'}], 'text':[], 'images':[]}
    with pytest.raises(ValueError): provider_bundle(local)


def test_alias_collision_cannot_cross_link(monkeypatch):
    monkeypatch.setattr('secrets.token_hex',lambda n:'0'*32)
    local = {'sources':[{'source_ref':'a'},{'source_ref':'b'}], 'text':[], 'images':[]}
    with pytest.raises(ValueError): provider_bundle(local)


def test_known_demo_pattern_cannot_support_clinical_hypothesis(case):
    from app.core.cases.sample import image_pattern
    from app.ai.review_schema import validate_review
    from tests.next_phase.test_gate62_output import safe_review, assertion
    data = image_pattern()
    local = bundle(case, artifacts=[artifact('ART_PATTERN',data,'image/png')], read_artifact=lambda a:data)
    outbound, mapping = provider_bundle(local)
    image = next(s for s in outbound['sources'] if s['kind']=='DOCUMENT_EXTRACTED')
    assert image['clinical_use'] == 'NON_CLINICAL'
    refs = list(mapping)
    raw = safe_review(refs[:1]); raw['source_index']=[{'source_ref':ref} for ref in refs]
    raw['diagnostic_hypotheses']=[{'label':'حساسیت دندانی','confidence_label':'LOW','truth_type':'MODEL_INFERRED',
        'supporting_evidence_refs':[image['source_ref']], 'contradicting_evidence_refs':[],
        'missing_information':[assertion('کفایت شواهد بالینی هنوز تأیید نشده است.', ())],
        'recommended_checks':[assertion('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.', ())], 'insufficient_support':True}]
    with pytest.raises(ValueError): validate_review(raw, refs, source_context=outbound)


def test_encrypted_pdf_cannot_be_rendered_as_reviewed():
    with pymupdf.open(stream=pdf(),filetype='pdf') as doc:
        data=doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='SYNTHETIC_ONLY',user_pw='SYNTHETIC_ONLY')
    with pytest.raises(ValueError): prepare_pdf(data)


def test_animated_png_cannot_silently_lose_frames():
    out=io.BytesIO()
    Image.new('RGB',(20,20),'red').save(out,'PNG',save_all=True,
        append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
    with pytest.raises(ValueError): prepare_image(out.getvalue())


def test_legacy_text_extraction_is_bounded(case):
    from app.core.artifacts.ingestion import extract_text_if_supported
    text='متن ساختگی '*4000
    data=text.encode()
    source=artifact('ART_TEXT',data,'text/plain')
    result=extract_text_if_supported(source,data)
    assert len(result) <= 20001  # Includes one sentinel character to mark partial extraction.
    with pymupdf.open() as doc:
        for _ in range(20): doc.new_page().insert_text((20,30),'SYNTHETIC text '*500)
        data=doc.tobytes()
    source=artifact('ART_PDF',data,'application/pdf')
    assert len(extract_text_if_supported(source,data)) <= 20001
