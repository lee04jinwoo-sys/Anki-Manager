import { describe, expect, it } from 'vitest'
import type { JobState } from '../types/dashboard'
import { shouldRefreshAfterPoll } from './jobPolling'

const base: JobState = {
  is_running: false,
  source: '노트 정리',
  progress: 0,
  current_step: '',
  status: 'idle',
  logs: [],
  meta: {},
  candidates: { sentences: [], vocab: [] },
}
const s = (o: Partial<JobState>): JobState => ({ ...base, ...o })

describe('shouldRefreshAfterPoll', () => {
  it('refreshes when an active job ends in any terminal state', () => {
    for (const status of ['success', 'error', 'cancelled', 'waiting_selection', 'idle'] as const) {
      expect(shouldRefreshAfterPoll(true, s({ status }))).toBe(true)
    }
  })

  it('does not refresh while still running or when nothing was active', () => {
    expect(shouldRefreshAfterPoll(true, s({ is_running: true, status: 'running' }))).toBe(false)
    expect(shouldRefreshAfterPoll(false, s({ status: 'success' }))).toBe(false)
  })
})
