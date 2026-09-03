import type {
  ChatResponse,
  Conversation,
  ConversationSummary,
  Favorite,
  Job,
  Profile,
} from './types'

const TOKEN_KEY = 'ygcx:accessToken'
export const AUTH_EVENT = 'ygcx:unauthorized'

export function getAccessToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setAccessToken(token: string) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

export function clearAccessToken() {
  setAccessToken('')
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  return token ? { 'X-Access-Token': token } : {}
}

async function readError(response: Response): Promise<string> {
  let detail = response.statusText
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) detail = body.detail
  } catch {
    /* ignore */
  }
  return detail
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  })
  if (response.status === 401) {
    clearAccessToken()
    window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return (await response.json()) as T
}

export const api = {
  health: () =>
    request<{ ok: boolean; auth_required?: boolean }>('/api/health'),
  checkAuth: () => request<{ ok: boolean }>('/api/auth/check'),
  getProfile: () => request<Profile>('/api/profile'),
  saveProfile: (payload: Profile) =>
    request<Profile>('/api/profile', { method: 'PUT', body: JSON.stringify(payload) }),
  searchJobs: (params: {
    q?: string
    city?: string
    source?: string
    job_type?: string
    salary_min?: number
    salary_max?: number
    refresh?: boolean
  }) => {
    const q = new URLSearchParams()
    if (params.q) q.set('q', params.q)
    if (params.city) q.set('city', params.city)
    if (params.source) q.set('source', params.source)
    if (params.job_type) q.set('job_type', params.job_type)
    if (params.salary_min) q.set('salary_min', String(params.salary_min))
    if (params.salary_max) q.set('salary_max', String(params.salary_max))
    if (params.refresh) q.set('refresh', 'true')
    return request<Job[]>(`/api/jobs/search?${q.toString()}`)
  },
  refreshJobs: () => request<Job[]>('/api/jobs/refresh', { method: 'POST' }),
  listFavorites: () => request<Favorite[]>('/api/favorites'),
  addFavorite: (jobId: string) =>
    request<Favorite>('/api/favorites', { method: 'POST', body: JSON.stringify({ job_id: jobId }) }),
  addLink: (payload: { title: string; url: string; kind?: string; note?: string }) =>
    request<Favorite>('/api/favorites', { method: 'POST', body: JSON.stringify(payload) }),
  saveBossLink: (url: string, note = '') =>
    request<Favorite>('/api/favorites/boss-link', {
      method: 'POST',
      body: JSON.stringify({ url, note }),
    }),
  removeFavorite: (id: number) => request<{ ok: boolean }>(`/api/favorites/${id}`, { method: 'DELETE' }),
  unfavoriteJob: (jobId: string) =>
    request<{ ok: boolean }>(`/api/favorites/by-job/${jobId}`, { method: 'DELETE' }),
  chat: (message: string, conversationId?: string | null, refresh = false) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        conversation_id: conversationId ?? null,
        refresh,
      }),
    }),
  chatStream: async (
    message: string,
    conversationId: string | null | undefined,
    handlers: {
      onStart?: (conversationId: string, jobs: Job[]) => void
      onDelta?: (text: string) => void
      onJobs?: (jobs: Job[]) => void
      onDone?: (payload: { conversation_id: string; assistant: string; jobs: Job[] }) => void
    },
    refresh = false,
  ) => {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        message,
        conversation_id: conversationId ?? null,
        refresh,
      }),
    })
    if (response.status === 401) {
      clearAccessToken()
      window.dispatchEvent(new Event(AUTH_EVENT))
    }
    if (!response.ok || !response.body) {
      throw new Error((await readError(response)) || '流式对话失败')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    const flush = (raw: string) => {
      const line = raw
        .split('\n')
        .filter((item) => item.startsWith('data:'))
        .map((item) => item.slice(5).trim())
        .join('')
      if (!line) return
      let event: {
        type?: string
        text?: string
        conversation_id?: string
        jobs?: Job[]
        assistant?: string
      }
      try {
        event = JSON.parse(line) as typeof event
      } catch {
        return
      }
      if (event.type === 'start' && event.conversation_id) {
        handlers.onStart?.(event.conversation_id, event.jobs ?? [])
      } else if (event.type === 'delta' && event.text) {
        handlers.onDelta?.(event.text)
      } else if (event.type === 'jobs' && event.jobs) {
        handlers.onJobs?.(event.jobs)
      } else if (event.type === 'done' && event.conversation_id) {
        handlers.onDone?.({
          conversation_id: event.conversation_id,
          assistant: event.assistant ?? '',
          jobs: event.jobs ?? [],
        })
      }
    }
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        buffer += decoder.decode()
        if (buffer.trim()) flush(buffer)
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) flush(part)
    }
  },
  listConversations: () => request<ConversationSummary[]>('/api/conversations'),
  getConversation: (id: string) => request<Conversation>(`/api/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<{ ok: boolean }>(`/api/conversations/${id}`, { method: 'DELETE' }),
}
