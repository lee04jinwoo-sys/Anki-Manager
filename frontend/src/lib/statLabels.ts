/**
 * 통계 카드·잔디 제목. 백엔드는 선택한 언어의 덱만 집계하므로(stats_service.get_overview)
 * 제목도 그 덱을 가리켜야 한다. 응답의 lang을 넘겨 숫자와 제목의 언어가 어긋나지 않게 한다.
 */
export function statLabels(lang: 'en' | 'zh' = 'en') {
  const scope = lang === 'zh' ? '중국어 덱' : '영어 덱'
  return {
    todayReviews: `오늘 리뷰 (${scope})`,
    dueRemaining: `남은 복습 (${scope})`,
    retention30d: `30일 정답률 (${scope}, 리뷰 단위)`,
    streak: `연속 학습 (${scope})`,
    heatmapScope: `최근 1년 ${scope}`,
  }
}
