import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { brand } from '../brand'
import { Sidebar } from './Sidebar'

export function AppShell() {
  const [open, setOpen] = useState(false)
  return (
    <div className="shell">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      {open ? <button className="backdrop" type="button" aria-label="关闭菜单" onClick={() => setOpen(false)} /> : null}
      <div className="main">
        <header className="topbar">
          <button className="menu-btn" type="button" onClick={() => setOpen(true)} aria-label="打开导航">
            菜单
          </button>
          <span className="topbar__title">{brand.fullName}</span>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
