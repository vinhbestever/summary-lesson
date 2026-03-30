import json
import os
from typing import Any

from openai import OpenAI


def summarize_report(report_text: str) -> dict[str, Any]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    system_prompt = (
        'Ban la tro ly tom tat bao cao buoi hoc. '
        'Tra ve duy nhat JSON hop le voi 3 truong: '
        'overall_summary (string), key_points (array string), action_items (array string). '
        'Su dung tieng Viet ngan gon, ro rang.'
    )

    completion = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': report_text},
        ],
        temperature=0.2,
    )

    content = completion.choices[0].message.content
    if not content:
        raise ValueError('LLM returned an empty response')

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError('LLM output is not a JSON object')

    required_fields = ('overall_summary', 'key_points', 'action_items')
    for field in required_fields:
        if field not in parsed:
            raise ValueError(f'Missing field in LLM response: {field}')

    return {
        'overall_summary': str(parsed['overall_summary']).strip(),
        'key_points': [str(item).strip() for item in parsed['key_points']],
        'action_items': [str(item).strip() for item in parsed['action_items']],
    }
