export type Lang = 'en' | 'zh'
export type ByLang<T> = Partial<Record<Lang, T>>

/** 불러온 데이터를 그 언어 칸에만 넣는다. */
export function storeForLang<T>(cache: ByLang<T>, lang: Lang, data: T): ByLang<T> {
  return { ...cache, [lang]: data }
}

/**
 * 지금 고른 언어의 데이터만 돌려준다. 다른 언어의 데이터는 절대 보여 주지 않는다
 * (언어를 바꾼 뒤 수 초간 이전 언어 화면이 남아 바뀌지 않은 것처럼 보였다).
 * loadingLang이 같은 언어이면 갱신 중 표시를 켠다.
 */
export function viewForLang<T>(cache: ByLang<T>, lang: Lang, loadingLang: Lang | null) {
  const data = cache[lang] ?? null
  return { data, refreshing: data !== null && loadingLang === lang }
}
