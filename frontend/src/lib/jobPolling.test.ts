import { describe, expect, it } from 'vitest'
import type { JobState } from '../types/dashboard'
import { interpretExtractState, shouldRefreshAfterPoll, EXTRACT_JOB_NAME } from './jobPolling'

const base: JobState = {
  is_running: false,
  source: EXTRACT_JOB_NAME,
  progress: 0,
  current_step: '',
  status: 'idle',
  logs: [],
  meta: {},
  candidates: { sentences: [], vocab: [] },
}
const s = (o: Partial<JobState>): JobState => ({ ...base, ...o })

describe('interpretExtractState', () => {
  it('waits while the extract job runs', () => {
    expect(interpretExtractState(s({ is_running: true, status: 'running' }))).toEqual({ kind: 'wait' })
  })

  it('returns candidates when waiting for selection', () => {
    const candidates = { sentences: ['a'], vocab: [{ 단어: 'x', 뜻: '' }] }
    expect(interpretExtractState(s({ status: 'waiting_selection', candidates }))).toEqual({ kind: 'ready', candidates })
  })

  it('treats an idle finish (empty inbox) as ready with no candidates', () => {
    expect(interpretExtractState(s({ status: 'idle' }))).toEqual({
      kind: 'ready',
      candidates: { sentences: [], vocab: [] },
    })
  })

  it('stops on error, cancelled and success instead of polling forever', () => {
    for (const status of ['error', 'cancelled', 'success'] as const) {
      expect(interpretExtractState(s({ status, current_step: 'boom' })).kind).toBe('error')
    }
  })

  it('stops when the state belongs to a different job', () => {
    expect(interpretExtractState(s({ source: '노트 정리', status: 'success' })).kind).toBe('error')
    expect(interpretExtractState(s({ source: '노트 정리', is_running: true, status: 'running' })).kind).toBe('error')
  })
})

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
