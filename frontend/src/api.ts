import type {
  ChatResponse,
  Conversation,
  ConversationSummary,
  Favorite,
  Job,
  Profile,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<{ ok: boolean }>('/api/health'),
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
  listConversations: () => request<ConversationSummary[]>('/api/conversations'),
  getConversation: (id: string) => request<Conversation>(`/api/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<{ ok: boolean }>(`/api/conversations/${id}`, { method: 'DELETE' }),
}
