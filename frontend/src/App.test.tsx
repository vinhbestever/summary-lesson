import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
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

  it('submits lesson_id when report_text is empty', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        overall_summary: 'Tom tat',
        key_points: ['A'],
        action_items: ['B'],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.change(screen.getByLabelText(/lesson id/i), { target: { value: '3724970' } })
    fireEvent.click(screen.getAllByRole('button', { name: /tom tat bao cao/i })[0])

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(requestBody).toMatchObject({ lesson_id: '3724970' })
  })
})
