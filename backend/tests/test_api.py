from fastapi.testclient import TestClient

from app.main import app, resolve_report_text
from app.schemas import SummaryRequest


client = TestClient(app)


def test_healthcheck_ok() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_create_summary_returns_expected_schema(monkeypatch) -> None:
    def fake_summary(_: str):
        return {
            'overall_summary': 'Buoi hoc tap trung vao phat am.',
            'key_points': ['Hoc vien doc doan van ngan.', 'Giao vien sua loi phat am.'],
            'action_items': ['On tap 10 tu moi.', 'Luyen doc 15 phut moi ngay.'],
        }

    monkeypatch.setattr('app.main.generate_summary', fake_summary)

    payload = {'report_text': 'Noi dung bao cao mau', 'lesson_id': 'TRIAL_LESSON_10_11'}
    response = client.post('/api/v1/summaries', json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body['overall_summary']
    assert isinstance(body['key_points'], list)
    assert isinstance(body['action_items'], list)


def test_create_summary_rejects_blank_report_text() -> None:
    response = client.post('/api/v1/summaries', json={'report_text': '   '})
    assert response.status_code == 422


def test_create_summary_accepts_report_url(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lay tu URL')
    monkeypatch.setattr(
        'app.main.generate_summary',
        lambda _: {
            'overall_summary': 'Tom tat URL',
            'key_points': ['A'],
            'action_items': ['B'],
        },
    )

    response = client.post('/api/v1/summaries', json={'report_url': 'https://example.com/report'})
    assert response.status_code == 200
    assert response.json()['overall_summary'] == 'Tom tat URL'


def test_create_summary_accepts_lesson_id(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lay tu lesson id')
    monkeypatch.setattr(
        'app.main.generate_summary',
        lambda _: {
            'overall_summary': 'Tom tat lesson',
            'key_points': ['A'],
            'action_items': ['B'],
        },
    )

    response = client.post('/api/v1/summaries', json={'lesson_id': '3724970'})
    assert response.status_code == 200
    assert response.json()['overall_summary'] == 'Tom tat lesson'


def test_resolve_report_text_prefers_local_lesson_json(monkeypatch) -> None:
    monkeypatch.setattr('app.main.load_lesson_json_from_local_data', lambda lesson_id: '{"reportId":"abc"}')

    def _unexpected_fetch(_: str) -> str:
        raise AssertionError('Should not call remote fetch when local lesson json exists')

    monkeypatch.setattr('app.main.fetch_report_text_from_url', _unexpected_fetch)

    payload = SummaryRequest(lesson_id='3724970')
    resolved = resolve_report_text(payload)
    assert resolved == '{"reportId":"abc"}'


def _feedback_payload() -> dict:
    return {
        'lesson_label': 'Lesson 1',
        'teacher_tone': 'warm_encouraging',
        'overall_comment': 'Con hoc rat tap trung.',
        'session_breakdown': {
            'participation': {'score': 85, 'comment': 'Tuong tac tot', 'evidence': ['45 luot noi']},
            'pronunciation': {'score': 72, 'comment': 'Can luyen am cuoi', 'evidence': ['diem trung binh 72']},
            'vocabulary': {'score': 80, 'comment': 'Nho tu kha tot', 'evidence': ['5 tu dat muc tot']},
            'grammar': {'score': 78, 'comment': 'Dung mau cau co ban', 'evidence': ['3 cau dat muc dat']},
            'reaction_confidence': {'score': 88, 'comment': 'Phan xa nhanh', 'evidence': ['reaction 1.5s']},
        },
        'strengths': ['Tu tin phat bieu', 'Nho tu nhanh'],
        'priority_improvements': [
            {
                'skill': 'pronunciation',
                'priority': 'high',
                'current_state': 'Am cuoi con bo sot',
                'target_next_lesson': 'Dat >=80',
                'coach_tip': 'Luyen shadowing 10 phut/ngay',
            },
        ],
        'next_lesson_plan': [
            {'step': 'On lai tu cu', 'duration_minutes': 8},
            {'step': 'Luyen am kho', 'duration_minutes': 10},
        ],
        'parent_message': 'Con dang tien bo rat tot, ba me tiep tuc dong hanh nhe.',
    }


def test_create_lesson_feedback_returns_schema(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung bao cao')
    monkeypatch.setattr('app.main.generate_lesson_feedback', lambda _text, _label: _feedback_payload(), raising=False)

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})

    assert response.status_code == 200
    body = response.json()
    assert body['lesson_label'] == 'Lesson 1'
    assert body['teacher_tone'] == 'warm_encouraging'
    assert body['overall_comment']
    for key in ['participation', 'pronunciation', 'vocabulary', 'grammar', 'reaction_confidence']:
        assert key in body['session_breakdown']
        assert 0 <= body['session_breakdown'][key]['score'] <= 100
    assert isinstance(body['strengths'], list)
    assert isinstance(body['priority_improvements'], list)
    assert isinstance(body['next_lesson_plan'], list)
    assert isinstance(body['parent_message'], str)


def test_generate_lesson_feedback_uses_warm_teacher_prompt(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    captured = {'messages': []}

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            captured['messages'] = kwargs['messages']

            class _Message:
                content = (
                    '{"lesson_label":"Lesson 1","teacher_tone":"warm_encouraging","overall_comment":"ok",'
                    '"session_breakdown":{"participation":{"score":80,"comment":"ok","evidence":["e1"]},'
                    '"pronunciation":{"score":70,"comment":"ok","evidence":["e2"]},'
                    '"vocabulary":{"score":75,"comment":"ok","evidence":["e3"]},'
                    '"grammar":{"score":78,"comment":"ok","evidence":["e4"]},'
                    '"reaction_confidence":{"score":82,"comment":"ok","evidence":["e5"]}},'
                    '"strengths":["s1"],'
                    '"priority_improvements":[{"skill":"pronunciation","priority":"high","current_state":"c",'
                    '"target_next_lesson":"t","coach_tip":"tip"}],'
                    '"next_lesson_plan":[{"step":"step1","duration_minutes":10}],"parent_message":"msg"}'
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == 'test-key'
            self.chat = _FakeChat()

    monkeypatch.setattr('app.llm.OpenAI', _FakeOpenAI)

    from app.llm import generate_lesson_feedback as generate_lesson_feedback_from_llm

    result = generate_lesson_feedback_from_llm('Noi dung report', lesson_label='Lesson 1')

    system_prompt = captured['messages'][0]['content'].lower()
    assert 'am ap' in system_prompt
    assert result['teacher_tone'] == 'warm_encouraging'
    assert result['lesson_label'] == 'Lesson 1'


def test_generate_lesson_feedback_filters_invalid_priority_improvements(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = (
                    '{"lesson_label":"Lesson 1","teacher_tone":"warm_encouraging","overall_comment":"ok",'
                    '"session_breakdown":{"participation":{"score":80,"comment":"ok","evidence":["e1"]},'
                    '"pronunciation":{"score":70,"comment":"ok","evidence":["e2"]},'
                    '"vocabulary":{"score":75,"comment":"ok","evidence":["e3"]},'
                    '"grammar":{"score":78,"comment":"ok","evidence":["e4"]},'
                    '"reaction_confidence":{"score":82,"comment":"ok","evidence":["e5"]}},'
                    '"strengths":["s1"],'
                    '"priority_improvements":[{"skill":"chua du du lieu","priority":"chua du du lieu","current_state":"c",'
                    '"target_next_lesson":"t","coach_tip":"tip"},'
                    '{"skill":"pronunciation","priority":"high","current_state":"c2","target_next_lesson":"t2","coach_tip":"tip2"}],'
                    '"next_lesson_plan":[{"step":"step1","duration_minutes":10}],"parent_message":"msg"}'
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == 'test-key'
            self.chat = _FakeChat()

    monkeypatch.setattr('app.llm.OpenAI', _FakeOpenAI)

    from app.llm import generate_lesson_feedback as generate_lesson_feedback_from_llm

    result = generate_lesson_feedback_from_llm('Noi dung report', lesson_label='Lesson 1')
    assert len(result['priority_improvements']) == 1
    assert result['priority_improvements'][0]['skill'] == 'pronunciation'
    assert result['priority_improvements'][0]['priority'] == 'high'


def test_generate_lesson_feedback_fills_next_plan_when_empty(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = (
                    '{"lesson_label":"Lesson 1","teacher_tone":"warm_encouraging","overall_comment":"ok",'
                    '"session_breakdown":{"participation":{"score":80,"comment":"ok","evidence":["e1"]},'
                    '"pronunciation":{"score":70,"comment":"ok","evidence":["e2"]},'
                    '"vocabulary":{"score":75,"comment":"ok","evidence":["e3"]},'
                    '"grammar":{"score":78,"comment":"ok","evidence":["e4"]},'
                    '"reaction_confidence":{"score":82,"comment":"ok","evidence":["e5"]}},'
                    '"strengths":["s1"],'
                    '"priority_improvements":[{"skill":"pronunciation","priority":"high","current_state":"c",'
                    '"target_next_lesson":"t","coach_tip":"tip"}],'
                    '"next_lesson_plan":[],"parent_message":"msg"}'
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == 'test-key'
            self.chat = _FakeChat()

    monkeypatch.setattr('app.llm.OpenAI', _FakeOpenAI)

    from app.llm import generate_lesson_feedback as generate_lesson_feedback_from_llm

    result = generate_lesson_feedback_from_llm('Noi dung report', lesson_label='Lesson 1')
    assert len(result['next_lesson_plan']) >= 1
    assert result['next_lesson_plan'][0]['step']


def test_create_lesson_feedback_with_lesson_id_success(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lesson id')
    monkeypatch.setattr('app.main.generate_lesson_feedback', lambda _text, _label: _feedback_payload(), raising=False)

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    assert response.status_code == 200
    assert response.json()['lesson_label'] == 'Lesson 1'


def test_create_lesson_feedback_returns_400_when_no_input() -> None:
    response = client.post('/api/v1/lesson-feedback', json={'lesson_label': 'Lesson 1'})
    assert response.status_code == 422


def test_create_lesson_feedback_returns_502_when_fetch_fails(monkeypatch) -> None:
    def _raise_http_error(payload):
        raise RuntimeError('fetch failed')

    monkeypatch.setattr('app.main.resolve_report_text', _raise_http_error)
    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970'})
    assert response.status_code in [500, 502]


def test_create_lesson_feedback_returns_500_when_llm_invalid(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lesson id')

    def _raise_invalid(_text, _label):
        raise ValueError('invalid json')

    monkeypatch.setattr('app.main.generate_lesson_feedback', _raise_invalid, raising=False)
    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970'})
    assert response.status_code in [500, 502]


def test_create_lesson_feedback_stream_returns_events(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lesson id')

    def _fake_stream(_text, _label):
        yield {'type': 'status', 'message': 'Dang phan tich'}
        yield {'type': 'result', 'data': _feedback_payload()}

    monkeypatch.setattr('app.main.stream_lesson_feedback', _fake_stream, raising=False)
    response = client.post('/api/v1/lesson-feedback/stream', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    assert response.status_code == 200
    assert 'event: status' in response.text
    assert 'event: result' in response.text
    assert 'event: done' in response.text
