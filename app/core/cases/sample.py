"""Invented, nonclinical fixtures. The pattern is NOT a radiograph."""
import io
import pymupdf
from PIL import Image, ImageDraw

DEMO_MARKER = 'DANDOONJAN_SYNTHETIC_SAMPLE_V1'
DEMO_VERSION = 'demo-review-v2'
DEMO_MODEL = 'mock-evidence-v1'

PORTFOLIO_SCENARIOS = {
    'root_canal': {
        'title': 'درمان ریشه و روکش',
        'question': (
            'آیا مدارک ثبت‌شده توضیح می‌دهند چرا برای دندان ۴۶ '
            'عصب‌کشی و سپس روکش پیشنهاد شده است؟'
        ),
        'dossier': {
            'symptoms': 'حساسیت به سرما و درد در دندان ۴۶ — ساختگی',
            'duration': 'سه روز',
            'medical_history': 'سابقه پزشکی مرتبط گزارش نشده — ساختگی',
            'medications': 'ندارد',
            'allergies': 'ندارد',
            'treatment_plan': (
                'برای دندان ۴۶ درمان ریشه و سپس روکش پیشنهاد شده است.'
            ),
            'previous_reports': 'گزارش قبلی ثبت نشده است.',
            'previous_treatments': 'درمان قبلی مرتبط ثبت نشده است.',
        },
        'dentist_recommendation': (
            'عصب‌کشی دندان ۴۶ و روکش پس از درمان ریشه پیشنهاد شده است.'
        ),
        'treatment_plan': (
            'SYNTHETIC Treatment Plan\n'
            'Tooth 46: RCT recommended\n'
            'Tooth 46: Crown recommended after RCT\n'
            'For software testing only; not clinical evidence.\n'
        ),
    },
    'extraction_gap': {
        'title': 'کشیدن دندان و کمبود شواهد',
        'question': (
            'آیا مدارک موجود برای ارزیابی پیشنهاد کشیدن دندان ۳۶ '
            'کافی هستند؟'
        ),
        'dossier': {
            'symptoms': 'درد متناوب در ناحیه دندان ۳۶ — ساختگی',
            'duration': 'نامشخص',
            'medical_history': 'نامشخص',
            'medications': 'نامشخص',
            'allergies': 'نامشخص',
            'treatment_plan': 'کشیدن دندان ۳۶ پیشنهاد شده است.',
            'previous_reports': 'نامشخص',
            'previous_treatments': 'نامشخص',
        },
        'dentist_recommendation': 'کشیدن دندان ۳۶ پیشنهاد شده است.',
        'treatment_plan': (
            'SYNTHETIC Treatment Plan\n'
            'Tooth 36: Extraction recommended\n'
            'Clinical examination details are not included.\n'
            'Appropriate radiographic evidence is not included.\n'
            'For software testing only; not clinical evidence.\n'
        ),
    },
    'treatment_cost': {
        'title': 'بررسی طرح درمان و هزینه',
        'question': (
            'طرح درمان پیشنهادی برای دندان‌های ۴۶ و ۳۶ شامل چه درمان‌هایی '
            'است و چه هزینه‌ای ثبت شده است؟'
        ),
        'dossier': {
            'symptoms': (
                'برای بررسی طرح درمان و هزینه مراجعه شده است — ساختگی'
            ),
            'duration': 'ثبت نشده',
            'medical_history': 'سابقه پزشکی مرتبط گزارش نشده — ساختگی',
            'medications': 'ندارد',
            'allergies': 'ندارد',
            'treatment_plan': (
                'برای دندان ۴۶ درمان ریشه و روکش و برای دندان ۳۶ '
                'ترمیم پیشنهاد شده است.'
            ),
            'previous_reports': 'گزارش قبلی مرتبط ثبت نشده است.',
            'previous_treatments': 'درمان قبلی مرتبط ثبت نشده است.',
        },
        'dentist_recommendation': (
            'برای دندان ۴۶ عصب‌کشی و روکش و برای دندان ۳۶ '
            'ترمیم پیشنهاد شده است.'
        ),
        'treatment_plan': (
            'SYNTHETIC Treatment Plan and Estimate\n'
            'Tooth 46: RCT recommended\n'
            'Tooth 46: Crown recommended\n'
            'Tooth 36: Filling recommended\n'
            'Estimated total: 18,500,000 toman\n'
            'For software testing only; not clinical evidence.\n'
        ),
    },
}

DEFAULT_PORTFOLIO_SCENARIO = 'root_canal'

# Backwards-compatible fixture used by the existing demo/test routes.
SAMPLE_TEXT = PORTFOLIO_SCENARIOS[DEFAULT_PORTFOLIO_SCENARIO]['treatment_plan']


def is_demo(case):
    return case.demo_visitor is not None


def execution_identity(case):
    from app.config import get_settings
    settings = get_settings()
    return ('mock', DEMO_MODEL) if is_demo(case) else (settings.ai_provider, settings.ai_model_name)


def image_pattern():
    image = Image.new('RGB', (512, 384), '#242424')
    draw = ImageDraw.Draw(image)
    for x in range(32, 480, 32):
        draw.line((x, 48, x, 320), fill=(x // 2, x // 2, x // 2), width=12)
    draw.text((20, 20), 'SYNTHETIC TRANSPORT PATTERN - NOT A RADIOGRAPH', fill='white')
    output = io.BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()


def plan_pdf():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), 'SYNTHETIC Treatment Plan\nTooth 46: RCT recommended\nFor software testing only; not clinical evidence.')
        return doc.tobytes()
