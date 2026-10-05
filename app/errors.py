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

    def __init__(self, message='', *, failure_code=None, retry_after=None):
        super().__init__(message)
        self.failure_code = failure_code
        self.retry_after = retry_after


class ProcessingInputChangedError(DandoonjanError):
    code = 'PROCESSING_INPUT_CHANGED'
    user_message_fa = 'اطلاعات پرونده تغییر کرده است؛ نتیجهٔ این اجرا جاری نیست.'


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
        'provider', 'ambiguous_remote_outcome', 'incompatible_request',
        'malformed_envelope', 'schema', 'reference', 'safety', 'refusal',
        'truncation', 'cancelled', 'model_mismatch'})

    def __init__(self, message=None, *, category='provider', retry_after=None):
        self.category = category if category in self.CATEGORIES else 'provider'
        self.retry_after = retry_after if type(retry_after) is int and 0 <= retry_after <= 86400 else None
        super().__init__('REAL_PROVIDER_' + self.category.upper())



class CaseNotFoundError(DandoonjanError):
    code = "CASE_NOT_FOUND"
    user_message_fa = "پرونده پیدا نشد."
