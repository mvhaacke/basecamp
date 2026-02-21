// useMemo: caches an expensive computation. React only re-runs the function when the listed
//   dependencies change, so we don't rebuild the calendar grid on every keystroke.
import { useEffect, useMemo, useState } from 'react'
import type { CalendarBreakdown, CalendarDay, CalendarPayload } from '../types'
import {
  API_BASE,
  activityBlockWidth,
  addMonths,
  firstDayOfMonth,
  fmtDate,
  formatCalendarTooltip,
  formatDurationMinutes,
  humanDate,
  isFutureDay,
  lastDayOfMonth,
  minutesFromHours,
  monthInputValue,
  parseMonthInput,
  sportToneClass,
} from '../utils'
import { Card } from './Card'

export function CalendarView({ refreshTick }: { refreshTick: number }) {
  const [anchorMonth, setAnchorMonth] = useState(() => firstDayOfMonth(new Date()))
  const [days, setDays] = useState<CalendarDay[]>([])
  const [totals, setTotals] = useState({ sessions: 0, duration_hours: 0, tss: 0 })
  const [breakdown, setBreakdown] = useState<CalendarBreakdown>({
    sport_minutes: [],
    zone_minutes: { lit: 0, mit: 0, hit: 0 },
  })
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [openDay, setOpenDay] = useState<CalendarDay | null>(null)
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
        setBreakdown(payload.breakdown)

        const todayKey = fmtDate(new Date())
        const hasToday = payload.days.some((day) => day.date === todayKey)
        setSelectedDate((current) => {
          if (current && payload.days.some((day) => day.date === current)) return current
          return hasToday ? todayKey : payload.days[0]?.date ?? null
        })
        setOpenDay((current) => (current ? payload.days.find((day) => day.date === current.date) ?? null : null))
      })
      .catch((err: Error) => setError(err.message))
  }, [anchorMonth, refreshTick])

  useEffect(() => {
    if (!openDay) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenDay(null)
    }
    window.addEventListener('keydown', onKeyDown)
    // Cleanup removes the listener when the modal closes, preventing memory leaks.
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openDay])

  // useMemo: builds the flat array of grid cells (including leading blank cells for day-of-week
  // alignment) only when `days` changes, not on every render.
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

  const monthLabel = anchorMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const monthInput = monthInputValue(anchorMonth)
  const maxActivityMinutes = useMemo(() => {
    const values = days.flatMap((day) => day.activities.map((activity) => activity.duration_minutes))
    return Math.max(1, ...values)
  }, [days])
  const monthSummary = useMemo(() => {
    const trainingDays = days.filter((day) => day.sessions > 0).length
    const restDays = days.filter((day) => day.sessions === 0 && !isFutureDay(day.date)).length
    const avgSessionMinutes =
      totals.sessions > 0 ? Math.round(minutesFromHours(totals.duration_hours) / totals.sessions) : 0

    let longestDate: string | null = null
    let longestMinutes = 0
    for (const day of days) {
      const minutes = minutesFromHours(day.duration_hours)
      if (day.sessions > 0 && minutes > longestMinutes) {
        longestMinutes = minutes
        longestDate = day.date
      }
    }

    const topSports = breakdown.sport_minutes
      .slice(0, 3)
      .map((entry) => `${entry.sport_type} ${formatDurationMinutes(entry.minutes)}`)

    return {
      trainingDays,
      restDays,
      avgSessionMinutes,
      longestMinutes,
      longestDate,
      topSportsText: topSports.length > 0 ? topSports.join(' · ') : 'No sessions this month',
    }
  }, [days, totals.duration_hours, totals.sessions, breakdown.sport_minutes])
  const zoneRows = [
    { label: 'LIT', minutes: breakdown.zone_minutes.lit, tone: 'lit' },
    { label: 'MIT', minutes: breakdown.zone_minutes.mit, tone: 'mit' },
    { label: 'HIT', minutes: breakdown.zone_minutes.hit, tone: 'hit' },
  ]
  const zoneTotalMinutes = zoneRows.reduce((sum, row) => sum + row.minutes, 0)

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

      <div className="calendar-main">
        <div className="calendar-primary">
          <div className="totals">
            <Card label="Sessions" value={totals.sessions.toString()} />
            <Card label="Time" value={formatDurationMinutes(minutesFromHours(totals.duration_hours))} />
            <Card label="Training Days" value={monthSummary.trainingDays.toString()} />
          </div>

          <div className="calendar-wrap panel">
            <div className="calendar-scroll">
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
                  const tooltip = formatCalendarTooltip(day)

                  return (
                    <button
                      key={day.date}
                      className={`calendar-cell${future ? ' future' : ''}${isSelected ? ' selected' : ''}`}
                      onClick={() => {
                        setSelectedDate(day.date)
                        setOpenDay(day)
                      }}
                      title={tooltip}
                    >
                      <p className="calendar-date">{new Date(`${day.date}T00:00:00`).getDate()}</p>
                      <p className="calendar-meta">{day.sessions === 0 ? (future ? 'Upcoming' : 'Rest') : `${day.sessions} sessions`}</p>
                      <p className="calendar-meta">{formatDurationMinutes(minutes)}</p>
                      <div className="activity-mini-stack">
                        {day.activities.slice(0, 3).map((activity) => (
                          <span
                            key={activity.id}
                            className={`activity-mini ${sportToneClass(activity.sport_type)}`}
                            style={{ width: `${activityBlockWidth(activity.duration_minutes, maxActivityMinutes)}%` }}
                          />
                        ))}
                        {day.activities.length > 3 && <span className="activity-mini-more">+{day.activities.length - 3}</span>}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        <aside className="calendar-side">
          <article className="panel month-summary side-block">
            <h3>Month Totals</h3>
            <ul className="summary-list">
              <li>
                <span>Training days</span>
                <strong>{monthSummary.trainingDays}</strong>
              </li>
              <li>
                <span>Rest days</span>
                <strong>{monthSummary.restDays}</strong>
              </li>
              <li>
                <span>Avg session</span>
                <strong>{monthSummary.avgSessionMinutes > 0 ? formatDurationMinutes(monthSummary.avgSessionMinutes) : '-'}</strong>
              </li>
              <li title={monthSummary.longestDate ? `On ${humanDate(monthSummary.longestDate)}` : undefined}>
                <span>Longest day</span>
                <strong>{monthSummary.longestMinutes > 0 ? formatDurationMinutes(monthSummary.longestMinutes) : '-'}</strong>
              </li>
            </ul>
            <p className="month-sports">Top sports: {monthSummary.topSportsText}</p>
          </article>

          <article className="panel side-block">
            <h3>Time by Sport</h3>
            {breakdown.sport_minutes.length === 0 ? (
              <p className="state">No sessions in this month.</p>
            ) : (
              <ul className="summary-list">
                {breakdown.sport_minutes.map((entry) => (
                  <li key={entry.sport_type}>
                    <span>{entry.sport_type}</span>
                    <strong>{formatDurationMinutes(entry.minutes)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="panel side-block">
            <h3>Time by Zone</h3>
            {zoneTotalMinutes === 0 ? (
              <p className="state">No zone data for this month.</p>
            ) : (
              <ul className="zone-list">
                {zoneRows.map((zone) => (
                  <li key={zone.label}>
                    <div className="zone-row">
                      <span>{zone.label}</span>
                      <strong>{formatDurationMinutes(zone.minutes)}</strong>
                    </div>
                    <div className="zone-track">
                      <span
                        className={`zone-fill ${zone.tone}`}
                        style={{ width: `${Math.round((zone.minutes / zoneTotalMinutes) * 100)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </aside>
      </div>

      {openDay && (
        <div className="day-modal-backdrop" onClick={() => setOpenDay(null)}>
          <article className="panel day-modal" onClick={(event) => event.stopPropagation()}>
            <div className="day-modal-head">
              <h3>{humanDate(openDay.date)}</h3>
              <button className="icon-button" onClick={() => setOpenDay(null)} title="Close day details" aria-label="Close day details">
                ×
              </button>
            </div>

            <ul className="summary-list">
              <li>
                <span>Sessions</span>
                <strong>{openDay.sessions}</strong>
              </li>
              <li>
                <span>Time</span>
                <strong>{formatDurationMinutes(minutesFromHours(openDay.duration_hours))}</strong>
              </li>
              <li>
                <span>Day Type</span>
                <strong>{openDay.sessions > 0 ? 'Training' : isFutureDay(openDay.date) ? 'Upcoming' : 'Rest'}</strong>
              </li>
            </ul>

            <div className="selected-activities">
              <p className="selected-activities-title">Activities</p>
              {openDay.activities.length === 0 ? (
                <p className="state">No activities logged for this day.</p>
              ) : (
                <ul>
                  {openDay.activities.map((activity) => (
                    <li key={activity.id}>
                      <span>{activity.start_time}</span>
                      <strong>{activity.sport_type ?? 'Activity'}</strong>
                      <span>{activity.name ?? 'Untitled activity'}</span>
                      <span>{formatDurationMinutes(activity.duration_minutes)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </article>
        </div>
      )}
    </section>
  )
}
