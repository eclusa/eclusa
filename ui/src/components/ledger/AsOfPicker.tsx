import { format } from 'date-fns'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TimestampPresets } from './TimestampPresets'

function toDatetimeLocalValue(asOf: string) {
  const date = new Date(asOf)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return format(date, "yyyy-MM-dd'T'HH:mm")
}

export function AsOfPicker({
  asOf,
  onChange,
}: {
  asOf: string
  onChange: (isoString: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="ledger-as-of" className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">
        AS OF
      </Label>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <Input
          id="ledger-as-of"
          type="datetime-local"
          value={toDatetimeLocalValue(asOf)}
          onChange={(event) => {
            const nextValue = event.target.value
            onChange(nextValue ? new Date(nextValue).toISOString() : '')
          }}
          className="max-w-xs border-zinc-800 bg-zinc-950 text-zinc-100"
        />
        <TimestampPresets onSelect={onChange} />
      </div>
    </div>
  )
}
