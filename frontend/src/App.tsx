import { useMemo, useState } from 'react'
import './App.css'

type SessionCriterion = {
  score: number
  comment: string
  evidence: string[]
}

type LessonFeedbackPayload = {
  lesson_label: string
  teacher_tone: string
  overall_comment: string
  session_breakdown: {
    participation: SessionCriterion
    pronunciation: SessionCriterion
    vocabulary: SessionCriterion
    grammar: SessionCriterion
    reaction_confidence: SessionCriterion
  }
  strengths: string[]
  priority_improvements: Array<{
    skill: string
    priority: string
    current_state: string
    target_next_lesson: string
    coach_tip: string
  }>
  next_lesson_plan: Array<{
    step: string
    duration_minutes: number
  }>
  parent_message: string
}

const reportLinks = [
  {
    label: 'Trial Lesson 10_11',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=TRIAL_LESSON_10_11&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjE0NjU3NDEiLCJpYXQiOjE3NzIxNTcwOTksImV4cCI6MTgwMzY5MzA5OX0.JEHtb_OS2C027eQrz1JuYiZBpgeA693xt2HAj5Sxp4s',
    lessonId: 'TRIAL_LESSON_10_11',
    detail: 'Bao cao hoc thu',
  },
  {
    label: 'Lesson 3724970',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjIxMTY5MTUiLCJpYXQiOjE3NzA0NzQ0ODQsImV4cCI6MTgwMjAxMDQ4NH0.bWMnciHCaUJ0sm7AS0Q3_wzuCo2udbU480tNG5lxO8c&erp_lesson_id=3724970',
    lessonId: '3724970',
    detail: 'Bao cao buoi hoc chi tiet',
  },
]

const STREAM_SECTION_LABELS: Array<{ key: string; label: string }> = [
  { key: 'overall_comment', label: 'Tong quan buoi hoc' },
  { key: 'session_breakdown', label: 'Phan tich ky nang' },
  { key: 'strengths', label: 'Diem manh' },
  { key: 'priority_improvements', label: 'Uu tien cai thien' },
  { key: 'next_lesson_plan', label: 'Ke hoach buoi sau' },
  { key: 'parent_message', label: 'Loi nhan phu huynh' },
]

