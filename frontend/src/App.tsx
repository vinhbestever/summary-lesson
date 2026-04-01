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
  reports?: Array<{
    scriptMetadata?: {
      name?: string
    }
    lessonTime?: {
      lessonStartTime?: string | null
      lessonEndTime?: string | null
    }
  }>
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
  const root = (payload ?? {}) as ReportPayload
  if (Array.isArray(root.reports) && root.reports[0]) {
    return root.reports[0]
  }
  return root
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

type RadarCompetency = {
  key: string
  label: string
  score: number
  level_text?: string
  insufficient_data?: boolean
}

type LessonRadarPayload = {
  type: 'lesson_radar'
  competencies: RadarCompetency[]
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

const levelScoreMap: Record<string, number> = {
  'rất cần hỗ trợ': 20,
  'can ho tro': 40,
  'cần hỗ trợ': 40,
  'đang hình thành': 60,
  'dang hinh thanh': 60,
  'khá vững': 80,
  'kha vung': 80,
  'vững vàng': 100,
  'vung vang': 100,
}

const competencySpecs = [
  { key: 'learn', code: 'A', name: 'Learn' },
  { key: 'recognize', code: 'B', name: 'Recognize' },
  { key: 'apply', code: 'C', name: 'Apply' },
  { key: 'retain', code: 'D', name: 'Retain' },
  { key: 'focus', code: 'E', name: 'Focus' },
  { key: 'express', code: 'F', name: 'Express' },
]

function normalizeForCompare(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function parseScoreFromResultLine(line: string): { score: number; levelText: string; insufficientData: boolean } {
  const normalized = normalizeForCompare(line)
  const insufficientData = normalized.includes('chua du du lieu')
  const numericMatch = line.match(/\b(100|[1-9]?\d)(?:\s*\/\s*100)?\b/)
  let score = numericMatch ? Number(numericMatch[1]) : NaN
  let levelText = ''

  if (Number.isNaN(score)) {
    const levelEntry = Object.entries(levelScoreMap).find(([level]) => normalized.includes(level))
    if (levelEntry) {
      score = levelEntry[1]
      levelText = levelEntry[0]
    }
  }

  if (!Number.isNaN(score) && !Number.isFinite(score)) {
    score = 0
  }

  if (Number.isNaN(score) || insufficientData) {
    return { score: 0, levelText, insufficientData: true }
  }

  return { score: Math.max(0, Math.min(100, Math.round(score))), levelText, insufficientData: false }
}

function parseLessonRadarFromMarkdown(markdown: string): LessonRadarPayload {
  const sectionStartRegex = /^##\s*(Đánh giá 6 năng lực|Danh gia 6 nang luc)\b/im
  const competencyLineRegex =
    /^\s*-\s*(?:([A-F])\.\s*)?(?:\*\*)?(Learn|Recognize|Apply|Retain|Focus|Express)(?:\*\*)?\b/i
  const resultLineRegex = /kết quả hiện tại|ket qua hien tai/i
  const lines = markdown.split('\n')
  const parsedByKey = new Map<string, RadarCompetency>()

  let insideSection = false
  let currentKey = ''
  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!insideSection) {
      if (sectionStartRegex.test(line)) {
        insideSection = true
      }
      continue
    }

    if (/^##\s+/i.test(line)) {
      break
    }

    const competencyMatch = line.match(competencyLineRegex)
    if (competencyMatch) {
      const keyFromName = competencySpecs.find(
        (item) =>
          item.code.toLowerCase() === (competencyMatch[1] ?? '').toLowerCase() ||
          item.name.toLowerCase() === competencyMatch[2].toLowerCase(),
      )?.key
      currentKey = keyFromName ?? ''
      continue
    }

    if (currentKey && resultLineRegex.test(line)) {
      const parsed = parseScoreFromResultLine(line)
      const spec = competencySpecs.find((item) => item.key === currentKey)
      if (spec) {
        parsedByKey.set(currentKey, {
          key: currentKey,
          label: `${spec.code}. ${spec.name}`,
          score: parsed.score,
          level_text: parsed.levelText,
          insufficient_data: parsed.insufficientData,
        })
      }
    }
  }

  return {
    type: 'lesson_radar',
    competencies: competencySpecs.map((spec) => {
      const existing = parsedByKey.get(spec.key)
      if (existing) {
        return existing
      }
      return {
        key: spec.key,
        label: `${spec.code}. ${spec.name}`,
        score: 0,
        level_text: '',
        insufficient_data: true,
      }
    }),
  }
}

