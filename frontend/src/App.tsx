import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

type ReportLink = {
  label: string
  href: string
  lessonId: string
  detail: string
}

type ReportPayload = {
  scriptMetadata?: {
    name?: string
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

    return {
      lessonId,
      label: `Lesson ${lessonId}`,
      detail: scriptName ? `${detailPrefix} - ${scriptName}` : detailPrefix,
      href: `https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=${encodeURIComponent(lessonId)}&token=${reportToken}`,
    }
  })
  .filter((item): item is ReportLink => item !== null)
  .sort((a, b) => a.lessonId.localeCompare(b.lessonId))

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

  const handleGenerateFeedback = async (lessonId: string, lessonLabel: string) => {
    setFeedbackMode('lesson')
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
        </div>
      </section>

      <section className="report-options" aria-label="Report options">
        {reportLinks.length === 0 && <p className="feedback">Chua co du lieu buoi hoc trong thu muc data.</p>}
        {reportLinks.map((item) => (
          <article key={item.lessonId} className="report-card">
            <a className="report-card__link" href={item.href} target="_blank" rel="noopener noreferrer">
              <span className="report-card__title">{item.label}</span>
              <span className="report-card__detail">{item.detail}</span>
            </a>
            <button
              type="button"
              className="report-card__feedback-button"
              onClick={() => handleGenerateFeedback(item.lessonId, item.label)}
              disabled={feedbackLoadingId !== null}
            >
              Nhan xet
            </button>
          </article>
        ))}
      </section>

      <section className="portfolio-action" aria-label="Portfolio feedback action">
        <button
          type="button"
          className="portfolio-action__button"
          onClick={handleGeneratePortfolioFeedback}
          disabled={feedbackLoadingId !== null}
        >
          Nhan xet chung
        </button>
      </section>

      <section className="lesson-feedback-panel" aria-label="Lesson feedback">
        {feedbackLoadingId && (
          <article className="streaming-visual">
            <div className="streaming-visual__head">
              <p className="feedback">{feedbackStreamingStatus ?? 'Dang tao nhan xet...'}</p>
              <p className="streaming-visual__meta">Dang nhan du lieu stream...</p>
            </div>
            <div className="streaming-progress" aria-hidden="true">
              <span />
            </div>
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
            <MarkdownView content={formattedMarkdown} />
          </article>
        )}
      </section>
    </main>
  )
}

export default App
