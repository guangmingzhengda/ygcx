import { memo, type CSSProperties } from 'react'
import type { Job } from '../types'
import { JobCard } from './JobCard'

type Props = {
  jobs: Job[]
  empty?: string
  enter?: boolean
  onFavoriteChange?: (job: Job) => void
}

export const JobList = memo(function JobList({
  jobs,
  empty = '暂无职位，先填写档案或刷新数据源。',
  enter = false,
  onFavoriteChange,
}: Props) {
  if (!jobs.length) {
    return <p className="empty">{empty}</p>
  }
  return (
    <div className={`job-grid${enter ? ' job-grid--enter' : ''}`}>
      {jobs.map((job, index) => (
        <div key={job.id} className="job-grid-item" style={{ ['--i']: index } as CSSProperties}>
          <JobCard job={job} onFavoriteChange={onFavoriteChange} />
        </div>
      ))}
    </div>
  )
})
