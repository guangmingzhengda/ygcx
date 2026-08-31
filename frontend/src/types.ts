export type Profile = {
  education: string
  graduation_year: number
  major: string
  expected_job_type: string
  expected_role: string
    expected_city: string
    expected_salary_min: number
    expected_salary_max: number
    skills: string
  self_intro: string
  updated_at?: string | null
}

export type Job = {
  id: string
  title: string
  company: string
  city: string
  job_type: string
  source: string
  apply_url: string
  official_url: string
  description: string
  tags: string[]
  company_info: string
  salary_min: number
  salary_max: number
  salary_text: string
  fetched_at?: string | null
  match_score?: number | null
  match_reason?: string | null
  boss_search_url: string
  favorited: boolean
  experience_posts?: { title: string; url: string; source: string }[]
  experience_search_links?: { label: string; url: string; source: string }[]
  nowcoder_experience_url?: string
  zhihu_experience_url?: string
}

export type Favorite = {
  id: number
  job_id: string | null
  title: string
  url: string
  kind: string
  note: string
  created_at?: string | null
  job: Job | null
}

export type ChatMessage = {
  id: number
  role: string
  content: string
  jobs: Job[]
  created_at?: string | null
}

export type ConversationSummary = {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
  preview: string
}

export type Conversation = {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
  messages: ChatMessage[]
}

export type ChatResponse = {
  conversation_id: string
  assistant: string
  jobs: Job[]
  conversation: Conversation
}
