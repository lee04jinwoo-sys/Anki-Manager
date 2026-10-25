export interface Rate {
  reviews: number
  passed: number
  rate: number | null
}

export interface RetentionSplit {
  young: Rate
  mature: Rate
  all: Rate
}

export interface HeatmapDay {
  date: string
  reviews: number
  minutes: number
}

export interface DeckStats {
  name: string
  label: string
  composition: { new: number; learning: number; young: number; mature: number; suspended: number }
  total: number
  due_today: number
  due_tomorrow: number
  reviewed_today: number
  retention_30d: RetentionSplit
  leech_notes: number
}

export interface StatsOverview {
  today: {
    date: string
    reviews: number
    minutes: number
    due_remaining: number
    due_tomorrow: number
    new_available: number
  }
  habit: {
    current: number
    longest: number
    days_studied_365: number
    avg_reviews_30d: number
    avg_minutes_30d: number
  }
  retention_30d: RetentionSplit
  weekly_retention: ({ week_end: string } & RetentionSplit)[]
  forecast: { date: string; due: number }[]
  heatmap: HeatmapDay[]
  decks: DeckStats[]
  rollover_hour: number
  desired_retention: number | null
  lang?: 'en' | 'zh'
}
