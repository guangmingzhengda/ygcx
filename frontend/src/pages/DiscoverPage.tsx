import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { JobList } from '../components/JobList'
import type { Job } from '../types'

export default function DiscoverPage() {
  const [q, setQ] = useState('')
  const [city, setCity] = useState('')
  const [source, setSource] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [bossUrl, setBossUrl] = useState('')

  async function load(refresh = false) {
    setBusy(true)
    setError('')
    try {
      const data = await api.searchJobs({ q, city, source, refresh })
      setJobs(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void load()
    // 首次进入按档案自动检索
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function saveBoss(event: FormEvent) {
    event.preventDefault()
    try {
      await api.saveBossLink(bossUrl)
      setBossUrl('')
      window.alert('已保存到收藏夹，可在收藏夹打开该链接。')
    } catch (err) {
      window.alert(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>职位发现</h1>
          <p>仪光赤心实践队科创组：聚合官网校招入口与牛客公开日程，按档案排序。</p>
        </div>
        <button className="btn" type="button" disabled={busy} onClick={() => void load(true)}>
          {busy ? '刷新中…' : '刷新数据源'}
        </button>
      </header>
      <form
        className="filters"
        onSubmit={(event) => {
          event.preventDefault()
          void load()
        }}
      >
        <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="关键词，如 后端 / 算法" />
        <input value={city} onChange={(event) => setCity(event.target.value)} placeholder="城市" />
        <select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="">全部来源</option>
          <option value="official">公司官网</option>
          <option value="nowcoder">牛客</option>
        </select>
        <button className="btn btn--primary" type="submit" disabled={busy}>
          筛选
        </button>
      </form>
      <form className="boss-form" onSubmit={(event) => void saveBoss(event)}>
        <input
          value={bossUrl}
          onChange={(event) => setBossUrl(event.target.value)}
          placeholder="粘贴 Boss 直聘公开分享链接，保存后可跳转"
        />
        <button className="btn" type="submit">
          保存链接
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      <JobList jobs={jobs} />
    </section>
  )
}
