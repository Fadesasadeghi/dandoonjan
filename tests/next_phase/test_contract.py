import pytest
from pydantic import ValidationError


def candidate():
    def statement(text, refs=()):
        return {'text':text,'source_refs':list(refs),'insufficient_support':True}
    return {'patient_summary': [statement('علائم گزارش‌شده نیازمند بررسی دندان‌پزشک است.', ['s1'])],
            'professional_report': [statement('برداشت شواهد برای تأیید علت علائم کافی نیست؛ ارزیابی بالینی لازم است.', ['s1'])],
            'diagnostic_hypotheses': [{'label': 'حساسیت دندانی', 'confidence_label': 'LOW',
            'supporting_evidence_refs': ['s1'], 'contradicting_evidence_refs': [],
            'missing_information': [statement('کفایت شواهد بالینی هنوز تأیید نشده است.')],
            'recommended_checks': [statement('درباره معاینه با دندان‌پزشک گفت‌وگو کنید.')], 'insufficient_support': True}],
            'safety_red_flags': [], 'limitations': [statement('این گزارش تشخیص قطعی نیست؛ برداشت نیازمند تأیید دندان‌پزشک است.')],
            'source_index': [{'source_ref': 's1'}]}


def test_contract_references_and_numeric_confidence():
    from app.ai.review_schema import validate_review
    value = candidate()
    assert validate_review(value, ['s1']).diagnostic_hypotheses[0].confidence_label == 'LOW'
    with pytest.raises(ValueError):
        validate_review(value, ['another-case'])
    value['diagnostic_hypotheses'][0]['confidence_label'] = 0.9
    with pytest.raises(ValidationError):
        validate_review(value, ['s1'])


@pytest.mark.parametrize('state', ['BLOCKED', 'MANUAL_REVIEW', 'URGENT_EVALUATION'])
def test_model_never_clears_restrictions(state):
    from app.ai.review_schema import escalated_state
    assert escalated_state(state, []) == state
    assert escalated_state(state, ['a concern']) == state


def test_unreferenced_assertion_and_prescription_rejected():
    from app.ai.review_schema import validate_review
    value = candidate()
    value['patient_summary'] = [{'text': 'Take amoxicillin', 'source_refs': ['s1'], 'insufficient_support': False}]
    with pytest.raises(ValueError):
        validate_review(value, ['s1'])


def test_safe_disclaimer_is_not_a_definitive_diagnosis():
    from app.ai.review_schema import validate_review, escalated_state
    value = candidate()
    value['limitations'] = [{'text':'این گزارش تشخیص قطعی نیست؛ برداشت نیازمند تأیید دندان‌پزشک است.', 'source_refs':[], 'insufficient_support':True}]
    assert validate_review(value, ['s1']).limitations
    assert escalated_state('NORMAL', ['concern']) == 'URGENT_EVALUATION'
    assert escalated_state('CAUTION', ['concern']) == 'URGENT_EVALUATION'
    value['patient_summary'] = [{'text': 'Something', 'source_refs': [], 'insufficient_support': False}]
    with pytest.raises(ValueError):
        validate_review(value, ['s1'])
