import { ISSUE_CATEGORIES as CANONICAL_CATEGORIES } from './types'

export const SENTIMENT_LABELS = {
  positive: 'Positive',
  negative: 'Negative',
  neutral: 'Neutral',
  unclear: 'Emotion Unclear',
}

export const PLATFORM_LABELS = {
  app_store: 'App Store',
  play_store: 'Play Store',
  youtube: 'YouTube',
  twitter: 'Twitter/X',
}

export const SAMPLE_QUESTIONS = [
  'Why are Premium users churned?',
  'Top 3 UI issues this month?',
  'Summary of YouTube comments',
]

export const GREEN_PILL_QUESTION = "Summarize the 'Discovery Quality' pain points from Spotify Reviews."

export const DATE_RANGES = [
  { value: '7', label: 'Last 7 Days' },
  { value: '30', label: 'Last 30 Days' },
  { value: '90', label: 'Last 90 Days' },
  { value: 'all', label: 'All Time' },
]

export const ISSUE_CATEGORIES = CANONICAL_CATEGORIES.reduce((acc, cat) => {
  acc[cat] = cat
  return acc
}, {} as Record<string, string>)
