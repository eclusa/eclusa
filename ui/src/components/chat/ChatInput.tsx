import type { FormEvent, KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled?: boolean
}) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSubmit()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3">
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Describe the work you want Eclusa to do..."
        className="h-11 border-zinc-800 bg-zinc-950/60 text-zinc-100 placeholder:text-zinc-500"
      />
      <Button type="submit" disabled={disabled || value.trim().length === 0} className="h-11 px-4">
        <Send className="mr-2 h-4 w-4" />
        Send
      </Button>
    </form>
  )
}
