"""Explicit domain errors. Translated to safe user-facing states at the API layer."""
from __future__ import annotations


class DandoonjanError(Exception):
    code = "INTERNAL_ERROR"
    user_message_fa = "خطای داخلی سیستم. لطفاً دوباره تلاش کنید."


class UnsupportedArtifactError(DandoonjanError):
    code = "UNSUPPORTED_ARTIFACT"
    user_message_fa = "این نوع فایل پشتیبانی نمی‌شود."


class UnreadableArtifactError(DandoonjanError):
    code = "UNREADABLE_ARTIFACT"
    user_message_fa = "فایل قابل خواندن نیست یا خراب است."


class InvalidTransitionError(DandoonjanError):
    code = "INVALID_TRANSITION"
    user_message_fa = "تغییر وضعیت پرونده مجاز نیست."


class ExtractionValidationError(DandoonjanError):
    code = "EXTRACTION_VALIDATION"
    user_message_fa = "خروجی پردازش سند معتبر نبود."


class OntologyValidationError(DandoonjanError):
    code = "ONTOLOGY_VALIDATION"
    user_message_fa = "مقدار شناسه‌شده در دانشنامه معتبر نیست."


class KnowledgePackUnavailableError(DandoonjanError):
    code = "KNOWLEDGE_PACK_UNAVAILABLE"
    user_message_fa = "دانشنامه بالینی در دسترس نیست."


class AssessmentBlockedError(DandoonjanError):
    code = "ASSESSMENT_BLOCKED"
    user_message_fa = "ارزیابی این پرونده مسدود شده است."


class SafetyBlockedError(DandoonjanError):
    code = "SAFETY_BLOCKED"
    user_message_fa = "به دلایل ایمنی، گزارش این پرونده تولید نشد."


class StorageError(DandoonjanError):
    code = "STORAGE_ERROR"
    user_message_fa = "خطا در ذخیره‌سازی فایل."


class ModelProviderError(DandoonjanError):
    code = "MODEL_PROVIDER_ERROR"
    user_message_fa = "خطا در سرویس پردازش هوشمند."


class ProviderUnavailableError(ModelProviderError):
    """Real provider unreachable/timeout/429/5xx. Triggers visible Mock fallback
    at the AI worker boundary ONLY (never at assessment/policy level)."""
    code = "PROVIDER_UNAVAILABLE"


class CaseNotFoundError(DandoonjanError):
    code = "CASE_NOT_FOUND"
    user_message_fa = "پرونده پیدا نشد."
