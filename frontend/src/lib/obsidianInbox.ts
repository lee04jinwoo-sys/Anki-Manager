import type { ObsidianInboxSummary } from '../types/dashboard'

/** Obsidian 볼트가 있는 곳(Mac)에서만 '가져오기' 버튼을 보인다. 서버에는 볼트가 없다. */
export function showObsidianImport(inbox: ObsidianInboxSummary | undefined): boolean {
  return inbox?.available === true
}
