import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

type ReportLink = {
  label: string
  href: string
  lessonId: string
  detail: string
  lessonStartTime: string | null
  lessonEndTime: string | null
  sortTimestamp: number | null
  timeLabel: string
}

type ReportPayload = {
  scriptMetadata?: {
    name?: string
  }
  lessonTime?: {
    lessonStartTime?: string | null
    lessonEndTime?: string | null
  }
}

const lessonReportFiles = import.meta.glob('../../data/lesson_*.json', {
  eager: true,
  import: 'default',
}) as Record<string, unknown>

const reportToken =
  import.meta.env.VITE_REPORT_TOKEN ??
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjEwMjU1NSwiZGV2aWNlSWQiOiJBUDNBLjI0MDkwNS4wMTUuQTIiLCJpYXQiOjE3NzQ5MjYwODEsImV4cCI6MTgwNjQ2MjA4MX0.h0NAX3uL9FDyVjZcI3jgLFQV87WNRzYadBl6b46G-_U'

function extractLessonId(filePath: string): string | null {
  const matched = filePath.match(/lesson_(.+)\.json$/)
  if (!matched?.[1]) {
    return null
  }
  return matched[1]
}

function toPrimaryReport(payload: unknown): ReportPayload {
  if (Array.isArray(payload)) {
    return (payload[0] ?? {}) as ReportPayload
  }
  return (payload ?? {}) as ReportPayload
}

function parseDateTimeValue(value: string | null | undefined): Date | null {
  if (!value) {
    return null
  }

  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  return parsed
}

function formatLessonTimeLabel(start: string | null, end: string | null): string {
  const startDate = parseDateTimeValue(start)
  const endDate = parseDateTimeValue(end)

  if (!startDate) {
    return 'Chua co thoi gian buoi hoc'
  }

  const formatter = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  const startLabel = formatter.format(startDate)
  if (!endDate) {
    return `Thoi gian hoc: ${startLabel}`
  }

  const endHour = String(endDate.getHours()).padStart(2, '0')
  const endMinute = String(endDate.getMinutes()).padStart(2, '0')
  return `Thoi gian hoc: ${startLabel} - ${endHour}:${endMinute}`
}

function compareLessonIdDesc(a: string, b: string): number {
  const aNum = Number(a)
  const bNum = Number(b)

  if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) {
    return bNum - aNum
  }

  return b.localeCompare(a)
}

const reportLinks: ReportLink[] = Object.entries(lessonReportFiles)
  .map(([filePath, payload]) => {
    const lessonId = extractLessonId(filePath)
    if (!lessonId) {
      return null
    }
    const primaryReport = toPrimaryReport(payload)
    const scriptName = primaryReport.scriptMetadata?.name
    const attemptCount = Array.isArray(payload) ? payload.length : 1
    const detailPrefix = attemptCount > 1 ? `${attemptCount} lan hoc` : '1 lan hoc'
    const lessonStartTime = primaryReport.lessonTime?.lessonStartTime ?? null
    const lessonEndTime = primaryReport.lessonTime?.lessonEndTime ?? null
    const sortTimestamp = parseDateTimeValue(lessonStartTime)?.getTime() ?? null

    return {
      lessonId,
      label: `Lesson ${lessonId}`,
      detail: scriptName ? `${detailPrefix} - ${scriptName}` : detailPrefix,
      href: `https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=${encodeURIComponent(lessonId)}&token=${reportToken}`,
      lessonStartTime,
      lessonEndTime,
      sortTimestamp,
      timeLabel: formatLessonTimeLabel(lessonStartTime, lessonEndTime),
    }
  })
  .filter((item): item is ReportLink => item !== null)
  .sort((a, b) => {
    if (a.sortTimestamp !== null && b.sortTimestamp !== null) {
      return b.sortTimestamp - a.sortTimestamp
    }
    if (a.sortTimestamp !== null) {
      return -1
    }
    if (b.sortTimestamp !== null) {
      return 1
    }
    return compareLessonIdDesc(a.lessonId, b.lessonId)
  })

type ParsedSseEvent = {
  eventName: string
  eventData: string
}

function parseSseEvent(rawEvent: string): ParsedSseEvent {
  const lines = rawEvent.split('\n')
  let eventName = ''
  const dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      const raw = line.slice(5)
      dataLines.push(raw.startsWith(' ') ? raw.slice(1) : raw)
    }
  }

  return {
    eventName,
    eventData: dataLines.join('\n'),
  }
}

