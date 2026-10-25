/**
 * 같은 화면에서 요청을 연달아 보낼 때 마지막 요청의 응답만 반영하게 한다.
 * 언어를 빠르게 바꾸면 이전 언어의 느린 응답이 나중에 도착해 화면을 덮어쓰기 때문이다.
 */
export function createLatestRequest() {
  let seq = 0
  return {
    /** 요청 시작. 반환된 함수는 이 요청이 아직 마지막 요청인지 알려 준다. */
    begin(): () => boolean {
      const id = ++seq
      return () => id === seq
    },
  }
}
