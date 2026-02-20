import { useEffect, useMemo, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type TabKey = 'status' | 'calendar' | 'activity'

type Status = {
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

type CalendarDay = {
  date: string
  sessions: number
  duration_hours: number
  tss: number
  activities: CalendarActivity[]
}

type CalendarActivity = {
  id: number
  name: string | null
  sport_type: string | null
  start_time: string
  duration_minutes: number
}

type CalendarPayload = {
  days: CalendarDay[]
  totals: {
    sessions: number
    duration_hours: number
    tss: number
  }
}

type Activity = {
  id: number
  start_date: string
  sport_type: string | null
  name: string | null
}

type ActivityDetail = {
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

const API_BASE = 'http://127.0.0.1:8000'
const BIKE_SPORTS = new Set(['Ride', 'VirtualRide', 'MountainBikeRide', 'GravelRide', 'EBikeRide'])
const RUN_SPORTS = new Set(['Run', 'TrailRun', 'VirtualRun', 'TreadmillRun'])

export function App() {
  const [tab, setTab] = useState<TabKey>('status')

  return (
    <div className="app-shell">
      <div className="container">
        <header className="header">
          <p className="eyebrow">Training Intelligence</p>
          <h1>Basecamp Journal</h1>
          <p className="subtitle">Simple training decisions, not dashboard overload.</p>
        </header>

        <nav className="tabs">
          {(['status', 'calendar', 'activity'] as const).map((item) => (
            <button
              key={item}
              className={tab === item ? 'active' : ''}
              onClick={() => setTab(item)}
              title={`Open ${item} view`}
            >
              {item}
            </button>
          ))}
        </nav>

        {tab === 'status' && <StatusView />}
        {tab === 'calendar' && <CalendarView />}
        {tab === 'activity' && <ActivityView />}
      </div>
    </div>
  )
}

function StatusView() {
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
    fetch(`${API_BASE}/api/status`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load status')
        return response.json()
      })
      .then(setStatus)
      .catch((err: Error) => setError(err.message))
  }, [])

  if (error) {
    return (
      <section className="panel">
        <p className="state error">Status unavailable: {error}</p>
      </section>
    )
  }

  if (!status) {
    return (
      <section className="panel">
        <p className="state">Loading status...</p>
      </section>
    )
  }

  const weeklyMinutes = minutesFromHours(status.weekly_hours)
  const readinessTone = readinessClass(status.readiness_score)

  return (
    <section className="status-layout">
      <article className="hero panel">
        <div>
          <p className="label">Today</p>
          <h2>{status.readiness_score == null ? 'No readiness data' : `Readiness ${Math.round(status.readiness_score)}`}</h2>
          <p>{status.nudge}</p>
        </div>
        <span className={`badge ${readinessTone}`}>{readinessTone}</span>
      </article>

      <div className="grid">
        <Card label="Weekly Time" value={formatDurationMinutes(weeklyMinutes)} tooltip="Total moving time over the last 7 days." />
        <Card label="Weekly Sessions" value={status.weekly_sessions.toString()} />
        <Card label="Weekly TSS" value={Math.round(status.weekly_tss).toString()} />
        <Card label="Body Battery" value={numberOrDash(status.body_battery_high)} />
        <Card label="Sleep" value={numberOrDash(status.sleep_score)} />
        <Card label="HRV" value={numberOrDash(status.hrv_last_night)} />
        <Card label="CTL" value={numberOrDash(status.ctl)} />
        <Card label="TSB" value={numberOrDash(status.tsb)} />
      </div>
    </section>
  )
}

