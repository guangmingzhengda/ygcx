import type { Job } from '../types'
import { JobCard } from './JobCard'

type Props = {
  jobs: Job[]
  empty?: string
  onFavoriteChange?: (job: Job) => void
}

export function JobList({ jobs, empty = '暂无职位，先填写档案或刷新数据源。', onFavoriteChange }: Props) {
  if (!jobs.length) {
    return <p className="empty">{empty}</p>
  }
  return (
    <div className="job-grid">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} onFavoriteChange={onFavoriteChange} />
      ))}
    </div>
  )
}
