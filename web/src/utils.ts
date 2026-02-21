// Pure helper functions: formatting, date math, class name derivation.
// Nothing here triggers React re-renders — these are plain functions.

import type { CalendarDay, SyncSnapshot } from './types'

// The API address. Hardcoded because this is a local personal tool.
export const API_BASE = 'http://127.0.0.1:8000'

// --- Sync helpers ---

export function formatSyncMeta(state: SyncSnapshot | null) {
  if (!state) return 'Loading sync state'
  if (state.running && state.last_started_at) return `Started ${formatRelativeTime(state.last_started_at)}`
  if (state.last_success_at) return `Last success ${formatRelativeTime(state.last_success_at)}`
  if (state.last_finished_at) return `Last attempt ${formatRelativeTime(state.last_finished_at)}`
  return 'No sync completed yet'
}

function formatRelativeTime(value: string) {
  const diffMs = Date.now() - new Date(value).getTime()
  if (!Number.isFinite(diffMs)) return 'just now'

  const diffMinutes = Math.max(0, Math.round(diffMs / 60000))
  if (diffMinutes < 1) return 'just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`

  const hours = Math.floor(diffMinutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// --- Duration & pace formatting ---

export function minutesFromHours(hours: number) {
  return Math.round(hours * 60)
}

export function formatDurationMinutes(minutes: number) {
  const rounded = Math.max(0, Math.round(minutes))
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  if (hours === 0) return `${mins}m`
  return `${hours}h ${mins}m`
}

export function formatPace(secondsPerKm: number) {
  const total = Math.round(secondsPerKm)
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${String(secs).padStart(2, '0')} /km`
}

export function formatElapsedHms(seconds: number) {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

// --- Display helpers ---

export function numberOrDash(value: number | null | undefined, suffix = '') {
  return value == null ? '-' : `${Math.round(value)}${suffix}`
}

export function readinessClass(readiness: number | null) {
  if (readiness == null) return 'unknown'
  if (readiness >= 75) return 'high'
  if (readiness >= 50) return 'moderate'
  return 'low'
}

// --- Stream data helpers ---

export function toValidNumber(value: number | undefined) {
  if (value == null || !Number.isFinite(value)) return null
  return Number(value)
}

export function velocityToPace(mPerS: number | undefined) {
  // Below 0.5 m/s (~1.8 km/h) is effectively stopped — a traffic light or pause.
  // Returning null lets Recharts break the line rather than drawing a huge spike.
  if (mPerS == null || !Number.isFinite(mPerS) || mPerS < 0.5) return null
  return 1000 / mPerS
}

// --- Calendar helpers ---

export function isFutureDay(value: string) {
  return value > fmtDate(new Date())
}

export function formatCalendarTooltip(day: CalendarDay) {
  const lines = [
    humanDate(day.date),
    `${day.sessions} sessions`,
    `${formatDurationMinutes(minutesFromHours(day.duration_hours))}`,
  ]
  if (day.activities.length > 0) {
    for (const activity of day.activities.slice(0, 6)) {
      const name = activity.name ? ` - ${activity.name}` : ''
      lines.push(
        `${activity.start_time} ${activity.sport_type ?? 'Activity'}${name} (${formatDurationMinutes(activity.duration_minutes)})`
      )
    }
    if (day.activities.length > 6) lines.push(`+${day.activities.length - 6} more`)
  }
  return lines.join('\n')
}

export function sportToneClass(sportType: string | null) {
  const value = (sportType ?? '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('bike')) return 'bike'
  if (value.includes('swim')) return 'swim'
  return 'other'
}

export function activityBlockWidth(minutes: number, maxMinutes: number) {
  const ratio = maxMinutes > 0 ? minutes / maxMinutes : 0
  return Math.max(24, Math.min(100, Math.round(ratio * 100)))
}

// --- Date math ---

export function firstDayOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1)
}

export function lastDayOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth() + 1, 0)
}

export function addMonths(value: Date, amount: number) {
  return new Date(value.getFullYear(), value.getMonth() + amount, 1)
}

export function monthInputValue(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

export function parseMonthInput(value: string) {
  const [year, month] = value.split('-')
  if (!year || !month) return null
  const yearNum = Number(year)
  const monthNum = Number(month)
  if (!Number.isInteger(yearNum) || !Number.isInteger(monthNum) || monthNum < 1 || monthNum > 12) return null
  return new Date(yearNum, monthNum - 1, 1)
}

export function fmtDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

export function humanDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}
