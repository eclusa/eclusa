import { format } from 'date-fns'
import { flexRender, getCoreRowModel, useReactTable, type ColumnDef, type PaginationState } from '@tanstack/react-table'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { LedgerEntry } from '@/api/ledger'

type LedgerTableProps = {
  data: LedgerEntry[]
  totalCount: number
  pagination: PaginationState
  onPaginationChange: (updater: PaginationState | ((old: PaginationState) => PaginationState)) => void
}

const columns: ColumnDef<LedgerEntry>[] = [
  {
    accessorKey: 'event_type',
    header: 'Event',
    cell: ({ row }) => <span className="font-mono text-amber-300">{row.original.event_type}</span>,
  },
  {
    accessorKey: 'cascade_id',
    header: 'Cascade',
    cell: ({ row }) => {
      const cascadeId = row.original.cascade_id
      return <span className="font-mono text-zinc-400">{cascadeId ? `${cascadeId.slice(0, 8)}…` : '—'}</span>
    },
  },
  {
    accessorKey: 'created_at',
    header: 'Created',
    cell: ({ row }) => <span className="text-zinc-500">{format(new Date(row.original.created_at), 'yyyy-MM-dd HH:mm')}</span>,
  },
]

export function LedgerTable({ data, totalCount, pagination, onPaginationChange }: LedgerTableProps) {
  const pageCount = Math.max(1, Math.ceil(totalCount / pagination.pageSize))
  const table = useReactTable({
    data,
    columns,
    state: {
      pagination,
    },
    pageCount,
    manualPagination: true,
    getCoreRowModel: getCoreRowModel(),
    onPaginationChange,
  })

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
        <Table className="w-full text-sm">
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="border-zinc-800 hover:bg-zinc-800/30">
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} className="border-zinc-800 text-zinc-500">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="border-b border-zinc-800 hover:bg-zinc-800/30">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="border-zinc-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="border-zinc-800 hover:bg-zinc-800/30">
                <TableCell colSpan={columns.length} className="py-10 text-center text-zinc-500">
                  No ledger entries available for this timestamp.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-3 border-t border-zinc-800 pt-4 text-sm text-zinc-400 sm:flex-row sm:items-center sm:justify-between">
        <div>
          Page {pagination.pageIndex + 1} of {pageCount} - Total {totalCount} entries
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-zinc-800 bg-zinc-950 text-zinc-300 hover:bg-zinc-800"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-zinc-800 bg-zinc-950 text-zinc-300 hover:bg-zinc-800"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
