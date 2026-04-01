import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / 'data'
DEFAULT_SOURCE_PATH = Path('/home/pc600/Downloads/Telegram Desktop/vh_digital_teacher.learning_results_2102555.json')


def _parse_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _to_iso_string(value: Any) -> str | None:
    if isinstance(value, dict):
        date_value = value.get('$date')
        if isinstance(date_value, str) and date_value.strip():
            return date_value.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        'event_id': event.get('_id'),
        'session_id': event.get('sessionId'),
        'student_id': event.get('studentId'),
        'lesson_id': str(event.get('erpLessonId')) if event.get('erpLessonId') is not None else '',
        'section_id': event.get('sectionId'),
        'script_version_id': event.get('scriptVersionId'),
        'flow_id': event.get('flowId'),
        'node_id': event.get('nodeId'),
        'block_id': event.get('blockId'),
        'lms_type': event.get('lmsType'),
        'lms_data': event.get('lmsData'),
        'interaction_type': event.get('interactionType'),
        'reaction_time_ms': event.get('reactionTimeMs'),
        'attempt_number': event.get('attemptNumber'),
        'result': event.get('result'),
        'matched_vocabulary': event.get('matchedVocabulary'),
        'matched_grammar': event.get('matchedGrammar'),
        'timestamp': _to_iso_string(event.get('timestamp')),
        'created_at': _to_iso_string(event.get('createdAt')),
        'raw_version': event.get('__v'),
    }


def _moment_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    timestamp = str(event.get('timestamp') or '')
    created_at = str(event.get('created_at') or '')
    event_id = str(event.get('event_id') or '')
    return (timestamp, created_at, event_id)


def _normalize_reports(lesson_payload: Any) -> list[dict[str, Any]]:
    if isinstance(lesson_payload, list):
        return [item for item in lesson_payload if isinstance(item, dict)]
    if isinstance(lesson_payload, dict):
        if isinstance(lesson_payload.get('reports'), list):
            return [item for item in lesson_payload.get('reports', []) if isinstance(item, dict)]
        return [lesson_payload]
    return []


def run_migration(source_path: Path = DEFAULT_SOURCE_PATH) -> dict[str, Any]:
    if not source_path.exists():
        raise FileNotFoundError(f'Source file not found: {source_path}')

    source_payload = _parse_json_file(source_path)
    if not isinstance(source_payload, list):
        raise ValueError('Source learning results must be a JSON array')

    events_by_lesson: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source_payload:
        if not isinstance(item, dict):
            continue
        lesson_id = item.get('erpLessonId')
        if lesson_id is None:
            continue
        events_by_lesson[str(lesson_id)].append(_normalize_event(item))

    for lesson_id in events_by_lesson:
        events_by_lesson[lesson_id].sort(key=_moment_sort_key)

    updated_files: list[str] = []
    skipped_files: list[str] = []
    mapped_lesson_ids: list[str] = []

    for lesson_path in sorted(DATA_DIR.glob('lesson_*.json')):
        lesson_id = lesson_path.stem.replace('lesson_', '', 1)
        if lesson_id not in events_by_lesson:
            skipped_files.append(lesson_path.name)
            continue

        old_payload = _parse_json_file(lesson_path)
        reports = _normalize_reports(old_payload)

        new_payload = {
            'schema_version': '2.0',
            'lesson_id': lesson_id,
            'reports': reports,
            'moments': events_by_lesson[lesson_id],
            'mapping_meta': {
                'source_file': str(source_path),
                'mapped_at': datetime.now(timezone.utc).isoformat(),
                'total_events': len(events_by_lesson[lesson_id]),
                'mapping_policy': 'intersection_only',
                'moment_policy': 'full_raw_fields',
            },
        }

        lesson_path.write_text(json.dumps(new_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        updated_files.append(lesson_path.name)
        mapped_lesson_ids.append(lesson_id)

    return {
        'source_file': str(source_path),
        'source_total_events': len(source_payload),
        'source_distinct_lessons': len(events_by_lesson),
        'updated_file_count': len(updated_files),
        'updated_files': updated_files,
        'skipped_file_count': len(skipped_files),
        'skipped_files': skipped_files,
        'mapped_lesson_ids': sorted(mapped_lesson_ids),
    }


if __name__ == '__main__':
    summary = run_migration()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
