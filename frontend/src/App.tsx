import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type SummaryPayload = {
  overall_summary: string
  key_points: string[]
  action_items: string[]
}

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
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=TRIAL_LESSON_10_11',
    lessonId: 'TRIAL_LESSON_10_11',
    detail: 'Bao cao hoc thu',
  },
  {
    label: 'Lesson 3724970',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=3724970',
    lessonId: '3724970',
    detail: 'Bao cao buoi hoc chi tiet',
  },
]

function App() {
  const [reportText, setReportText] = useState('')
  const [reportUrl, setReportUrl] = useState('')
  const [lessonId, setLessonId] = useState('')
  const [summary, setSummary] = useState<SummaryPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState<LessonFeedbackPayload | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackLoadingId, setFeedbackLoadingId] = useState<string | null>(null)

  const apiBaseUrl = useMemo(
    () => import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
    [],
  )

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSummary(null)

    const normalizedReportText = reportText.trim()
    const normalizedReportUrl = reportUrl.trim()
    const normalizedLessonId = lessonId.trim()

    if (!normalizedReportText && !normalizedReportUrl && !normalizedLessonId) {
      setError('Vui long nhap report_text, report_url hoac lesson_id.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/summaries`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          report_text: normalizedReportText || undefined,
          report_url: normalizedReportUrl || undefined,
          lesson_id: normalizedLessonId || undefined,
        }),
      })

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(payload?.detail ?? 'Khong the tom tat bao cao luc nay.')
      }

      const payload = (await response.json()) as SummaryPayload
      setSummary(payload)
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Da xay ra loi khong xac dinh.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateFeedback = async (lessonId: string, lessonLabel: string) => {
    setFeedbackError(null)
    setFeedback(null)
    setFeedbackLoadingId(lessonId)

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/lesson-feedback`, {
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

      const payload = (await response.json()) as LessonFeedbackPayload
      setFeedback(payload)
    } catch (_requestError) {
      setFeedbackError('Chua tao duoc nhan xet. Vui long thu lai.')
    } finally {
      setFeedbackLoadingId(null)
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero__header">
          <p className="hero__eyebrow">Bao cao sau buoi hoc</p>
          <h1>RinoDigi Lesson</h1>
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
              Nhan xet AI
            </button>
          </article>
        ))}
      </section>

      <section className="lesson-feedback-panel" aria-label="Lesson feedback">
        {feedbackLoadingId && <p className="feedback">Dang tao nhan xet...</p>}
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

      <section className="summary-box" aria-label="Summary lab">
        <div className="quote-card">"Dan noi dung bao cao de he thong tong hop thong tin chinh va ke hoach tiep theo."</div>

        <form className="summary-form" onSubmit={handleSubmit}>
          <label htmlFor="report-text">Noi dung bao cao</label>
          <textarea
            id="report-text"
            value={reportText}
            onChange={(event) => setReportText(event.target.value)}
            placeholder="Nhap report text..."
            rows={8}
          />
          <label htmlFor="report-url">Report URL (tu chon)</label>
          <input
            id="report-url"
            value={reportUrl}
            onChange={(event) => setReportUrl(event.target.value)}
            placeholder="https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=..."
            type="url"
          />
          <label htmlFor="lesson-id">Lesson ID (tu chon)</label>
          <input
            id="lesson-id"
            value={lessonId}
            onChange={(event) => setLessonId(event.target.value)}
            placeholder="3724970"
            type="text"
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Dang tom tat...' : 'Tom tat bao cao'}
          </button>
        </form>

        {error && <p className="feedback feedback--error">{error}</p>}

        {summary && (
          <article className="summary-result">
            <h2>Tong hop</h2>
            <p>{summary.overall_summary}</p>

            <h3>Y chinh</h3>
            <ul>
              {summary.key_points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>

            <h3>Hanh dong de xuat</h3>
            <ul>
              {summary.action_items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        )}
      </section>
    </main>
  )
}

export default App
