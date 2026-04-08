import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { SessionPage } from '@/pages/SessionPage'
import { TranscriptMessage } from '@/components/session/TranscriptMessage'

vi.mock('@/api/sessions', () => ({
  useSessions: () => ({
    data: [
      {
        id: 'session-1',
        stage_id: 'stage-1',
        model: 'gpt-5.4',
        state: 'running',
        cost_estimated_usd: 0.0012,
        created_at: '2026-04-05T10:00:00.000Z',
      },
    ],
    isLoading: false,
    error: null,
  }),
  useSessionMessages: () => ({
    data: [
      {
        id: 'msg-1',
        role: 'assistant',
        content: { type: 'text', text: 'Ready for review' },
        created_at: '2026-04-05T10:01:00.000Z',
        model: 'gpt-5.4',
        cost_estimated_usd: 0.0012,
      },
    ],
    isLoading: false,
    error: null,
  }),
}))

vi.mock('@/ws/useSessionStream', () => ({
  useSessionStream: () => ({
    messages: [],
    isConnected: true,
  }),
}))

test('TranscriptMessage renders verdicts and tool calls', () => {
  const html = renderToStaticMarkup(
    <TranscriptMessage
      role="assistant"
      model="gpt-5.4"
      content={{
        type: 'text',
        text: 'Approved',
        verdict: {
          model: 'gpt-5.4',
          confidence: 0.82,
          decision: 'approved',
          rationale: 'The cascade is ready to ship.',
        },
      }}
      cost={{ estimated_usd: 0.0012, tokens_in: 20, tokens_out: 15 }}
    />,
  )

  expect(html).toContain('assistant')
  expect(html).toContain('Judgment')
  expect(html).toContain('approved')
  expect(html).toContain('0.0012 USD')
})

test('SessionPage renders selected session transcript', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={['/sessions/session-1']}>
      <Routes>
        <Route path="/sessions/:id?" element={<SessionPage />} />
      </Routes>
    </MemoryRouter>,
  )

  expect(html).toContain('Transcript viewer')
  expect(html).toContain('session-1')
  expect(html).toContain('Ready for review')
  expect(html).toContain('Live')
})
