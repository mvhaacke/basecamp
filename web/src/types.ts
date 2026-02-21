// Mirrors the shape of API responses from FastAPI (schemas.py).
// Keeping types in one file means a single place to update when the API changes.

export type TabKey = 'status' | 'calendar' | 'activity'

export type Status = {
  readiness_score: number | null
  sleep_score: number | null
  hrv_last_night: number | null
  body_battery_high: number | null
  weekly_hours: number
  weekly_sessions: number
  weekly_tss: number
  ctl: number | null
  atl: number | null
  tsb: number | null
  nudge: string
}

export type CalendarDay = {
  date: string
  sessions: number
  duration_hours: number
  tss: number
  activities: CalendarActivity[]
}

export type CalendarActivity = {
  id: number
  name: string | null
  sport_type: string | null
  start_time: string
  duration_minutes: number
}

export type CalendarPayload = {
  days: CalendarDay[]
  totals: {
    sessions: number
    duration_hours: number
    tss: number
  }
  breakdown: CalendarBreakdown
}

export type CalendarBreakdown = {
  sport_minutes: Array<{
    sport_type: string
    minutes: number
  }>
  zone_minutes: {
    lit: number
    mit: number
    hit: number
  }
}

export type Activity = {
  id: number
  start_date: string
  sport_type: string | null
  name: string | null
}

export type ActivityDetail = {
  id: number
  sport_type: string | null
  name: string | null
  start_date: string
  duration_s: number
  distance_m: number | null
  average_heartrate: number | null
  average_watts: number | null
  average_speed_m_per_s: number | null
  calories: number | null
  stream_time: number[]
  stream_heartrate: number[]
  stream_watts: number[]
  stream_velocity_smooth: number[]
  wellness: Record<string, number | null>
}

export type SyncSnapshot = {
  running: boolean
  last_started_at: string | null
  last_finished_at: string | null
  last_success_at: string | null
  last_error: string | null
  status_message: string
  last_trigger: string | null
  runs: number
}

export type SyncTriggerResponse = {
  started: boolean
  message: string
  state: SyncSnapshot
}
