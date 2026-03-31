import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function createStreamResponse(events: string[]) {
  const encoder = new TextEncoder()
  const payload = events.join('\n\n') + '\n\n'
  let sent = false

  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (sent) {
            return { done: true, value: undefined }
          }
          sent = true
          return { done: false, value: encoder.encode(payload) }
        },
      }),
    },
  }
}

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows two report options linking to the expected URLs', () => {
    render(<App />)

    const linkOne = screen.getByRole('link', { name: /trial lesson 10_11/i })
    const linkTwo = screen.getByRole('link', { name: /lesson 3724970/i })

    expect(linkOne).toHaveAttribute(
      'href',
      expect.stringContaining('erp_lesson_id=TRIAL_LESSON_10_11'),
    )
    expect(linkOne).toHaveAttribute('target', '_blank')

    expect(linkTwo).toHaveAttribute(
      'href',
      expect.stringContaining('erp_lesson_id=3724970'),
    )
    expect(linkTwo).toHaveAttribute('target', '_blank')
  })

  it('requests lesson feedback and renders shared panel', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: {"type":"status","message":"Dang phan tich"}',
        'event: result\ndata: {"type":"result","data":{"lesson_label":"Trial Lesson 10_11","teacher_tone":"warm_encouraging","overall_comment":"Con hoc rat tap trung.","session_breakdown":{"participation":{"score":85,"comment":"Tot","evidence":["20 luot noi"]},"pronunciation":{"score":72,"comment":"Kha","evidence":["Diem 72"]},"vocabulary":{"score":80,"comment":"Tot","evidence":["5 tu"]},"grammar":{"score":78,"comment":"On","evidence":["3 cau"]},"reaction_confidence":{"score":88,"comment":"Nhanh","evidence":["2s"]}},"strengths":["Tu tin","Nho tu tot"],"priority_improvements":[{"skill":"pronunciation","priority":"high","current_state":"Am cuoi con yeu","target_next_lesson":"Dat 80+","coach_tip":"Luyen 10 phut/ngay"}],"next_lesson_plan":[{"step":"On tu","duration_minutes":8}],"parent_message":"Con dang tien bo rat tot."}}',
        'event: done\ndata: {"type":"done"}',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(requestBody).toMatchObject({ lesson_id: 'TRIAL_LESSON_10_11' })
    expect(await screen.findByRole('heading', { name: /nhan xet buoi hoc - trial lesson 10_11/i })).toBeInTheDocument()
    expect(screen.getByText(/con hoc rat tap trung/i)).toBeInTheDocument()
  })

  it('shows loading state while requesting lesson feedback', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: {"type":"status","message":"Dang bat dau tao nhan xet..."}',
        'event: done\ndata: {"type":"done"}',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    expect(screen.getByText(/dang bat dau tao nhan xet/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(/dang bat dau tao nhan xet/i)).not.toBeInTheDocument())
  })

  it('shows friendly error when lesson feedback request fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      body: null,
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    expect(await screen.findByText(/chua tao duoc nhan xet\. vui long thu lai\./i)).toBeInTheDocument()
  })

  it('requests portfolio feedback stream and renders portfolio panel', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: {"type":"status","message":"Dang phan tich tong hop"}',
        'event: result\ndata: {"type":"result","data":{"portfolio_label":"Tong hop toan bo buoi hoc","total_lessons":2,"date_range":{"from_date":"2026-03-01","to_date":"2026-03-31"},"overall_assessment":"Tien bo on dinh qua cac buoi.","skill_trends":{"participation":{"current_level":"kha","trend":"improving","evidence":["e1"],"recommendation":"r1"},"pronunciation":{"current_level":"tb","trend":"stable","evidence":["e2"],"recommendation":"r2"},"vocabulary":{"current_level":"kha","trend":"improving","evidence":["e3"],"recommendation":"r3"},"grammar":{"current_level":"tb","trend":"mixed","evidence":["e4"],"recommendation":"r4"},"reaction_confidence":{"current_level":"kha","trend":"improving","evidence":["e5"],"recommendation":"r5"}},"top_strengths":["Tu tin"],"top_priorities":[{"skill":"pronunciation","priority":"high","reason":"x","next_2_weeks_target":"y","coach_tip":"z"}],"study_plan_2_weeks":[{"step":"On tu","frequency":"4 buoi/tuan","duration_minutes":10}],"parent_message":"Con dang tien bo rat tot."}}',
        'event: done\ndata: {"type":"done"}',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /nhan xet chung/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/portfolio-feedback/stream')
    expect(await screen.findByRole('heading', { name: /nhan xet chung qua trinh hoc/i })).toBeInTheDocument()
    expect(screen.getByText(/tong so buoi: 2/i)).toBeInTheDocument()
    expect(screen.getByText(/tien bo on dinh qua cac buoi/i)).toBeInTheDocument()
  })
})
