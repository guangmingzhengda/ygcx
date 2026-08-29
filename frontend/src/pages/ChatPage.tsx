import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { brand } from '../brand'
import { JobList } from '../components/JobList'
import type { ChatMessage, Job } from '../types'

export default function ChatPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!id) {
      setMessages([])
      return
    }
    void api
      .getConversation(id)
      .then((conv) => setMessages(conv.messages))
      .catch((err: Error) => setError(err.message))
  }, [id])

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setError('')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', content: text, jobs: [] },
    ])
    try {
      const result = await api.chat(text, id)
      if (!id) navigate(`/chat/${result.conversation_id}`, { replace: true })
      setMessages(result.conversation.messages)
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败')
    } finally {
      setBusy(false)
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
              <video autoPlay muted loop playsInline poster={brand.logo} aria-label={brand.team}>
                <source src={brand.logoVideo} type="video/mp4" />
              </video>
            </div>
            <p className="hero__team">
              {brand.team} · {brand.group}
            </p>
            <h1>今天想找哪类校招？</h1>
            <p>结合你的学历、专业和意向城市，从官网与牛客公开信息里整理岗位，并给出 Boss 搜索跳转。</p>
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
            <div key={msg.id} className={`bubble bubble--${msg.role}`}>
              <p>{msg.content}</p>
              {msg.jobs.length ? <JobList jobs={msg.jobs} onFavoriteChange={onFav} /> : null}
            </div>
          ))
        )}
        {busy ? <p className="muted">正在检索公开校招信息…</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </div>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          void send()
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="输入意向，例如：深圳前端校招"
        />
        <button className="btn btn--primary" type="submit" disabled={busy}>
          发送
        </button>
      </form>
    </section>
  )
}
