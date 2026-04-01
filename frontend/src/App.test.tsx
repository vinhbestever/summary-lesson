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

  it('loads report options from local lesson data files', () => {
    render(<App />)

    const trialLink = screen.getByRole('link', { name: /trial_lesson_over_7/i })
    const reportLinks = screen.getAllByRole('link')

    expect(trialLink).toHaveAttribute(
      'href',
      expect.stringContaining('erp_lesson_id=TRIAL_LESSON_OVER_7'),
    )
    expect(trialLink).toHaveAttribute('target', '_blank')
    expect(reportLinks.length).toBeGreaterThan(2)
  })

  it('shows lesson time and keeps lessons sorted by latest start time first', () => {
    render(<App />)

    const timeNodes = screen.getAllByTestId('report-card-time')
    expect(timeNodes.length).toBeGreaterThan(0)
    expect(timeNodes.some((node) => /thoi gian hoc:/i.test(node.textContent ?? ''))).toBe(true)

    const timestamps = timeNodes
      .map((node) => node.getAttribute('data-start-time') ?? '')
      .filter((value) => value.length > 0)
      .map((value) => {
        const normalized = value.replace(' ', 'T')
        return Number(new Date(normalized))
      })
      .filter((value) => Number.isFinite(value))

    expect(timestamps.length).toBeGreaterThan(1)
    for (let i = 0; i < timestamps.length - 1; i += 1) {
      expect(timestamps[i]).toBeGreaterThanOrEqual(timestamps[i + 1])
    }
  })

  it('shows lesson order from highest to lowest', () => {
    const { container } = render(<App />)

    const orderNodes = Array.from(container.querySelectorAll('.report-card__order'))
    expect(orderNodes.length).toBeGreaterThan(1)

    const orders = orderNodes
      .map((node) => node.textContent?.match(/\d+/)?.[0] ?? '')
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value))

    expect(orders.length).toBe(orderNodes.length)
    for (let i = 0; i < orders.length - 1; i += 1) {
      expect(orders[i]).toBeGreaterThan(orders[i + 1])
    }
  })

  it('renders lesson markdown from raw sse chunks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet buoi hoc - TRIAL_LESSON_OVER_7\ndata: \ndata: ## Tong quan\ndata: \ndata: Con hoc rat tap trung.',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    const trialLink = screen.getByRole('link', { name: /trial_lesson_over_7/i })
    const trialCard = trialLink.closest('article')
    const trialFeedbackButton = trialCard?.querySelector<HTMLButtonElement>('button')
    if (!trialFeedbackButton) {
      throw new Error('Trial lesson feedback button not found')
    }
    fireEvent.click(trialFeedbackButton)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(requestBody).toMatchObject({ lesson_id: 'TRIAL_LESSON_OVER_7' })
    expect(
      await screen.findByRole('heading', { name: /nhan xet buoi hoc - trial_lesson_over_7/i }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: /tong quan/i })).toBeInTheDocument()
    expect(screen.getByText(/con hoc rat tap trung/i)).toBeInTheDocument()
  })

  it('renders radar chart from lesson result event', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: result\ndata: {"type":"lesson_radar","competencies":[{"key":"learn","label":"A. Learn","score":76,"insufficient_data":false},{"key":"recognize","label":"B. Recognize","score":80,"insufficient_data":false},{"key":"apply","label":"C. Apply","score":62,"insufficient_data":false},{"key":"retain","label":"D. Retain","score":55,"insufficient_data":false},{"key":"focus","label":"E. Focus","score":70,"insufficient_data":false},{"key":"express","label":"F. Express","score":48,"insufficient_data":false}]}',
        'event: chunk\ndata: # Nhan xet buoi hoc - TRIAL_LESSON_OVER_7\ndata: \ndata: ## Tong quan\ndata: \ndata: Con hoc rat tap trung.',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    expect(await screen.findByRole('heading', { name: /nhan xet buoi hoc - trial_lesson_over_7/i })).toBeInTheDocument()
  })

  it('falls back to parse radar from markdown when no result event', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet\ndata: \ndata: ## Đánh giá 6 năng lực\ndata: \ndata: - Learn - Học\ndata:   - Kết quả hiện tại: 72/100\ndata: - Recognize - Nhận biết\ndata:   - Kết quả hiện tại: Khá vững',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    expect(await screen.findByRole('heading', { name: /nhan xet/i })).toBeInTheDocument()
    expect(screen.getAllByText(/learn/i).length).toBeGreaterThan(0)
  })

  it('shows loading state while requesting lesson feedback', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang bat dau tao nhan xet...',
        'event: done\ndata: done',
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

  it('renders portfolio markdown from raw sse chunks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich tong hop',
        'event: chunk\ndata: # Nhan xet chung qua trinh hoc\ndata: \ndata: ## Tong quan qua trinh\ndata: \ndata: Tien bo on dinh qua cac buoi.',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /nhan xet chung/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/portfolio-feedback/stream')
    expect(await screen.findByRole('heading', { name: /nhan xet chung qua trinh hoc/i })).toBeInTheDocument()
    expect(screen.getByText(/tien bo on dinh qua cac buoi/i)).toBeInTheDocument()
  })

  it('does not render raw html from markdown content', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet\ndata: \ndata: <script>alert(1)</script>\ndata: Noi dung an toan',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    await screen.findByRole('heading', { name: /nhan xet/i })
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText(/noi dung an toan/i)).toBeInTheDocument()
  })

  it('formats inline skill details into clearer line breaks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet\ndata: \ndata: ## Danh gia tung ky nang\ndata: \ndata: - Nghe: Tốt: Bé nghe tốt | Chưa tốt: Một vài câu dài còn nhầm | Yếu: Cần nghe kỹ từ khóa',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    await screen.findByRole('heading', { name: /nhan xet/i })
    const listItems = container.querySelectorAll('.summary-result li')
    expect(listItems.length).toBeGreaterThan(1)
    expect(screen.getByText(/chưa tốt:/i)).toBeInTheDocument()
    expect(screen.getByText(/yếu:/i)).toBeInTheDocument()
  })

  it('groups misplaced skill sub-bullets under each skill', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet\ndata: \ndata: ## Danh gia tung ky nang\ndata: \ndata: - Nghe: - Tốt: Bé nghe tốt\ndata: - Chưa tốt: Còn nhầm vài câu\ndata: - Yếu: Chưa ổn định\ndata: - Nói: - Tốt: Nói khá tự tin\ndata: - Chưa tốt: Cần tròn âm hơn\ndata: - Yếu: Một số từ khó\ndata: - Đọc: - Tốt: Đọc khá trôi chảy\ndata: - Chưa tốt: Vấp ở câu dài\ndata: - Yếu: Cần luyện nhịp câu',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    await screen.findByRole('heading', { name: /nhan xet/i })

    const allLists = container.querySelectorAll('.summary-result ul')
    const topList = allLists[allLists.length - 1]
    expect(topList).not.toBeNull()
    const topLevelItems = topList?.querySelectorAll(':scope > li') ?? []
    expect(topLevelItems.length).toBe(3)
    expect(screen.getByText(/nghe:/i)).toBeInTheDocument()
    expect(screen.getByText(/nói:/i)).toBeInTheDocument()
    expect(screen.getByText(/đọc:/i)).toBeInTheDocument()
  })

  it('formats competency section into clear parent-child bullets', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'event: status\ndata: Dang phan tich',
        'event: chunk\ndata: # Nhan xet\ndata: \ndata: ## Đánh giá 6 năng lực\ndata: \ndata: - Learn - Học và tiếp thu kiến thức mới\ndata: - Đo lường: Hoàn thành 90%\ndata: - Kết quả hiện tại: Khá vững\ndata: - Nhận xét: Tiến bộ tốt\ndata: - Khuyến nghị: Duy trì luyện tập',
        'event: done\ndata: done',
      ]),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: /nhan xet/i })[0])

    await screen.findByRole('heading', { name: /nhan xet/i })

    const summary = container.querySelector('.summary-result')
    expect(summary).not.toBeNull()
    const items = summary?.querySelectorAll('li') ?? []
    expect(items.length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/a\. learn/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/đo lường:/i)).toBeInTheDocument()
    expect(screen.getByText(/kết quả hiện tại:/i)).toBeInTheDocument()
    expect(screen.getByText(/nhận xét:/i)).toBeInTheDocument()
    expect(screen.getByText(/khuyến nghị:/i)).toBeInTheDocument()
  })
})
