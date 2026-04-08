import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { SubMenu } from './SubMenu'

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-900 text-zinc-100">
      <Sidebar />
      <SubMenu />
      <main className="min-w-0 flex-1 overflow-auto">
        <div className="max-w-7xl p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
