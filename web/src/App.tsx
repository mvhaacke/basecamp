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
  calories: number | null
  stream_time: number[]
  stream_heartrate: number[]
  stream_watts: number[]
  wellness: Record<string, number | null>
}

type CalendarPayload = {
  days: CalendarDay[]
  totals: {
    sessions: number
    duration_hours: number
    tss: number
  }
}

const API_BASE = 'http://127.0.0.1:8000'

export function App() {
  const [tab, setTab] = useState<TabKey>('status')

  return (
    <div className="container">
      <header>
        <h1>Basecamp Journal</h1>
        <p>Simple training decisions, not dashboard overload.</p>
      </header>
      <nav>
        {(['status', 'calendar', 'activity'] as const).map((item) => (
          <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </nav>

      {tab === 'status' && <StatusView />}
      {tab === 'calendar' && <CalendarView />}
      {tab === 'activity' && <ActivityView />}
    </div>
  )
}

function StatusView() {
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/status`)
      .then((response) => response.json())
      .then(setStatus)
  }, [])

  if (!status) return <p>Loading status...</p>

  return (
    <section>
      <div className="grid">
        <Card label="Readiness" value={numberOrDash(status.readiness_score)} />
        <Card label="Sleep" value={numberOrDash(status.sleep_score)} />
        <Card label="HRV" value={numberOrDash(status.hrv_last_night)} />
        <Card label="Body Battery" value={numberOrDash(status.body_battery_high)} />
        <Card label="7-day Hours" value={status.weekly_hours.toFixed(1)} />
        <Card label="7-day Sessions" value={status.weekly_sessions.toString()} />
        <Card label="7-day TSS" value={status.weekly_tss.toFixed(1)} />
        <Card label="TSB" value={numberOrDash(status.tsb)} />
      </div>
      <blockquote>{status.nudge}</blockquote>
    </section>
  )
}

function CalendarView() {
  const [days, setDays] = useState<CalendarDay[]>([])
  const [totals, setTotals] = useState({ sessions: 0, duration_hours: 0, tss: 0 })
  const [monthLabel, setMonthLabel] = useState('')

  useEffect(() => {
    const start = new Date()
    start.setDate(1)
    const end = new Date(start.getFullYear(), start.getMonth() + 1, 0)
    setMonthLabel(start.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }))

    fetch(`${API_BASE}/api/calendar?start=${fmtDate(start)}&end=${fmtDate(end)}`)
      .then((response) => response.json())
      .then((payload: CalendarPayload) => {
        setDays(payload.days)
        setTotals(payload.totals)
      })
  }, [])

  const calendarCells = useMemo(() => {
    if (days.length === 0) return []
    const firstDay = new Date(`${days[0].date}T00:00:00`)
    const leadingBlanks = firstDay.getDay()
    const cells: Array<CalendarDay | null> = []
    for (let i = 0; i < leadingBlanks; i += 1) cells.push(null)
    for (const day of days) cells.push(day)
    while (cells.length % 7 !== 0) cells.push(null)
    return cells
  }, [days])

  return (
    <section>
      <h2>{monthLabel || 'Calendar'}</h2>
      <div className="totals">
        <Card label="Sessions" value={totals.sessions.toString()} />
        <Card label="Hours" value={totals.duration_hours.toFixed(1)} />
        <Card label="TSS" value={totals.tss.toFixed(1)} />
      </div>
      <div className="calendar-wrap">
        <div className="calendar-head">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
            <div key={label} className="calendar-head-cell">
              {label}
            </div>
          ))}
        </div>
        <div className="calendar-grid">
          {calendarCells.map((day, index) => (
            <article key={`${day?.date ?? 'blank'}-${index}`} className={`calendar-cell${day ? '' : ' blank'}`}>
              {day && (
                <>
                  <p className="calendar-date">{new Date(`${day.date}T00:00:00`).getDate()}</p>
                  <h3>{day.sessions ? `${day.sessions} session${day.sessions > 1 ? 's' : ''}` : 'Rest'}</h3>
                  <p>{day.duration_hours.toFixed(1)} h</p>
                  <p>{day.tss.toFixed(0)} TSS</p>
                </>
              )}
            </article>
          ))}
        </div>
      </div>
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
    fetch(`${API_BASE}/api/activities?limit=100`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load activities')
        return response.json()
      })
      .then((items: Activity[]) => {
        setActivities(items)
        if (items.length > 0) setSelectedId(items[0].id)
      })
      .catch((err: Error) => {
        setError(err.message)
      })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoadingDetail(true)
    setError(null)
    fetch(`${API_BASE}/api/activities/${selectedId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load activity detail')
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
      hr: detail.stream_heartrate[index],
      watts: detail.stream_watts[index],
    }))
  }, [detail])

  return (
    <section>
      {error && <p>{error}</p>}
      {activities.length === 0 && !error && <p>No activities found. Run `basecamp strava sync` first.</p>}
      <label>
        Activity
        <select value={selectedId ?? ''} onChange={(event) => setSelectedId(Number(event.target.value))}>
          {activities.length === 0 && <option value="">No activities</option>}
          {activities.map((activity) => (
            <option key={activity.id} value={activity.id}>
              {new Date(activity.start_date).toLocaleDateString()} · {activity.sport_type} · {activity.name}
            </option>
          ))}
        </select>
      </label>

      {loadingDetail && <p>Loading activity...</p>}
      {detail && (
        <>
          <div className="grid">
            <Card label="Duration" value={`${Math.round(detail.duration_s / 60)} min`} />
            <Card label="Distance" value={detail.distance_m ? `${(detail.distance_m / 1000).toFixed(1)} km` : '-'} />
            <Card label="Avg HR" value={numberOrDash(detail.average_heartrate)} />
            <Card label="Avg Power" value={numberOrDash(detail.average_watts)} />
            <Card label="Sleep Score" value={numberOrDash(detail.wellness.sleep_score)} />
            <Card label="Readiness" value={numberOrDash(detail.wellness.training_readiness_score)} />
          </div>

          <div className="chart-wrap">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <XAxis dataKey="time" hide />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="hr" stroke="#8a6ec9" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="watts" stroke="#c27836" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p>No stream data for this activity. Re-sync with `basecamp strava sync --streams`.</p>
            )}
          </div>
        </>
      )}
    </section>
  )
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <article>
      <p>{label}</p>
      <h3>{value}</h3>
    </article>
  )
}

function numberOrDash(value: number | null | undefined) {
  return value == null ? '-' : value.toFixed(0)
}

function fmtDate(value: Date) {
  return value.toISOString().slice(0, 10)
}
