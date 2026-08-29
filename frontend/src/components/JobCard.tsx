import { useEffect, useState } from 'react'
import type { Job } from '../types'
import { api } from '../api'

const SOURCE_LABEL: Record<string, string> = {
  nowcoder: '牛客',
  official: '官网',
  boss: 'Boss',
}

type Props = {
  job: Job
  onFavoriteChange?: (job: Job) => void
}

export function JobCard({ job, onFavoriteChange }: Props) {
  const [busy, setBusy] = useState(false)
  const [local, setLocal] = useState(job)

  useEffect(() => {
    setLocal(job)
  }, [job])

  async function toggleFavorite() {
    setBusy(true)
    try {
      if (local.favorited) {
        await api.unfavoriteJob(local.id)
        const next = { ...local, favorited: false }
        setLocal(next)
        onFavoriteChange?.(next)
      } else {
        await api.addFavorite(local.id)
        const next = { ...local, favorited: true }
        setLocal(next)
        onFavoriteChange?.(next)
      }
    } catch (error) {
      window.alert(error instanceof Error ? error.message : '收藏失败')
    } finally {
      setBusy(false)
    }
  }

  const score = local.match_score ?? 0

  return (
    <article className="job-card">
      <header className="job-card__head">
        <div>
          <p className="job-card__company">{local.company || '未知公司'}</p>
          <h3>{local.title}</h3>
        </div>
        <div className="score-ring" title="匹配度">
          <span>{score}</span>
        </div>
      </header>
      <div className="job-card__meta">
        <span className={`badge badge--${local.source}`}>{SOURCE_LABEL[local.source] ?? local.source}</span>
        {local.job_type ? <span className="chip">{local.job_type}</span> : null}
        {local.city ? <span className="chip">{local.city}</span> : null}
        {local.tags.slice(0, 3).map((tag) => (
          <span className="chip" key={tag}>
            {tag}
          </span>
        ))}
      </div>
      {local.company_info ? <p className="job-card__info">{local.company_info}</p> : null}
      {local.description && local.description !== local.company_info ? (
        <p className="job-card__desc">{local.description}</p>
      ) : null}
      {local.match_reason ? <p className="job-card__reason">{local.match_reason}</p> : null}
      <footer className="job-card__actions">
        {local.apply_url ? (
          <a className="btn btn--primary" href={local.apply_url} target="_blank" rel="noreferrer">
            投递 / 查看
          </a>
        ) : null}
        {local.official_url ? (
          <a className="btn" href={local.official_url} target="_blank" rel="noreferrer">
            官网
          </a>
        ) : null}
        {local.boss_search_url ? (
          <a className="btn" href={local.boss_search_url} target="_blank" rel="noreferrer">
            Boss 搜索
          </a>
        ) : null}
        <button className="btn" type="button" disabled={busy} onClick={() => void toggleFavorite()}>
          {local.favorited ? '已收藏' : '收藏'}
        </button>
      </footer>
    </article>
  )
}
