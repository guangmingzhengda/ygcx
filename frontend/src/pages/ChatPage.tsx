import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { brand } from '../brand'
import { JobList } from '../components/JobList'
import { getLastConversationId, setLastConversationId, clearLastConversationId, stashStreamHandoff, takeStreamHandoff } from '../conversation'
import type { ChatMessage, Job } from '../types'

export default function ChatPage() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)
  const isNew = location.pathname === '/new'
  const lastId = getLastConversationId()

  useEffect(() => {
    if (!id) {
      setMessages([])
      setError('')
      return
    }
    const stashed = takeStreamHandoff(id)
    if (stashed) {
      setMessages(stashed)
      setError('')
      return
    }
    void api
      .getConversation(id)
      .then((conv) => {
        setLastConversationId(conv.id)
        setMessages(conv.messages)
        setError('')
      })
      .catch(() => {
        clearLastConversationId(id)
        navigate('/new', { replace: true })
      })
  }, [id, navigate])

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  if (!id && !isNew && lastId) {
    return <Navigate to={`/chat/${lastId}`} replace />
  }

  async function send() {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setStreaming(true)
    setError('')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', content: text, jobs: [] },
      { id: -1, role: 'assistant', content: '', jobs: [] },
    ])
    try {
      await api.chatStream(text, id, {
        onStart: (conversationId, jobs) => {
          setLastConversationId(conversationId)
          setMessages((prev) =>
            prev.map((msg) => (msg.id === -1 ? { ...msg, jobs } : msg)),
          )
        },
        onDelta: (chunk) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === -1 ? { ...msg, content: msg.content + chunk } : msg)),
          )
        },
        onJobs: (jobs) => {
          setMessages((prev) => prev.map((msg) => (msg.id === -1 ? { ...msg, jobs } : msg)))
        },
        onDone: ({ conversation_id, assistant, jobs }) => {
          setLastConversationId(conversation_id)
          setMessages((prev) => {
            const next = prev.map((msg) =>
              msg.id === -1 ? { ...msg, id: Date.now(), content: assistant, jobs } : msg,
            )
            if (!id) stashStreamHandoff(conversation_id, next)
            return next
          })
          if (!id) navigate(`/chat/${conversation_id}`, { replace: true })
        },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败')
      setMessages((prev) => prev.filter((msg) => msg.id !== -1))
    } finally {
      setBusy(false)
      setStreaming(false)
    }
  }

  function onFav(job: Job) {
    setMessages((prev) =>
      prev.map((msg) => ({
        ...msg,
        jobs: msg.jobs.map((item) => (item.id === job.id ? job : item)),
      })),
    )
  }

  return (
    <section className="page page--chat">
      <div className="chat-log" ref={boxRef}>
        {messages.length === 0 ? (
          <div className="hero">
            <div className="hero-logo">
              <img src={brand.logo} alt={brand.team} />
            </div>
            <p className="hero__team">
              {brand.team} · {brand.group}
            </p>
            <h1>今天想找哪类校招？</h1>
            <p>结合你的学历、专业和意向城市，从官网与牛客公开信息里整理岗位，并附上多来源面经搜索。</p>
            <div className="hint-row">
              {['帮我找杭州的后端校招', '有哪些大厂算法实习', '推荐适合计算机专业的网申'].map((text) => (
                <button key={text} type="button" className="chip chip--click" onClick={() => setInput(text)}>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`bubble bubble--${msg.role}${streaming && msg.id === -1 ? ' bubble--stream' : ''}`}
            >
              <p>
                {msg.content}
                {streaming && msg.id === -1 ? <span className="stream-cursor" /> : null}
              </p>
              {msg.jobs.length ? <JobList jobs={msg.jobs} onFavoriteChange={onFav} /> : null}
            </div>
          ))
        )}
        {busy && !streaming ? <p className="muted">正在检索公开信息，并请模型点评卡片…</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </div>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          void send()
        }}
      >
        <div className="composer__box">
          <textarea
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            placeholder="说说意向，例如：杭州后端校招，不要社招"
            disabled={busy}
          />
          <button className="btn btn--primary composer__send" type="submit" disabled={busy || !input.trim()}>
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path
                d="M5 12h11M12 6l6 6-6 6"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.9"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {busy ? (streaming ? '生成中' : '检索中') : '发送'}
          </button>
        </div>
        <p className="composer__hint">Enter 发送，Shift + Enter 换行</p>
      </form>
    </section>
  )
}
