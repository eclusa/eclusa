import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useChatSessions } from '@/api/chat'
import { useSessions } from '@/api/sessions'
import { cn } from '@/lib/utils'

const STATUS_DOT_COLOR: Record<string, string> = {
  running: 'bg-blue-400',
  completed: 'bg-emerald-400',
  failed: 'bg-red-400',
}

function ChatSubMenu() {
  const { sessions } = useChatSessions()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const activeSession = searchParams.get('s')

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-800 px-4 py-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Threads</div>
      </div>
      <div className="px-2 pt-2">
        <button
          onClick={() => navigate('/chat')}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-zinc-300 transition-colors hover:bg-zinc-800/60"
        >
          <Plus className="h-3 w-3" />
          New thread
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-1">
        <div className="flex flex-col gap-0.5">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => navigate(`/chat?s=${s.id}`)}
              className={cn(
                'w-full rounded-md px-3 py-2 text-left text-xs leading-tight transition-colors',
                s.id === activeSession
                  ? 'bg-zinc-800/80 text-zinc-200'
                  : 'text-zinc-500 hover:bg-zinc-800/40 hover:text-zinc-400',
              )}
            >
              <div className="truncate">{s.preview || 'Empty session'}</div>
              <div className="mt-1 text-[10px] text-zinc-600">
                {new Date(s.created_at).toLocaleString()}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function SessionsSubMenu() {
  const { data: sessions, isLoading } = useSessions()
  const navigate = useNavigate()
  const { id: activeSessionId } = useParams()

  return (
    <div className="flex h-full flex-col" data-testid="sessions-submenu">
      <div className="border-b border-zinc-800 px-4 py-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Sessions</div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {isLoading ? (
          <div className="px-3 py-2 text-xs text-zinc-600">Loading...</div>
        ) : sessions && sessions.length > 0 ? (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => {
              const active = session.id === activeSessionId
              const dotColor = STATUS_DOT_COLOR[session.state] ?? 'bg-zinc-500'
              return (
                <button
                  key={session.id}
                  type="button"
                  title={session.id}
                  onClick={() => navigate(`/sessions/${session.id}`)}
                  data-testid="session-item"
                  className={cn(
                    'w-full rounded-md px-3 py-2 text-left text-xs leading-tight transition-colors',
                    active
                      ? 'bg-zinc-800/80 text-zinc-200'
                      : 'text-zinc-500 hover:bg-zinc-800/40 hover:text-zinc-400',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-full', dotColor)}
                      data-testid="status-dot"
                      data-status={session.state}
                    />
                    <div className="truncate" data-testid="session-title">{session.title}</div>
                  </div>
                  <div className="mt-1 pl-3.5 text-[10px] text-zinc-600">
                    {new Date(session.created_at).toLocaleString()}
                  </div>
                  <div className="pl-3.5 text-[10px] text-zinc-600">
                    {session.model}
                  </div>
                </button>
              )
            })}
          </div>
        ) : (
          <div className="px-3 py-2 text-xs text-zinc-600">No sessions yet</div>
        )}
      </div>
    </div>
  )
}

export function SubMenu() {
  const location = useLocation()

  if (location.pathname === '/chat') {
    return (
      <aside className="flex h-full w-56 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950/80">
        <ChatSubMenu />
      </aside>
    )
  }

  if (location.pathname.startsWith('/sessions')) {
    return (
      <aside className="flex h-full w-56 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950/80">
        <SessionsSubMenu />
      </aside>
    )
  }

  return null
}
