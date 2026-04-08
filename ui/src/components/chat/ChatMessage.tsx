import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/api/chat'

const roleStyles: Record<ChatMessageType['role'], string> = {
  user: 'border-zinc-800 bg-zinc-950/70 text-zinc-300',
  assistant: 'border-blue-900/40 bg-blue-950/20 text-blue-100',
}

export function ChatMessage({
  message,
  isStreaming = false,
}: {
  message: ChatMessageType
  isStreaming?: boolean
}) {
  return (
    <div data-role={message.role} className={cn('flex gap-3', message.role === 'assistant' ? 'justify-start' : 'justify-end')}>
      <Card className={cn('max-w-[min(42rem,100%)] border shadow-none', roleStyles[message.role])}>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-3">
            <Badge
              variant="outline"
              className={cn(
                'border text-[11px] font-mono uppercase tracking-[0.2em]',
                message.role === 'assistant'
                  ? 'border-blue-900/40 bg-blue-950/20 text-blue-300'
                  : 'border-zinc-800 bg-zinc-950/80 text-zinc-400',
              )}
            >
              {message.role}
            </Badge>
            <div className="text-[11px] text-zinc-500">{new Date(message.createdAt).toLocaleTimeString()}</div>
          </div>

          <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-100">
            {message.content}
            {message.role === 'assistant' && isStreaming ? (
              <span className="ml-1 inline-block h-4 w-[2px] align-middle bg-current [animation:chat-cursor-blink_1s_step-end_infinite]" />
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
