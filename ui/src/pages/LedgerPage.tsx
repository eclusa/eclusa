import { useState } from 'react'
import type { PaginationState } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { AsOfPicker } from '@/components/ledger/AsOfPicker'
import { LedgerTable } from '@/components/ledger/LedgerTable'
import { useLedgerAsOf } from '@/api/ledger'

function LedgerSkeletonRow() {
  return (
    <div className="grid grid-cols-3 gap-4 border-b border-zinc-800 px-4 py-4">
      <Skeleton className="h-4 w-32 bg-zinc-800" />
      <Skeleton className="h-4 w-24 bg-zinc-800" />
      <Skeleton className="h-4 w-40 bg-zinc-800" />
    </div>
  )
}

export function LedgerPage() {
  const [asOf, setAsOf] = useState(() => new Date().toISOString())
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 50 })
  const { data, isLoading, error } = useLedgerAsOf(asOf, pagination)

  const ledger = data?.items ?? []
  const totalCount = data?.total_count ?? 0

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Ledger</div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-zinc-100">Ledger</h1>
          <Badge variant="outline" className="border-amber-800/50 bg-amber-950/30 text-amber-300">
            {totalCount}
          </Badge>
        </div>
        <AsOfPicker
          asOf={asOf}
          onChange={(nextAsOf) => {
            setAsOf(nextAsOf)
            setPagination((current) => ({ ...current, pageIndex: 0 }))
          }}
        />
      </header>

      {isLoading ? (
        <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
          {Array.from({ length: 3 }, (_, index) => (
            <LedgerSkeletonRow key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">
          Failed to load ledger entries
        </div>
      ) : (
        <LedgerTable
          data={ledger}
          totalCount={totalCount}
          pagination={pagination}
          onPaginationChange={(updater) => {
            setPagination((current) => (typeof updater === 'function' ? updater(current) : updater))
          }}
        />
      )}
    </div>
  )
}