function normalizeMarkdownLineBreaks(raw: string): string {
  if (!raw.trim()) {
    return ''
  }

  return raw
    .replace(/([.!?])\s*-\s+/g, '$1\n- ')
    .replace(/\n-\s*\n-/g, '\n- ')
}

function MarkdownView({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

function App() {
  const [feedbackMode, setFeedbackMode] = useState<'lesson' | 'portfolio' | null>(null)
  const [activeFeedbackLabel, setActiveFeedbackLabel] = useState('')
  const [feedbackMarkdown, setFeedbackMarkdown] = useState('')
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackLoadingId, setFeedbackLoadingId] = useState<string | null>(null)
  const [feedbackStreamingStatus, setFeedbackStreamingStatus] = useState<string | null>(null)

  const apiBaseUrl = useMemo(
    () => import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
    [],
  )
  const formattedMarkdown = useMemo(
    () => normalizeMarkdownLineBreaks(feedbackMarkdown),
    [feedbackMarkdown],
  )
  const lessonCount = reportLinks.length

  const handleGenerateFeedback = async (lessonId: string, lessonLabel: string) => {
    setFeedbackMode('lesson')
    setActiveFeedbackLabel(lessonLabel)
    setFeedbackError(null)
    setFeedbackLoadingId(lessonId)
    setFeedbackStreamingStatus('Dang bat dau tao nhan xet...')
    setFeedbackMarkdown('')

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/lesson-feedback/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lesson_id: lessonId,
          lesson_label: lessonLabel,
        }),
      })

      if (!response.ok) {
        throw new Error('Chua tao duoc nhan xet. Vui long thu lai.')
      }

      if (!response.body) {
        const fallbackResponse = await fetch(`${apiBaseUrl}/api/v1/lesson-feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            lesson_id: lessonId,
            lesson_label: lessonLabel,
          }),
        })
        if (!fallbackResponse.ok) {
          throw new Error('Chua tao duoc nhan xet. Vui long thu lai.')
        }
        const markdown = (await fallbackResponse.text()).trim()
        setFeedbackMarkdown(markdown)
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const rawEvent of events) {
          const { eventName, eventData } = parseSseEvent(rawEvent)

          if (eventName === 'status') {
            if (eventData) {
              setFeedbackStreamingStatus(eventData)
            }
          } else if (eventName === 'chunk') {
            setFeedbackStreamingStatus('Dang tao noi dung nhan xet...')
            setFeedbackMarkdown((previous) => previous + (eventData || '\n'))
          } else if (eventName === 'error') {
            throw new Error(eventData || 'Chua tao duoc nhan xet. Vui long thu lai.')
          } else if (eventName === 'done') {
            setFeedbackStreamingStatus('Da hoan tat nhan xet.')
          }
        }
      }
    } catch (_requestError) {
      setFeedbackError('Chua tao duoc nhan xet. Vui long thu lai.')
      setFeedbackStreamingStatus(null)
    } finally {
      setFeedbackLoadingId(null)
    }
  }

  const handleGeneratePortfolioFeedback = async () => {
    setFeedbackMode('portfolio')
    setActiveFeedbackLabel('Tong hop tat ca buoi hoc')
    setFeedbackError(null)
    setFeedbackLoadingId('portfolio')
    setFeedbackStreamingStatus('Dang bat dau tao nhan xet chung...')
    setFeedbackMarkdown('')

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/portfolio-feedback/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          portfolio_label: 'Tong hop toan bo buoi hoc',
        }),
      })

      if (!response.ok) {
        throw new Error('Chua tao duoc nhan xet. Vui long thu lai.')
      }

      if (!response.body) {
        const fallbackResponse = await fetch(`${apiBaseUrl}/api/v1/portfolio-feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            portfolio_label: 'Tong hop toan bo buoi hoc',
          }),
        })
        if (!fallbackResponse.ok) {
          throw new Error('Chua tao duoc nhan xet. Vui long thu lai.')
        }
        const markdown = (await fallbackResponse.text()).trim()
        setFeedbackMarkdown(markdown)
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const rawEvent of events) {
          const { eventName, eventData } = parseSseEvent(rawEvent)

          if (eventName === 'status') {
            if (eventData) {
              setFeedbackStreamingStatus(eventData)
            }
          } else if (eventName === 'chunk') {
            setFeedbackStreamingStatus('Dang tao noi dung nhan xet...')
            setFeedbackMarkdown((previous) => previous + (eventData || '\n'))
          } else if (eventName === 'error') {
            throw new Error(eventData || 'Chua tao duoc nhan xet. Vui long thu lai.')
          } else if (eventName === 'done') {
            setFeedbackStreamingStatus('Da hoan tat nhan xet.')
          }
        }
      }
    } catch (_requestError) {
      setFeedbackError('Chua tao duoc nhan xet. Vui long thu lai.')
      setFeedbackStreamingStatus(null)
    } finally {
      setFeedbackLoadingId(null)
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero__header">
          <p className="hero__eyebrow">Bao cao sau buoi hoc</p>
          <h1>RinoDigi Lesson Feedback</h1>
          <p className="hero__subtitle">
            Khong gian xem buoi hoc va nhan xet duoc toi uu cho tre: de nhin, de tim, de theo doi tien bo.
          </p>
        </div>
        <div className="hero__stats" aria-label="Thong ke">
          <article className="hero-stat">
            <p className="hero-stat__label">Tong buoi hoc</p>
            <p className="hero-stat__value">{lessonCount}</p>
          </article>
          <article className="hero-stat">
            <p className="hero-stat__label">Trang thai</p>
            <p className="hero-stat__value hero-stat__value--small">
              {feedbackLoadingId ? 'Dang tao nhan xet' : 'San sang'}
            </p>
          </article>
        </div>
      </section>

      <div className="layout">
        <section className="report-options" aria-label="Report options">
          <header className="section-head">
            <h2>Danh sach buoi hoc</h2>
            <p>Chon buoi hoc de xem nhanh bao cao hoac tao nhan xet AI.</p>
          </header>
          {reportLinks.length === 0 && (
            <p className="feedback">Chua co du lieu buoi hoc trong thu muc data.</p>
          )}
          {reportLinks.map((item, index) => (
            <article
              key={item.lessonId}
              className={`report-card ${activeFeedbackLabel === item.label ? 'report-card--active' : ''}`}
            >
              <p className="report-card__order">Buoi {lessonCount - index}</p>
              <a className="report-card__link" href={item.href} target="_blank" rel="noopener noreferrer">
                <span className="report-card__title">{item.label}</span>
                <span className="report-card__detail">{item.detail}</span>
                <span
                  className="report-card__time"
                  data-testid="report-card-time"
                  data-start-time={item.lessonStartTime ?? ''}
                >
                  {item.timeLabel}
                </span>
              </a>
              <div className="report-card__actions">
                <a
                  className="report-card__open"
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Xem bao cao
                </a>
                <button
                  type="button"
                  className="report-card__feedback-button"
                  onClick={() => handleGenerateFeedback(item.lessonId, item.label)}
                  disabled={feedbackLoadingId !== null}
                >
                  Nhan xet
                </button>
              </div>
            </article>
          ))}
        </section>

        <section className="lesson-feedback-panel" aria-label="Lesson feedback">
          <header className="section-head section-head--feedback">
            <h2>Ket qua nhan xet</h2>
            <p>Tap trung hien thi noi dung de giao vien va phu huynh de doc.</p>
            <button
              type="button"
              className="portfolio-action__button"
              onClick={handleGeneratePortfolioFeedback}
              disabled={feedbackLoadingId !== null}
            >
              Nhan xet chung
            </button>
          </header>

          {feedbackLoadingId && (
            <article className="streaming-visual">
              <div className="streaming-visual__head">
                <p className="feedback">{feedbackStreamingStatus ?? 'Dang tao nhan xet...'}</p>
                <p className="streaming-visual__meta">Dang nhan du lieu stream...</p>
              </div>
              <div className="streaming-progress" aria-hidden="true">
                <span />
              </div>
              <p className="streaming-visual__context">
                Dang xu ly: <strong>{activeFeedbackLabel}</strong>
              </p>
              {feedbackMarkdown && (
                <article className="summary-result">
                  <MarkdownView content={formattedMarkdown} />
                </article>
              )}
            </article>
          )}

          {feedbackError && <p className="feedback feedback--error">{feedbackError}</p>}

          {!feedbackLoadingId && feedbackMarkdown && (
            <article className="summary-result" data-testid={`markdown-result-${feedbackMode ?? 'none'}`}>
              <p className="summary-result__context">
                Dang hien thi: <strong>{activeFeedbackLabel}</strong>
              </p>
              <MarkdownView content={formattedMarkdown} />
            </article>
          )}
        </section>
      </div>
    </main>
  )
}

export default App
