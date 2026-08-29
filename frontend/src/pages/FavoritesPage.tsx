import { useEffect, useState } from 'react'
import { api } from '../api'
import { JobCard } from '../components/JobCard'
import type { Favorite } from '../types'

export default function FavoritesPage() {
  const [items, setItems] = useState<Favorite[]>([])
  const [error, setError] = useState('')

  async function load() {
    try {
      setItems(await api.listFavorites())
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function remove(id: number) {
    await api.removeFavorite(id)
    await load()
  }

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>收藏夹</h1>
          <p>职位、官网入口和 Boss 分享链接都在这里。</p>
        </div>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!items.length ? <p className="empty">还没有收藏。在职位卡片上点「收藏」，或粘贴 Boss 链接。</p> : null}
      <div className="fav-list">
        {items.map((item) => (
          <div key={item.id} className="fav-item">
            {item.job ? (
              <JobCard job={{ ...item.job, favorited: true }} onFavoriteChange={() => void load()} />
            ) : (
              <article className="job-card">
                <p className="job-card__company">{item.kind === 'boss' ? 'Boss 直聘' : '外链'}</p>
                <h3>{item.title}</h3>
                {item.note ? <p className="job-card__desc">{item.note}</p> : null}
                <footer className="job-card__actions">
                  <a className="btn btn--primary" href={item.url} target="_blank" rel="noreferrer">
                    打开链接
                  </a>
                  <button className="btn" type="button" onClick={() => void remove(item.id)}>
                    移除
                  </button>
                </footer>
              </article>
            )}
            {item.job ? (
              <button className="link-btn" type="button" onClick={() => void remove(item.id)}>
                从收藏夹移除
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  )
}
