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
VERSION = 'outbound-v3'
MAX_TEXT = 20000


def prepare_image(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('IMAGE_MULTIFRAME_UNSUPPORTED')
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
            if doc.needs_pass or doc.is_encrypted or (doc.metadata or {}).get('encryption') or not 0 < doc.page_count <= MAX_PAGES:
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


def bundle(case, *, artifacts=None, read_artifact=None):
    from app.core.cases.dossier import fields
    from app.security.ingestion import read_bytes
    sources, text, images, coverage = [], [], [], {}
    intake = fields(case)
    values = {'main_question': case.question_text,
              'clinician_recommendation': case.dentist_recommendation_text,
              'context': case.context_text, **intake}
    for key, value in values.items():
        if not value.strip():
            continue
        ref = f'{case.public_id}:v{case.version}:{key}'
        sources.append({'source_ref': ref, 'kind': 'CLINICIAN_REPORTED' if key == 'clinician_recommendation' else 'PATIENT_REPORTED',
                        'artifact_id': None, 'page': None, 'label': key,
                        'sha256': hashlib.sha256(value.encode()).hexdigest()})
        text.append({'source_ref': ref, 'text': value})
        coverage[ref] = {'representation': 'TEXT', 'partial': False, 'clinical_use': 'UNVERIFIED'}
    total = 0
    selected = list(case.artifacts if artifacts is None else artifacts)
    for artifact in sorted(selected, key=lambda a: a.public_id):
        data = read_artifact(artifact) if read_artifact else read_bytes(artifact.storage_key)
        if hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise ValueError('ARTIFACT_INTEGRITY')
        if artifact.detected_mime_type not in ('application/pdf', 'image/jpeg', 'image/png', 'text/plain'):
            raise ValueError('UNSUPPORTED_REVIEW_ARTIFACT')
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
            nonclinical = False
            if artifact.detected_mime_type.startswith('image/'):
                from app.core.cases.sample import image_pattern
                # Exact application-owned transport pattern, including metadata
                # variants with the same pixels. No filename-based clinical claim.
                with Image.open(io.BytesIO(data)) as original, Image.open(io.BytesIO(image_pattern())) as known:
                    nonclinical = original.size == known.size and original.convert('RGB').tobytes() == known.convert('RGB').tobytes()
            coverage[ref] = {'representation': 'PDF_PAGE' if artifact.detected_mime_type == 'application/pdf' else 'IMAGE',
                             'partial': False, 'clinical_use': 'NON_CLINICAL' if nonclinical else 'UNVERIFIED'}
        if not pages:
            try:
                original_text = data.decode('utf-8-sig')
            except UnicodeError:
                raise ValueError('TEXT_INVALID') from None
            if not original_text.strip() or '\x00' in original_text:
                raise ValueError('TEXT_INVALID')
            ref = f'{artifact.public_id}:text'
            sources.append({'source_ref': ref, 'kind': 'DOCUMENT_EXTRACTED',
                            'artifact_id': artifact.public_id, 'page': None,
                            'label': f'document-{len(sources)+1}', 'document_role': artifact.document_role, 'sha256': artifact.sha256})
            text.append({'source_ref': ref, 'text': original_text[:MAX_TEXT]})
            coverage[ref] = {'representation': 'TEXT', 'partial': len(original_text) > MAX_TEXT,
                             'original_characters': len(original_text), 'clinical_use': 'UNVERIFIED'}
    if sum(len(t['text']) for t in text) > 100000:
        raise ValueError('OUTBOUND_TEXT_LIMIT')
    if len(sources) > 100:
        raise ValueError('OUTBOUND_SOURCE_LIMIT')
    missing = [key for key, value in values.items() if key in intake and
               value.strip().lower() in ('', 'unknown', 'نامشخص', 'نمی‌دانم', 'نمی دانم')]
    omitted = len({a.public_id for a in case.artifacts} - {a.public_id for a in selected})
    return {'version': VERSION, 'sources': sources, 'text': text, 'images': images,
            'coverage': coverage, 'missing_intake': missing, 'omitted_artifacts': omitted}


def provider_bundle(local):
    """Fresh aliases per request; mapping never leaves this process."""
    import secrets
    refs = [s['source_ref'] for s in local['sources']]
    from app.ai.preflight import failure
    if len(refs) != len(set(refs)):
        raise failure('reference')
    aliases = {ref: 'src_' + secrets.token_hex(16) for ref in refs}
    if len(set(aliases.values())) != len(aliases):
        raise failure('reference')
    sources = []
    for source in local['sources']:
        sources.append({'source_ref': aliases[source['source_ref']],
            **{key: source[key] for key in ('kind', 'page', 'label', 'document_role') if key in source},
            **{key: value for key, value in local.get('coverage', {}).get(source['source_ref'], {}).items()
               if key in ('representation', 'partial', 'clinical_use')}})
    outbound = {'sources': sources,
        'text': [{'source_ref': aliases[t['source_ref']], 'text': t['text']} for t in local['text']],
        'images': [{'source_ref': aliases[i['source_ref']], 'data': i['data']} for i in local['images']]}
    outbound['coverage_notes'] = {'missing_intake': local.get('missing_intake', []),
                                 'omitted_artifacts': local.get('omitted_artifacts', 0)}
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
