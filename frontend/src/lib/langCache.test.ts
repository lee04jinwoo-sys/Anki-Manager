import { describe, expect, it } from 'vitest'
import { storeForLang, viewForLang } from './langCache'

describe('viewForLang', () => {
  it('never shows English data right after switching to Chinese (no zh data yet → loading)', () => {
    const cache = storeForLang({}, 'en', 'EN-DATA')
    expect(viewForLang(cache, 'zh', 'zh')).toEqual({ data: null, refreshing: false })
  })

  it('shows the cached language at once and marks it refreshing while its request runs', () => {
    let cache = storeForLang({}, 'en', 'EN-DATA')
    cache = storeForLang(cache, 'zh', 'ZH-DATA')
    expect(viewForLang(cache, 'en', 'en')).toEqual({ data: 'EN-DATA', refreshing: true })
    expect(viewForLang(cache, 'zh', null)).toEqual({ data: 'ZH-DATA', refreshing: false })
  })

  it('replaces only the language that was loaded', () => {
    let cache = storeForLang({}, 'en', 'EN-1')
    cache = storeForLang(cache, 'zh', 'ZH-1')
    cache = storeForLang(cache, 'en', 'EN-2')
    expect(cache).toEqual({ en: 'EN-2', zh: 'ZH-1' })
  })
})
