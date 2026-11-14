import type { JobState } from '../types/dashboard'

/** 실행 중이던 작업이 어떤 상태로든 끝났으면 대시보드를 새로고침한다. */
export function shouldRefreshAfterPoll(wasActive: boolean, current: JobState): boolean {
  return wasActive && !current.is_running && current.status !== 'running'
}
