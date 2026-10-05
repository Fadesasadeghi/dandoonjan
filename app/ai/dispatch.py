"""In-memory, opt-in-readable dispatch evidence. Never receives request content."""
from threading import Lock


class DispatchAccounting:
    def __init__(self):
        self._lock = Lock()
        self._events = []

    def record(self, event, provider, model, kind, image_bearing):
        if event not in ('logical_call', 'http_dispatch'):
            raise ValueError('INVALID_DISPATCH_EVENT')
        if kind not in ('artifact_classifier', 'treatment_plan_extractor',
                        'invoice_extractor', 'claim_builder', 'review'):
            raise ValueError('INVALID_DISPATCH_KIND')
        # Values originate only from validated adapter identity, never request data.
        with self._lock:
            self._events.append({'event': event, 'provider': provider, 'model': model,
                                 'kind': kind, 'image_bearing': bool(image_bearing)})

    def snapshot(self):
        with self._lock:
            return [dict(event) for event in self._events]
