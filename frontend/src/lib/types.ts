export const PRIMARY_THEMES = [
  "Music Discovery",
  "Recommendations",
  "Playlists",
  "Shuffle Experience",
  "Radio",
  "Search & Browse",
  "Library Management",
  "Social Discovery",
  "Podcast vs Music",
  "Premium vs Free Experience",
  "Unidentified"
] as const

export const SECONDARY_TAGS = [
  "Artist Discovery",
  "Genre Exploration",
  "Mood-Based Listening",
  "Activity-Based Listening",
  "Personalization",
  "Recommendation Accuracy",
  "Content Variety",
  "Listening Habits",
  "New Releases",
  "Feature Requests",
  "Recommendation Trust",
  "Discovery Features",
  "Repetitive Listening"
] as const

export const SENTIMENT_TAGS = [
  "positive",
  "negative",
  "neutral",
  "unclear"
] as const

export const ISSUE_CATEGORIES = PRIMARY_THEMES
export type IssueCategory = typeof PRIMARY_THEMES[number]

export interface FeedbackItem {
  id: string
  source_type: string
  platform: string
  text: string
  title?: string
  rating_or_score?: number
  author?: string
  created_at?: string
  url?: string
  sentiment?: string
  issue_category?: string
  primary_theme?: string
  app_version?: string
  has_mixed_sentiment?: boolean
  sentiment_profile?: {
    positive_aspects: string[]
    negative_aspects: string[]
  }
}

export interface KPIData {
  totalAnalyzed: number
  negativeCount: number
  positiveCount: number
  neutralCount: number
  unclearCount: number
  topCategoryName: IssueCategory | string
  topCategoryCount: number
  isAnalyzing?: boolean
  secondaryTags?: { name: string; count: number }[]
}

export interface CompareMatrixData {
  [platformOrSource: string]: {
    [category in IssueCategory]?: number
  }
}

export interface SentimentBreakdown {
  positive: number
  negative: number
  neutral: number
  total: number
}

export interface InsightItem {
  type: 'Pain Points' | 'Unmet Needs' | 'Personas'
  text: string
}

export interface ChatRequest {
  query: string
  q?: string | null
  platform?: string | null
  source_type?: string | null
  sentiment?: string | null
  user_segment?: string | null
  issue_category?: IssueCategory | null
  has_mixed_sentiment?: boolean | null
}

export interface ChatResponse {
  answer: string
  total_count: number
  evidence_snippets: string[]
  mode: 'llm' | 'fallback'
  llm_used: boolean
}

export interface ExplorerFilters {
  date_range?: string
  sentiment_list?: string[]
  platform_list?: string[]
  q?: string
  source_type?: string
  sentiment?: string
  user_segment?: string
  start_date?: string
  end_date?: string
  has_mixed_sentiment?: boolean
}
