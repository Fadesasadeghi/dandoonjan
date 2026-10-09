"""Generate only publish-directory routing; never mutate Netlify configuration."""
from pathlib import Path
import os
import re
import sys
from urllib.parse import urlsplit


def generate(origin: str, destination: Path) -> None:
    # Reject whitespace/control characters before urlsplit can normalize them.
    if not origin or re.search(r'[^\x21-\x7e]', origin):
        raise ValueError('BACKEND_HTTPS_ORIGIN_REQUIRED')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path or parsed.query or parsed.fragment
            or '?' in origin or '#' in origin
            or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]+)?', parsed.netloc)
            or parsed.port == 0):
        raise ValueError('BACKEND_HTTPS_ORIGIN_REQUIRED')
    destination.write_text(
        f'/api/* {origin}/api/:splat 200!\n'
        '/ui/* /:splat 200\n'
        '/case/* /index.html 200\n', encoding='utf-8')


def main() -> int:
    try:
        generate(os.environ.get('DANDOONJAN_BACKEND_URL', ''),
                 Path(__file__).resolve().parents[1] / 'frontend' / '_redirects')
    except ValueError:
        print('BACKEND_HTTPS_ORIGIN_REQUIRED', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
