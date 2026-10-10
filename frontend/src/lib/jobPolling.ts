import type { Candidates, JobState } from '../types/dashboard'

/** backend/services/importer_service.py start_extract 의 작업 이름 */
export const EXTRACT_JOB_NAME = 'Obsidian 가져오기'

export type ExtractOutcome =
  | { kind: 'wait' }
  | { kind: 'ready'; candidates: Candidates }
  | { kind: 'error'; message: string }

/** Obsidian 후보 추출 폴링 한 번의 결과를 해석한다. 'wait' 외에는 폴링을 멈춘다. */
export function interpretExtractState(state: JobState): ExtractOutcome {
  if (state.source !== EXTRACT_JOB_NAME) {
    return { kind: 'error', message: `다른 작업(${state.source || '없음'})이 실행되어 후보를 가져오지 못했습니다.` }
  }
  if (state.is_running || state.status === 'running') return { kind: 'wait' }
  if (state.status === 'waiting_selection') return { kind: 'ready', candidates: state.candidates }
  if (state.status === 'idle') return { kind: 'ready', candidates: { sentences: [], vocab: [] } }
  if (state.status === 'cancelled') return { kind: 'error', message: '추출이 취소되었습니다.' }
  return { kind: 'error', message: state.current_step || '추출 중 오류 발생' }
}

/** 실행 중이던 작업이 어떤 상태로든 끝났으면 대시보드를 새로고침한다. */
export function shouldRefreshAfterPoll(wasActive: boolean, current: JobState): boolean {
  return wasActive && !current.is_running && current.status !== 'running'
}
