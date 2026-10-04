"""Explicit domain errors. Translated to safe user-facing states at the API layer."""
from __future__ import annotations


class DandoonjanError(Exception):
    code = "INTERNAL_ERROR"
    user_message_fa = "خطای داخلی سیستم. لطفاً دوباره تلاش کنید."


class UnsupportedArtifactError(DandoonjanError):
    code = "UNSUPPORTED_ARTIFACT"
    user_message_fa = "این نوع فایل پشتیبانی نمی‌شود."

    def __init__(self, message='', *, user_message_fa=None):
        super().__init__(message)
        if user_message_fa:
            self.user_message_fa = user_message_fa


class UnreadableArtifactError(DandoonjanError):
    code = "UNREADABLE_ARTIFACT"
    user_message_fa = "فایل قابل خواندن نیست یا خراب است."

    def __init__(self, message='', *, user_message_fa=None):
        super().__init__(message)
        if user_message_fa:
            self.user_message_fa = user_message_fa


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


class ProviderUnavailableError(ModelProviderError, ValueError):
    """Content-free real-provider failure; never authorizes a fallback."""
    code = "PROVIDER_UNAVAILABLE"
    CATEGORIES = frozenset({'configuration', 'authentication', 'timeout', 'rate_limit',
        'provider', 'malformed_envelope', 'schema', 'reference', 'safety'})

    def __init__(self, message=None, *, category='provider'):
        self.category = category if category in self.CATEGORIES else 'provider'
        super().__init__('REAL_PROVIDER_' + self.category.upper())



class CaseNotFoundError(DandoonjanError):
    code = "CASE_NOT_FOUND"
    user_message_fa = "پرونده پیدا نشد."
