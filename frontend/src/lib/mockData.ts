import { FeedbackItem, KPIData, CompareMatrixData, InsightItem } from './types'

export const MOCK_FEEDBACK_ITEMS: FeedbackItem[] = [
  {
    id: 'mock-1',
    author: 'John Doe',
    source_type: 'app_review',
    platform: 'app_store',
    sentiment: 'positive',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    text: 'The new analytics dashboard is incredibly fast. I love how I can drill down into specific user segments without any lag. Great job on the performance improvements!',
    rating_or_score: 5.0,
  },
  {
    id: 'mock-2',
    author: 'Alice Smith',
    source_type: 'app_review',
    platform: 'google_play',
    sentiment: 'neutral',
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    text: "It's okay, but I'm having trouble finding the export button for the raw data. It used to be right at the top, now I have to dig through settings.",
    rating_or_score: 3.0,
  },
  {
    id: 'mock-3',
    author: 'Unknown User',
    source_type: 'social_post',
    platform: 'twitter',
    sentiment: 'unclear',
    created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    text: 'Just updated the app. Still testing the new features. Will see how it goes over the next week.',
  },
]

export const MOCK_KPI_DATA: KPIData = {
  totalAnalyzed: 141347,
  negativeCount: 28542,
  positiveCount: 84109,
  neutralCount: 18542,
  unclearCount: 10154,
  topCategoryName: 'Recommendations',
  topCategoryCount: 4128,
  secondaryTags: [
    { name: 'Feature Requests', count: 3830 },
    { name: 'Activity-Based Listening', count: 1671 },
    { name: 'Discovery Features', count: 1298 },
    { name: 'Repetitive Listening', count: 1188 },
    { name: 'Genre Exploration', count: 1077 },
    { name: 'Listening Habits', count: 1070 },
  ]
}

export const MOCK_COMPARE_MATRIX: CompareMatrixData = {
  app_review: {
    'Music Discovery': 1240,
    'Recommendations': 15670,
    'Playlists': 8412,
    'Shuffle Experience': 3100,
    'Radio': 540,
    'Search & Browse': 1230,
    'Library Management': 320,
    'Social Discovery': 190,
    'Podcast vs Music': 250,
    'Premium vs Free Experience': 4300,
    'Unidentified': 1340,
  },
  producthunt_post: {
    'Music Discovery': 2,
    'Recommendations': 2,
    'Playlists': 5,
    'Shuffle Experience': 2,
    'Radio': 0,
    'Search & Browse': 1,
    'Library Management': 0,
    'Social Discovery': 0,
    'Podcast vs Music': 0,
    'Premium vs Free Experience': 1,
    'Unidentified': 2,
  },
  youtube_comment: {
    'Music Discovery': 68,
    'Recommendations': 24,
    'Playlists': 5,
    'Shuffle Experience': 10,
    'Radio': 1,
    'Search & Browse': 4,
    'Library Management': 5,
    'Social Discovery': 0,
    'Podcast vs Music': 0,
    'Premium vs Free Experience': 15,
    'Unidentified': 18,
  },
}

export const MOCK_INSIGHTS: InsightItem[] = [
  {
    type: 'Pain Points',
    text: 'Users feel recommendations are "recycled" and lacking novelty in Daily Mixes.',
  },
  {
    type: 'Unmet Needs',
    text: 'Request for "Collaborative Discovery" where friends can seed a shared discovery queue.',
  },
  {
    type: 'Personas',
    text: '"Active Explorers" are migrating to competitors for niche genre deep-dives.',
  },
]

export const MOCK_LOOP_CAUSES = [
  { name: 'Algo Monotony', percentage: 42 },
  { name: 'UI Navigation Friction', percentage: 28 },
  { name: 'Podcast Intrusiveness', percentage: 20 },
]

export const MOCK_VOLUME_DATA = [
  { date: 'Oct 02', count: 3200, height: '40%', opacity: '0.2' },
  { date: 'Oct 05', count: 2800, height: '35%', opacity: '0.2' },
  { date: 'Oct 08', count: 4800, height: '55%', opacity: '0.2' },
  { date: 'Oct 11', count: 3500, height: '45%', opacity: '0.2' },
  { date: 'Oct 14', count: 7800, height: '70%', opacity: '0.2' },
  { date: 'Oct 17', count: 7200, height: '85%', opacity: '0.2' },
  { date: 'Oct 20', count: 9600, height: '60%', opacity: '0.2' },
  { date: 'Oct 23', count: 8500, height: '75%', opacity: '0.3' },
  { date: 'Oct 26', count: 11200, height: '90%', opacity: '0.3' },
  { date: 'Oct 29', count: 14800, height: '100%', opacity: '1.0' }, // active highlighted bar
  { date: 'Oct 30', count: 10400, height: '80%', opacity: '0.3' },
  { date: 'Oct 31', count: 8900, height: '65%', opacity: '0.2' },
]
export const MOCK_PIE_TOTAL = '141k'
