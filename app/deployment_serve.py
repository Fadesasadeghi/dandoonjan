"""Environment-only production entry point; preflight precedes HTTP serving."""
from __future__ import annotations

import ipaddress
import json
import os
import sys


def trusted_peers(value: str | None) -> str:
    """Accept only a nonempty finite list of literal IP peers, without DNS."""
    if value is None:
        raise ValueError('PROXY_TRUST_INVALID')
    peers = value.split(',')
    normalized = []
    for peer in peers:
        peer = peer.strip()
        # Scoped IPv6 introduces interface-dependent matching; require plain IPs.
        if not peer or '%' in peer:
            raise ValueError('PROXY_TRUST_INVALID')
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            raise ValueError('PROXY_TRUST_INVALID') from None
        if address.is_unspecified or address.is_multicast:
            raise ValueError('PROXY_TRUST_INVALID')
        if str(address) not in normalized:
            normalized.append(str(address))
    return ','.join(normalized)


def run_preflight() -> int:
    from app.deployment_preflight import main
    return main()


def main() -> int:
    try:
        peers = trusted_peers(os.environ.get('DJ_TRUSTED_PROXY_PEERS'))
    except ValueError:
        print(json.dumps({'status': 'FAIL', 'code': 'PROXY_TRUST_INVALID'}, sort_keys=True))
        return 1
    raw_port = os.environ.get('PORT', '8000')
    if (len(raw_port) > 5 or not raw_port.isascii() or not raw_port.isdecimal()
            or not 1 <= int(raw_port) <= 65535):
        print(json.dumps({'status': 'FAIL', 'code': 'PORT_INVALID'}, sort_keys=True))
        return 1
    result = run_preflight()
    if result != 0:
        return result
    sys.stdout.flush()  # Preserve preflight evidence even with buffered stdout.
    # Replace the wrapper process: no shell or implicit Uvicorn trust settings.
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app',
                             '--host', '0.0.0.0', '--port', str(int(raw_port)),
                             '--log-config', 'app/logging.json', '--proxy-headers',
                             '--forwarded-allow-ips', peers])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