function CalendarView() {
  const [anchorMonth, setAnchorMonth] = useState(() => firstDayOfMonth(new Date()))
  const [days, setDays] = useState<CalendarDay[]>([])
  const [totals, setTotals] = useState({ sessions: 0, duration_hours: 0, tss: 0 })
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const start = firstDayOfMonth(anchorMonth)
    const end = lastDayOfMonth(anchorMonth)

    setError(null)
    fetch(`${API_BASE}/api/calendar?start=${fmtDate(start)}&end=${fmtDate(end)}`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load calendar')
        return response.json()
      })
      .then((payload: CalendarPayload) => {
        setDays(payload.days)
        setTotals(payload.totals)

        const todayKey = fmtDate(new Date())
        const hasToday = payload.days.some((day) => day.date === todayKey)
        setSelectedDate(hasToday ? todayKey : payload.days[0]?.date ?? null)
      })
      .catch((err: Error) => setError(err.message))
  }, [anchorMonth])

  const calendarCells = useMemo(() => {
    if (days.length === 0) return []

    const first = new Date(`${days[0].date}T00:00:00`)
    const lead = first.getDay()
    const cells: Array<CalendarDay | null> = []

    for (let i = 0; i < lead; i += 1) cells.push(null)
    for (const day of days) cells.push(day)
    while (cells.length % 7 !== 0) cells.push(null)

    return cells
  }, [days])

  const selectedDay = days.find((day) => day.date === selectedDate) ?? null
  const monthLabel = anchorMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const monthInput = monthInputValue(anchorMonth)

  return (
    <section className="calendar-layout">
      <div className="calendar-top">
        <h2>{monthLabel}</h2>
        <div className="calendar-nav">
          <button onClick={() => setAnchorMonth(addMonths(anchorMonth, -1))} title="Previous month">
            ←
          </button>
          <input
            type="month"
            aria-label="Select month"
            value={monthInput}
            onChange={(event) => {
              const next = parseMonthInput(event.target.value)
              if (next) setAnchorMonth(next)
            }}
          />
          <button onClick={() => setAnchorMonth(firstDayOfMonth(new Date()))} title="Jump to current month">
            Today
          </button>
          <button onClick={() => setAnchorMonth(addMonths(anchorMonth, 1))} title="Next month">
            →
          </button>
        </div>
      </div>

      {error && <p className="state error">Calendar unavailable: {error}</p>}

      <div className="totals">
        <Card label="Sessions" value={totals.sessions.toString()} />
        <Card label="Time" value={formatDurationMinutes(minutesFromHours(totals.duration_hours))} />
        <Card label="TSS" value={Math.round(totals.tss).toString()} />
      </div>

      <div className="calendar-wrap panel">
        <div className="calendar-head">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
            <div key={label} className="calendar-head-cell">
              {label}
            </div>
          ))}
        </div>

        <div className="calendar-grid">
          {calendarCells.map((day, index) => {
            if (!day) {
              return <div key={`blank-${index}`} className="calendar-cell blank" />
            }

            const minutes = minutesFromHours(day.duration_hours)
            const isSelected = selectedDate === day.date
            const future = isFutureDay(day.date)
            const dayClass = dayLoadClass(day, future)
            const tooltip = formatCalendarTooltip(day)

            return (
              <button
                key={day.date}
                className={`calendar-cell ${dayClass}${isSelected ? ' selected' : ''}`}
                onClick={() => setSelectedDate(day.date)}
                title={tooltip}
              >
                <p className="calendar-date">{new Date(`${day.date}T00:00:00`).getDate()}</p>
                <p className="calendar-meta">{day.sessions === 0 ? (future ? 'Upcoming' : 'Rest') : `${day.sessions} sessions`}</p>
                <p className="calendar-meta">{formatDurationMinutes(minutes)}</p>
                <p className="calendar-meta">{Math.round(day.tss)} TSS</p>
              </button>
            )
          })}
        </div>
      </div>

      <article className="panel selected-day">
        <h3>{selectedDay ? humanDate(selectedDay.date) : 'No day selected'}</h3>
        {selectedDay ? (
          <div className="grid compact">
            <Card label="Sessions" value={selectedDay.sessions.toString()} />
            <Card label="Time" value={formatDurationMinutes(minutesFromHours(selectedDay.duration_hours))} />
            <Card label="TSS" value={Math.round(selectedDay.tss).toString()} />
            <Card label="Load" value={dayLoadClass(selectedDay, isFutureDay(selectedDay.date))} />
          </div>
        ) : (
          <p className="state">Select a day to inspect details.</p>
        )}
      </article>
    </section>
  )
}

