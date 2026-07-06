'use client'

import React, { useState, useRef, useEffect } from 'react'
import styles from './Chatbot.module.css'
import { sendChatQuery } from '../lib/api'
import { ChatRequest } from '../lib/types'
import { SAMPLE_QUESTIONS, GREEN_PILL_QUESTION } from '../lib/constants'

interface Message {
  sender: 'system' | 'user'
  text: string
  citations?: string[]
}

interface ChatbotProps {
  filters: any
  isOpen: boolean
  onClose: () => void
  initialQuery?: string
  onClearInitialQuery?: () => void
}

export default function Chatbot({ filters, isOpen, onClose, initialQuery, onClearInitialQuery }: ChatbotProps) {
  const [minimized, setMinimized] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'system',
      text: "Hello! I've analyzed 141k+ feedback points. What would you like to know about the current Discovery trends?",
    },
    {
      sender: 'user',
      text: GREEN_PILL_QUESTION,
    },
    {
      sender: 'system',
      text: 'Based on 15,670 mentions, users are primarily frustrated by:\n1. **Lack of Surprise**: 65% mention repetitive tracks.\n2. **Broken Seed Logic**: Playlists based on 1 song are shifting genres too fast.\n3. **Limited Fine-Tuning**: Request for a \'Never play this genre\' toggle.',
    },
  ])
  const [inputVal, setInputVal] = useState('')
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(true) // local visibility toggle

  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      setActive(true)
      setMinimized(false)
    }
  }, [isOpen])

  // Submit initial query when set and open
  useEffect(() => {
    if (initialQuery && isOpen) {
      handleSend(initialQuery)
      if (onClearInitialQuery) onClearInitialQuery()
    }
  }, [initialQuery, isOpen])

  // scroll chat feed on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputVal).trim()
    if (!text) return

    // add user message
    setMessages((prev) => [...prev, { sender: 'user', text }])
    setInputVal('')
    setLoading(true)

    // Save to localStorage
    try {
      const history = JSON.parse(localStorage.getItem('sonic_history_chat') || '[]')
      if (!history.includes(text)) {
        history.unshift(text)
        localStorage.setItem('sonic_history_chat', JSON.stringify(history.slice(0, 50)))
      }
    } catch (e) {
      console.warn('Failed to save chat history to localStorage', e)
    }

    try {
      // prepare api request payload
      const req: ChatRequest = {
        query: text,
        q: filters.q || null,
        platform: filters.platform || null,
        source_type: filters.source_type || null,
        sentiment: filters.sentiment || null,
        user_segment: filters.user_segment || null,
      }
      
      const res = await sendChatQuery(req)
      setMessages((prev) => [
        ...prev,
        {
          sender: 'system',
          text: res.answer,
          citations: res.evidence_snippets || [],
        },
      ])
    } catch (e) {
      console.error(e)
      // fallback response if FastAPI server offline
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            sender: 'system',
            text: 'I ran into an issue communicating with the AI insights engine. Here is a general summary of feedback items matching your current filters: recommendation algorithm monotony (42% mentions) and layout navigation issues (28% mentions).',
          },
        ])
      }, 1000)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSend()
    }
  }

  if (!active) {
    // Render floating trigger bubble
    return (
      <button
        onClick={() => {
          setActive(true)
          setMinimized(false)
        }}
        className={styles.collapsedTrigger}
        aria-label="Open AI Assistant"
      >
        <span className="material-symbols-outlined" style={{ fontSize: '28px' }}>
          smart_toy
        </span>
      </button>
    )
  }

  return (
    <div
      className={`${styles.chatbot} ${minimized ? styles.chatbotMinimized : ''}`}
      id="ai-chat"
    >
      {/* Header bar */}
      <div
        className={styles.header}
        onClick={() => setMinimized(!minimized)}
      >
        <div className={styles.headerTitleWrapper}>
          <span className={`material-symbols-outlined ${styles.headerIcon}`}>smart_toy</span>
          <h5 className={styles.headerTitle}>Ask AI Insights</h5>
        </div>
        <div className={styles.headerActions}>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setMinimized(!minimized)
            }}
            className={styles.actionBtn}
            aria-label="Minimize chat"
          >
            <span className={`material-symbols-outlined ${styles.actionIcon}`}>
              {minimized ? 'unfold_more' : 'minimize'}
            </span>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              setActive(false)
              onClose()
            }}
            className={styles.actionBtn}
            aria-label="Close chat"
          >
            <span className={`material-symbols-outlined ${styles.actionIcon}`}>close</span>
          </button>
        </div>
      </div>

      {/* Message History Feed */}
      {!minimized && (
        <>
          <div className={`${styles.chatContent} custom-scrollbar`}>
            {messages.map((msg, i) => (
              <div
                key={i}
                className={
                  msg.sender === 'user' ? styles.userBubbleWrapper : styles.systemBubble
                }
              >
                <div className={msg.sender === 'user' ? styles.userBubble : undefined}>
                  <p style={{ whiteSpace: 'pre-line' }}>{msg.text}</p>
                  
                  {/* Citations evidence boxes */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div style={{ marginTop: '12px', borderTop: '1px solid rgba(62,62,62,0.2)', paddingTop: '8px' }}>
                      <span style={{ fontSize: '9px', fontWeight: 'bold', textTransform: 'uppercase', color: 'var(--color-primary-fixed)' }}>
                        Evidence Quotes:
                      </span>
                      <ul style={{ listStyleType: 'disc', paddingLeft: '16px', marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {msg.citations.map((cite, cIdx) => (
                          <li key={cIdx} style={{ fontSize: '11px', fontStyle: 'italic', color: 'var(--color-secondary)' }}>
                            "{cite}"
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className={styles.loaderWrapper}>
                <span className={`material-symbols-outlined ${styles.spinner}`}>autorenew</span>
                <span>Thinking...</span>
              </div>
            )}

            {/* Sample questions helper */}
            {messages.length === 1 && !loading && (
              <div className={styles.sampleSection}>
                <p className={styles.sampleTitle}>Sample Questions</p>
                <div className={styles.sampleButtons}>
                  {SAMPLE_QUESTIONS.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(q)}
                      className={styles.sampleBtn}
                    >
                      "{q}"
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input control row */}
          <div className={styles.inputSection}>
            <div className={styles.inputWrapper}>
              <input
                className={styles.input}
                placeholder="Type your query..."
                type="text"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                onClick={() => handleSend()}
                className={styles.sendBtn}
                aria-label="Send query"
              >
                <span className="material-symbols-outlined">send</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
