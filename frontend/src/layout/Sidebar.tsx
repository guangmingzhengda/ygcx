import { NavLink } from 'react-router-dom'
import { brand } from '../brand'

const items = [
  { to: '/', label: '新对话', icon: 'chat', end: true },
  { to: '/discover', label: '职位发现', icon: 'search', end: false },
  { to: '/favorites', label: '收藏夹', icon: 'book', end: false },
  { to: '/profile', label: '个人档案', icon: 'user', end: false },
  { to: '/history', label: '历史对话', icon: 'clock', end: false },
] as const

function Icon({ name }: { name: (typeof items)[number]['icon'] }) {
  const common = { width: 18, height: 18, fill: 'none', stroke: 'currentColor', strokeWidth: 1.7 }
  if (name === 'chat') {
    return (
      <svg viewBox="0 0 24 24" {...common}>
        <path d="M5 6h14v9H8l-3 3V6z" />
      </svg>
    )
  }
  if (name === 'search') {
    return (
      <svg viewBox="0 0 24 24" {...common}>
        <circle cx="11" cy="11" r="6" />
        <path d="M20 20l-4-4" />
      </svg>
    )
  }
  if (name === 'book') {
    return (
      <svg viewBox="0 0 24 24" {...common}>
        <path d="M6 5h11a2 2 0 0 1 2 2v12H8a2 2 0 0 0-2 2V5z" />
        <path d="M6 5a2 2 0 0 1 2-2h11" />
      </svg>
    )
  }
  if (name === 'user') {
    return (
      <svg viewBox="0 0 24 24" {...common}>
        <circle cx="12" cy="8" r="3.2" />
        <path d="M5 19c1.4-3 4-4.5 7-4.5S17.6 16 19 19" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" {...common}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" />
    </svg>
  )
}

type Props = {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <div className="brand">
        <span className="brand__mark">
          <img src={brand.logo} alt={brand.team} />
        </span>
        <div>
          <strong>{brand.product}</strong>
          <p>{brand.team}</p>
        </div>
      </div>
      <nav className="nav">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav__item ${isActive ? 'is-active' : ''}`}
            onClick={onClose}
          >
            <Icon name={item.icon} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__foot">
        <div className="brand-badges">
          <img src={brand.teamBadge} alt={`${brand.team}队徽`} />
          <img src={brand.scienceBadge} alt={`${brand.team}${brand.group}`} />
        </div>
        <p className="sidebar__hint">
          {brand.team}
          {brand.group}出品。面向应届生的校招工作台。Boss 仅跳转官方搜索，不抓取站内接口。
        </p>
      </div>
    </aside>
  )
}