function normalizeMarkdownLineBreaks(raw: string): string {
  if (!raw.trim()) {
    return ''
  }

  const normalized = raw
    .replace(/-\s*(Nghe|Nói|Doc|Đọc):\s*Tốt:\s*/g, '- $1:\n  - Tốt: ')
    .replace(/\s*\|\s*Chưa tốt:\s*/g, '\n  - Chưa tốt: ')
    .replace(/\s*\|\s*Yếu:\s*/g, '\n  - Yếu: ')
    .replace(
      /-\s*([A-F])\.\s*(Learn|Recognize|Apply|Retain|Focus|Express)\s*[–-]\s*([^\n]+?)\s*-\s*Đo lường:\s*/g,
      '- $1. $2 - $3\n  - Đo lường: ',
    )
    .replace(/\s*\|\s*Kết quả hiện tại:\s*/g, '\n  - Kết quả hiện tại: ')
    .replace(/\s*\|\s*Nhận xét:\s*/g, '\n  - Nhận xét: ')
    .replace(/\s*\|\s*Khuyến nghị:\s*/g, '\n  - Khuyến nghị: ')
    .replace(/-\s*(Tuần\s*[12])\s*:\s*(?=\S)/g, '- $1:\n  - ')
    .replace(/([.!?])\s*-\s+/g, '$1\n- ')
    .replace(/\n-\s*\n-/g, '\n- ')

  const lines = normalized.split('\n')
  const output: string[] = []
  let insideSkillSection = false
  let currentSkill: string | null = null
  let insideCompetencySection = false
  let currentCompetency: string | null = null
  const competencyNameToCode: Record<string, string> = {
    learn: 'A',
    recognize: 'B',
    apply: 'C',
    retain: 'D',
    focus: 'E',
    express: 'F',
  }

  for (const line of lines) {
    if (/^##\s*(Đánh giá từng kỹ năng|Danh gia tung ky nang)/i.test(line.trim())) {
      insideSkillSection = true
      currentSkill = null
      output.push(line)
      continue
    }

    if (insideSkillSection && /^##\s+/.test(line.trim())) {
      insideSkillSection = false
      currentSkill = null
      output.push(line)
      continue
    }

    if (/^##\s*(Đánh giá 6 năng lực|Danh gia 6 nang luc)/i.test(line.trim())) {
      insideCompetencySection = true
      currentCompetency = null
      output.push(line)
      continue
    }

    if (insideCompetencySection && /^##\s+/.test(line.trim())) {
      insideCompetencySection = false
      currentCompetency = null
      output.push(line)
      continue
    }

    if (insideCompetencySection) {
      const competencyMatch = line.match(
        /^\s*-\s*(?:([A-F])\.\s*)?(Learn|Recognize|Apply|Retain|Focus|Express)\s*(?:[–-]\s*(.*))?$/i,
      )
      if (competencyMatch) {
        const rawName = competencyMatch[2]
        const normalizedName = rawName.toLowerCase()
        const code = (competencyMatch[1] ?? competencyNameToCode[normalizedName] ?? '').toUpperCase()
        const description = (competencyMatch[3] ?? '').trim()
        const label = code ? `${code}. ${rawName}` : rawName
        output.push(`- ${label}${description ? ` - ${description}` : ''}`)
        currentCompetency = rawName
        continue
      }

      const competencyChildMatch = line.match(
        /^\s*-\s*(Đo lường|Do lường|Kết quả hiện tại|Ket qua hien tai|Nhận xét|Nhan xet|Khuyến nghị|Khuyen nghi)\s*:\s*(.*)$/i,
      )
      if (competencyChildMatch && currentCompetency) {
        const rawKey = competencyChildMatch[1].toLowerCase()
        let normalizedKey = competencyChildMatch[1]
        if (rawKey.includes('do l')) normalizedKey = 'Đo lường'
        if (rawKey.includes('ket qua')) normalizedKey = 'Kết quả hiện tại'
        if (rawKey.includes('nhan')) normalizedKey = 'Nhận xét'
        if (rawKey.includes('khuyen')) normalizedKey = 'Khuyến nghị'
        output.push(`  - ${normalizedKey}: ${competencyChildMatch[2].trim()}`)
        continue
      }

      if (/^\s*-\s+/.test(line)) {
        currentCompetency = null
        output.push(line)
        continue
      }
    }

    if (!insideSkillSection) {
      output.push(line)
      continue
    }

    const skillMatch = line.match(/^\s*-\s*(Nghe|Nói|Doc|Đọc)\s*:\s*(.*)$/i)
    if (skillMatch) {
      const skillName = skillMatch[1].toLowerCase() === 'doc' ? 'Đọc' : skillMatch[1]
      const rest = skillMatch[2].trim().replace(/^-+\s*/, '')
      output.push(`- ${skillName}:`)
      currentSkill = skillName
      if (rest) {
        if (/^tốt\s*:/i.test(rest)) {
          output.push(`  - ${rest}`)
        } else {
          output.push(`  - Tốt: ${rest}`)
        }
      }
      continue
    }

    const childMatch = line.match(/^\s*-\s*(Tốt|Chưa tốt|Yếu)\s*:\s*(.*)$/i)
    if (childMatch && currentSkill) {
      output.push(`  - ${childMatch[1]}: ${childMatch[2].trim()}`)
      continue
    }

    if (/^\s*-\s+/.test(line)) {
      currentSkill = null
      output.push(line)
      continue
    }

    output.push(line)
  }

  return output.join('\n')
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

function RadarChart({ payload }: { payload: LessonRadarPayload }) {
  const size = 320
  const center = size / 2
  const radius = 106
  const levels = [20, 40, 60, 80, 100]
  const points = payload.competencies.map((item, index) => {
    const angle = (-Math.PI / 2) + (index * 2 * Math.PI) / payload.competencies.length
    const valueRadius = (Math.max(0, Math.min(100, item.score)) / 100) * radius
    return {
      x: center + valueRadius * Math.cos(angle),
      y: center + valueRadius * Math.sin(angle),
    }
  })
  const polygonPoints = points.map((point) => `${point.x},${point.y}`).join(' ')

  return (
    <section className="radar-card" aria-label="Radar 6 nang luc">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Bieu do radar 6 nang luc">
        {levels.map((level) => {
          const ringPoints = payload.competencies.map((_item, index) => {
            const angle = (-Math.PI / 2) + (index * 2 * Math.PI) / payload.competencies.length
            const ringRadius = (level / 100) * radius
            const x = center + ringRadius * Math.cos(angle)
            const y = center + ringRadius * Math.sin(angle)
            return `${x},${y}`
          })
          return (
            <polygon key={level} points={ringPoints.join(' ')} className="radar-ring" />
          )
        })}
        {payload.competencies.map((item, index) => {
          const angle = (-Math.PI / 2) + (index * 2 * Math.PI) / payload.competencies.length
          const x = center + radius * Math.cos(angle)
          const y = center + radius * Math.sin(angle)
          const labelX = center + (radius + 24) * Math.cos(angle)
          const labelY = center + (radius + 24) * Math.sin(angle)
          return (
            <g key={item.key}>
              <line x1={center} y1={center} x2={x} y2={y} className="radar-axis" />
              <text x={labelX} y={labelY} className="radar-label" textAnchor="middle">
                {item.label}
              </text>
            </g>
          )
        })}
        <polygon points={polygonPoints} className="radar-shape" />
      </svg>
      <ul className="radar-legend">
        {payload.competencies.map((item) => (
          <li key={item.key}>
            <strong>{item.label}</strong>: {item.score}
            {item.insufficient_data ? ' (chua du du lieu)' : ''}
          </li>
        ))}
      </ul>
    </section>
  )
}

function RadarChartSkeleton() {
  return (
    <section className="radar-card radar-card--skeleton" aria-label="Dang tai bieu do radar">
      <div className="radar-skeleton__title" />
      <div className="radar-skeleton__chart" />
      <div className="radar-skeleton__legend">
        <span />
        <span />
        <span />
        <span />
      </div>
    </section>
  )
}

function App() {
  const [feedbackMode, setFeedbackMode] = useState<'lesson' | 'portfolio' | null>(null)
  const [activeFeedbackLabel, setActiveFeedbackLabel] = useState('')
  const [feedbackMarkdown, setFeedbackMarkdown] = useState('')
  const [lessonRadarPayload, setLessonRadarPayload] = useState<LessonRadarPayload | null>(null)
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
  const resolvedLessonRadarPayload = useMemo(() => {
    if (feedbackMode !== 'lesson') {
      return null
    }
    if (lessonRadarPayload) {
      return lessonRadarPayload
    }
    if (!formattedMarkdown.trim()) {
      return null
    }
    return parseLessonRadarFromMarkdown(formattedMarkdown)
  }, [feedbackMode, formattedMarkdown, lessonRadarPayload])
  const lessonCount = reportLinks.length

  const handleGenerateFeedback = async (lessonId: string, lessonLabel: string) => {
    setFeedbackMode('lesson')
    setActiveFeedbackLabel(lessonLabel)
    setFeedbackError(null)
    setFeedbackLoadingId(lessonId)
    setFeedbackStreamingStatus('Dang bat dau tao nhan xet...')
    setFeedbackMarkdown('')
    setLessonRadarPayload(null)

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
          } else if (eventName === 'result') {
            try {
              const parsed = JSON.parse(eventData) as LessonRadarPayload
              if (parsed?.type === 'lesson_radar' && Array.isArray(parsed.competencies)) {
                setLessonRadarPayload(parsed)
              }
            } catch (_error) {
              // Ignore invalid result payload and rely on markdown fallback parser.
            }
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
    setLessonRadarPayload(null)

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
              <article className="summary-result">
                <p className="summary-result__context">
                  Dang hien thi: <strong>{activeFeedbackLabel}</strong>
                </p>
                <div className="summary-result__split">
                  <div className="summary-result__chart-pane">
                    <RadarChartSkeleton />
                  </div>
                  <div className="summary-result__markdown-pane">
                    {feedbackMarkdown ? (
                      <MarkdownView content={formattedMarkdown} />
                    ) : (
                      <p className="summary-result__placeholder">Dang tai noi dung nhan xet...</p>
                    )}
                  </div>
                </div>
              </article>
            </article>
          )}

          {feedbackError && <p className="feedback feedback--error">{feedbackError}</p>}

          {!feedbackLoadingId && feedbackMarkdown && (
            <article className="summary-result" data-testid={`markdown-result-${feedbackMode ?? 'none'}`}>
              <p className="summary-result__context">
                Dang hien thi: <strong>{activeFeedbackLabel}</strong>
              </p>
              <div
                className={`summary-result__split ${resolvedLessonRadarPayload ? '' : 'summary-result__split--single'}`}
              >
                {resolvedLessonRadarPayload && (
                  <div className="summary-result__chart-pane">
                    <RadarChart payload={resolvedLessonRadarPayload} />
                  </div>
                )}
                <div className="summary-result__markdown-pane">
                  <MarkdownView content={formattedMarkdown} />
                </div>
              </div>
            </article>
          )}
        </section>
      </div>
    </main>
  )
}

export default App
