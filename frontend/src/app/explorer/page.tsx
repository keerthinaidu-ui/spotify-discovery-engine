'use client'

import React, { useState, useEffect } from 'react'
import explorerStyles from './page.module.css'
import Sidebar from '@/components/Sidebar'
import ExplorerFilters from '@/components/ExplorerFilters'
import Header from '@/components/Header'
import FeedbackCard from '@/components/FeedbackCard'
import Chatbot from '@/components/Chatbot'
import HistoryView from '@/components/HistoryView'
import { getFeedback, getSummary } from '../../lib/api'
import { FeedbackItem } from '../../lib/types'

export default function ExplorerPage() {
  const [filters, setFilters] = useState<any>({
    start_date: '',
    end_date: '',
    sentiment_list: ['positive', 'neutral', 'negative', 'unclear'],
    platform_list: ['app_store', 'play_store', 'product_hunt', 'youtube'],
    rating: '',
    app_version: '',
    issue_category: '',
    secondary_tag: '',
  })
  
  const [headerSearch, setHeaderSearch] = useState('')
  const [headerTab, setHeaderTab] = useState('reports')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInitialQuery, setChatInitialQuery] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // API states
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [analyzedCount, setAnalyzedCount] = useState(0)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('created_at')
  const [loading, setLoading] = useState(false)

  const itemsPerPage = 10

  // Load initial filters from URL on mount (Deep Linking)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const category = params.get('issue_category') || ''
    const secondary_tag = params.get('secondary_tag') || ''
    const rating = params.get('rating') || ''
    const app_version = params.get('app_version') || ''
    const start_date = params.get('start_date') || ''
    const end_date = params.get('end_date') || ''
    const q = params.get('q') || ''
    
    const sentimentParam = params.get('sentiment')
    const sentiment_list = sentimentParam ? sentimentParam.split(',') : ['positive', 'neutral', 'negative', 'unclear']
    
    const platformParam = params.get('platform')
    const platform_list = platformParam ? platformParam.split(',') : ['app_store', 'play_store', 'product_hunt', 'youtube']

    setFilters({
      start_date,
      end_date,
      sentiment_list,
      platform_list,
      rating,
      app_version,
      issue_category: category,
      secondary_tag,
    })
    
    if (q) {
      setHeaderSearch(q)
    }

    // Scroll to reviews section if issue_category, secondary_tag, or search is preset
    if (category || secondary_tag || q || rating || app_version) {
      setTimeout(() => {
        const reviewSection = document.getElementById('reviews-section')
        if (reviewSection) {
          reviewSection.scrollIntoView({ behavior: 'smooth' })
        }
      }, 500)
    }
  }, [])

  // Synchronize active filters to URL search params
  useEffect(() => {
    const params = new URLSearchParams()
    if (filters.issue_category) params.set('issue_category', filters.issue_category)
    if (filters.secondary_tag) params.set('secondary_tag', filters.secondary_tag)
    if (filters.rating) params.set('rating', filters.rating)
    if (filters.app_version) params.set('app_version', filters.app_version)
    if (filters.start_date) params.set('start_date', filters.start_date)
    if (filters.end_date) params.set('end_date', filters.end_date)
    
    if (filters.sentiment_list && filters.sentiment_list.length < 4) {
      params.set('sentiment', filters.sentiment_list.join(','))
    }
    if (filters.platform_list && filters.platform_list.length < 4) {
      params.set('platform', filters.platform_list.join(','))
    }
    if (headerSearch) {
      params.set('q', headerSearch)
    }

    const queryString = params.toString()
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname
    window.history.replaceState(null, '', newUrl)
  }, [filters, headerSearch])

  // Fetch feedback entries and summary on filter changes
  useEffect(() => {
    let active = true
    async function loadData() {
      setLoading(true)
      try {
        const activePlatform = filters.platform_list && filters.platform_list.length > 0
          ? filters.platform_list.join(',')
          : undefined
        const activeSentiment = filters.sentiment_list && filters.sentiment_list.length > 0
          ? filters.sentiment_list.join(',')
          : undefined

        const activeFilters = {
          platform: activePlatform,
          sentiment: activeSentiment,
          q: headerSearch || undefined,
          start_date: filters.start_date || undefined,
          end_date: filters.end_date || undefined,
          rating: filters.rating || undefined,
          app_version: filters.app_version || undefined,
          issue_category: filters.issue_category || undefined,
          secondary_tag: filters.secondary_tag || undefined,
          has_mixed_sentiment: filters.has_mixed_sentiment,
        }

        const [feedbackRes, summaryRes] = await Promise.all([
          getFeedback({
            page,
            perPage: itemsPerPage,
            sortBy,
            q: headerSearch || undefined,
            platform: activePlatform,
            sentiment: activeSentiment,
            start_date: filters.start_date || undefined,
            end_date: filters.end_date || undefined,
            rating: filters.rating || undefined,
            app_version: filters.app_version || undefined,
            issue_category: filters.issue_category || undefined,
            secondary_tag: filters.secondary_tag || undefined,
            has_mixed_sentiment: filters.has_mixed_sentiment,
          }),
          getSummary(activeFilters)
        ])

        if (!active) return

        setItems(feedbackRes.items)
        setTotalCount(feedbackRes.total)
        setAnalyzedCount(summaryRes.totalAnalyzed)
        setIsAnalyzing(summaryRes.isAnalyzing || false)
      } catch (e) {
        console.error(e)
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }
    loadData()
    return () => {
      active = false
    }
  }, [filters, headerSearch, page, sortBy])

  // Polling logic when background analysis is active
  useEffect(() => {
    let active = true
    let intervalId: any
    if (isAnalyzing) {
      intervalId = setInterval(async () => {
        try {
          const activePlatform = filters.platform_list && filters.platform_list.length > 0
            ? filters.platform_list.join(',')
            : undefined
          const activeSentiment = filters.sentiment_list && filters.sentiment_list.length > 0
            ? filters.sentiment_list.join(',')
            : undefined
          const activeFilters = {
            platform: activePlatform,
            sentiment: activeSentiment,
            q: headerSearch || undefined,
            start_date: filters.start_date || undefined,
            end_date: filters.end_date || undefined,
            rating: filters.rating || undefined,
            app_version: filters.app_version || undefined,
            issue_category: filters.issue_category || undefined,
            has_mixed_sentiment: filters.has_mixed_sentiment,
          }

          const [feedbackRes, summaryRes] = await Promise.all([
            getFeedback({
              page,
              perPage: itemsPerPage,
              sortBy,
              q: headerSearch || undefined,
              platform: activePlatform,
              sentiment: activeSentiment,
              start_date: filters.start_date || undefined,
              end_date: filters.end_date || undefined,
              rating: filters.rating || undefined,
              app_version: filters.app_version || undefined,
              issue_category: filters.issue_category || undefined,
              has_mixed_sentiment: filters.has_mixed_sentiment,
            }),
            getSummary(activeFilters)
          ])

          if (!active) return

          setItems(feedbackRes.items)
          setTotalCount(feedbackRes.total)
          setAnalyzedCount(summaryRes.totalAnalyzed)
          setIsAnalyzing(summaryRes.isAnalyzing || false)
        } catch (e) {
          console.error(e)
        }
      }, 3000)
    }
    return () => {
      active = false
      if (intervalId) clearInterval(intervalId)
    }
  }, [isAnalyzing, filters, headerSearch, page, sortBy])

  const handleFilterChange = (key: string, value: any) => {
    setFilters((prev: any) => ({ ...prev, [key]: value }))
    setPage(1)
  }

  const handleHistorySearchClick = (keyword: string) => {
    setHeaderSearch(keyword)
    setPage(1)
    setHeaderTab('reports')
  }

  const handleHistoryChatClick = (query: string) => {
    setChatInitialQuery(query)
    setChatOpen(true)
    setHeaderTab('reports')
  }

  const handleResetAll = () => {
    setFilters({
      start_date: '',
      end_date: '',
      sentiment_list: ['positive', 'neutral', 'negative', 'unknown'],
      platform_list: ['app_store', 'play_store', 'product_hunt', 'youtube'],
      rating: '',
      app_version: '',
      issue_category: '',
    })
    setHeaderSearch('')
    setPage(1)
  }

  const handleSortToggle = () => {
    setSortBy((prev) => (prev === 'created_at' ? 'rating_or_score' : 'created_at'))
    setPage(1)
  }

  const totalPages = Math.max(Math.ceil(totalCount / itemsPerPage), 1)

  // Safeguard: Reset page to 1 if it goes out of bounds when totalPages shrinks
  useEffect(() => {
    if (page > totalPages) {
      setPage(1)
    }
  }, [totalPages, page])

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* 1. Left Sidebar Navigation Column */}
      <Sidebar
        activeTab="explorer"
        filters={filters}
        onFilterChange={handleFilterChange}
        onResetFilters={handleResetAll}
        onToggleChat={() => setChatOpen(!chatOpen)}
        sidebarOpen={sidebarOpen}
        onCloseSidebar={() => setSidebarOpen(false)}
      />

      {/* Main Canvas Wrapping Center Filters Column & Right Feed Canvas */}
      <div className={explorerStyles.container}>
        
        {/* 2. Center Explorer Filters Sidebar Column */}
        {headerTab !== 'history' && (
          <ExplorerFilters
            filters={filters}
            onFilterChange={handleFilterChange}
            onResetFilters={handleResetAll}
          />
        )}

        {/* 3. Right Feed Canvas Column */}
        <div className={explorerStyles.feedCanvas} style={headerTab === 'history' ? { flex: 1 } : undefined}>
          <Header
            searchText={headerSearch}
            onSearchChange={(val) => {
              setHeaderSearch(val)
              setPage(1)
            }}
            activeTab={headerTab}
            onTabChange={setHeaderTab}
            onNewQuery={handleResetAll}
            placeholder="Search evidence..."
            onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
            reportsTabLabel="Reviews"
          />

          <div className={explorerStyles.contentArea}>
            {headerTab === 'history' ? (
              <HistoryView
                onSearchClick={handleHistorySearchClick}
                onChatClick={handleHistoryChatClick}
              />
            ) : (
              <>
                {/* Analyzed Feedback Meter Banner */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-surface-container-high)',
                  borderRadius: 'var(--radius-lg)',
                  marginBottom: '16px',
                  border: '1px solid rgba(62, 62, 62, 0.1)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="material-symbols-outlined" style={{ color: 'var(--color-primary-fixed)' }}>
                      insights
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: '600' }}>
                      Analyzed Feedback Meter: {analyzedCount.toLocaleString()} / {totalCount.toLocaleString()} reviews
                    </span>
                  </div>
                  {isAnalyzing && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-secondary)' }}>
                      <span className={`material-symbols-outlined ${explorerStyles.spinner}`} style={{ fontSize: '18px' }}>
                        autorenew
                      </span>
                      <span style={{ fontSize: '12px' }}>AI Ingestion Analysis Running...</span>
                    </div>
                  )}
                </div>

                <div id="reviews-section" className={explorerStyles.headerRow}>
                  <h2 className={explorerStyles.title}>
                    {totalCount.toLocaleString()} Feedback entries found
                  </h2>
                  
                  <button
                    onClick={handleSortToggle}
                    className={explorerStyles.sortContainer}
                    aria-label={`Sort by ${sortBy === 'created_at' ? 'Rating' : 'Date'}`}
                  >
                    <span className={`material-symbols-outlined ${explorerStyles.sortIcon}`}>
                      swap_vert
                    </span>
                    <span>Sort by: {sortBy === 'created_at' ? 'Newest' : 'Rating'}</span>
                  </button>
                </div>

                <div className={explorerStyles.feedList}>
                  {loading ? (
                    <div className={explorerStyles.loadingWrapper}>
                      <span className={`material-symbols-outlined ${explorerStyles.spinner}`}>
                        autorenew
                      </span>
                      <span>Fetching feedback...</span>
                    </div>
                  ) : items.length === 0 ? (
                    <div className={explorerStyles.emptyState}>
                      <span className={`material-symbols-outlined ${explorerStyles.emptyIcon}`}>
                        rule_folder
                      </span>
                      <p>No feedback entries match your active filters.</p>
                    </div>
                  ) : (
                    items.map((item) => (
                      <FeedbackCard key={item.id} item={item} />
                    ))
                  )}
                </div>

                {/* Pagination controls */}
                {totalCount > 0 && (
                  <div className={explorerStyles.paginationRow}>
                    <span className={explorerStyles.pageInfo}>
                      Page {page} of {totalPages}
                    </span>
                    <div className={explorerStyles.paginationBtnWrapper}>
                      <button
                        disabled={page === 1}
                        onClick={() => setPage((prev) => prev - 1)}
                        className={explorerStyles.paginationBtn}
                      >
                        Previous
                      </button>
                      <button
                        disabled={page === totalPages}
                        onClick={() => setPage((prev) => prev + 1)}
                        className={explorerStyles.paginationBtn}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Floating chatbot window */}
      <Chatbot
        filters={filters}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        initialQuery={chatInitialQuery}
        onClearInitialQuery={() => setChatInitialQuery('')}
      />
    </div>
  )
}
