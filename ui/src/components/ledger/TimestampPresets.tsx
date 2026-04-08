import { addHours, subDays, subWeeks } from 'date-fns'
import { Button } from '@/components/ui/button'

const PRESETS = [
  { label: 'Now', getValue: () => new Date().toISOString() },
  { label: '1h ago', getValue: () => addHours(new Date(), -1).toISOString() },
  { label: 'Yesterday', getValue: () => subDays(new Date(), 1).toISOString() },
  { label: 'Last week', getValue: () => subWeeks(new Date(), 1).toISOString() },
]

export function TimestampPresets({ onSelect }: { onSelect: (iso: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {PRESETS.map((preset) => (
        <Button
          key={preset.label}
          type="button"
          variant="outline"
          size="sm"
          className="border-zinc-800 bg-zinc-900 px-3 font-mono text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
          onClick={() => onSelect(preset.getValue())}
        >
          {preset.label}
        </Button>
      ))}
    </div>
  )
}
