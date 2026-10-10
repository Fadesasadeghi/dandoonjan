"""Explicit Render staging TLS termination contract; no forwarded-header trust."""
from __future__ import annotations


def render_boundary_enabled(environment: str, mode: str, *, peers_present: bool = False) -> bool:
    if mode == 'disabled':
        return False
    if mode != 'render-managed-tls' or environment != 'staging' or peers_present:
        raise ValueError('RENDER_STAGING_HTTPS_BOUNDARY_INVALID')
    return True


class RenderStagingHTTPSBoundaryMiddleware:
    """Represent Render's external TLS hop, never information supplied by callers.

    Enable only where Render redirects HTTP to HTTPS and the listener cannot be
    reached outside its managed ingress. The deployment launcher disables
    Uvicorn proxy headers. Host, client address, Origin and Referer are untouched.
    This does not establish a trusted browser origin or make staging private.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            from app.config import get_settings
            settings = get_settings()
            if render_boundary_enabled(settings.environment, settings.render_staging_https_boundary):
                scope = {**scope, 'scheme': 'https'}
        await self.app(scope, receive, send)
