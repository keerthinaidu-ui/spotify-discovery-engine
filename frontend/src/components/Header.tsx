'use client'

import React from 'react'
import styles from './Header.module.css'

interface HeaderProps {
  searchText: string
  onSearchChange: (val: string) => void
  activeTab: string
  onTabChange: (val: string) => void
  onNewQuery: () => void
  placeholder?: string
  onToggleSidebar: () => void
  reportsTabLabel?: string
}

export default function Header({
  searchText,
  onSearchChange,
  activeTab,
  onTabChange,
  onNewQuery,
  placeholder = "Explore topics, trends, or user quotes...",
  onToggleSidebar,
  reportsTabLabel,
}: HeaderProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const text = searchText.trim()
      if (text) {
        try {
          const history = JSON.parse(localStorage.getItem('sonic_history_search') || '[]')
          if (!history.includes(text)) {
            history.unshift(text)
            localStorage.setItem('sonic_history_search', JSON.stringify(history.slice(0, 50)))
          }
        } catch (err) {
          console.warn('Failed to save search history', err)
        }
      }
    }
  }

  return (
    <header className={styles.header}>
      <div className={styles.leftSection}>
        {/* Mobile Hamburger menu toggle */}
        <button
          onClick={onToggleSidebar}
          className={styles.hamburgerBtn}
          aria-label="Open menu"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>

        <div className={styles.searchContainer}>
          <span className={`material-symbols-outlined ${styles.searchIcon}`}>search</span>
          <input
            className={styles.searchInput}
            placeholder={placeholder}
            type="text"
            value={searchText}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>

        <nav className={styles.navTabs}>
          <span
            className={`${styles.tabLink} ${
              activeTab === 'ask_ai' ? styles.tabActive : styles.tabInactive
            }`}
            onClick={() => onTabChange('ask_ai')}
          >
            Ask AI
          </span>
          <span
            className={`${styles.tabLink} ${
              activeTab === 'reports' ? styles.tabActive : styles.tabInactive
            }`}
            onClick={() => onTabChange('reports')}
          >
            {reportsTabLabel || 'Reports'}
          </span>
          <span
            className={`${styles.tabLink} ${
              activeTab === 'history' ? styles.tabActive : styles.tabInactive
            }`}
            onClick={() => onTabChange('history')}
          >
            History
          </span>
        </nav>
      </div>

      <div className={styles.rightSection}>
        <button
          onClick={onNewQuery}
          className={styles.newQueryBtn}
        >
          New Query
        </button>

        <div className={styles.rightSection}>
          <button className={styles.notificationBtn} aria-label="Notifications">
            <span className="material-symbols-outlined">notifications</span>
          </button>

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
        </div>
      </div>
    </header>
  )
}
