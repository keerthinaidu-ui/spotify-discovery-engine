'use client'

import React, { useState, useEffect } from 'react'
import styles from './ExplorerFilters.module.css'
import { PRIMARY_THEMES, SECONDARY_TAGS } from '../lib/types'

interface ExplorerFiltersProps {
  filters: any
  onFilterChange: (key: string, value: any) => void
  onResetFilters: () => void
}

export default function ExplorerFilters({
  filters,
  onFilterChange,
  onResetFilters,
}: ExplorerFiltersProps) {
  // Local state for typed Start, End Date, and App Version Inputs
  const [localStartDate, setLocalStartDate] = useState(filters.start_date || '')
  const [localEndDate, setLocalEndDate] = useState(filters.end_date || '')
  const [localAppVersion, setLocalAppVersion] = useState(filters.app_version || '')

  useEffect(() => {
    setLocalStartDate(filters.start_date || '')
    setLocalEndDate(filters.end_date || '')
    setLocalAppVersion(filters.app_version || '')
  }, [filters.start_date, filters.end_date, filters.app_version])

  const handleApply = () => {
    onFilterChange('start_date', localStartDate)
    onFilterChange('end_date', localEndDate)
    onFilterChange('app_version', localAppVersion)
  }

  const handleReset = () => {
    setLocalStartDate('')
    setLocalEndDate('')
    setLocalAppVersion('')
    onResetFilters()
  }

  const handleCheckboxChange = (group: 'sentiment_list' | 'platform_list', val: string) => {
    const list = [...(filters[group] || [])]
    const index = list.indexOf(val)
    if (index > -1) {
      list.splice(index, 1)
    } else {
      list.push(val)
    }
    onFilterChange(group, list)
  }

  return (
    <aside className={styles.panel}>
      <h3 className={styles.title}>Filters</h3>

      {/* Date Range Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Date Range</label>
        <input
          className={styles.input}
          placeholder="mm/dd/yyyy"
          type="text"
          value={localStartDate}
          onChange={(e) => setLocalStartDate(e.target.value)}
        />
        <input
          className={styles.input}
          placeholder="mm/dd/yyyy"
          style={{ marginTop: '8px' }}
          type="text"
          value={localEndDate}
          onChange={(e) => setLocalEndDate(e.target.value)}
        />
        <div className={styles.buttonRow}>
          <button onClick={handleApply} className={styles.applyBtn}>
            Apply
          </button>
          <button onClick={handleReset} className={styles.resetBtn}>
            Reset
          </button>
        </div>
      </div>

      {/* Sentiment Checkboxes Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Sentiment</label>
        <div className={styles.checkboxList}>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.sentiment_list || []).includes('positive')}
              onChange={() => handleCheckboxChange('sentiment_list', 'positive')}
            />
            <span>Positive</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.sentiment_list || []).includes('neutral')}
              onChange={() => handleCheckboxChange('sentiment_list', 'neutral')}
            />
            <span>Neutral</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.sentiment_list || []).includes('negative')}
              onChange={() => handleCheckboxChange('sentiment_list', 'negative')}
            />
            <span>Negative</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.sentiment_list || []).includes('unclear')}
              onChange={() => handleCheckboxChange('sentiment_list', 'unclear')}
            />
            <span>Emotion Unclear</span>
          </label>
        </div>
      </div>

      {/* Source Checkboxes Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Source</label>
        <div className={styles.checkboxList}>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.platform_list || []).includes('app_store')}
              onChange={() => handleCheckboxChange('platform_list', 'app_store')}
            />
            <span>App Store</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.platform_list || []).includes('play_store')}
              onChange={() => handleCheckboxChange('platform_list', 'play_store')}
            />
            <span>Play Store</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.platform_list || []).includes('product_hunt')}
              onChange={() => handleCheckboxChange('platform_list', 'product_hunt')}
            />
            <span>Product Hunt</span>
          </label>
          <label className={styles.checkboxItem}>
            <input
              type="checkbox"
              className={styles.checkboxInput}
              checked={(filters.platform_list || []).includes('youtube')}
              onChange={() => handleCheckboxChange('platform_list', 'youtube')}
            />
            <span>YouTube</span>
          </label>
        </div>
      </div>

      {/* Rating Filter Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Rating</label>
        <select
          className={styles.input}
          value={filters.rating || ''}
          onChange={(e) => onFilterChange('rating', e.target.value)}
        >
          <option value="">All Ratings</option>
          <option value="5">5 Stars</option>
          <option value="4">4 Stars</option>
          <option value="3">3 Stars</option>
          <option value="2">2 Stars</option>
          <option value="1">1 Star</option>
        </select>
      </div>

      {/* Primary Theme Filter Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Primary Theme</label>
        <select
          className={styles.input}
          value={filters.issue_category || ''}
          onChange={(e) => onFilterChange('issue_category', e.target.value)}
        >
          <option value="">All Primary Themes</option>
          {PRIMARY_THEMES.map((theme) => (
            <option key={theme} value={theme}>
              {theme}
            </option>
          ))}
        </select>
      </div>

      {/* Secondary Tag Filter Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Secondary Tag</label>
        <select
          className={styles.input}
          value={filters.secondary_tag || ''}
          onChange={(e) => onFilterChange('secondary_tag', e.target.value)}
        >
          <option value="">All Secondary Tags</option>
          {SECONDARY_TAGS.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </select>
      </div>

      {/* App Version Filter Group */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>App Version</label>
        <input
          className={styles.input}
          placeholder="e.g. 9.1.52.1394"
          type="text"
          value={localAppVersion}
          onChange={(e) => setLocalAppVersion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleApply()
            }
          }}
        />
      </div>
    </aside>
  )
}
