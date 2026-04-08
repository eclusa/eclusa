import { cn } from '@/lib/utils'
import type { HTMLAttributes } from 'react'

function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('animate-pulse rounded-md bg-zinc-200', className)} {...props} />
}

export { Skeleton }
