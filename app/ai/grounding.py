"""Conservative source checks, not clinical validation or a new ontology.

Atomic extraction must match an explicit relationship in a supplied text line.
Claim candidates may restate supplied atomic facts, never invent new ones.
"""
import hashlib
import re

from app.core.ontology import ontology as ont
from app.errors import ExtractionValidationError


def validate_extraction_source(artifact, output):
    body = (artifact.text_content or '')[:20000]
    from app.security.ingestion import read_bytes
    data = read_bytes(artifact.storage_key)
    if hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise ExtractionValidationError('SOURCE_INTEGRITY')
    if artifact.detected_mime_type == 'application/pdf':
        from app.core.artifacts.ingestion import pdf_text_pages_bounded
        pages = pdf_text_pages_bounded(data)
    else:
        pages = [data.decode('utf-8-sig')[:20000]]

    def candidate_lines(page, span):
        if page is not None and not 1 <= page <= len(pages):
            raise ExtractionValidationError('SOURCE_PAGE_INVALID')
        selected = pages[page-1] if page is not None else body
        lines = selected.splitlines()
        if span and span.startswith('line:'):
            match = re.fullmatch(r'line:(\d+)(?::char:(\d+)-(\d+))?', span)
            if not match or int(match[1]) >= len(lines):
                raise ExtractionValidationError('SOURCE_SPAN_INVALID')
            line = lines[int(match[1])]
            if match[2] is not None and not 0 <= int(match[2]) < int(match[3]) <= len(line):
                raise ExtractionValidationError('SOURCE_SPAN_INVALID')
            snippet = line[int(match[2]):int(match[3])] if match[2] is not None else line
            return [(line, snippet)] if line in body else []
        # No invented locator is accepted. A missing locator may be grounded by
        # matching the bounded input, without pretending a page/span was supplied.
        if span:
            match = re.fullmatch(r'char:(\d+)-(\d+)', span)
            if not match or not 0 <= int(match[1]) < int(match[2]) <= len(selected):
                raise ExtractionValidationError('SOURCE_SPAN_INVALID')
            start, end = int(match[1]), int(match[2])
            snippet = selected[start:end]
            line_start = selected.rfind('\n',0,start)+1
            line_end = selected.find('\n',end)
            line = selected[line_start:line_end if line_end != -1 else len(selected)]
            return [(line,snippet)] if line in body else []
        return [(line,line) for line in lines if line in body]

    for item in output.treatment_items:
        location = item.source_locator
        if location and location.bounding_box is not None:
            # This stage supplies text without layout coordinates. A model may
            # not invent image-space provenance from that text-only request.
            raise ExtractionValidationError('SOURCE_BOX_UNSUPPORTED')
        lines = candidate_lines(location.page if location else None, location.span if location else None)
        synonyms = ont._TREATMENT_SYNONYMS.get(item.treatment, [])
        def supported(pair):
            line, snippet = pair
            low = line.lower()
            if re.search(r'\b(?:not|never|no)\b|توصیه\s+نمی|لازم\s+نیست|نیازی\s+نیست|نباید', low):
                return False
            if not any(term in snippet.lower() for term in synonyms): return False
            if item.tooth and ont.normalize_tooth(line) != item.tooth: return False
            if item.predicate == 'REQUIRED' and not any(word in low for word in (
                    'required','necessary','needs','must','لازم است','لازمه','باید','نیاز')): return False
            if item.predicate == 'PERFORMED' and not any(word in low for word in (
                    'performed','completed','انجام شد','انجام شده')): return False
            return True
        if not any(supported(line) for line in lines):
            raise ExtractionValidationError('UNSUPPORTED_TREATMENT_ITEM')
    for field in output.fields:
        lines = candidate_lines(field.page, field.source_span)
        if field.field_name == 'tooth_reference' and field.normalized_value:
            if not any(ont.normalize_tooth(line) == field.normalized_value for line, _ in lines):
                raise ExtractionValidationError('UNSUPPORTED_TOOTH')
        elif field.field_name in ('price','total_price'):
            if not any(field.raw_value in snippet for _, snippet in lines):
                raise ExtractionValidationError('UNSUPPORTED_PRICE')


def validate_claim_sources(output, facts):
    allowed = {(item['tooth'] or '', item['treatment'], item['predicate']) for item in facts['treatment_items']}
    prices = {(item['subject'] or '', item['object_value']) for item in facts['price_facts']}
    for claim in output.claims:
        if claim.claim_type == 'TREATMENT':
            if (claim.subject, claim.treatment, claim.modality) not in allowed:
                raise ExtractionValidationError('UNSUPPORTED_CLAIM')
        elif claim.claim_type == 'TREATMENT_QUOTED':
            if (claim.subject, claim.object_value) not in prices:
                raise ExtractionValidationError('UNSUPPORTED_PRICE_CLAIM')
        else:
            raise ExtractionValidationError('UNSUPPORTED_CLAIM_KIND')
