import { env } from './env'
import { KPIData, CompareMatrixData, FeedbackItem, ChatRequest, ChatResponse } from './types'
import { MOCK_KPI_DATA, MOCK_COMPARE_MATRIX, MOCK_FEEDBACK_ITEMS } from './mockData'

const getBaseUrl = () => env.apiBaseUrl

function buildQueryParams(filters?: any): URLSearchParams {
  const query = new URLSearchParams()
  if (!filters) return query
  if (filters.platform) query.append('platform', filters.platform)
  if (filters.source_type) query.append('source_type', filters.source_type)
  if (filters.sentiment) query.append('sentiment', filters.sentiment)
  if (filters.q) query.append('q', filters.q)
  if (filters.user_segment) query.append('user_segment', filters.user_segment)
  if (filters.start_date) query.append('start_date', filters.start_date)
  if (filters.end_date) query.append('end_date', filters.end_date)
  if (filters.rating) query.append('rating', filters.rating.toString())
  if (filters.app_version) query.append('app_version', filters.app_version)
  if (filters.issue_category) query.append('issue_category', filters.issue_category)
  if (filters.secondary_tag) query.append('secondary_tag', filters.secondary_tag)
  if (filters.has_mixed_sentiment !== undefined) query.append('has_mixed_sentiment', filters.has_mixed_sentiment.toString())
  return query
}

export async function getSummary(filters?: any): Promise<KPIData> {
  try {
    const query = buildQueryParams(filters)
    const res = await fetch(`${getBaseUrl()}/insights/summary?${query.toString()}`)
    if (!res.ok) throw new Error('API request failed')
    const data = await res.json()
    
    // map FastAPI summary shape to KPIData interface
    const topCat = data.top_categories?.[0] || { name: 'Discovery Quality', count: 0 }
    
    // fetch pos/neg/neu/uncl totals to complement summary, passing filters
    let positiveCount = 0
    let negativeCount = 0
    let neutralCount = 0
    let unclearCount = 0
    try {
      const posQuery = buildQueryParams(filters)
      posQuery.set('sentiment', 'positive')
      posQuery.set('per_page', '1')

      const negQuery = buildQueryParams(filters)
      negQuery.set('sentiment', 'negative')
      negQuery.set('per_page', '1')

      const neuQuery = buildQueryParams(filters)
      neuQuery.set('sentiment', 'neutral')
      neuQuery.set('per_page', '1')

      const unclQuery = buildQueryParams(filters)
      unclQuery.set('sentiment', 'unclear')
      unclQuery.set('per_page', '1')

      const [posRes, negRes, neuRes, unclRes] = await Promise.all([
        fetch(`${getBaseUrl()}/feedback?${posQuery.toString()}`),
        fetch(`${getBaseUrl()}/feedback?${negQuery.toString()}`),
        fetch(`${getBaseUrl()}/feedback?${neuQuery.toString()}`),
        fetch(`${getBaseUrl()}/feedback?${unclQuery.toString()}`)
      ])
      if (posRes.ok) {
        const posData = await posRes.json()
        if (posData && posData.total >= 0) positiveCount = posData.total
      }
      if (negRes.ok) {
        const negData = await negRes.json()
        if (negData && negData.total >= 0) negativeCount = negData.total
      }
      if (neuRes.ok) {
        const neuData = await neuRes.json()
        if (neuData && neuData.total >= 0) neutralCount = neuData.total
      }
      if (unclRes.ok) {
        const unclData = await unclRes.json()
        if (unclData && unclData.total >= 0) unclearCount = unclData.total
      }
    } catch (e) {
      console.warn('FastAPI sentiment totals offline, using mock values.')
    }

    return {
      totalAnalyzed: data.total_analyzed || 0,
      negativeCount,
      positiveCount,
      neutralCount,
      unclearCount,
      topCategoryName: topCat.name,
      topCategoryCount: topCat.count,
      isAnalyzing: data.is_analyzing || false,
      secondaryTags: data.top_secondary_tags || [],
    }
  } catch (err) {
    console.warn('FastAPI offline, serving mock KPI data', err)
    return MOCK_KPI_DATA
  }
}

export async function getComparison(filters?: any): Promise<CompareMatrixData> {
  try {
    const query = buildQueryParams(filters)
    query.append('compare_by', 'source_type')
    const res = await fetch(`${getBaseUrl()}/insights/compare?${query.toString()}`)
    if (!res.ok) throw new Error('API request failed')
    const data = await res.json()
    return data.comparison || {}
  } catch (err) {
    console.warn('FastAPI offline, serving mock Compare Matrix data', err)
    return MOCK_COMPARE_MATRIX
  }
}

export async function getFeedback(params: {
  page: number
  perPage: number
  sortBy: string
  q?: string
  platform?: string
  source_type?: string
  sentiment?: string
  user_segment?: string
  start_date?: string
  end_date?: string
  rating?: string | number
  app_version?: string
  issue_category?: string
  secondary_tag?: string
  has_mixed_sentiment?: boolean
}): Promise<{ items: FeedbackItem[]; total: number }> {
  try {
    const query = new URLSearchParams()
    query.append('page', params.page.toString())
    query.append('per_page', params.perPage.toString())
    query.append('sort_by', params.sortBy)
    
    if (params.q) query.append('q', params.q)
    if (params.platform) query.append('platform', params.platform)
    if (params.source_type) query.append('source_type', params.source_type)
    if (params.sentiment) query.append('sentiment', params.sentiment)
    if (params.user_segment) query.append('user_segment', params.user_segment)
    if (params.start_date) query.append('start_date', params.start_date)
    if (params.end_date) query.append('end_date', params.end_date)
    if (params.rating) query.append('rating', params.rating.toString())
    if (params.app_version) query.append('app_version', params.app_version)
    if (params.issue_category) query.append('issue_category', params.issue_category)
    if (params.secondary_tag) query.append('secondary_tag', params.secondary_tag)
    if (params.has_mixed_sentiment !== undefined) query.append('has_mixed_sentiment', params.has_mixed_sentiment.toString())

    const res = await fetch(`${getBaseUrl()}/feedback?${query.toString()}`)
    if (!res.ok) throw new Error('API request failed')
    const data = await res.json()
    
    return {
      items: data.items || [],
      total: data.total || 0,
    }
  } catch (err) {
    console.warn('FastAPI offline, serving mock Feedback Items', err)
    return {
      items: MOCK_FEEDBACK_ITEMS,
      total: MOCK_FEEDBACK_ITEMS.length,
    }
  }
}

export async function sendChatQuery(payload: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${getBaseUrl()}/insights/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  
  if (!res.ok) {
    throw new Error(`Server returned HTTP ${res.status}`)
  }
  
  return res.json()
}
