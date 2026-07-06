import { PLATFORM_LABELS, ISSUE_CATEGORIES } from '../constants'

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}m`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(0)}k`
  }
  return num.toLocaleString()
}

export function formatPercentage(num: number): string {
  return `${Math.round(num)}%`
}

export function formatPlatform(platform: string): string {
  return PLATFORM_LABELS[platform as keyof typeof PLATFORM_LABELS] || platform.replace(/_/g, ' ')
}

export function formatCategory(category: string): string {
  return ISSUE_CATEGORIES[category as keyof typeof ISSUE_CATEGORIES] || category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function formatDate(dateStr?: string): string {
  if (!dateStr) return '2 hours ago'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
