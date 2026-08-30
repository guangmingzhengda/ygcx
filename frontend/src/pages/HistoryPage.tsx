import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { clearLastConversationId } from '../conversation'
import type { ConversationSummary } from '../types'

export default function HistoryPage() {
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [error, setError] = useState('')

  async function load() {
    try {
      setItems(await api.listConversations())
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function remove(id: string) {
    await api.deleteConversation(id)
    clearLastConversationId(id)
    await load()
  }

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>历史对话</h1>
          <p>点左侧最近记录可继续上次对话；「新对话」只会开空白会话。</p>
        </div>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!items.length ? <p className="empty">还没有对话。去「新对话」问一句即可。</p> : null}
      <ul className="history-list">
        {items.map((item) => (
          <li key={item.id} className="history-item">
            <Link to={`/chat/${item.id}`}>
              <strong>{item.title}</strong>
              <span>{item.preview}</span>
            </Link>
            <button className="btn" type="button" onClick={() => void remove(item.id)}>
              删除
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
