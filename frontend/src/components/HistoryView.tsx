'use client'

import React, { useState, useEffect } from 'react'
import styles from './HistoryView.module.css'

interface HistoryViewProps {
  onSearchClick: (keyword: string) => void
  onChatClick: (query: string) => void
}

export default function HistoryView({ onSearchClick, onChatClick }: HistoryViewProps) {
  const [searchHistory, setSearchHistory] = useState<string[]>([])
  const [chatHistory, setChatHistory] = useState<string[]>([])

  useEffect(() => {
    try {
      const savedSearch = JSON.parse(localStorage.getItem('sonic_history_search') || '[]')
      const savedChat = JSON.parse(localStorage.getItem('sonic_history_chat') || '[]')
      setSearchHistory(savedSearch)
      setChatHistory(savedChat)
    } catch (e) {
      console.warn('Failed to load history from localStorage', e)
    }
  }, [])

  const handleClearHistory = () => {
    try {
      localStorage.removeItem('sonic_history_search')
      localStorage.removeItem('sonic_history_chat')
      setSearchHistory([])
      setChatHistory([])
    } catch (e) {
      console.warn('Failed to clear history from localStorage', e)
    }
  }

  return (
    <div className={styles.historyContainer}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Query & Search History</h3>
        {(searchHistory.length > 0 || chatHistory.length > 0) && (
          <button onClick={handleClearHistory} className={styles.clearBtn}>
            <span className="material-symbols-outlined">delete</span>
            Clear History
          </button>
        )}
      </div>

      <div className={styles.sectionsGrid}>
        {/* Search History Section */}
        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>
            <span className={`material-symbols-outlined ${styles.sectionIcon}`}>search</span>
            Search Keywords
          </h4>
          {searchHistory.length === 0 ? (
            <div className={styles.emptyState}>
              <span className={`material-symbols-outlined ${styles.emptyIcon}`}>history</span>
              <p className={styles.emptyText}>No recent search keywords</p>
            </div>
          ) : (
            <div className={styles.list}>
              {searchHistory.map((item, idx) => (
                <div
                  key={idx}
                  className={styles.item}
                  onClick={() => onSearchClick(item)}
                >
                  <div className={styles.itemContent}>
                    <span className={`material-symbols-outlined ${styles.itemIcon}`}>history</span>
                    <span>{item}</span>
                  </div>
                  <span className={`material-symbols-outlined ${styles.itemArrow}`}>
                    arrow_forward
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chat History Section */}
        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>
            <span className={`material-symbols-outlined ${styles.sectionIcon}`}>smart_toy</span>
            AI Queries
          </h4>
          {chatHistory.length === 0 ? (
            <div className={styles.emptyState}>
              <span className={`material-symbols-outlined ${styles.emptyIcon}`}>chat_bubble</span>
              <p className={styles.emptyText}>No recent AI chatbot queries</p>
            </div>
          ) : (
            <div className={styles.list}>
              {chatHistory.map((item, idx) => (
                <div
                  key={idx}
                  className={styles.item}
                  onClick={() => onChatClick(item)}
                >
                  <div className={styles.itemContent}>
                    <span className={`material-symbols-outlined ${styles.itemIcon}`}>forum</span>
                    <span>{item}</span>
                  </div>
                  <span className={`material-symbols-outlined ${styles.itemArrow}`}>
                    chat
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
