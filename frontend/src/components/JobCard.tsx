import { useEffect, useState } from 'react'
import type { Job } from '../types'
import { api } from '../api'

const SOURCE_LABEL: Record<string, string> = {
  nowcoder: '牛客',
  official: '官网',
  boss: 'Boss',
}

const EXP_SOURCE_LABEL: Record<string, string> = {
  nowcoder: '牛客',
  segmentfault: '思否',
  zhihu: '知乎',
  juejin: '掘金',
  csdn: 'CSDN',
  xiaohongshu: '小红书',
  v2ex: 'V2EX',
  yingjiesheng: '应届生',
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
  const apply = (local.apply_url || '').replace(/\/$/, '')
  const official = (local.official_url || '').replace(/\/$/, '')
  const showOfficial = Boolean(official && official !== apply)

  const searchLinks =
    local.experience_search_links && local.experience_search_links.length > 0
      ? local.experience_search_links
      : [
          local.nowcoder_experience_url
            ? { label: '牛客面经搜索', url: local.nowcoder_experience_url, source: 'nowcoder' }
            : null,
          local.zhihu_experience_url
            ? { label: '知乎面经搜索', url: local.zhihu_experience_url, source: 'zhihu' }
            : null,
        ].filter((item): item is { label: string; url: string; source: string } => Boolean(item))

  return (
    <article className="job-card">
      <header className="job-card__head">
        <div>
          <p className="job-card__company">{local.company || '未知公司'}</p>
          <h3>{local.title}</h3>
        </div>
        <div
          className="score-box"
          title="与你档案/关键词的匹配度，0–100。库里多为公司校招入口而不是具体岗位 JD，所以相近公司数字可能接近。"
        >
          <div className="score-ring">
            <span>{score}</span>
          </div>
          <span className="score-ring__label">匹配度</span>
        </div>
      </header>
      <div className="job-card__meta">
        <span className={`badge badge--${local.source}`}>{SOURCE_LABEL[local.source] ?? local.source}</span>
        {local.job_type ? (
          <span className={`chip ${local.job_type === '社招' ? 'chip--warn' : ''}`}>{local.job_type}</span>
        ) : null}
        {local.salary_text ? <span className="chip">{local.salary_text}</span> : null}
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
      {(local.experience_posts && local.experience_posts.length > 0) || searchLinks.length > 0 ? (
        <section className="job-card__exps">
          <p className="job-card__exps-title">相关经验贴</p>
          {local.experience_posts?.slice(0, 4).map((post) => (
            <a key={post.url} className="job-card__exp" href={post.url} target="_blank" rel="noreferrer">
              <span className="job-card__exp-src">{EXP_SOURCE_LABEL[post.source] ?? post.source}</span>
              {post.title}
            </a>
          ))}
          <div className="job-card__exp-links">
            {searchLinks.map((link) => (
              <a key={link.source || link.url} href={link.url} target="_blank" rel="noreferrer">
                {link.label}
              </a>
            ))}
          </div>
        </section>
      ) : null}
      <footer className="job-card__actions">
        {local.apply_url ? (
          <a className="btn btn--primary" href={local.apply_url} target="_blank" rel="noreferrer">
            投递 / 校招页
          </a>
        ) : null}
        {showOfficial ? (
          <a className="btn" href={local.official_url} target="_blank" rel="noreferrer">
            公司官网
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
