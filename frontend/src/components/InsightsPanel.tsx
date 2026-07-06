'use client'

import React from 'react'
import styles from './InsightsPanel.module.css'
import { MOCK_INSIGHTS, MOCK_LOOP_CAUSES } from '../lib/mockData'
import { InsightItem } from '../lib/types'

interface InsightsPanelProps {
  insights?: InsightItem[]
  loopCauses?: { name: string; percentage: number }[]
  onInsightSelect?: (text: string) => void
}

export default function InsightsPanel({
  insights,
  loopCauses,
  onInsightSelect,
}: InsightsPanelProps) {
  const listInsights = insights && insights.length > 0 ? insights : MOCK_INSIGHTS
  const listCauses = loopCauses && loopCauses.length > 0 ? loopCauses : MOCK_LOOP_CAUSES

  const getTagClass = (type: string) => {
    if (type === 'Pain Points') return `${styles.insightTag} ${styles.tagPainPoints}`
    if (type === 'Unmet Needs') return `${styles.insightTag} ${styles.tagUnmetNeeds}`
    return `${styles.insightTag} ${styles.tagPersonas}`
  }

  const getLoopBarClass = (index: number) => {
    if (index === 0) return `${styles.loopBar} ${styles.loopBarAlgo}`
    if (index === 1) return `${styles.loopBar} ${styles.loopBarUI}`
    return `${styles.loopBar} ${styles.loopBarPodcast}`
  }

  return (
    <div>
      {/* AI Discovery Insights Card */}
      <div className={styles.insightsCard}>
        <div className={styles.insightsHeader}>
          <h4 className={styles.insightsTitle}>
            <span className={`material-symbols-outlined ${styles.insightsIcon}`}>lightbulb</span>
            AI Discovery Insights
          </h4>
        </div>
        <div className={styles.insightsList}>
          {listInsights.map((item, index) => (
            <div
              key={index}
              className={styles.insightBlock}
              onClick={() => onInsightSelect?.(item.text)}
            >
              <p className={getTagClass(item.type)}>{item.type}</p>
              <p className={styles.insightText}>{item.text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Top Loop Causes Card */}
      <div className={styles.loopCausesCard}>
        <h4 className={styles.loopCausesTitle}>Top Loop Causes</h4>
        <div className={styles.loopList}>
          {listCauses.map((cause, index) => (
            <div key={index} className={styles.loopItem}>
              <div className={styles.loopHeader}>
                <span>{cause.name}</span>
                <span>{cause.percentage}%</span>
              </div>
              <div className={styles.loopTrack}>
                <div
                  className={getLoopBarClass(index)}
                  style={{ width: `${cause.percentage}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
