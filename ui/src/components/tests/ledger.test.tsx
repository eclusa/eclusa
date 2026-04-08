import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { LedgerPage } from '@/pages/LedgerPage'
import { vi } from 'vitest'

vi.mock('@/api/ledger', () => ({
  useLedgerAsOf: () => ({
    data: {
      items: [
        {
          id: 'ledger-1',
          event_type: 'cascade.created',
          cascade_id: 'cascade-abcdef123456',
          stage_id: null,
          session_id: null,
          content: {},
          schema_version: '1',
          created_at: '2026-04-05T10:00:00.000Z',
        },
      ],
      total_count: 1,
      page: 0,
      size: 50,
    },
    isLoading: false,
    error: null,
  }),
}))

test('ledger page renders AS OF controls and ledger rows', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <LedgerPage />
    </MemoryRouter>,
  )

  expect(html).toContain('Ledger')
  expect(html).toContain('Now')
  expect(html).toContain('1h ago')
  expect(html).toContain('Yesterday')
  expect(html).toContain('Last week')
  expect(html).toContain('cascade.created')
  expect(html).toContain('Page 1 of 1')
  expect(html).toContain('Total 1 entries')
})
