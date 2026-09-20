"""Regression coverage for prompt templates containing literal JSON braces."""

from app.ai.prompts import Prompt, render_prompt


def test_literal_json_braces_are_not_treated_as_placeholders():
    prompt = Prompt(
        "brace-regression", "test-v1",
        'Return JSON like {"claim": {"status": "unknown"}}. DATA: {content}',
    )

    rendered = render_prompt(prompt, content='document has {"patient": "data"}')

    assert '{"claim": {"status": "unknown"}}' in rendered
    assert 'document has {"patient": "data"}' in rendered


def test_known_dynamic_substitution_still_works_without_recursive_rendering():
    prompt = Prompt("content", "test-v1", "DATA={content}")

    rendered = render_prompt(prompt, content="{content} stays literal in data")

    assert rendered == "DATA={content} stays literal in data"
