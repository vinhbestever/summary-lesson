import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

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
      'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=TRIAL_LESSON_10_11',
    )
    expect(linkOne).toHaveAttribute('target', '_blank')

    expect(linkTwo).toHaveAttribute(
      'href',
      'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=3724970',
    )
    expect(linkTwo).toHaveAttribute('target', '_blank')
  })

  it('requests lesson feedback and renders shared panel', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        lesson_label: 'Trial Lesson 10_11',
        teacher_tone: 'warm_encouraging',
        overall_comment: 'Con hoc rat tap trung.',
        session_breakdown: {
          participation: { score: 85, comment: 'Tot', evidence: ['20 luot noi'] },
          pronunciation: { score: 72, comment: 'Kha', evidence: ['Diem 72'] },
          vocabulary: { score: 80, comment: 'Tot', evidence: ['5 tu'] },
          grammar: { score: 78, comment: 'On', evidence: ['3 cau'] },
          reaction_confidence: { score: 88, comment: 'Nhanh', evidence: ['2s'] },
        },
        strengths: ['Tu tin', 'Nho tu tot'],
        priority_improvements: [
          {
            skill: 'pronunciation',
            priority: 'high',
            current_state: 'Am cuoi con yeu',
            target_next_lesson: 'Dat 80+',
            coach_tip: 'Luyen 10 phut/ngay',
          },
        ],
        next_lesson_plan: [{ step: 'On tu', duration_minutes: 8 }],
        parent_message: 'Con dang tien bo rat tot.',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet ai/i })[0])

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(requestBody).toMatchObject({ lesson_id: 'TRIAL_LESSON_10_11' })
    expect(await screen.findByRole('heading', { name: /nhan xet buoi hoc - trial lesson 10_11/i })).toBeInTheDocument()
    expect(screen.getByText(/con hoc rat tap trung/i)).toBeInTheDocument()
  })

  it('shows loading state while requesting lesson feedback', async () => {
    let resolveRequest: ((value: unknown) => void) | undefined
    const pendingPromise = new Promise((resolve) => {
      resolveRequest = resolve
    })
    const fetchMock = vi.fn().mockReturnValue(pendingPromise)
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet ai/i })[0])

    expect(screen.getByText(/dang bat dau tao nhan xet/i)).toBeInTheDocument()
    resolveRequest?.({
      ok: true,
      json: async () => ({
        lesson_label: 'Trial Lesson 10_11',
        teacher_tone: 'warm_encouraging',
        overall_comment: 'ok',
        session_breakdown: {
          participation: { score: 80, comment: 'ok', evidence: ['e'] },
          pronunciation: { score: 80, comment: 'ok', evidence: ['e'] },
          vocabulary: { score: 80, comment: 'ok', evidence: ['e'] },
          grammar: { score: 80, comment: 'ok', evidence: ['e'] },
          reaction_confidence: { score: 80, comment: 'ok', evidence: ['e'] },
        },
        strengths: ['s'],
        priority_improvements: [],
        next_lesson_plan: [],
        parent_message: 'msg',
      }),
    })

    await waitFor(() => expect(screen.queryByText(/dang tao nhan xet/i)).not.toBeInTheDocument())
  })

  it('shows friendly error when lesson feedback request fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'boom' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet ai/i })[0])

    expect(await screen.findByText(/chua tao duoc nhan xet\. vui long thu lai\./i)).toBeInTheDocument()
  })
})
