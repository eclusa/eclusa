import { useEffect, useRef, useState } from 'react'
import { Input } from '@/components/ui/input'

export function SearchBar({ onSearch }: { onSearch: (query: string) => void }) {
  const [value, setValue] = useState('')
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return (
    <Input
      value={value}
      placeholder="Search entities..."
      className="border-zinc-800 bg-zinc-950 text-zinc-100 placeholder:text-zinc-500"
      onChange={(event) => {
        const nextValue = event.target.value
        setValue(nextValue)

        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
        }

        if (!nextValue.trim()) {
          onSearch('')
          return
        }

        timeoutRef.current = setTimeout(() => {
          onSearch(nextValue.trim())
        }, 300)
      }}
    />
  )
}
