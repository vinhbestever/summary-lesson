from fastapi.testclient import TestClient

from app.main import app


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
