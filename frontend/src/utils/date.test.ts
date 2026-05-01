import { describe, expect, it } from 'vitest'
import {
  calculateTripDays,
  formatShortDate,
  isDateRangeValid,
  toISODate,
} from '@/utils/date'

describe('date utils', () => {
  it('formats ISO date string', () => {
    const date = new Date(2026, 2, 1)
    expect(toISODate(date)).toBe('2026-03-01')
  })

  it('validates date range', () => {
    expect(isDateRangeValid('2026-03-01', '2026-03-05')).toBe(true)
    expect(isDateRangeValid('2026-03-05', '2026-03-01')).toBe(false)
  })

  it('calculates inclusive trip days', () => {
    expect(calculateTripDays('2026-03-01', '2026-03-03')).toBe(3)
  })

  it('formats short date for display', () => {
    expect(formatShortDate('2026-03-01')).toContain('3/')
  })
})
