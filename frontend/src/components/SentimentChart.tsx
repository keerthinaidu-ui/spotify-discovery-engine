'use client'

import React from 'react'
import styles from './SentimentChart.module.css'

interface SentimentChartProps {
  positivePercentage?: number
  negativePercentage?: number
  neutralPercentage?: number
  unclearPercentage?: number
  totalCount?: string
}

export default function SentimentChart({
  positivePercentage = 50,
  negativePercentage = 20,
  neutralPercentage = 15,
  unclearPercentage = 15,
  totalCount = '141k',
}: SentimentChartProps) {
  // calculate dash-offsets dynamically matching the stroke circumferences
  const posVal = Math.round(positivePercentage)
  const negVal = Math.round(negativePercentage)
  const neuVal = Math.round(neutralPercentage)
  const unclVal = Math.round(unclearPercentage)

  const negOffset = -posVal
  const neuOffset = -(posVal + negVal)
  const unclOffset = -(posVal + negVal + neuVal)

  return (
    <div className={styles.card}>
      <h4 className={styles.title}>Sentiment Distribution</h4>
      <div className={styles.chartRow}>
        <div className={styles.pieWrapper}>
          <svg className={styles.svg} viewBox="0 0 36 36">
            {/* Positive Segment */}
            <circle
              className={styles.circlePos}
              cx="18"
              cy="18"
              fill="none"
              r="16"
              strokeDasharray={`${posVal}, 100`}
              strokeWidth="4"
            />
            {/* Negative Segment */}
            <circle
              className={styles.circleNeg}
              cx="18"
              cy="18"
              fill="none"
              r="16"
              strokeDasharray={`${negVal}, 100`}
              strokeDashoffset={negOffset}
              strokeWidth="4"
            />
            {/* Neutral Segment */}
            <circle
              className={styles.circleNeu}
              cx="18"
              cy="18"
              fill="none"
              r="16"
              strokeDasharray={`${neuVal}, 100`}
              strokeDashoffset={neuOffset}
              strokeWidth="4"
            />
            {/* Unclear Segment */}
            <circle
              className={styles.circleUncl}
              cx="18"
              cy="18"
              fill="none"
              r="16"
              strokeDasharray={`${unclVal}, 100`}
              strokeDashoffset={unclOffset}
              strokeWidth="4"
            />
          </svg>

          {/* Central Total Indicator */}
          <div className={styles.centerLabel}>
            <span className={styles.centerTotal}>{totalCount}</span>
            <span className={styles.centerLabelText}>TOTAL</span>
          </div>
        </div>

        {/* Breakdown Legend List */}
        <div className={styles.legendList}>
          <div className={styles.legendItem}>
            <span className={styles.legendName}>
              <div className={`${styles.legendDot} ${styles.dotPos}`} /> Pos
            </span>
            <span className={styles.legendValue}>{posVal}%</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendName}>
              <div className={`${styles.legendDot} ${styles.dotNeg}`} /> Neg
            </span>
            <span className={styles.legendValue}>{negVal}%</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendName}>
              <div className={`${styles.legendDot} ${styles.dotNeu}`} /> Neu
            </span>
            <span className={styles.legendValue}>{neuVal}%</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendName}>
              <div className={`${styles.legendDot} ${styles.dotUncl}`} /> Unclear
            </span>
            <span className={styles.legendValue}>{unclVal}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
