'use client'

import React from 'react'
import styles from './FeedbackCard.module.css'
import { FeedbackItem } from '../lib/types'
import { formatPlatform, formatDate } from '../lib/utils/format'

interface FeedbackCardProps {
  item: FeedbackItem
}

export default function FeedbackCard({ item }: FeedbackCardProps) {
  // Extract initials from author name
  const getInitials = (name?: string) => {
    if (!name) return 'UK'
    const parts = name.split(' ')
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }

  // Get sentiment colors
  const getSentimentPillClass = (sentiment?: string) => {
    const s = sentiment?.toLowerCase() || 'unclear'
    if (s === 'positive') return `${styles.sentimentPill} sentiment-positive`
    if (s === 'negative') return `${styles.sentimentPill} sentiment-negative`
    if (s === 'neutral') return `${styles.sentimentPill} sentiment-neutral`
    return `${styles.sentimentPill} sentiment-unclear`
  }

  const getSentimentLabel = (sentiment?: string) => {
    const s = sentiment?.toLowerCase() || 'unclear'
    if (s === 'positive') return 'Positive'
    if (s === 'negative') return 'Negative'
    if (s === 'neutral') return 'Neutral'
    return 'Emotion Unclear'
  }

  const renderStars = (rating?: number) => {
    if (!rating) return null
    const stars = Math.round(rating)
    return (
      <div className={styles.ratingRow}>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className="material-symbols-outlined"
            style={{
              fontSize: '14px',
              fontVariationSettings: ` 'FILL' ${i < stars ? 1 : 0}, 'wght' 400`,
            }}
          >
            star
          </span>
        ))}
        <span style={{ fontSize: '11px', marginLeft: '4px', color: 'var(--color-secondary)' }}>
          ({rating.toFixed(1)})
        </span>
      </div>
    )
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={styles.authorWrapper}>
          <div className={styles.avatar}>{getInitials(item.author)}</div>
          <div className={styles.authorMeta}>
            <span className={styles.authorName}>{item.author || 'Anonymous'}</span>
            <span className={styles.metaText}>
              {formatPlatform(item.platform)} • {formatDate(item.created_at)}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className={getSentimentPillClass(item.sentiment)}>
            {getSentimentLabel(item.sentiment)}
          </span>
          {item.has_mixed_sentiment && (
            <div className={styles.mixedContainer}>
              <span className={`${styles.sentimentPill} ${styles.mixedBadge}`}>
                Mixed
              </span>
              {((item.sentiment_profile?.positive_aspects?.length || 0) + 
                (item.sentiment_profile?.negative_aspects?.length || 0)) > 0 && (
                <div className={styles.aspectsTooltip}>
                  {item.sentiment_profile?.positive_aspects && item.sentiment_profile.positive_aspects.length > 0 && (
                    <div className={styles.tooltipSection}>
                      <span className={styles.tooltipLabelPos}>Positive:</span>
                      <ul className={styles.tooltipList}>
                        {item.sentiment_profile.positive_aspects.map((asp, idx) => (
                          <li key={idx}>{asp.replace('_', ' ')}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {item.sentiment_profile?.negative_aspects && item.sentiment_profile.negative_aspects.length > 0 && (
                    <div className={styles.tooltipSection}>
                      <span className={styles.tooltipLabelNeg}>Negative:</span>
                      <ul className={styles.tooltipList}>
                        {item.sentiment_profile.negative_aspects.map((asp, idx) => (
                          <li key={idx}>{asp.replace('_', ' ')}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <p className={styles.text}>{item.text}</p>

      {item.rating_or_score !== undefined && renderStars(item.rating_or_score)}
    </div>
  )
}
