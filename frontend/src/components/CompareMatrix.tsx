'use client'

import React from 'react'
import styles from './CompareMatrix.module.css'
import { CompareMatrixData, IssueCategory } from '../lib/types'
import { MOCK_COMPARE_MATRIX } from '../lib/mockData'

interface CompareMatrixProps {
  data?: CompareMatrixData
  onCellClick: (filterType: string, filterValue: string, category: string) => void
}

export default function CompareMatrix({ data, onCellClick }: CompareMatrixProps) {
  const comparison = data && Object.keys(data).length > 0 ? data : MOCK_COMPARE_MATRIX

  const rows: Array<{ key: IssueCategory; label: string; icon: string }> = [
    { key: 'Music Discovery', label: 'Music Discovery', icon: 'explore' },
    { key: 'Recommendations', label: 'Recommendations', icon: 'auto_awesome' },
    { key: 'Playlists', label: 'Playlists', icon: 'queue_music' },
    { key: 'Shuffle Experience', label: 'Shuffle Experience', icon: 'shuffle' },
    { key: 'Radio', label: 'Radio', icon: 'radio' },
    { key: 'Search & Browse', label: 'Search & Browse', icon: 'search' },
    { key: 'Library Management', label: 'Library Management', icon: 'library_music' },
    { key: 'Social Discovery', label: 'Social Discovery', icon: 'group' },
    { key: 'Podcast vs Music', label: 'Podcast vs Music', icon: 'podcasts' },
    { key: 'Premium vs Free Experience', label: 'Premium vs Free', icon: 'workspace_premium' },
    { key: 'Unidentified', label: 'Unidentified', icon: 'help' },
  ]

  const getCount = (source: string, catKey: IssueCategory) => {
    return comparison[source]?.[catKey] ?? 0
  }

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h4 className={styles.title}>Cross-Source Category Matrix</h4>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead className={styles.tableHead}>
            <tr>
              <th className={styles.th}>Issue Category</th>
              <th className={styles.th}>Spotify Reviews</th>
              <th className={styles.th}>Product Hunt</th>
              <th className={styles.th}>YouTube</th>
            </tr>
          </thead>
          <tbody className="text-body-md">
            {rows.map((row) => (
              <tr key={row.key} className={styles.row}>
                <td
                  className={styles.td}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onCellClick('issue_category', '', row.key)}
                >
                  <div className={styles.categoryCell}>
                    <span className={`material-symbols-outlined ${styles.cellIcon}`}>
                      {row.icon}
                    </span>
                    {row.label}
                  </div>
                </td>
                
                {/* Spotify Reviews Column (triggers source_type=app_review and category filter) */}
                <td
                  className={`${styles.td} ${styles.valueCell}`}
                  onClick={() => onCellClick('source_type', 'app_review', row.key)}
                >
                  {getCount('app_review', row.key).toLocaleString()}
                </td>

                {/* Product Hunt Column (triggers source_type=producthunt_post and category filter) */}
                <td
                  className={`${styles.td} ${styles.valueCell}`}
                  onClick={() => onCellClick('source_type', 'producthunt_post', row.key)}
                >
                  {getCount('producthunt_post', row.key).toLocaleString()}
                </td>

                {/* YouTube Column (triggers source_type=youtube_comment and category filter) */}
                <td
                  className={`${styles.td} ${styles.valueCell}`}
                  onClick={() => onCellClick('source_type', 'youtube_comment', row.key)}
                >
                  {getCount('youtube_comment', row.key).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
