import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { EntityRow } from '@/components/knowledge/EntityRow'
import { vi } from 'vitest'

vi.mock('@/api/knowledge', () => ({
  useEntitySearch: () => ({
    data: [
      {
        id: 'entity-1',
        name: 'Release Gate Review',
        entity_type: 'cascade',
        score: 0.918,
      },
    ],
    isLoading: false,
    error: null,
  }),
  useEntityFacts: () => ({
    data: [
      {
        id: 'fact-1',
        subject_id: 'entity-1',
        predicate: 'has_status',
        object_id: null,
        object_value: 'active',
        t_valid: '2026-04-05T10:00:00.000Z',
        t_invalid: null,
        t_created: '2026-04-05T10:01:00.000Z',
        t_expired: null,
      },
    ],
    isLoading: false,
    error: null,
  }),
  useCommunities: () => ({
    data: [
      {
        id: 'community-1',
        name: 'Review Cluster',
        member_count: 12,
      },
    ],
    isLoading: false,
    error: null,
  }),
}))

vi.mock('@/store/ui', () => ({
  useUIStore: (selector: (state: { openPanels: Set<string>; togglePanel: (panel: string) => void }) => unknown) =>
    selector({
      openPanels: new Set(['entity-entity-1']),
      togglePanel: vi.fn(),
    }),
}))

test('knowledge page renders search bar, entity results, and communities', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <KnowledgePage />
    </MemoryRouter>,
  )

  expect(html).toContain('Search entities...')
  expect(html).toContain('Enter a search term to explore entities')
  expect(html).toContain('Entities')
  expect(html).toContain('Facts')
  expect(html).toContain('Communities')
})

test('entity rows render facts with bi-temporal badges', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <EntityRow
        entity={{
          id: 'entity-1',
          name: 'Release Gate Review',
          entity_type: 'cascade',
          score: 0.918,
        }}
      />
    </MemoryRouter>,
  )

  expect(html).toContain('has_status')
  expect(html).toContain('t_valid')
  expect(html).toContain('t_invalid')
  expect(html).toContain('current')
  expect(html).toContain('t_created')
  expect(html).toContain('t_expired')
})
