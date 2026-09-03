import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { AUTH_EVENT, api, clearAccessToken, getAccessToken, setAccessToken } from './api'
import { brand } from './brand'

export function AccessGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [locked, setLocked] = useState(false)
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function boot() {
      try {
        const health = await api.health()
        if (cancelled) return
        if (!health.auth_required) {
          setLocked(false)
          setReady(true)
          return
        }
        if (!getAccessToken()) {
          setLocked(true)
          setReady(true)
          return
        }
        await api.checkAuth()
        if (cancelled) return
        setLocked(false)
        setReady(true)
      } catch {
        if (cancelled) return
        clearAccessToken()
        setLocked(true)
        setReady(true)
      }
    }
    void boot()
    const onUnauthorized = () => setLocked(true)
    window.addEventListener(AUTH_EVENT, onUnauthorized)
    return () => {
      cancelled = true
      window.removeEventListener(AUTH_EVENT, onUnauthorized)
    }
  }, [])

  async function unlock(event: FormEvent) {
    event.preventDefault()
    const value = token.trim()
    if (!value || busy) return
    setBusy(true)
    setError('')
    setAccessToken(value)
    try {
      await api.checkAuth()
      setLocked(false)
      setToken('')
    } catch {
      clearAccessToken()
      setError('口令不对，问问部署的同学。')
    } finally {
      setBusy(false)
    }
  }

  if (!ready) {
    return (
      <div className="gate">
        <p className="muted">正在连接服务…</p>
      </div>
    )
  }

  if (locked) {
    return (
      <div className="gate">
        <div className="gate__card">
          <img src={brand.logo} alt={brand.team} />
          <p className="hero__team">
            {brand.team} · {brand.group}
          </p>
          <h1>输入访问口令</h1>
          <p>这是内部分享站点，不对外开放注册。口令由部署的同学私下发给你。</p>
          <form onSubmit={(event) => void unlock(event)}>
            <input
              type="password"
              autoComplete="current-password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="访问口令"
              autoFocus
            />
            <button className="btn btn--primary" type="submit" disabled={busy || !token.trim()}>
              {busy ? '验证中' : '进入'}
            </button>
          </form>
          {error ? <p className="error">{error}</p> : null}
        </div>
      </div>
    )
  }

  return children
}
