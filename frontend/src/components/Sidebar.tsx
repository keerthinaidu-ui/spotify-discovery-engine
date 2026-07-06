'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import styles from './Sidebar.module.css'

interface SidebarProps {
  activeTab: 'overview' | 'explorer'
  filters: any
  onFilterChange: (key: string, value: any) => void
  onResetFilters: () => void
  onToggleChat: () => void
  sidebarOpen: boolean
  onCloseSidebar: () => void
}

export default function Sidebar({
  activeTab,
  filters,
  onFilterChange,
  onResetFilters,
  onToggleChat,
  sidebarOpen,
  onCloseSidebar,
}: SidebarProps) {
  // Local state for Overview Date Range inputs
  const [localStartDate, setLocalStartDate] = useState(filters.start_date || '')
  const [localEndDate, setLocalEndDate] = useState(filters.end_date || '')

  useEffect(() => {
    setLocalStartDate(filters.start_date || '')
    setLocalEndDate(filters.end_date || '')
  }, [filters.start_date, filters.end_date])

  const handleApplyFilters = () => {
    onFilterChange('start_date', localStartDate)
    onFilterChange('end_date', localEndDate)
  }

  const handleResetAll = () => {
    setLocalStartDate('')
    setLocalEndDate('')
    onResetFilters()
  }

  const handleSentimentPillClick = (val: string) => {
    const current = filters.sentiment || ''
    if (current === val) {
      onFilterChange('sentiment', '') // toggle off
    } else {
      onFilterChange('sentiment', val)
    }
  }

  const handleSourceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value
    if (val === 'app_review_google_play') {
      onFilterChange('source_type', 'app_review')
      onFilterChange('platform', 'play_store')
    } else if (val === 'app_review_app_store') {
      onFilterChange('source_type', 'app_review')
      onFilterChange('platform', 'app_store')
    } else if (val === 'producthunt_post') {
      onFilterChange('source_type', 'producthunt_post')
      onFilterChange('platform', '')
    } else if (val === 'youtube_comment') {
      onFilterChange('source_type', 'youtube_comment')
      onFilterChange('platform', '')
    } else {
      onFilterChange('source_type', '')
      onFilterChange('platform', '')
    }
  }

  let selectValue = ''
  if (filters.source_type === 'app_review') {
    if (filters.platform === 'play_store') selectValue = 'app_review_google_play'
    else if (filters.platform === 'app_store') selectValue = 'app_review_app_store'
  } else if (filters.source_type) {
    selectValue = filters.source_type
  }

  const getPillClass = (pillKey: string, activeVal: string) => {
    const isActive = activeVal === pillKey
    if (pillKey === 'positive') return isActive ? `${styles.pillButton} ${styles.pillPOSActive}` : `${styles.pillButton} ${styles.pillPOS}`
    if (pillKey === 'neutral') return isActive ? `${styles.pillButton} ${styles.pillNEUActive}` : `${styles.pillButton} ${styles.pillNEU}`
    if (pillKey === 'negative') return isActive ? `${styles.pillButton} ${styles.pillNEGActive}` : `${styles.pillButton} ${styles.pillNEG}`
    return isActive ? `${styles.pillButton} ${styles.pillUNCActive}` : `${styles.pillButton} ${styles.pillUNC}`
  }

  return (
    <>
      {/* Mobile Drawer Overlay Backdrop */}
      {sidebarOpen && (
        <div
          className={styles.sidebarOverlay}
          onClick={onCloseSidebar}
        />
      )}

      <aside
        className={`${styles.aside} ${
          sidebarOpen ? styles.asideVisible : styles.asideHidden
        }`}
      >
        <div className={styles.brandHeader}>
          <div>
            <h1 className={styles.brandTitle}>Spotify AI Review Discovery Engine</h1>
            <p className={styles.brandSubtitle}>Feedback Dashboard</p>
          </div>
          <button
            onClick={onCloseSidebar}
            className={styles.closeMobileBtn}
            aria-label="Close menu"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <nav className={styles.navMenu}>
          <Link
            href="/"
            onClick={onCloseSidebar}
            className={`${styles.navLink} ${
              activeTab === 'overview' ? styles.navLinkActive : styles.navLinkInactive
            }`}
          >
            <span className="material-symbols-outlined mr-base">dashboard</span>
            <span className="font-body-md text-body-md">Overview</span>
          </Link>
          <Link
            href="/explorer/"
            onClick={onCloseSidebar}
            className={`${styles.navLink} ${
              activeTab === 'explorer' ? styles.navLinkActive : styles.navLinkInactive
            }`}
          >
            <span className="material-symbols-outlined mr-base">explore</span>
            <span className="font-body-md text-body-md">Explorer</span>
          </Link>
        </nav>

        {/* Sidebar Filters Area (Only visible on Overview/Main tab) */}
        {activeTab === 'overview' && (
          <div className={styles.filtersContainer}>
            <p className={styles.filterGroupTitle}>Filters</p>

            <div className="space-y-md">
              <div className={styles.filterGroup}>
                <label className={styles.filterLabel}>Keywords</label>
                <input
                  className={styles.filterInput}
                  placeholder="Search feedback..."
                  type="text"
                  value={filters.q || ''}
                  onChange={(e) => onFilterChange('q', e.target.value)}
                />
              </div>

              <div className={styles.filterGroup}>
                <label className={styles.filterLabel}>Source Type</label>
                <select
                  className={styles.filterInput}
                  value={selectValue}
                  onChange={handleSourceChange}
                >
                  <option value="">All Sources</option>
                  <option value="app_review_google_play">Playstore Reviews</option>
                  <option value="app_review_app_store">App Store Reviews</option>
                  <option value="producthunt_post">Product Hunt</option>
                  <option value="youtube_comment">YouTube</option>
                </select>
              </div>

              <div className={styles.filterGroup}>
                <label className={styles.filterLabel}>Sentiment</label>
                <div className={styles.sentimentPills}>
                  <button
                    onClick={() => handleSentimentPillClick('positive')}
                    className={getPillClass('positive', filters.sentiment)}
                  >
                    POS
                  </button>
                  <button
                    onClick={() => handleSentimentPillClick('neutral')}
                    className={getPillClass('neutral', filters.sentiment)}
                  >
                    NEU
                  </button>
                  <button
                    onClick={() => handleSentimentPillClick('negative')}
                    className={getPillClass('negative', filters.sentiment)}
                  >
                    NEG
                  </button>
                  <button
                    onClick={() => handleSentimentPillClick('unclear')}
                    className={getPillClass('unclear', filters.sentiment)}
                  >
                    UNC
                  </button>
                </div>
              </div>

              <div className={styles.filterGroup}>
                <label className={styles.filterLabel} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={filters.has_mixed_sentiment === true}
                    onChange={(e) => onFilterChange('has_mixed_sentiment', e.target.checked ? true : undefined)}
                    style={{ cursor: 'pointer' }}
                  />
                  <span>Mixed Sentiment Only</span>
                </label>
              </div>

              <div className={styles.filterGroup}>
                <label className={styles.filterLabel}>User Segment</label>
                <select
                  className={styles.filterInput}
                  value={filters.user_segment || ''}
                  onChange={(e) => onFilterChange('user_segment', e.target.value)}
                >
                  <option value="">All Segments</option>
                  <option value="premium_subscriber">Premium</option>
                  <option value="free_tier">Free</option>
                  <option value="artist">Artist</option>
                </select>
              </div>

              {/* Date Range Section */}
              <div className={styles.filterGroup}>
                <label className={styles.filterLabel}>Date Range</label>
                <input
                  className={styles.filterInput}
                  placeholder="mm/dd/yyyy"
                  type="text"
                  value={localStartDate}
                  onChange={(e) => setLocalStartDate(e.target.value)}
                />
                <input
                  className={styles.filterInput}
                  placeholder="mm/dd/yyyy"
                  style={{ marginTop: '8px' }}
                  type="text"
                  value={localEndDate}
                  onChange={(e) => setLocalEndDate(e.target.value)}
                />
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <button
                    onClick={handleApplyFilters}
                    className={styles.applyBtn}
                  >
                    Apply Filters
                  </button>
                  <button
                    onClick={handleResetAll}
                    className={styles.resetBtn}
                  >
                    Reset All
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className={styles.sidebarFooter}>
          <button
            onClick={() => {
              onToggleChat()
              onCloseSidebar()
            }}
            className={styles.askAiBtn}
          >
            <span className="material-symbols-outlined">smart_toy</span>
            Ask AI Insights
          </button>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingTop: '8px' }}>
            <a className={styles.footerLink} href="#">
              <span className="material-symbols-outlined mr-base" style={{ fontSize: '18px' }}>settings</span>
              Settings
            </a>
            <a className={styles.footerLink} href="#">
              <span className="material-symbols-outlined mr-base" style={{ fontSize: '18px' }}>help</span>
              Support
            </a>
          </div>

          <div className={styles.profileCard}>
            <div className={styles.avatarWrapper}>
              <img
                src="/alex_chen_avatar.png"
                alt="Alex Chen"
                className={styles.avatarImg}
                onError={(e) => {
                  ;(e.target as HTMLElement).style.display = 'none'
                }}
              />
              <span className={styles.avatarFallback}>AC</span>
            </div>
            <div className={styles.profileDetails}>
              <h4 className={styles.profileName}>Alex Chen</h4>
              <span className={styles.profileRole}>Workspace Admin</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
