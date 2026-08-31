import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { JobList } from '../components/JobList'
import type { Job } from '../types'

export default function DiscoverPage() {
  const [q, setQ] = useState('')
  const [city, setCity] = useState('')
  const [source, setSource] = useState('')
  const [jobType, setJobType] = useState('校招全职')
  const [salaryMin, setSalaryMin] = useState(0)
  const [salaryMax, setSalaryMax] = useState(0)
  const [jobs, setJobs] = useState<Job[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [bossUrl, setBossUrl] = useState('')

  async function load(refresh = false) {
    setBusy(true)
    setError('')
    try {
      const data = await api.searchJobs({
        q,
        city,
        source,
        job_type: jobType,
        salary_min: salaryMin,
        salary_max: salaryMax,
        refresh,
      })
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
          <p>
            卡片右上角是匹配度。职位发现用规则打分；对话里会再用 AI 理解条件并重排。每张卡会附带该公司在牛客、思否等公开页上的面经；抓不到具体帖时仍可跳转知乎、掘金、CSDN、小红书等搜索。
          </p>
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
        <select value={jobType} onChange={(event) => setJobType(event.target.value)}>
          <option value="校招全职">只要校招</option>
          <option value="实习">只要实习</option>
          <option value="校招全职 / 实习均可">校招或实习</option>
          <option value="不限">不限类型</option>
        </select>
        <select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="">全部来源</option>
          <option value="official">公司官网</option>
          <option value="nowcoder">牛客</option>
        </select>
        <input
          type="number"
          min={0}
          value={salaryMin || ''}
          onChange={(event) => setSalaryMin(Number(event.target.value) || 0)}
          placeholder="最低月薪 K"
        />
        <input
          type="number"
          min={0}
          value={salaryMax || ''}
          onChange={(event) => setSalaryMax(Number(event.target.value) || 0)}
          placeholder="最高月薪 K"
        />
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
      <JobList jobs={jobs} empty="没有符合校招类型和薪资条件的职位。未标注薪资的校招入口仍会显示；社招默认排除。" />
    </section>
  )
}