function ActivityView() {
  const [activities, setActivities] = useState<Activity[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<ActivityDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    setError(null)
    fetch(`${API_BASE}/api/activities?limit=100`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load activity list')
        return response.json()
      })
      .then((items: Activity[]) => {
        setActivities(items)
        setSelectedId(items[0]?.id ?? null)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setError(null)
    setLoadingDetail(true)

    fetch(`${API_BASE}/api/activities/${selectedId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load activity details')
        return response.json()
      })
      .then(setDetail)
      .catch((err: Error) => {
        setDetail(null)
        setError(err.message)
      })
      .finally(() => setLoadingDetail(false))
  }, [selectedId])

  const chartData = useMemo(() => {
    if (!detail) return []
    return detail.stream_time.map((value, index) => ({
      time: value,
      hr: toValidNumber(detail.stream_heartrate[index]),
      watts: toValidNumber(detail.stream_watts[index]),
      pace: velocityToPace(detail.stream_velocity_smooth[index]),
    }))
  }, [detail])

  const sport = detail?.sport_type ?? ''
  const showPower = BIKE_SPORTS.has(sport)
  const showPace = RUN_SPORTS.has(sport)
  const hasHrStream = chartData.some((point) => point.hr != null)
  const hasPowerStream = showPower && chartData.some((point) => point.watts != null)
  const hasPaceStream = showPace && chartData.some((point) => point.pace != null)
  const paceSecondsPerKm = detail?.average_speed_m_per_s ? 1000 / detail.average_speed_m_per_s : null

  return (
    <section className="activity-layout">
      {error && <p className="state error">Activity unavailable: {error}</p>}
      <label htmlFor="activity-select">Activity</label>
      <select
        id="activity-select"
        name="activity"
        value={selectedId ?? ''}
        onChange={(event) => setSelectedId(Number(event.target.value))}
      >
        {activities.length === 0 && <option value="">No activities</option>}
        {activities.map((activity) => (
          <option key={activity.id} value={activity.id}>
            {new Date(activity.start_date).toLocaleDateString()} · {activity.sport_type} · {activity.name}
          </option>
        ))}
      </select>

      {loadingDetail && <p className="state">Loading activity...</p>}
      {detail && (
        <>
          <div className="grid">
            <Card label="Duration" value={formatDurationMinutes(Math.round(detail.duration_s / 60))} />
            <Card label="Distance" value={detail.distance_m ? `${(detail.distance_m / 1000).toFixed(1)} km` : '-'} />
            <Card label="Avg HR" value={numberOrDash(detail.average_heartrate)} />
            {showPower && <Card label="Avg Power" value={numberOrDash(detail.average_watts, ' W')} />}
            {showPace && <Card label="Avg Pace" value={paceSecondsPerKm ? formatPace(paceSecondsPerKm) : '-'} />}
            <Card label="Sleep Score" value={numberOrDash(detail.wellness.sleep_score)} />
            <Card label="Readiness" value={numberOrDash(detail.wellness.training_readiness_score)} />
          </div>

          <div className="chart-wrap panel">
            {chartData.length > 0 && (hasHrStream || hasPowerStream || hasPaceStream) ? (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                  <XAxis
                    dataKey="time"
                    tickFormatter={(value) => `${Math.round(Number(value) / 60)}m`}
                    minTickGap={48}
                  />
                  <YAxis yAxisId="hr" hide />
                  <YAxis yAxisId="power" hide />
                  <YAxis yAxisId="pace" hide reversed />
                  <Tooltip
                    formatter={(value, name) => {
                      if (name === 'hr') return [`${Math.round(Number(value))} bpm`, 'Heart Rate']
                      if (name === 'watts') return [`${Math.round(Number(value))} W`, 'Power']
                      if (name === 'pace') return [formatPace(Number(value)), 'Pace']
                      return [String(value), String(name)]
                    }}
                    labelFormatter={(value) => `Minute ${Math.round(Number(value) / 60)}`}
                  />
                  {hasHrStream && (
                    <Line type="monotone" dataKey="hr" name="Heart Rate" stroke="var(--hr)" strokeWidth={2.25} dot={false} yAxisId="hr" />
                  )}
                  {hasPowerStream && (
                    <Line type="monotone" dataKey="watts" name="Power" stroke="var(--power)" strokeWidth={2.25} dot={false} yAxisId="power" />
                  )}
                  {hasPaceStream && (
                    <Line type="monotone" dataKey="pace" name="Pace" stroke="var(--pace)" strokeWidth={2.25} dot={false} yAxisId="pace" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="state">No stream data for this activity. Re-sync with `basecamp strava sync --streams`.</p>
            )}
          </div>
        </>
      )}
    </section>
  )
}

function Card({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <article className="card" title={tooltip ?? `${label}: ${value}`}>
      <p>{label}</p>
      <h3>{value}</h3>
    </article>
  )
}

function minutesFromHours(hours: number) {
  return Math.round(hours * 60)
}

function formatDurationMinutes(minutes: number) {
  const rounded = Math.max(0, Math.round(minutes))
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  if (hours === 0) return `${mins}m`
  return `${hours}h ${mins}m`
}

function formatPace(secondsPerKm: number) {
  const total = Math.round(secondsPerKm)
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${String(secs).padStart(2, '0')} /km`
}

function numberOrDash(value: number | null | undefined, suffix = '') {
  return value == null ? '-' : `${Math.round(value)}${suffix}`
}

function readinessClass(readiness: number | null) {
  if (readiness == null) return 'unknown'
  if (readiness >= 75) return 'high'
  if (readiness >= 50) return 'moderate'
  return 'low'
}

function dayLoadClass(day: CalendarDay, future: boolean) {
  if (future && day.sessions === 0 && day.tss <= 0) return 'future'
  const tss = day.tss
  if (tss >= 110) return 'high'
  if (tss >= 60) return 'moderate'
  if (tss > 0) return 'low'
  return 'rest'
}

function isFutureDay(value: string) {
  return value > fmtDate(new Date())
}

function toValidNumber(value: number | undefined) {
  if (value == null || !Number.isFinite(value)) return null
  return Number(value)
}

function velocityToPace(mPerS: number | undefined) {
  if (mPerS == null || !Number.isFinite(mPerS) || mPerS <= 0) return null
  return 1000 / mPerS
}

function formatCalendarTooltip(day: CalendarDay) {
  const lines = [
    humanDate(day.date),
    `${day.sessions} sessions`,
    `${formatDurationMinutes(minutesFromHours(day.duration_hours))}`,
    `${Math.round(day.tss)} TSS`,
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

function firstDayOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1)
}

function lastDayOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth() + 1, 0)
}

function addMonths(value: Date, amount: number) {
  return new Date(value.getFullYear(), value.getMonth() + amount, 1)
}

function monthInputValue(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

function parseMonthInput(value: string) {
  const [year, month] = value.split('-')
  if (!year || !month) return null
  const yearNum = Number(year)
  const monthNum = Number(month)
  if (!Number.isInteger(yearNum) || !Number.isInteger(monthNum) || monthNum < 1 || monthNum > 12) return null
  return new Date(yearNum, monthNum - 1, 1)
}

function fmtDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

function humanDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}
