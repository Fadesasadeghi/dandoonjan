"""Bound temporary file retention before ordinary upload validation runs."""
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException, MultiPartParser, parse_options_header

from app.config import get_settings


class BoundedUploadParser(MultiPartParser):
    """Keep the configured file maximum plus the ingestion oversize sentinel.

    Consume the remainder without retaining it, so ownership, selected-field
    semantics, rejection status and durable audit still belong to the existing
    handler. This is not a total request-byte or request-duration limit.
    """

    def __init__(self, *args, file_limit: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_limit = file_limit

    def on_part_begin(self):
        super().on_part_begin()
        self.remaining = self.file_limit + 1

    def on_part_data(self, data, start, end):
        if self._current_part.file is not None:
            end = min(end, start + self.remaining)
            self.remaining -= end - start
            if end == start:
                return
        super().on_part_data(data, start, end)


async def with_bounded_upload_form(request, handler):
    content_type, _ = parse_options_header(request.headers.get('content-type', ''))
    if content_type != b'multipart/form-data':
        return await handler(request)
    parser = BoundedUploadParser(request.headers, request.stream(),
                                 file_limit=get_settings().max_upload_bytes)
    try:
        try:
            # FastAPI reuses this Request cache and closes completed form files.
            request._form = await parser.parse()
        except MultiPartException as exc:
            raise HTTPException(400, detail=exc.message) from exc
        except Exception as exc:
            # Match FastAPI's existing sanitized body-parsing failure response.
            raise HTTPException(400, detail='There was an error parsing the body') from exc
        return await handler(request)
    finally:
        # A truncated part can be absent from FormData even when parse returns.
        # Close all allocated spools, including unfinished/ignored parts.
        for stream in parser._files_to_close_on_error:
            if not stream.closed:
                await run_in_threadpool(stream.close)
