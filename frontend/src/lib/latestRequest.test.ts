import { describe, expect, it } from 'vitest'
import { createLatestRequest } from './latestRequest'

/** 응답 순서를 테스트가 정하는 가짜 요청 */
function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

describe('createLatestRequest', () => {
  it('drops a slower earlier response so the last request wins (zh → en quick switch)', async () => {
    const latest = createLatestRequest()
    const shown: string[] = []
    const zh = deferred<string>()
    const en = deferred<string>()

    const a = latest.begin(); const pa = zh.promise.then((v) => { if (a()) shown.push(v) })
    const b = latest.begin(); const pb = en.promise.then((v) => { if (b()) shown.push(v) })
    en.resolve('en')   // 나중 요청이 먼저 도착
    await pb
    zh.resolve('zh')   // 이전 요청이 늦게 도착
    await pa

    expect(shown).toEqual(['en'])
  })

  it('keeps a single request current', () => {
    const latest = createLatestRequest()
    const isCurrent = latest.begin()
    expect(isCurrent()).toBe(true)
  })
})
