# LLM Markdown Output Design

Date: 2026-03-31
Status: Approved

## 1. Goal

Replace JSON-based LLM feedback output with markdown output for both lesson and portfolio flows, and update frontend to render markdown safely in both streaming and final states.

## 2. Scope

In scope:
- `POST /api/v1/lesson-feedback` returns plain markdown text
- `POST /api/v1/portfolio-feedback` returns plain markdown text
- `POST /api/v1/lesson-feedback/stream` streams raw markdown chunks via SSE
- `POST /api/v1/portfolio-feedback/stream` streams raw markdown chunks via SSE
- Frontend renders markdown safely for streaming and final output

Out of scope:
- Maintaining JSON output compatibility on the same endpoints
- Rich structured JSON rendering cards/chips tied to schema keys

## 3. Chosen Approach

Chosen approach: LLM returns markdown directly.

Why:
- Matches requested target exactly
- Removes fragile JSON extraction logic from streaming UI
- Unifies rendering path between streaming and final output

Tradeoff:
- Structured fields (scores, priorities as typed JSON) are no longer available as backend contract for these endpoints.

## 4. API Contract Changes

### 4.1 Non-stream endpoints

- Response content type: `text/markdown; charset=utf-8`
- Response body: plain markdown text (not JSON-wrapped)

Endpoints:
- `/api/v1/lesson-feedback`
- `/api/v1/portfolio-feedback`

### 4.2 Stream endpoints (SSE)

SSE events:
- `event: status`, `data: <plain status text>`
- `event: chunk`, `data: <raw markdown chunk text>`
- `event: error`, `data: <plain error text>`
- `event: done`, `data: done`

No JSON wrapper is used for `chunk` data.

## 5. Backend Design

## 5.1 LLM prompting and parsing
- Remove forced JSON response format for feedback flows
- Update prompts to request well-structured Vietnamese markdown
- Non-stream: return full markdown string
- Stream: emit text deltas directly as markdown chunks

## 5.2 Route behavior
- `lesson-feedback` and `portfolio-feedback` routes return markdown text response
- Streaming routes keep SSE transport but send plain text payloads in `data:`

## 5.3 Error handling
- Empty LLM output: treat as error
- Upstream/network/model errors mapped to existing HTTP error strategy
- Stream sends `error` then always emits `done`

## 6. Frontend Design

## 6.1 Rendering
- Replace JSON-schema-specific rendering with markdown rendering
- Use one shared markdown renderer for:
  - live streaming buffer
  - final result

## 6.2 Streaming parser
- Remove `JSON.parse` for SSE payloads
- Parse `event:` and raw `data:` text
- Append chunk data to markdown buffer in realtime

## 6.3 Markdown safety
- Use safe markdown rendering mode
- Do not enable raw HTML rendering
- Keep standard markdown features (headings, lists, emphasis, links)

## 7. Migration Impact

Breaking changes:
- Feedback endpoint response shape changes from JSON to plain markdown text
- Frontend types and UI paths tied to JSON fields are removed for feedback display

No compatibility layer is included in this change.

## 8. Testing Strategy

Backend tests:
- Non-stream endpoints return markdown content type and plain text body
- Stream endpoints emit plain-text SSE chunk payloads and end with `done`

Frontend tests:
- Streaming markdown renders incrementally as chunks arrive
- Final markdown renders correctly
- Unsafe HTML is not rendered as raw HTML
- Error state still displays correctly

## 9. Definition of Done

- Lesson and portfolio flows use markdown output for stream and non-stream
- Frontend no longer depends on JSON chunk parsing
- Markdown renders safely in live and final views
- Relevant backend/frontend tests pass
