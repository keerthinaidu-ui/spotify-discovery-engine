'use client'

import React, { useState } from 'react'
import styles from './VolumeChart.module.css'

interface SecondaryTagDataPoint {
  name: string
  count: number
}

interface VolumeChartProps {
  data?: SecondaryTagDataPoint[]
}

export default function VolumeChart({ data }: VolumeChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  const chartData = data && data.length > 0 ? data.slice(0, 8) : [
    { name: 'Feature Requests', count: 3830 },
    { name: 'Activity-Based Listening', count: 1671 },
    { name: 'Discovery Features', count: 1298 },
    { name: 'Repetitive Listening', count: 1188 },
    { name: 'Genre Exploration', count: 1077 },
    { name: 'Listening Habits', count: 1070 },
    { name: 'Personalization', count: 951 },
    { name: 'Mood-Based Listening', count: 877 }
  ]

  const maxVal = Math.max(...chartData.map(d => d.count), 1)

  const handleBarClick = (tagName: string) => {
    const params = new URLSearchParams()
    params.set('secondary_tag', tagName)
    window.location.href = `/explorer/?${params.toString()}#reviews-section`
  }

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h4 className={styles.title}>Theme Lens</h4>
        <div className={styles.legendRow}>
          <span className={styles.legendItem}>
            <div className={styles.legendDot} /> Mentions (Click to Filter)
          </span>
        </div>
      </div>

      {/* Bars Layout */}
      <div className={styles.timelineContainer} style={{ height: '220px', paddingBottom: '30px' }}>
        <div className={styles.barsWrapper} style={{ height: '160px' }}>
          {chartData.map((d, index) => {
            const barHeightPercent = `${(d.count / maxVal) * 80 + 10}%` // scale between 10% and 90%
            const isHighlighted = hoveredIndex === index
            return (
              <div 
                key={index} 
                style={{ 
                  flex: 1, 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'flex-end', 
                  height: '100%',
                  position: 'relative'
                }}
              >
                {/* The Bar */}
                <div
                  className={`${styles.bar} ${isHighlighted ? styles.barHighlighted : ''}`}
                  style={{
                    height: barHeightPercent,
                    opacity: isHighlighted ? 1.0 : 0.85,
                    backgroundColor: 'var(--color-primary-fixed)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-end',
                    alignItems: 'center',
                    paddingBottom: '8px',
                    width: '100%',
                  }}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  onClick={() => handleBarClick(d.name)}
                >
                  <span style={{ fontSize: '9px', fontWeight: 'bold', color: '#000000', transform: 'rotate(-90deg)', whiteSpace: 'nowrap', marginBottom: '12px' }}>
                    {d.count.toLocaleString()}
                  </span>
                </div>

                {/* The Label */}
                <div 
                  style={{ 
                    fontSize: '10px', 
                    color: 'var(--color-on-surface-variant)', 
                    textAlign: 'center',
                    marginTop: '6px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: '100%',
                    fontWeight: 500,
                  }}
                  title={d.name}
                >
                  {d.name.length > 12 ? d.name.slice(0, 10) + '..' : d.name}
                </div>
              </div>
            )
          })}

          {/* Tooltip Box */}
          {hoveredIndex !== null && (
            <div
              className={styles.tooltip}
              style={{
                bottom: '110%',
                left: `${(hoveredIndex / chartData.length) * 90 + 5}%`,
              }}
            >
              <div className={styles.tooltipDate}>{chartData[hoveredIndex].name}</div>
              <div>Volume: {chartData[hoveredIndex].count.toLocaleString()}</div>
              <div style={{ fontSize: '8px', color: '#00D166', marginTop: '2px', fontWeight: 'bold' }}>Click to view reviews</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
