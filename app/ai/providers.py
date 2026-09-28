"""Provider abstraction. Domain modules never call a provider directly.

- MockProvider: deterministic, offline, no network. Development/test fallback only.
- OpenRouterProvider: real provider (OpenRouter, OpenAI-compatible chat completions)
  for classification, structured extraction and claim candidates. Conservative settings:
  temperature 0, JSON response format, bounded output, timeout, limited retries.
  Any unavailability (network, timeout, 429/5xx, unparseable envelope) raises
  ProviderUnavailableError; the gateway fails closed in production and retains
  visible development/test fallback at the worker boundary only.

Credentials come from environment only; never hardcoded. Accepts an injected
httpx client for offline tests (no live API in the test suite).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Protocol

import httpx

from app.ai.prompts import Prompt, render_prompt
from app.errors import ProviderUnavailableError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_DEFAULT_TIMEOUT = 30.0
_MAX_ATTEMPTS = 2


def _fenced(content: str) -> str:
    """Extract the untrusted DATA section from a rendered prompt."""
    if "<<<" in content and ">>>" in content:
        return content.split("<<<", 1)[1].rsplit(">>>", 1)[0].strip()
    return content


class AIProvider(Protocol):
    name: str

    def run(self, prompt: Prompt, content: str, params: dict[str, Any]) -> dict[str, Any]:
        ...


def _predicate_for(text: str) -> str:
    low = text.lower()
    necessity = ["لازم است", "لازمه", "باید", "نیاز", "required", "necessary",
                 "needs", "must be", "must"]
    recommend = ["پیشنهاد", "recommend", "suggested", "توصیه"]
    if any(m in low for m in necessity):
        return "REQUIRED"
    if any(m in low for m in recommend):
        return "RECOMMENDED"
    return "PLANNED"


class MockProvider:
    name = "mock"

    def run(self, prompt: Prompt, content: str, params: dict[str, Any]) -> dict[str, Any]:
        # Deterministic dispatch by prompt id; content is treated strictly as data.
        if prompt.prompt_id == "artifact_classifier":
            return self._classify(_fenced(content))
        if prompt.prompt_id in ("treatment_plan_extractor", "invoice_extractor"):
            return self._extract(_fenced(content), prompt.prompt_id)
        if prompt.prompt_id == "claim_builder":
            return self._claims(json.loads(_fenced(content)))
        if prompt.prompt_id == "report_composer":
            return {"sections": [{"section": s["section"], "text": s["text"]}
                                 for s in json.loads(_fenced(content)).get("sections", [])]}
        raise ValueError(f"Unknown prompt {prompt.prompt_id}")

    def _classify(self, content: str) -> dict[str, Any]:
        header = content.split("\n", 1)[0]
        meta = json.loads(header) if header.startswith("{") else {}
        mime = meta.get("mime", "")
        fname = meta.get("filename", "").lower()
        body = content.split("\n", 1)[1] if "\n" in content else ""

        def has(*words: str) -> bool:
            return any(w in body.lower() or w in fname for w in words)

        if mime.startswith("image/"):
            if has("opg", "panoramic", "پانورامیک"):
                return {"category": "RADIOGRAPH", "subtype": "OPG", "confidence": 0.7}
            if has("cbct", "سه بعدی"):
                return {"category": "RADIOGRAPH", "subtype": "CBCT", "confidence": 0.7}
            if has("periapical", "پری اپیکال"):
                return {"category": "RADIOGRAPH", "subtype": "PERIAPICAL", "confidence": 0.6}
            if has("intraoral", "داخل دهان"):
                return {"category": "PHOTO", "subtype": "INTRAORAL", "confidence": 0.6}
            return {"category": "PHOTO", "subtype": "UNKNOWN_PHOTO", "confidence": 0.4}
        if mime == "application/pdf" or mime.startswith("text/"):
            if has("treatment plan", "طرح درمان", "plan درمان", "برنامه درمان"):
                return {"category": "CLINICAL_DOCUMENT", "subtype": "TREATMENT_PLAN",
                        "confidence": 0.85}
            if has("prescription", "نسخه", "دارو"):
                return {"category": "CLINICAL_DOCUMENT", "subtype": "PRESCRIPTION",
                        "confidence": 0.7}
            if has("referral", "ارجاع"):
                return {"category": "CLINICAL_DOCUMENT", "subtype": "REFERRAL", "confidence": 0.7}
            if has("invoice", "صورت حساب", "صورتحساب", "فاکتور", "جمع کل", "مبلغ",
                   "estimate", "برآورد"):
                return {"category": "FINANCIAL_DOCUMENT",
                        "subtype": "ESTIMATE" if has("estimate", "برآورد") else "INVOICE",
                        "confidence": 0.8}
            if has("note", "شرح حال", "معاینه"):
                return {"category": "CLINICAL_DOCUMENT", "subtype": "CLINICAL_NOTE",
                        "confidence": 0.6}
            return {"category": "CLINICAL_DOCUMENT", "subtype": "OTHER_CLINICAL",
                    "confidence": 0.3}
        return {"category": "UNKNOWN", "subtype": "UNKNOWN", "confidence": 0.1}

    def _extract(self, content: str, prompt_id: str) -> dict[str, Any]:
        """Emit atomic relationships. Line-level association: a treatment term and a
        tooth reference found in the SAME source line form one TreatmentItem
        (association made here, at extraction, never downstream)."""
        from app.core.ontology import ontology as ont

        fields: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []

        # Line numbers are relative to the DOCUMENT body, not the fenced envelope
        # (the first envelope line is the metadata header).
        body_lines = content.split("\n")
        if body_lines and body_lines[0].startswith("{"):
            body_lines = body_lines[1:]
        for line_number, line in enumerate(body_lines):
            low = line.lower()
            tooth_norm = ont.normalize_tooth(line)
            # collect every distinct treatment mentioned in the line
            line_treatments: list[tuple[str, str]] = []  # (canonical, span)
            for canonical, synonyms in ont._TREATMENT_SYNONYMS.items():
                for s in synonyms:
                    idx = low.find(s)
                    if idx >= 0:
                        line_treatments.append((canonical,
                                                f"line:{line_number}:char:{idx}-{idx + len(s)}"))
                        break
            if tooth_norm:
                fields.append({"field_name": "tooth_reference",
                               "raw_value": f"line:{line_number}",
                               "normalized_value": tooth_norm,
                               "confidence": 0.9, "page": 1,
                               "source_span": f"line:{line_number}"})
            for treatment_norm, span in line_treatments:
                items.append({"tooth": tooth_norm, "treatment": treatment_norm,
                              "predicate": _predicate_for(line),
                              "confidence": 0.85 if tooth_norm else 0.7,
                              "source_locator": {"page": 1, "span": span,
                                                 "bounding_box": None}})

        price = re.search(r"(\d[\d,،\.]*)\s*(تومان|ریال|toman|rial)", content.lower())
        if price:
            fields.append({"field_name": "price", "raw_value": price.group(0),
                           "confidence": 0.7, "page": 1,
                           "source_span": "char:{0}-{1}".format(*price.span())})
        return {"fields": fields, "treatment_items": items}

    def _claims(self, facts: dict[str, Any]) -> dict[str, Any]:
        """Deterministic claim candidates from atomic TreatmentItem facts
        (already validated upstream). One candidate per item — no cartesian."""
        claims: list[dict[str, Any]] = []
        for item in facts.get("treatment_items", []):
            claims.append({
                "claim_type": "TREATMENT",
                "subject": item.get("tooth") or "",
                "treatment": item.get("treatment"),
                "modality": item.get("predicate"),
                "predicate": "REQUIRES_TREATMENT" if item.get("predicate") == "REQUIRED"
                             else "PROPOSES_TREATMENT",
                "object_value": item.get("treatment") or "",
                "confidence": float(item.get("confidence", 0.5)),
            })
        for f in facts.get("price_facts", []):
            claims.append({
                "claim_type": "TREATMENT_QUOTED", "subject": f.get("subject", ""),
                "predicate": "QUOTED_PRICE", "object_value": f.get("object_value", ""),
                "confidence": float(f.get("confidence", 0.5)),
            })
        return {"claims": claims}


class OpenRouterProvider:
    """Real provider via OpenRouter (OpenAI-compatible). Structured candidates only;
    the ModelGateway schema firewall validates every
    response before it can touch Core state."""
    name = "openrouter"

    def __init__(self, api_key: str, model: str, timeout: float = _DEFAULT_TIMEOUT,
                 client: httpx.Client | None = None):
        if not api_key:
            raise ProviderUnavailableError("DJ_OPENROUTER_API_KEY is not configured")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    def _post(self, prompt: Prompt, content: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": render_prompt(prompt, content=content)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = self._client.post(OPENROUTER_URL, json=payload, headers=headers,
                                         timeout=self.timeout)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            else:
                if resp.status_code == 200:
                    return resp.json()
                # 429/5xx are retryable-then-unavailable; 4xx (other) unusable
                last_error = ProviderUnavailableError(
                    f"openrouter http {resp.status_code}")
                if resp.status_code < 500 and resp.status_code != 429:
                    raise last_error
            if attempt < _MAX_ATTEMPTS:
                time.sleep(0.5 * attempt)
        raise ProviderUnavailableError("openrouter unavailable") from None

    def run(self, prompt: Prompt, content: str, params: dict[str, Any]) -> dict[str, Any]:
        if prompt.prompt_id not in ("artifact_classifier", "treatment_plan_extractor",
                                    "invoice_extractor", "claim_builder"):
            # Candidate generation remains behind schema and ontology firewalls.
            raise ProviderUnavailableError(
                f"prompt {prompt.prompt_id} not in real-provider scope")
        data = self._post(prompt, content)
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError("openrouter malformed envelope") from None
        try:
            return json.loads(message)
        except json.JSONDecodeError as exc:
            # tolerate markdown-fenced JSON
            m = re.search(r"\{.*\}", message, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            raise ProviderUnavailableError("openrouter non-JSON content") from None


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
