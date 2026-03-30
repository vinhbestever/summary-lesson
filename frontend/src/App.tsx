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
    label: 'Trial Lesson 10_11',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=TRIAL_LESSON_10_11',
    detail: 'Bao cao hoc thu',
  },
  {
    label: 'Lesson 3724970',
    href: 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=3724970',
    detail: 'Bao cao buoi hoc chi tiet',
  },
]

function App() {
  const [reportText, setReportText] = useState('')
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

    if (!reportText.trim()) {
      setError('Vui long nhap noi dung bao cao truoc khi tom tat.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/summaries`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ report_text: reportText }),
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
          <h1>RinoEdu Lesson Summary</h1>
          <p className="hero__subtitle">Chon nhanh bao cao mau hoac dan noi dung de tom tat bang LLM.</p>
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
