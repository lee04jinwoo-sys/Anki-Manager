import { describe, expect, it } from 'vitest'
import { showObsidianImport } from './obsidianInbox'

describe('showObsidianImport', () => {
  it('hides the import button when the inbox is not available (server has no vault)', () => {
    expect(showObsidianImport(undefined)).toBe(false)
    expect(showObsidianImport({ available: false, vocab_count: 0, sentence_count: 0, total_count: 0 })).toBe(false)
  })
  it('shows it when the inbox is available, even with zero items', () => {
    expect(showObsidianImport({ available: true, vocab_count: 0, sentence_count: 0, total_count: 0 })).toBe(true)
  })
})
