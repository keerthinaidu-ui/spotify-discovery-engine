'use client'

import React from 'react'
import styles from './KpiCard.module.css'

interface KpiCardProps {
  type: 'analyzed' | 'negative' | 'positive' | 'top_cause'
  title: string
  value: string | number
  trend?: string
  percentage?: number
  subBreakdown?: { label: string; count: string | number }[]
  mentionsCount?: string | number
  onClick?: () => void
}

export default function KpiCard({
  type,
  title,
  value,
  trend,
  percentage,
  subBreakdown,
  mentionsCount,
  onClick,
}: KpiCardProps) {
  const getIconWrapperClass = () => {
    if (type === 'analyzed') return `${styles.iconWrapper} ${styles.iconWrapperForum}`
    if (type === 'negative') return `${styles.iconWrapper} ${styles.iconWrapperDissatisfied}`
    if (type === 'positive') return `${styles.iconWrapper} ${styles.iconWrapperSatisfied}`
    return `${styles.iconWrapper} ${styles.iconWrapperReplay}`
  }

  const getIconName = () => {
    if (type === 'analyzed') return 'forum'
    if (type === 'negative') return 'sentiment_very_dissatisfied'
    if (type === 'positive') return 'sentiment_satisfied'
    return 'replay'
  }

  const getTrendClass = () => {
    if (!trend) return ''
    return trend.startsWith('+') ? `${styles.trendTag} ${styles.trendPositive}` : `${styles.trendTag} ${styles.trendNegative}`
  }

  return (
    <div 
      className={styles.card} 
      onClick={onClick}
      style={onClick ? { cursor: 'pointer' } : undefined}
    >
      <div>
        <div className={styles.headerRow}>
          <span className={getIconWrapperClass()}>
            <span className="material-symbols-outlined">{getIconName()}</span>
          </span>
          {trend && <span className={getTrendClass()}>{trend}</span>}
        </div>
        <p className={styles.label}>{title}</p>
        
        {type === 'top_cause' ? (
          <h3 className={styles.subValueTitle}>{value}</h3>
        ) : (
          <h3 className={styles.value}>{value}</h3>
        )}
      </div>

      {/* Conditional Bottom Section Mappings */}
      {type === 'analyzed' && subBreakdown && (
        <div className={styles.subDetailsBox}>
          {subBreakdown.map((row, i) => (
            <div key={i} className={styles.subDetailsRow}>
              <span>{row.label}</span>
              <span>{row.count}</span>
            </div>
          ))}
        </div>
      )}

      {(type === 'positive' || type === 'negative') && percentage !== undefined && (
        <div className={styles.progressContainer}>
          <div className={styles.progressBarBg}>
            <div
              className={`${styles.progressBar} ${
                type === 'positive' ? styles.progressBarPos : styles.progressBarNeg
              }`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span
            className={`${styles.percentageText} ${
              type === 'positive' ? styles.percentageTextPos : styles.percentageTextNeg
            }`}
          >
            {percentage}%
          </span>
        </div>
      )}

      {type === 'top_cause' && mentionsCount !== undefined && (
        <div className={styles.badgeRow}>
          <span className={styles.mentionsBadge}>{mentionsCount} MENTIONS</span>
          <span className={`material-symbols-outlined ${styles.trendingUpIcon}`}>trending_up</span>
        </div>
      )}
    </div>
  )
}
