"""Bounded outbound derivatives. Originals stay immutable; no filenames/metadata leave."""
import base64
import hashlib
import io
import warnings
import pymupdf
from PIL import Image, ImageOps

MAX_PAGES = 8
MAX_PIXELS = 20_000_000
MAX_IMAGES = 16
MAX_BYTES = 12 * 1024 * 1024
VERSION = 'outbound-v2'


def prepare_image(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('IMAGE_PIXEL_LIMIT')
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1600))
                # Copy pixels into a fresh image; do not propagate EXIF/ICC/comments.
                clean = Image.new('RGB', image.size, 'white')
                if image.mode == 'RGBA':
                    clean.paste(image, mask=image.getchannel('A'))
                else:
                    clean.paste(image.convert('RGB'))
                out = io.BytesIO()
                clean.save(out, 'JPEG', quality=88)
                return out.getvalue()
    except Exception:
        raise ValueError('IMAGE_INVALID_OR_LIMIT') from None


def prepare_pdf(data: bytes) -> list[bytes]:
    try:
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass or not 0 < doc.page_count <= MAX_PAGES:
                raise ValueError('PDF_PAGE_LIMIT_OR_LOCKED')
            output = []
            for page in doc:
                scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                output.append(prepare_image(pix.tobytes('png')))
            return output
    except ValueError:
        raise
    except Exception:
        raise ValueError('PDF_INVALID') from None


def bundle(case):
    from app.core.cases.dossier import fields, latest
    from app.security.ingestion import read_bytes
    revision = latest(case)
    sources, text, images = [], [], []
    values = {'main_question': case.question_text,
              'clinician_recommendation': case.dentist_recommendation_text,
              'context': case.context_text, **fields(case)}
    for key, value in values.items():
        if not value.strip():
            continue
        ref = f'{case.public_id}:v{case.version}:{key}'
        sources.append({'source_ref': ref, 'kind': 'CLINICIAN_REPORTED' if key == 'clinician_recommendation' else 'PATIENT_REPORTED',
                        'artifact_id': None, 'page': None, 'label': key,
                        'sha256': hashlib.sha256(value.encode()).hexdigest()})
        text.append({'source_ref': ref, 'text': value})
    total = 0
    for artifact in case.artifacts:
        data = read_bytes(artifact.storage_key)
        pages = (prepare_pdf(data) if artifact.detected_mime_type == 'application/pdf'
                 else [prepare_image(data)] if artifact.detected_mime_type.startswith('image/') else [])
        for page, image in enumerate(pages, 1):
            total += len(image)
            if len(images) >= MAX_IMAGES or total > MAX_BYTES:
                raise ValueError('OUTBOUND_LIMIT')
            ref = f'{artifact.public_id}:page:{page}'
            sources.append({'source_ref': ref, 'kind': 'DOCUMENT_EXTRACTED',
                            'artifact_id': artifact.public_id, 'page': page,
                            'label': f'document-{len(sources)+1}', 'document_role': artifact.document_role,
                            'sha256': artifact.sha256,
                            'derivative_sha256': hashlib.sha256(image).hexdigest()})
            images.append({'source_ref': ref, 'data': base64.b64encode(image).decode()})
        if not pages and artifact.text_content:
            ref = f'{artifact.public_id}:text'
            sources.append({'source_ref': ref, 'kind': 'DOCUMENT_EXTRACTED',
                            'artifact_id': artifact.public_id, 'page': None,
                            'label': f'document-{len(sources)+1}', 'document_role': artifact.document_role, 'sha256': artifact.sha256})
            text.append({'source_ref': ref, 'text': artifact.text_content[:20000]})
    if sum(len(t['text']) for t in text) > 100000:
        raise ValueError('OUTBOUND_TEXT_LIMIT')
    return {'version': VERSION, 'sources': sources, 'text': text, 'images': images}


def provider_bundle(local):
    """Fresh aliases per request; mapping never leaves this process."""
    import secrets
    aliases = {s['source_ref']: 'src_' + secrets.token_hex(16) for s in local['sources']}
    sources = []
    for source in local['sources']:
        sources.append({'source_ref': aliases[source['source_ref']],
            **{key: source[key] for key in ('kind', 'page', 'label', 'document_role') if key in source}})
    outbound = {'sources': sources,
        'text': [{'source_ref': aliases[t['source_ref']], 'text': t['text']} for t in local['text']],
        'images': [{'source_ref': aliases[i['source_ref']], 'data': i['data']} for i in local['images']]}
    return outbound, {alias: ref for ref, alias in aliases.items()}


def resolve_review(output, mapping):
    """Only a validated ReviewOutput may cross back to local provenance."""
    value = output.model_dump()
    def resolve(node):
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if isinstance(node, dict):
            result = {}
            for key, item in node.items():
                if key == 'source_ref':
                    result[key] = mapping[item]
                elif key in ('source_refs', 'supporting_evidence_refs', 'contradicting_evidence_refs'):
                    result[key] = [mapping[ref] for ref in item]
                else:
                    result[key] = resolve(item)
            return result
        return node
    return resolve(value)
