import * as React from 'react'
import { cn } from '@/lib/utils'

type TabsContextValue = {
  value: string
  setValue: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

function Tabs({ value, defaultValue, onValueChange, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value?: string; defaultValue?: string; onValueChange?: (value: string) => void }) {
  const [internalValue, setInternalValue] = React.useState(defaultValue ?? '')
  const currentValue = value ?? internalValue
  const setValue = onValueChange ?? setInternalValue

  return (
    <TabsContext.Provider value={{ value: currentValue, setValue }}>
      <div className={className} {...props} />
    </TabsContext.Provider>
  )
}

function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('inline-flex items-center justify-center rounded-md bg-zinc-100 p-1 text-zinc-500', className)} {...props} />
}

function TabsTrigger({ className, value, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }) {
  const context = React.useContext(TabsContext)
  const active = context?.value === value
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-all',
        active ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500',
        className,
      )}
      onClick={(event) => {
        props.onClick?.(event)
        context?.setValue(value)
      }}
      {...props}
    />
  )
}

function TabsContent({ className, value, ...props }: React.HTMLAttributes<HTMLDivElement> & { value: string }) {
  const context = React.useContext(TabsContext)
  if (context?.value !== value) return null
  return <div className={cn('mt-2', className)} {...props} />
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
