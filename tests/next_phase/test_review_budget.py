"""Review generation bounds: synthetic completions, owned offline transport only."""
import json

import httpx
import pytest

from app.ai.providers import OpenRouterProvider
from app.ai.review_schema import ReviewOutput, validate_review
from app.errors import ProviderUnavailableError
from tests.next_phase.test_contract import candidate


def without_titles(value):
    if isinstance(value, dict):
        return {k: without_titles(v) for k, v in value.items() if k != 'title'}
    if isinstance(value, list):
        return [without_titles(v) for v in value]
    return value


def test_review_budget_and_lossless_schema_compaction(regression_settings):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'model': 'synthetic/fixed', 'choices': [
            {'finish_reason': 'stop', 'message': {'content': json.dumps(candidate())}}]})
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', offline_handler=handler)
    output = provider.review({'sources': [{'source_ref': 's1'}], 'text': [], 'images': []})
    assert validate_review(output, ['s1']).source_index[0].source_ref == 's1'
    payload = seen[0]
    assert payload['max_tokens'] == 1200
    assert payload['temperature'] == 0
    assert payload['response_format'] == {'type': 'json_object'}
    instructions = payload['messages'][0]['content']
    schema_text = instructions.split('Schema: ', 1)[1]
    assert json.loads(schema_text) == without_titles(ReviewOutput.model_json_schema())
    assert len(schema_text) < len(json.dumps(ReviewOutput.model_json_schema()))
    assert 'Keep every required field' in instructions
    assert 'Do not omit safety concerns or source refs to save space' in instructions


@pytest.mark.parametrize('finish', ['length', 'cancelled'])
def test_incomplete_review_rejected_even_when_json_is_valid(regression_settings, finish):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'model': 'synthetic/fixed', 'choices': [
            {'finish_reason': finish, 'message': {'content': json.dumps(candidate())}}]})
    provider = OpenRouterProvider('OFFLINE_TEST_ONLY', 'synthetic/fixed', offline_handler=handler)
    with pytest.raises(ProviderUnavailableError) as exc:
        provider.review({'sources': [{'source_ref': 's1'}], 'text': [], 'images': []})
    assert exc.value.category == {'length': 'truncation', 'cancelled': 'cancelled'}[finish]
    assert len(calls) == 1
