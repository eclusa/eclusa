import { useMemo, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/auth/AuthProvider'
import { useResolveGate } from '@/api/gates'

function base64UrlDecode(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4)
  return atob(padded)
}

function readActorId(token: string | null) {
  if (!token) return 'operator'
  const parts = token.split('.')
  if (parts.length !== 3 || !parts[1]) return 'operator'

  try {
    const payload = JSON.parse(base64UrlDecode(parts[1])) as {
      actor_id?: unknown
      actorId?: unknown
      sub?: unknown
    }
    const candidate = payload.actor_id ?? payload.actorId ?? payload.sub
    return typeof candidate === 'string' && candidate.trim() ? candidate : 'operator'
  } catch {
    return 'operator'
  }
}

export function GateResolveForm({ gateId }: { gateId: string }) {
  const [decision, setDecision] = useState('')
  const mutation = useResolveGate()
  const { token } = useAuth()

  const actorId = useMemo(() => readActorId(token), [token])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedDecision = decision.trim()
    if (!trimmedDecision || mutation.isPending) {
      return
    }

    mutation.mutate({
      gateId,
      decision: trimmedDecision,
      actorId,
      token: '',
    })

    setDecision('')
    if (typeof window !== 'undefined' && typeof window.alert === 'function') {
      window.alert('Gate resolved')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor={`decision-${gateId}`} className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          Decision
        </Label>
        <Input
          id={`decision-${gateId}`}
          value={decision}
          onChange={(event) => setDecision(event.target.value)}
          placeholder="approve"
          className="border-zinc-800 bg-zinc-950/60 text-zinc-100 placeholder:text-zinc-600"
        />
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={mutation.isPending || !decision.trim()} className="bg-zinc-100 text-zinc-950 hover:bg-zinc-200">
          {mutation.isPending ? 'Resolving...' : 'Resolve gate'}
        </Button>
        <div className="text-xs text-zinc-500">Actor {actorId}</div>
      </div>

      {mutation.error instanceof Error ? <div className="text-sm text-red-400">{mutation.error.message}</div> : null}
    </form>
  )
}
