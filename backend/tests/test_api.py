import json

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


def test_load_all_lessons_json_from_local_data_returns_sorted_items() -> None:
    from app.ingest import load_all_lessons_json_from_local_data

    items = load_all_lessons_json_from_local_data()

    assert len(items) >= 2
    assert all('lesson_id' in item for item in items)
    assert all('source_file' in item for item in items)
    assert all('raw_json_text' in item for item in items)
    assert all(item['raw_json_text'].strip() for item in items)

    source_files = [item['source_file'] for item in items]
    assert source_files == sorted(source_files)
    assert any(item['lesson_id'] == '3724970' for item in items)


def _feedback_payload() -> dict:
    return {
        'lesson_label': 'Lesson 1',
        'teacher_tone': 'warm_encouraging',
        'overall_comment': 'Con hoc rat tap trung.',
        'session_breakdown': {
            'proficiency': {'score': 72, 'comment': 'Nen tang con dao dong', 'evidence': ['diem noi/doc trung binh 72']},
            'capacity': {'score': 78, 'comment': 'Theo kip tien do co ban', 'evidence': ['sections_completion 78%']},
            'engagement': {'score': 85, 'comment': 'Tuong tac tot', 'evidence': ['45 luot noi']},
            'self_regulation': {'score': 70, 'comment': 'Can nhac nhap bai', 'evidence': ['it dau hieu tu kiem tra']},
        },
        'strengths': ['Tu tin phat bieu', 'Nho tu nhanh'],
        'priority_improvements': [
            {
                'skill': 'proficiency',
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


def _portfolio_feedback_payload() -> dict:
    return {
        'portfolio_label': 'Tong hop toan bo buoi hoc',
        'total_lessons': 2,
        'date_range': {'from_date': '2026-03-01', 'to_date': '2026-03-31'},
        'overall_assessment': 'Hoc vien tien bo on dinh qua cac buoi.',
        'skill_trends': {
            'proficiency': {
                'current_level': 'meets_expectation',
                'trend': 'stable',
                'evidence': ['Diem noi/doc on dinh qua cac buoi'],
                'recommendation': 'Cung co tu va cau mau trong tam',
            },
            'capacity': {
                'current_level': 'meets_expectation',
                'trend': 'improving',
                'evidence': ['Hoan thanh phan co ban dung tien do'],
                'recommendation': 'Tang nhip tiep thu khi co hoat dong moi',
            },
            'engagement': {
                'current_level': 'exceeds_expectation',
                'trend': 'improving',
                'evidence': ['Tang so luot phat bieu va hoi dap nhanh'],
                'recommendation': 'Duy tri tham gia chu dong',
            },
            'self_regulation': {
                'current_level': 'needs_improvement',
                'trend': 'mixed',
                'evidence': ['Doi khi can nhac de vao bai'],
                'recommendation': 'Luyen tu kiem tra truoc khi nop bai',
            },
        },
        'top_strengths': ['Tu tin phat bieu', 'Nho tu nhanh'],
        'top_priorities': [
            {
                'skill': 'proficiency',
                'priority': 'high',
                'reason': 'Nen tang ki thuat con dao dong',
                'next_2_weeks_target': 'On dinh diem noi/doc va giam loi lap lai',
                'coach_tip': 'Luyen cap toi thieu 10 phut moi ngay',
            }
        ],
        'study_plan_2_weeks': [
            {'step': 'On tu theo chu de', 'frequency': '4 buoi/tuan', 'duration_minutes': 10}
        ],
        'parent_message': 'Con dang tien bo tot, gia dinh tiep tuc dong hanh.',
    }


def test_portfolio_feedback_response_schema() -> None:
    from app.schemas import PortfolioFeedbackResponse

    payload = PortfolioFeedbackResponse(**_portfolio_feedback_payload())
    assert payload.total_lessons == 2
    assert payload.skill_trends.proficiency.trend == 'stable'
    assert payload.top_priorities[0].skill == 'proficiency'


def test_create_lesson_feedback_returns_markdown_text_response(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung bao cao')
    monkeypatch.setattr(
        'app.main.generate_lesson_feedback',
        lambda _text, _label: '# Nhan xet buoi hoc - Lesson 1\n\n## Tong quan\n\n- Con hoc rat tap trung.',
        raising=False,
    )

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/markdown')
    assert '# Nhan xet buoi hoc - Lesson 1' in response.text


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
                    '"session_breakdown":{"proficiency":{"score":70,"comment":"ok","evidence":["e1"]},'
                    '"capacity":{"score":75,"comment":"ok","evidence":["e2"]},'
                    '"engagement":{"score":80,"comment":"ok","evidence":["e3"]},'
                    '"self_regulation":{"score":72,"comment":"ok","evidence":["e4"]}},'
                    '"strengths":["s1"],'
                    '"priority_improvements":[{"skill":"proficiency","priority":"high","current_state":"c",'
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
    user_payload = json.loads(captured['messages'][1]['content'])
    assert 'ấm áp' in system_prompt
    assert 'recent_lessons' in system_prompt
    assert 'buổi học đầu tiên' in system_prompt
    assert 'so sánh buổi gần đây' in system_prompt
    assert '## so sánh buổi gần đây' in system_prompt
    assert '- nghe:' in system_prompt
    assert '- nói:' in system_prompt
    assert '- đọc:' in system_prompt
    assert 'tốt:' in system_prompt
    assert 'chưa tốt:' in system_prompt
    assert 'yếu:' in system_prompt
    assert 'reading_fluency' in system_prompt
    assert 'lesson_skill_context' in system_prompt
    assert '4 tiêu chí' in system_prompt
    assert 'proficiency' in system_prompt
    assert 'self-regulation' in system_prompt or 'self regulation' in system_prompt
    assert 'độ tin cậy' in system_prompt
    assert 'củng cố đánh giá' in system_prompt
    assert isinstance(user_payload.get('lesson_input'), str)
    assert isinstance(result, str)
    assert result


def test_build_lesson_feedback_messages_parses_json_input_payload() -> None:
    from app.llm import _build_lesson_feedback_messages

    messages = _build_lesson_feedback_messages('{"current_lesson_data":{"a":1}}', lesson_label='Lesson 1')
    payload = json.loads(messages[1]['content'])

    assert isinstance(payload.get('lesson_input'), dict)
    assert payload['lesson_input']['current_lesson_data']['a'] == 1


def test_generate_lesson_feedback_returns_plain_markdown_text(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = '# Nhan xet buoi hoc - Lesson 1\n\n- Con tien bo'

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
    assert isinstance(result, str)
    assert result.startswith('#')


def test_generate_lesson_feedback_raises_on_empty_response(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = ''

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

    import pytest

    with pytest.raises(ValueError, match='empty response'):
        generate_lesson_feedback_from_llm('Noi dung report', lesson_label='Lesson 1')


def test_generate_portfolio_feedback_returns_markdown_text(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = '# Nhan xet chung qua trinh hoc\n\n- Tong quan tien bo on dinh'

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

    from app.llm import generate_portfolio_feedback

    result = generate_portfolio_feedback([{'lesson_id': '1', 'raw_json_text': '{}', 'source_file': 'lesson_1.json'}])
    assert isinstance(result, str)
    assert result.startswith('#')


def test_build_portfolio_input_context_extracts_lesson_metrics() -> None:
    from app.llm import _build_portfolio_input_context

    lessons_payload = [
        {
            'lesson_id': '3724970',
            'source_file': 'lesson_3724970.json',
            'raw_json_text': '{"achievements":{"stats":{"speakingTurnCount":45,"averageReactionTimeMs":1543,"sectionsCompletionPercent":71,"teacherComment":"Can cai thien phat am"},"pronunciation":{"averagePronunciationScore":38.67}}}',
        },
        {
            'lesson_id': 'TRIAL_LESSON_10_11',
            'source_file': 'lesson_TRIAL_LESSON_10_11.json',
            'raw_json_text': '[{"achievements":{"stats":{"speakingTurnCount":20,"averageReactionTimeMs":2000.2,"sectionsCompletionPercent":57,"teacherComment":"Phat am kha on"},"pronunciation":{"averagePronunciationScore":86.26}}}]',
        },
    ]

    context = _build_portfolio_input_context(lessons_payload)

    assert context['total_lessons'] == 2
    assert len(context['lesson_summaries']) == 2
    assert context['lesson_summaries'][0]['lesson_id'] == '3724970'
    assert context['lesson_summaries'][1]['lesson_id'] == 'TRIAL_LESSON_10_11'
    assert context['aggregates']['speaking_turn_avg'] >= 30
    assert context['aggregates']['reaction_time_avg_ms'] >= 1500
    assert len(context['evidence_highlights']) >= 2


def test_build_portfolio_feedback_messages_has_deep_detail_contract() -> None:
    import json

    from app.llm import _build_portfolio_feedback_messages

    lessons_payload = [
        {
            'lesson_id': '3724970',
            'source_file': 'lesson_3724970.json',
            'raw_json_text': '{"achievements":{"stats":{"speakingTurnCount":45},"pronunciation":{"averagePronunciationScore":38.67}}}',
        }
    ]

    messages = _build_portfolio_feedback_messages(lessons_payload, portfolio_label='Tong hop toan bo')
    system_prompt = messages[0]['content']
    user_payload = json.loads(messages[1]['content'])

    assert 'Chỉ trả về markdown' in system_prompt
    assert '## Đánh giá 4 tiêu chí in-class' in system_prompt
    assert '## Kế hoạch 2 tuần' in system_prompt
    assert 'A->D' in system_prompt
    assert 'Kết quả hiện tại' in system_prompt
    assert '## Ưu tiên can thiệp' in system_prompt
    assert '## Xu hướng tiến bộ' in system_prompt
    assert '## Phong cách học hiện tại' in system_prompt
    assert 'portfolio_context' in user_payload
    assert user_payload['portfolio_context']['total_lessons'] == 1
    assert 'Độ tin cậy kết luận' in system_prompt
    assert 'Cách củng cố đánh giá' in system_prompt


def test_select_recent_portfolio_lessons_excludes_trial_and_limits_to_8() -> None:
    from app.main import _select_recent_portfolio_lessons

    def _lesson_item(lesson_id: str, start_time: str | None) -> dict[str, str]:
        if start_time is None:
            raw_json_text = '{"lessonTime":{}}'
        else:
            raw_json_text = json.dumps({'lessonTime': {'lessonStartTime': start_time}})
        return {
            'lesson_id': lesson_id,
            'source_file': f'lesson_{lesson_id}.json',
            'raw_json_text': raw_json_text,
        }

    lessons_payload = [
        _lesson_item('TRIAL_LESSON_1', '2026-03-31 09:00:00'),
        _lesson_item('100', '2026-03-31 10:00:00'),
        _lesson_item('101', '2026-03-30 10:00:00'),
        _lesson_item('102', '2026-03-29 10:00:00'),
        _lesson_item('103', '2026-03-28 10:00:00'),
        _lesson_item('104', '2026-03-27 10:00:00'),
        _lesson_item('105', '2026-03-26 10:00:00'),
        _lesson_item('106', '2026-03-25 10:00:00'),
        _lesson_item('107', '2026-03-24 10:00:00'),
        _lesson_item('999', None),
        _lesson_item('108', '2026-03-23 10:00:00'),
    ]

    selected = _select_recent_portfolio_lessons(lessons_payload, limit=8)
    selected_ids = [item['lesson_id'] for item in selected]

    assert len(selected_ids) == 8
    assert not any(lesson_id.startswith('TRIAL_') for lesson_id in selected_ids)
    assert selected_ids == ['100', '101', '102', '103', '104', '105', '106', '107']


def test_stream_portfolio_feedback_emits_chunk_events(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _Delta:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            if kwargs.get('stream'):
                return iter(
                    [
                        _Chunk(
                            '{"portfolio_label":"Tong hop","total_lessons":2,'
                            '"date_range":{"from_date":"2026-03-01","to_date":"2026-03-31"},'
                            '"overall_assessment":"Tien bo on dinh","skill_trends":{"proficiency":{"current_level":"meets","trend":"improving","evidence":["e1"],"recommendation":"r1"},'
                            '"capacity":{"current_level":"meets","trend":"stable","evidence":["e2"],"recommendation":"r2"},'
                            '"engagement":{"current_level":"exceeds","trend":"improving","evidence":["e3"],"recommendation":"r3"},'
                            '"self_regulation":{"current_level":"needs","trend":"mixed","evidence":["e4"],"recommendation":"r4"}},'
                            '"top_strengths":["s1"],"top_priorities":[{"skill":"proficiency","priority":"high","reason":"x","next_2_weeks_target":"y","coach_tip":"z"}],'
                            '"study_plan_2_weeks":['
                            '{"step":"On tu","frequency":"4 buoi/tuan","duration_minutes":10},'
                            '{"step":"Luyen am cuoi","frequency":"4 buoi/tuan","duration_minutes":12},'
                            '{"step":"Luyen hoi dap","frequency":"3 buoi/tuan","duration_minutes":10},'
                            '{"step":"On grammar","frequency":"3 buoi/tuan","duration_minutes":10}'
                            '],'
                            '"parent_message":"msg"}'
                        )
                    ]
                )
            raise AssertionError('Expected stream=True')

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == 'test-key'
            self.chat = _FakeChat()

    monkeypatch.setattr('app.llm.OpenAI', _FakeOpenAI)

    from app.llm import stream_portfolio_feedback

    events = list(stream_portfolio_feedback([{'lesson_id': '1', 'raw_json_text': '{}', 'source_file': 'lesson_1.json'}]))
    assert events[0]['type'] == 'status'
    assert any(event['type'] == 'chunk' for event in events)
    result_events = [event for event in events if event['type'] == 'result']
    assert len(result_events) == 0


def test_generate_portfolio_feedback_single_call_no_repair(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    call_count = {'count': 0}

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            call_count['count'] += 1

            class _Message:
                if call_count['count'] == 1:
                    content = (
                        '{"portfolio_label":"Tong hop","total_lessons":2,'
                        '"date_range":{"from_date":"","to_date":""},'
                        '"overall_assessment":"Du lieu con thieu o mot so muc, can theo doi them de ket luan chac chan.",'
                        '"skill_trends":{'
                        '"proficiency":{"current_level":"","trend":"stable","evidence":[],"recommendation":""},'
                        '"capacity":{"current_level":"","trend":"stable","evidence":[],"recommendation":""},'
                        '"engagement":{"current_level":"","trend":"stable","evidence":[],"recommendation":""},'
                        '"self_regulation":{"current_level":"","trend":"stable","evidence":[],"recommendation":""}'
                        '},'
                        '"top_strengths":[],'
                        '"top_priorities":[],'
                        '"study_plan_2_weeks":[],'
                        '"parent_message":"Can bo sung du lieu o cac buoi tiep theo de co ke hoach sat hon."}'
                    )
                else:
                    content = (
                        '{"portfolio_label":"Tong hop","total_lessons":2,'
                        '"date_range":{"from_date":"","to_date":""},'
                        '"overall_assessment":"Da bo sung ke hoach tu du lieu co san.",'
                        '"skill_trends":{'
                        '"proficiency":{"current_level":"meets","trend":"stable","evidence":["lesson_1 pronunciation 65"],"recommendation":"Cung co noi doc"},'
                        '"capacity":{"current_level":"meets","trend":"stable","evidence":["lesson_1 completion 78"],"recommendation":"Theo kip tien do"},'
                        '"engagement":{"current_level":"kha","trend":"stable","evidence":["lesson_1 speaking turn 20"],"recommendation":"Tang luot hoi dap"},'
                        '"self_regulation":{"current_level":"tb","trend":"stable","evidence":["lesson_1 reaction 1800"],"recommendation":"Tu vao bai nhanh hon"}'
                        '},'
                        '"top_strengths":["Con phan xa kha nhanh"],'
                        '"top_priorities":[{"skill":"proficiency","priority":"high","reason":"Can tang do on dinh","next_2_weeks_target":"Dat 75+","coach_tip":"10 phut moi ngay"}],'
                        '"study_plan_2_weeks":['
                        '{"step":"Ngay 1-2: Luyen phat am am cuoi theo shadowing","frequency":"4 buoi/tuan","duration_minutes":12},'
                        '{"step":"Ngay 3-4: On tu vung theo speaking turn hien tai","frequency":"4 buoi/tuan","duration_minutes":10},'
                        '{"step":"Ngay 5-6: Luyen hoi dap ngan de tang participation","frequency":"3 buoi/tuan","duration_minutes":12},'
                        '{"step":"Ngay 7-8: Luyen pattern grammar co ban theo tinh huong","frequency":"3 buoi/tuan","duration_minutes":10}'
                        '],'
                        '"parent_message":"Gia dinh giup con on tap deu moi ngay."}'
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

    from app.llm import generate_portfolio_feedback

    result = generate_portfolio_feedback([{'lesson_id': '1', 'raw_json_text': '{}', 'source_file': 'lesson_1.json'}])
    assert call_count['count'] == 1
    assert isinstance(result, str)


def test_create_lesson_feedback_with_lesson_id_success(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lesson id')
    monkeypatch.setattr(
        'app.main.generate_lesson_feedback',
        lambda _text, _label: '# Nhan xet buoi hoc - Lesson 1\n\n- Noi dung',
        raising=False,
    )

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    assert response.status_code == 200
    assert '# Nhan xet buoi hoc - Lesson 1' in response.text


def test_lesson_feedback_cache_key_uses_version_prefix() -> None:
    from app.feedback_cache import LESSON_FEEDBACK_CACHE_VERSION, lesson_feedback_cache_key

    key = lesson_feedback_cache_key('3724970', None, None, 'Lesson 1')
    assert key.startswith(f'lesson_{LESSON_FEEDBACK_CACHE_VERSION}_')


def test_create_lesson_feedback_uses_cache_when_available(monkeypatch) -> None:
    from app.feedback_cache import lesson_feedback_cache_key, write_feedback_cache

    cache_key = lesson_feedback_cache_key('3724970', None, None, 'Lesson 1')
    write_feedback_cache(cache_key, '# Cached lesson markdown')

    def _should_not_call(_text, _label):
        raise AssertionError('LLM should not be called on cache hit')

    monkeypatch.setattr('app.main.generate_lesson_feedback', _should_not_call, raising=False)

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    assert response.status_code == 200
    assert response.text.strip() == '# Cached lesson markdown'


def test_create_lesson_feedback_writes_cache_and_reuses(monkeypatch) -> None:
    call_count = {'count': 0}
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung lesson id')

    def _fake_generate(_text, _label):
        call_count['count'] += 1
        return '# Generated lesson markdown'

    monkeypatch.setattr('app.main.generate_lesson_feedback', _fake_generate, raising=False)

    first = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    second = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.text.strip().startswith('# Generated lesson markdown')
    assert 'Phụ lục (hệ thống)' in first.text
    assert first.text.strip() == second.text.strip()
    assert call_count['count'] == 1


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


def test_create_lesson_feedback_stream_uses_cache_when_available(monkeypatch) -> None:
    from app.feedback_cache import lesson_feedback_cache_key, write_feedback_cache

    cache_key = lesson_feedback_cache_key('3724970', None, None, 'Lesson 1')
    write_feedback_cache(cache_key, '# Cached stream lesson markdown')

    def _should_not_stream(_text, _label):
        raise AssertionError('LLM stream should not be called on cache hit')
        yield {'type': 'chunk', 'content': 'unreachable'}

    monkeypatch.setattr('app.main.stream_lesson_feedback', _should_not_stream, raising=False)

    response = client.post('/api/v1/lesson-feedback/stream', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})
    assert response.status_code == 200
    assert 'event: status' in response.text
    assert 'cache' in response.text.lower()
    assert 'data: # Cached stream lesson markdown' in response.text
    assert '"type": "lesson_radar"' in response.text
    assert 'event: done' in response.text


def test_create_portfolio_feedback_success(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [{'lesson_id': '3724970', 'source_file': 'lesson_3724970.json', 'raw_json_text': '{"ok":true}'}],
    )
    monkeypatch.setattr(
        'app.main.generate_portfolio_feedback',
        lambda _lessons, _label, **_kwargs: '# Nhan xet chung qua trinh hoc\n\n- Tong so buoi: 2',
        raising=False,
    )

    response = client.post('/api/v1/portfolio-feedback', json={'portfolio_label': 'Tong hop toan bo'})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/markdown')
    assert '# Nhan xet chung qua trinh hoc' in response.text


def test_create_portfolio_feedback_uses_cache_when_available(monkeypatch) -> None:
    from app.feedback_cache import portfolio_feedback_cache_key, write_feedback_cache

    write_feedback_cache(portfolio_feedback_cache_key(), '# Cached portfolio markdown')

    def _should_not_call(_payload, _label):
        raise AssertionError('LLM should not be called on cache hit')

    monkeypatch.setattr('app.main.generate_portfolio_feedback', _should_not_call, raising=False)

    response = client.post('/api/v1/portfolio-feedback', json={'portfolio_label': 'Tong hop toan bo'})
    assert response.status_code == 200
    assert response.text.strip() == '# Cached portfolio markdown'


def test_create_portfolio_feedback_stream_returns_events(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [{'lesson_id': '3724970', 'source_file': 'lesson_3724970.json', 'raw_json_text': '{"ok":true}'}],
    )

    def _fake_stream(_lessons, _label, **_kwargs):
        yield {'type': 'status', 'message': 'Dang phan tich'}
        yield {'type': 'result', 'data': _portfolio_feedback_payload()}

    monkeypatch.setattr('app.main.stream_portfolio_feedback', _fake_stream, raising=False)
    response = client.post('/api/v1/portfolio-feedback/stream', json={'portfolio_label': 'Tong hop toan bo'})
    assert response.status_code == 200
    assert 'event: status' in response.text
    assert 'event: result' in response.text
    assert 'event: done' in response.text


def test_create_portfolio_feedback_stream_writes_cache_and_reuses(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [{'lesson_id': '3724970', 'source_file': 'lesson_3724970.json', 'raw_json_text': '{"ok":true}'}],
    )
    call_count = {'count': 0}

    def _fake_stream(_lessons, _label, **_kwargs):
        call_count['count'] += 1
        yield {'type': 'status', 'message': 'Dang tao'}
        yield {'type': 'chunk', 'content': '# Generated portfolio markdown'}

    monkeypatch.setattr('app.main.stream_portfolio_feedback', _fake_stream, raising=False)

    first = client.post('/api/v1/portfolio-feedback/stream', json={'portfolio_label': 'Tong hop toan bo'})
    second = client.post('/api/v1/portfolio-feedback/stream', json={'portfolio_label': 'Tong hop toan bo'})

    assert first.status_code == 200
    assert second.status_code == 200
    assert 'data: # Generated portfolio markdown' in first.text
    assert 'event: result' in first.text
    assert '"type": "lesson_radar"' in first.text
    assert 'cache' in second.text.lower()
    assert 'data: # Generated portfolio markdown' in second.text
    assert 'event: result' in second.text
    assert '"type": "lesson_radar"' in second.text
    assert call_count['count'] == 1


def test_create_portfolio_feedback_returns_400_when_no_local_lesson(monkeypatch) -> None:
    monkeypatch.setattr('app.main.load_all_lessons_json_from_local_data', lambda: [])

    response = client.post('/api/v1/portfolio-feedback', json={})
    assert response.status_code == 400


def test_create_lesson_feedback_returns_markdown(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung bao cao')
    monkeypatch.setattr(
        'app.main.generate_lesson_feedback',
        lambda _text, _label: '# Nhan xet\n\n- Noi dung',
        raising=False,
    )

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '3724970', 'lesson_label': 'Lesson 1'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/markdown')
    assert '# Nhan xet' in response.text


def test_create_portfolio_feedback_returns_markdown(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [{'lesson_id': '1', 'source_file': 'a.json', 'raw_json_text': '{}'}],
    )
    monkeypatch.setattr(
        'app.main.generate_portfolio_feedback',
        lambda _payload, _label, **_kwargs: '# Tong ket\n\n- Noi dung',
        raising=False,
    )

    response = client.post('/api/v1/portfolio-feedback', json={'portfolio_label': 'Tong hop'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/markdown')
    assert '# Tong ket' in response.text


def test_lesson_feedback_stream_emits_raw_text_chunks(monkeypatch) -> None:
    monkeypatch.setattr('app.main.resolve_report_text', lambda payload: 'Noi dung')

    def _fake_stream(_text, _label):
        yield {'type': 'status', 'message': 'Dang tao'}
        yield {'type': 'chunk', 'content': '# Nhan xet'}

    monkeypatch.setattr('app.main.stream_lesson_feedback', _fake_stream, raising=False)

    response = client.post('/api/v1/lesson-feedback/stream', json={'lesson_id': '3724970'})

    assert response.status_code == 200
    body = response.text
    assert 'event: chunk' in body
    assert 'data: # Nhan xet' in body
    assert '"type": "lesson_radar"' in body
    assert 'event: done' in body


def test_build_lesson_radar_payload_extracts_scores_and_levels() -> None:
    from app.main import _build_lesson_radar_payload

    markdown = (
        '## Đánh giá 4 tiêu chí in-class\n\n'
        '- A. Proficiency - Nen tang kien thuc\n'
        '  - Kết quả hiện tại: Meets Expectation (65/100)\n\n'
        '- B. Capacity - Tiep thu va tien do\n'
        '  - Kết quả hiện tại: Exceeds Expectation\n\n'
        '- C. Engagement - Tuong tac\n'
        '  - Kết quả hiện tại: chưa đủ dữ liệu\n'
    )

    payload = _build_lesson_radar_payload(markdown)
    competencies = {item['key']: item for item in payload['competencies']}

    assert payload['type'] == 'lesson_radar'
    assert len(payload['competencies']) == 4
    assert competencies['proficiency']['score'] == 65
    assert competencies['proficiency']['insufficient_data'] is False
    assert competencies['capacity']['score'] == 90
    assert competencies['capacity']['level_text'] == 'Exceeds Expectation'
    assert competencies['engagement']['score'] == 0
    assert competencies['engagement']['insufficient_data'] is True


def test_build_lesson_radar_payload_accepts_competency_without_letter_prefix() -> None:
    from app.main import _build_lesson_radar_payload

    markdown = (
        '## Đánh giá 4 tiêu chí in-class\n\n'
        '- Proficiency – Năng lực kiến thức\n'
        '  - Kết quả hiện tại: Needs Improvement\n\n'
        '- Self-regulation – Tự điều chỉnh\n'
        '  - Kết quả hiện tại: 74/100\n'
    )

    payload = _build_lesson_radar_payload(markdown)
    competencies = {item['key']: item for item in payload['competencies']}
    assert competencies['proficiency']['score'] == 25
    assert competencies['self_regulation']['score'] == 74


def test_build_lesson_radar_payload_maps_legacy_six_competencies_to_four() -> None:
    from app.main import _build_lesson_radar_payload

    markdown = (
        '## Đánh giá 6 năng lực\n\n'
        '- Learn – Học và tiếp thu\n'
        '  - Kết quả hiện tại: 76/100\n\n'
        '- Focus – Chú ý\n'
        '  - Kết quả hiện tại: Khá vững\n'
    )

    payload = _build_lesson_radar_payload(markdown)
    competencies = {item['key']: item for item in payload['competencies']}
    assert competencies['proficiency']['score'] == 76
    assert competencies['self_regulation']['score'] == 80


def test_portfolio_feedback_stream_emits_raw_text_chunks(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [{'lesson_id': '1', 'source_file': 'a.json', 'raw_json_text': '{}'}],
    )

    def _fake_stream(_payload, _label, **_kwargs):
        yield {'type': 'status', 'message': 'Dang tao'}
        yield {'type': 'chunk', 'content': '# Tong ket'}

    monkeypatch.setattr('app.main.stream_portfolio_feedback', _fake_stream, raising=False)

    response = client.post('/api/v1/portfolio-feedback/stream', json={'portfolio_label': 'Tong hop'})

    assert response.status_code == 200
    body = response.text
    assert 'event: chunk' in body
    assert 'data: # Tong ket' in body
    assert '"type": "lesson_radar"' in body
    assert 'event: done' in body


def test_generate_lesson_feedback_returns_markdown_text(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class _Message:
                content = '# Nhan xet\n\n- Con tien bo'

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
    assert isinstance(result, str)
    assert result.startswith('#')


def test_stream_lesson_feedback_yields_text_chunks(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')

    class _Delta:
        def __init__(self, content):
            self.content = content

    class _ChoiceDelta:
        def __init__(self, content):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content):
            self.choices = [_ChoiceDelta(content)]

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            if kwargs.get('stream'):
                return iter([_Chunk('## Tong quan'), _Chunk('\n- Con tien bo')])
            raise AssertionError('Expected stream=True')

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == 'test-key'
            self.chat = _FakeChat()

    monkeypatch.setattr('app.llm.OpenAI', _FakeOpenAI)

    from app.llm import stream_lesson_feedback as stream_lesson_feedback_from_llm

    events = list(stream_lesson_feedback_from_llm('report', lesson_label='Lesson 1'))
    chunk_events = [event for event in events if event.get('type') == 'chunk']
    assert chunk_events
    assert isinstance(chunk_events[0].get('content'), str)


def test_build_lesson_progress_context_marks_first_when_current_time_missing() -> None:
    from app.main import _build_lesson_progress_context

    context = _build_lesson_progress_context('{"achievements":{"stats":{"speakingTurnCount":10}}}', '3724970')

    assert context['progress_context']['is_first_lesson'] is True
    assert context['progress_context']['reason'] == 'missing_current_lesson_time'
    assert context['recent_lessons'] == []


def test_build_lesson_progress_context_uses_two_most_recent_previous_lessons(monkeypatch) -> None:
    from app.main import _build_lesson_progress_context

    lessons_payload = [
        {
            'lesson_id': '1',
            'source_file': 'lesson_1.json',
            'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-01 20:00:00"}}',
        },
        {
            'lesson_id': '2',
            'source_file': 'lesson_2.json',
            'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-02 20:00:00"}}',
        },
        {
            'lesson_id': '3',
            'source_file': 'lesson_3.json',
            'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-03 20:00:00"}}',
        },
        {
            'lesson_id': '4',
            'source_file': 'lesson_4.json',
            'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-04 20:00:00"}}',
        },
    ]
    monkeypatch.setattr('app.main.load_all_lessons_json_from_local_data', lambda: lessons_payload)

    current_report_text = '{"lessonTime":{"lessonStartTime":"2025-10-04 20:00:00"}}'
    context = _build_lesson_progress_context(current_report_text, '4')

    recent_ids = [item['lesson_id'] for item in context['recent_lessons']]
    assert context['progress_context']['is_first_lesson'] is False
    assert recent_ids == ['3', '2']


def test_build_lesson_skill_context_extracts_speaking_and_listening_metrics() -> None:
    from app.main import _build_lesson_skill_context

    report_text = json.dumps(
        {
            'moments': [
                {
                    'interaction_type': 'AUDIO',
                    'lms_type': 'practice',
                    'lms_data': {
                        'questionType': 'speaking_scripted',
                        'expectedTranscript': 'Britain',
                    },
                    'result': {'userTranscript': 'britain', 'score': 95, 'pronunciationScore': 90},
                },
                {
                    'interaction_type': 'AUDIO',
                    'lms_type': 'dialogue',
                    'lms_data': {
                        'expectedTranscript': 'The costume is more expensive than the pyjamas.',
                    },
                    'result': {'userTranscript': 'the costume is more expensive', 'score': 88},
                },
                {
                    'interaction_type': 'NON_AUDIO',
                    'lms_type': 'practice',
                    'lms_data': {'questionType': 'single_choice', 'question': 'How much is it?'},
                    'result': {'score': 100},
                },
            ]
        }
    )
    context = _build_lesson_skill_context(report_text)

    assert context['speaking_pronunciation_vocab']['attempt_count'] == 1
    assert context['speaking_pronunciation_vocab']['average_score'] == 90
    assert context['speaking_sentence_length_by_activity']['long_sentence']['attempt_count'] == 1
    assert context['listening_quiz']['attempt_count'] == 1
    assert context['listening_quiz']['accuracy_percent'] == 100
    assert context['reading_fluency']['attempt_count'] == 2
    assert context['data_coverage']['speaking_pronunciation_vocab'] is True
    assert context['data_coverage']['listening_quiz'] is True
    assert context['data_coverage']['reading_fluency'] is True


def test_create_lesson_feedback_passes_recent_lesson_context_to_llm(monkeypatch) -> None:
    captured = {'input_text': ''}

    monkeypatch.setattr(
        'app.main.resolve_report_text',
        lambda payload: '{"lessonTime":{"lessonStartTime":"2025-10-04 20:00:00"},'
        '"achievements":{"stats":{"speakingTurnCount":30}}}',
    )
    monkeypatch.setattr(
        'app.main.load_all_lessons_json_from_local_data',
        lambda: [
            {
                'lesson_id': '3',
                'source_file': 'lesson_3.json',
                'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-03 20:00:00"},'
                '"achievements":{"stats":{"speakingTurnCount":20}}}',
            },
            {
                'lesson_id': '2',
                'source_file': 'lesson_2.json',
                'raw_json_text': '{"lessonTime":{"lessonStartTime":"2025-10-02 20:00:00"},'
                '"achievements":{"stats":{"speakingTurnCount":18}}}',
            },
        ],
    )

    def _fake_generate(input_text, _label):
        captured['input_text'] = input_text
        return '# Nhan xet'

    monkeypatch.setattr('app.main.generate_lesson_feedback', _fake_generate, raising=False)

    response = client.post('/api/v1/lesson-feedback', json={'lesson_id': '4', 'lesson_label': 'Lesson 4'})
    assert response.status_code == 200

    sent_payload = json.loads(captured['input_text'])
    assert 'current_lesson_data' in sent_payload
    assert 'lesson_progress_context' in sent_payload
    assert 'lesson_skill_context' in sent_payload
    assert 'rubric_data_quality' in sent_payload
    assert 'skill_pillars' in sent_payload['rubric_data_quality']
    assert 'rubric_criteria' in sent_payload['rubric_data_quality']
    assert isinstance(sent_payload['current_lesson_data'], dict)
    assert len(sent_payload['lesson_progress_context']['recent_lessons']) == 2
    assert sent_payload['lesson_progress_context']['progress_context']['is_first_lesson'] is False
    assert isinstance(sent_payload['lesson_skill_context'], dict)
