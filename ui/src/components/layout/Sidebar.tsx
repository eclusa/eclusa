import { NavLink } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  BookOpen,
  Clock,
  LayoutDashboard,
  MessageSquare,
  Sparkles,
  ShieldAlert,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { label: 'Chat', path: '/chat', icon: Sparkles },
  { label: 'Cascades', path: '/cascades', icon: LayoutDashboard },
  { label: 'Gates', path: '/gates', icon: ShieldAlert },
  { label: 'Sessions', path: '/sessions', icon: MessageSquare },
  { label: 'Costs', path: '/costs', icon: BarChart3 },
  { label: 'Ledger', path: '/ledger', icon: Clock },
  { label: 'Knowledge', path: '/knowledge', icon: BookOpen },
  { label: 'Metrics', path: '/metrics', icon: Activity },
]

export function Sidebar() {
  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950 px-4 py-5 text-zinc-100">
      <div className="mb-8 px-2 font-mono text-xs font-semibold tracking-[0.35em] text-zinc-500">
        ECLUSA
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-zinc-800/60 text-zinc-100'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100',
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}
