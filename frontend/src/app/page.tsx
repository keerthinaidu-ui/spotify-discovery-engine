'use client'

import React, { useState, useEffect } from 'react'
import pageStyles from './page.module.css'
import Sidebar from '@/components/Sidebar'
import Header from '@/components/Header'
import KpiCard from '@/components/KpiCard'
import VolumeChart from '@/components/VolumeChart'
import CompareMatrix from '@/components/CompareMatrix'
import SentimentChart from '@/components/SentimentChart'
import InsightsPanel from '@/components/InsightsPanel'
import Chatbot from '@/components/Chatbot'
import HistoryView from '@/components/HistoryView'
import { getSummary, getComparison } from '../lib/api'
import { KPIData, CompareMatrixData } from '../lib/types'
import { formatNumber, formatCategory } from '../lib/utils/format'

export default function OverviewPage() {
  const [filters, setFilters] = useState<any>({
    q: '',
    source_type: '',
    sentiment: '',
    user_segment: '',
    start_date: '',
    end_date: '',
    platform: '',
  })
  
  const [headerSearch, setHeaderSearch] = useState('')
  const [headerTab, setHeaderTab] = useState('ask_ai')
  const [chatOpen, setChatOpen] = useState(true)
  const [chatInitialQuery, setChatInitialQuery] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // API states
  const [kpiData, setKpiData] = useState<KPIData>({
    totalAnalyzed: 0,
    negativeCount: 0,
    positiveCount: 0,
    neutralCount: 0,
    unclearCount: 0,
    topCategoryName: '',
    topCategoryCount: 0,
  })
  const [compareData, setCompareData] = useState<CompareMatrixData>({})

  // Fetch summary and comparison metrics
  useEffect(() => {
    async function loadMetrics() {
      const summary = await getSummary(filters)
      setKpiData(summary)
      
      const comparison = await getComparison(filters)
      setCompareData(comparison)
    }
    loadMetrics()
  }, [filters])

  // Sync search input with filter keywords
  useEffect(() => {
    setFilters((prev: any) => ({ ...prev, q: headerSearch }))
  }, [headerSearch])

  const handleFilterChange = (key: string, value: any) => {
    setFilters((prev: any) => ({ ...prev, [key]: value }))
  }

  const handleCellClick = (filterType: string, filterValue: string, category: string) => {
    const params = new URLSearchParams()
    if (filterType === 'source_type') {
      if (filterValue === 'app_review') {
        params.set('platform', 'app_store,play_store')
      } else if (filterValue === 'producthunt_post') {
        params.set('platform', 'product_hunt')
      } else if (filterValue === 'youtube_comment') {
        params.set('platform', 'youtube')
      }
    }
    if (category) {
      params.set('issue_category', category)
    }
    window.location.href = `/explorer/?${params.toString()}#reviews-section`
  }

  const handleHistorySearchClick = (keyword: string) => {
    setHeaderSearch(keyword)
    setFilters((prev: any) => ({ ...prev, q: keyword }))
    setHeaderTab('ask_ai')
  }

  const handleHistoryChatClick = (query: string) => {
    setChatInitialQuery(query)
    setChatOpen(true)
    setHeaderTab('ask_ai')
  }

  const handleInsightSelect = (text: string) => {
    // Fill search input and chatbot when insight selected
    setHeaderSearch(text)
    setChatOpen(true)
  }

  const handleNewQuery = () => {
    setFilters({
      q: '',
      source_type: '',
      sentiment: '',
      user_segment: '',
      start_date: '',
      end_date: '',
      platform: '',
    })
    setHeaderSearch('')
  }

  // Calculate sentiment percentages for doughnut ring legend
  const totalSentiment = kpiData.positiveCount + kpiData.negativeCount + (kpiData.neutralCount || 0) + (kpiData.unclearCount || 0)
  const positivePercentage = totalSentiment > 0 ? (kpiData.positiveCount / totalSentiment) * 100 : 0
  const negativePercentage = totalSentiment > 0 ? (kpiData.negativeCount / totalSentiment) * 100 : 0
  const neutralPercentage = totalSentiment > 0 ? ((kpiData.neutralCount || 0) / totalSentiment) * 100 : 0
  const unclearPercentage = totalSentiment > 0 ? ((kpiData.unclearCount || 0) / totalSentiment) * 100 : 0

  return (
    <div style={{ display: 'flex' }}>
      {/* Sidebar navigation */}
      <Sidebar
        activeTab="overview"
        filters={filters}
        onFilterChange={handleFilterChange}
        onResetFilters={handleNewQuery}
        onToggleChat={() => setChatOpen(!chatOpen)}
        sidebarOpen={sidebarOpen}
        onCloseSidebar={() => setSidebarOpen(false)}
      />

      {/* Main Container */}
      <div className={pageStyles.container}>
        <Header
          searchText={headerSearch}
          onSearchChange={setHeaderSearch}
          activeTab={headerTab}
          onTabChange={setHeaderTab}
          onNewQuery={handleNewQuery}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        {/* Dashboard Content */}
        <div className={pageStyles.contentArea}>
          
          {/* Header title area */}
          <div className={pageStyles.titleRow}>
            <div className={pageStyles.titleBlock}>
              <h2>Discovery Overview</h2>
              <p className={pageStyles.subtitle}>
                Aggregated insights across all connected feedback ecosystems.
              </p>
            </div>
          </div>

          {/* KPI Cards section */}
          <div className={pageStyles.kpiGrid}>
            <KpiCard
              type="analyzed"
              title="Analyzed Feedback"
              value={formatNumber(kpiData.totalAnalyzed)}
              trend="+12%"
              subBreakdown={[
                { label: 'Spotify CSV', count: '141,234' },
                { label: 'PH / YT', count: '113' },
              ]}
            />
            <KpiCard
              type="negative"
              title="Negative Sentiment"
              value={formatNumber(kpiData.negativeCount)}
              trend="-4.2%"
              percentage={Math.round(negativePercentage * 10) / 10}
            />
            <KpiCard
              type="positive"
              title="Positive Sentiment"
              value={formatNumber(kpiData.positiveCount)}
              trend="+8.1%"
              percentage={Math.round(positivePercentage * 10) / 10}
            />
            <KpiCard
              type="top_cause"
              title="Top Loop Cause"
              value={formatCategory(kpiData.topCategoryName)}
              mentionsCount={formatNumber(kpiData.topCategoryCount)}
              onClick={() => handleCellClick('issue_category', '', kpiData.topCategoryName)}
            />
          </div>

          {headerTab === 'history' ? (
            <HistoryView
              onSearchClick={handleHistorySearchClick}
              onChatClick={handleHistoryChatClick}
            />
          ) : (
            /* Asymmetric split layout */
            <div className={pageStyles.mainGrid}>
              {/* Left asymmetric panel (span 8) */}
              <div className={pageStyles.leftColumn}>
                <VolumeChart data={kpiData.secondaryTags} />
                <CompareMatrix
                  data={compareData}
                  onCellClick={handleCellClick}
                />
              </div>

              {/* Right asymmetric panel (span 4) */}
              <div className={pageStyles.rightColumn}>
                <SentimentChart
                  positivePercentage={positivePercentage}
                  negativePercentage={negativePercentage}
                  neutralPercentage={neutralPercentage}
                  unclearPercentage={unclearPercentage}
                  totalCount={formatNumber(kpiData.totalAnalyzed)}
                />
                <InsightsPanel
                  onInsightSelect={handleInsightSelect}
                />
              </div>
            </div>
          )}

        </div>

        {/* Floating Chatbot Overlay */}
        <Chatbot
          filters={filters}
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          initialQuery={chatInitialQuery}
          onClearInitialQuery={() => setChatInitialQuery('')}
        />
      </div>
    </div>
  )
}
