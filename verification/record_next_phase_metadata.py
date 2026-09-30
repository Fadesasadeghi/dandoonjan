"""Supplemental offline Chrome/PDF evidence; run as a module from the repo root."""
import importlib.metadata
import json
import os
import platform
import tempfile
from pathlib import Path
import pymupdf
from PIL import Image
from playwright.sync_api import sync_playwright
from verification.test_rc_runtime import running_server

def main():
    evidence = Path(os.environ.get('NEXT_PHASE_EVIDENCE', 'docs/next-phase/evidence'))
    record = {'python': platform.python_version(), 'platform': platform.system(),
              'packages': {n: importlib.metadata.version(n) for n in
                           ['pytest', 'fastapi', 'starlette', 'sqlalchemy', 'playwright', 'pymupdf', 'pillow', 'anyio']}}
    with tempfile.TemporaryDirectory(prefix='offline-motion-', ignore_cleanup_errors=True) as folder:
        path = Path(folder)
        with running_server(path, f"sqlite:///{(path / 'motion.db').as_posix()}") as client:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome', headless=True)
                record['chrome'] = browser.version
                page = browser.new_page(reduced_motion='reduce')
                page.goto(str(client.base_url))
                record['reduced_motion'] = page.evaluate('''() => ({
                    media_matches: matchMedia('(prefers-reduced-motion: reduce)').matches,
                    tooth_animation: getComputedStyle(document.querySelector('.landing-artwork')).animationName,
                    scan_display: getComputedStyle(document.querySelector('.scan-line')).display,
                    scroll_behavior: getComputedStyle(document.documentElement).scrollBehavior
                })''')
                assert record['reduced_motion'] == {'media_matches': True, 'tooth_animation': 'none',
                    'scan_display': 'none', 'scroll_behavior': 'auto'}
                browser.close()
    record['screenshots'] = {}
    for stage in ['landing', 'dossier', 'analysis', 'results']:
        for width in [390, 768, 1440]:
            name = f'{stage}-{width}.png'
            with Image.open(evidence / name) as image:
                assert image.width == width
                record['screenshots'][name] = list(image.size)
    with pymupdf.open(evidence / 'offline-report.pdf') as doc:
        record['pdf_pages'] = len(doc)
        content = ''.join(page.get_text() for page in doc)
        report = json.loads((evidence / 'offline-run.json').read_text(encoding='utf-8'))
        assert report['snapshot_id'] in content
        assert report['review']['run']['run_id'] in content
        assert report['review']['run']['model'] in content
        record['pdf_matches_recorded_snapshot_run_model'] = True
        for number, page in enumerate(doc, 1):
            page.get_pixmap().save(str(evidence / f'pdf-page-{number}.png'))
    (evidence / 'verification-metadata.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
