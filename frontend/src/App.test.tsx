import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
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
})
