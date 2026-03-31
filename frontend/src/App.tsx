import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type SummaryPayload = {
  overall_summary: string
  key_points: string[]
  action_items: string[]
}

const reportLinks = [
  {
    label: 'Lesson 1',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjIxMTY5MTUiLCJpYXQiOjE3NzA0NzQ0ODQsImV4cCI6MTgwMjAxMDQ4NH0.bWMnciHCaUJ0sm7AS0Q3_wzuCo2udbU480tNG5lxO8c&erp_lesson_id=3724970',
    detail: 'Buổi học chào hỏi',
  },
  {
    label: 'Lesson 2',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=TRIAL_LESSON_10_11&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjE0NjU3NDEiLCJpYXQiOjE3NzIxNTcwOTksImV4cCI6MTgwMzY5MzA5OX0.JEHtb_OS2C027eQrz1JuYiZBpgeA693xt2HAj5Sxp4s',
    detail: 'Buổi học về các nước',
  },
]

function App() {
  const [reportText, setReportText] = useState('')
  const [reportUrl, setReportUrl] = useState('')
  const [lessonId, setLessonId] = useState('')
  const [summary, setSummary] = useState<SummaryPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
          <a key={item.href} className="report-card" href={item.href} target="_blank" rel="noopener noreferrer">
            <span className="report-card__title">{item.label}</span>
            <span className="report-card__detail">{item.detail}</span>
          </a>
        ))}
      </section>
    </main>
  )
}

export default App
