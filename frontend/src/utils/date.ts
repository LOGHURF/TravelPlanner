export function toISODate(date: Date): string {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatDateLabel(value?: string): string {
  if (!value) {
    return ''
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
}

export function formatShortDate(value?: string): string {
  if (!value) {
    return ''
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}

export function isDateRangeValid(startDate?: string, endDate?: string): boolean {
  if (!startDate || !endDate) {
    return false
  }

  return new Date(startDate).getTime() <= new Date(endDate).getTime()
}

export function calculateTripDays(startDate: string, endDate: string): number {
  const start = new Date(startDate)
  const end = new Date(endDate)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return 0
  }

  return Math.max(1, Math.floor((end.getTime() - start.getTime()) / 86400000) + 1)
}
