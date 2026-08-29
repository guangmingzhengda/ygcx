import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import type { Profile } from '../types'

const empty: Profile = {
  education: '本科',
  graduation_year: 2027,
  major: '',
  expected_job_type: '校招全职',
  expected_role: '',
  expected_city: '',
  skills: '',
  self_intro: '',
}

export default function ProfilePage() {
  const [form, setForm] = useState<Profile>(empty)
  const [status, setStatus] = useState('')

  useEffect(() => {
    void api.getProfile().then(setForm)
  }, [])

  function set<K extends keyof Profile>(key: K, value: Profile[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setStatus('保存中…')
    try {
      const saved = await api.saveProfile(form)
      setForm(saved)
      setStatus('已保存，对话和职位发现会按这份档案匹配。')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <section className="page page--narrow">
      <header className="page-head">
        <div>
          <h1>个人档案</h1>
          <p>这些信息只存在本机 SQLite，用来生成检索词和匹配理由。</p>
        </div>
      </header>
      <form className="form" onSubmit={(event) => void save(event)}>
        <label>
          学历
          <select value={form.education} onChange={(event) => set('education', event.target.value)}>
            <option>本科</option>
            <option>硕士</option>
            <option>博士</option>
            <option>专科</option>
          </select>
        </label>
        <label>
          毕业年份
          <input
            type="number"
            min={2020}
            max={2035}
            value={form.graduation_year}
            onChange={(event) => set('graduation_year', Number(event.target.value))}
          />
        </label>
        <label>
          专业
          <input value={form.major} onChange={(event) => set('major', event.target.value)} placeholder="计算机科学与技术" />
        </label>
        <label>
          期望工作类型
          <select value={form.expected_job_type} onChange={(event) => set('expected_job_type', event.target.value)}>
            <option>校招全职</option>
            <option>实习</option>
            <option>校招全职 / 实习均可</option>
          </select>
        </label>
        <label>
          期望岗位
          <input
            value={form.expected_role}
            onChange={(event) => set('expected_role', event.target.value)}
            placeholder="后端开发 / 算法 / 前端"
          />
        </label>
        <label>
          期望城市
          <input
            value={form.expected_city}
            onChange={(event) => set('expected_city', event.target.value)}
            placeholder="杭州"
          />
        </label>
        <label className="span-2">
          技能关键词
          <input
            value={form.skills}
            onChange={(event) => set('skills', event.target.value)}
            placeholder="Python, Java, SQL"
          />
        </label>
        <label className="span-2">
          一句话介绍
          <textarea
            rows={4}
            value={form.self_intro}
            onChange={(event) => set('self_intro', event.target.value)}
            placeholder="应届生，做过课程设计 / 实习项目…"
          />
        </label>
        <div className="span-2 form-actions">
          <button className="btn btn--primary" type="submit">
            保存档案
          </button>
          {status ? <span className="muted">{status}</span> : null}
        </div>
      </form>
    </section>
  )
}