function extractJsonStringField(raw: string, key: string): string | null {
  const pattern = new RegExp(`"${key}"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"`)
  const match = raw.match(pattern)
  if (!match?.[1]) {
    return null
  }
  return match[1].replace(/\\"/g, '"').replace(/\\n/g, '\n').trim()
}

function extractJsonStringArray(raw: string, key: string): string[] {
  const arrayPattern = new RegExp(`"${key}"\\s*:\\s*\\[([\\s\\S]*?)\\]`)
  const match = raw.match(arrayPattern)
  if (!match?.[1]) {
    return []
  }
  const values = [...match[1].matchAll(/"([^"\\]*(?:\\.[^"\\]*)*)"/g)].map((item) =>
    item[1].replace(/\\"/g, '"').replace(/\\n/g, '\n').trim(),
  )
  return values.filter(Boolean)
}

function App() {
  const [feedback, setFeedback] = useState<LessonFeedbackPayload | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackLoadingId, setFeedbackLoadingId] = useState<string | null>(null)
  const [feedbackStreamingStatus, setFeedbackStreamingStatus] = useState<string | null>(null)
  const [feedbackStreamingText, setFeedbackStreamingText] = useState('')
  const streamSectionStates = useMemo(() => {
    return STREAM_SECTION_LABELS.map((section) => {
      const appeared = feedbackStreamingText.includes(`"${section.key}"`)
      return {
        ...section,
        state: appeared ? 'done' : 'pending',
      }
    })
  }, [feedbackStreamingText])
  const overallPreview = useMemo(
    () => extractJsonStringField(feedbackStreamingText, 'overall_comment'),
    [feedbackStreamingText],
  )
  const strengthsPreview = useMemo(
    () => extractJsonStringArray(feedbackStreamingText, 'strengths').slice(0, 3),
    [feedbackStreamingText],
  )
  const parentPreview = useMemo(
    () => extractJsonStringField(feedbackStreamingText, 'parent_message'),
    [feedbackStreamingText],
  )

  const apiBaseUrl = useMemo(
    () => import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
    [],
  )

  const handleGenerateFeedback = async (lessonId: string, lessonLabel: string) => {
    setFeedbackError(null)
    setFeedback(null)
    setFeedbackLoadingId(lessonId)
    setFeedbackStreamingStatus('Dang bat dau tao nhan xet...')
    setFeedbackStreamingText('')

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
        const payload = (await fallbackResponse.json()) as LessonFeedbackPayload
        setFeedback(payload)
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
          const lines = rawEvent.split('\n')
          let eventName = ''
          let eventData = ''
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventName = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              eventData += line.slice(5).trim()
            }
          }

          if (!eventData) {
            continue
          }

          const parsed = JSON.parse(eventData) as {
            type: string
            message?: string
            content?: string
            data?: LessonFeedbackPayload
          }

          if (eventName === 'status' && parsed.message) {
            setFeedbackStreamingStatus(parsed.message)
          } else if (eventName === 'chunk') {
            setFeedbackStreamingStatus('Dang tao noi dung nhan xet...')
            const chunkContent = parsed.content
            if (chunkContent) {
              setFeedbackStreamingText((previous) => previous + chunkContent)
            }
          } else if (eventName === 'result' && parsed.data) {
            setFeedback(parsed.data)
            setFeedbackStreamingStatus('Da hoan tat nhan xet.')
          } else if (eventName === 'error') {
            throw new Error(parsed.message ?? 'Chua tao duoc nhan xet. Vui long thu lai.')
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
        {reportLinks.map((item) => (
          <article key={item.href} className="report-card">
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
            <div className="streaming-section-chips">
              {streamSectionStates.map((section) => (
                <span key={section.key} className={`stream-chip stream-chip--${section.state}`}>
                  {section.label}
                </span>
              ))}
            </div>
            {(overallPreview || strengthsPreview.length > 0 || parentPreview) && (
              <div className="streaming-live-cards">
                {overallPreview && (
                  <section className="stream-card">
                    <h4>Tong quan dang tao</h4>
                    <p>{overallPreview}</p>
                  </section>
                )}
                {strengthsPreview.length > 0 && (
                  <section className="stream-card">
                    <h4>Diem manh dang tao</h4>
                    <ul>
                      {strengthsPreview.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}
                {parentPreview && (
                  <section className="stream-card">
                    <h4>Loi nhan phu huynh dang tao</h4>
                    <p>{parentPreview}</p>
                  </section>
                )}
              </div>
            )}
            <div className="streaming-skeleton">
              <div className="streaming-skeleton__block streaming-skeleton__block--large" />
              <div className="streaming-skeleton__grid">
                <div className="streaming-skeleton__block" />
                <div className="streaming-skeleton__block" />
                <div className="streaming-skeleton__block" />
                <div className="streaming-skeleton__block" />
              </div>
              <div className="streaming-skeleton__block" />
              <div className="streaming-skeleton__block" />
            </div>
          </article>
        )}
        {feedbackError && <p className="feedback feedback--error">{feedbackError}</p>}

        {feedback && (
          <article className="summary-result">
            <h2>Nhan xet buoi hoc - {feedback.lesson_label}</h2>
            <p>{feedback.overall_comment}</p>

            <h3>Danh gia tung muc</h3>
            <ul className="feedback-score-list">
              <li>Participation: {feedback.session_breakdown.participation.score}</li>
              <li>Pronunciation: {feedback.session_breakdown.pronunciation.score}</li>
              <li>Vocabulary: {feedback.session_breakdown.vocabulary.score}</li>
              <li>Grammar: {feedback.session_breakdown.grammar.score}</li>
              <li>Reaction confidence: {feedback.session_breakdown.reaction_confidence.score}</li>
            </ul>

            <h3>Diem manh</h3>
            <ul>
              {feedback.strengths.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>

            <h3>Uu tien cai thien</h3>
            <ul>
              {feedback.priority_improvements.map((item, index) => (
                <li key={`${item.skill}-${index}`}>
                  {item.skill}: {item.coach_tip}
                </li>
              ))}
            </ul>

            <h3>Ke hoach buoi sau</h3>
            <ul>
              {feedback.next_lesson_plan.map((item, index) => (
                <li key={`${item.step}-${index}`}>
                  {item.step} ({item.duration_minutes} phut)
                </li>
              ))}
            </ul>

            <h3>Loi nhan phu huynh</h3>
            <p>{feedback.parent_message}</p>
          </article>
        )}
      </section>

    </main>
  )
}

export default App
