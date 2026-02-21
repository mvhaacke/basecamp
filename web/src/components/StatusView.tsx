// useState: declares a reactive variable. When the setter is called React re-renders the component.
// useEffect: runs side effects (fetch, timers, subscriptions) after render. The dependency array
//   controls when it re-runs — [refreshTick] means "re-run whenever refreshTick changes".
import { useEffect, useState } from 'react'
import type { Status } from '../types'
import { API_BASE, formatDurationMinutes, minutesFromHours, numberOrDash, readinessClass } from '../utils'
import { Card } from './Card'

export function StatusView({ refreshTick }: { refreshTick: number }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // The `cancelled` flag handles the case where this effect re-runs before the previous
    // fetch resolves — we ignore stale responses instead of overwriting fresh state.
    let cancelled = false

    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/api/status`)
      .then((response) => {
        if (!response.ok) throw new Error('Could not load status')
        return response.json()
      })
      .then((payload: Status) => {
        if (cancelled) return
        setStatus(payload)
      })
      .catch((err: Error) => {
        if (cancelled) return
        setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    // The cleanup function returned from useEffect runs when the component unmounts
    // or before the next effect fires — setting cancelled = true stops the stale update.
    return () => {
      cancelled = true
    }
  }, [refreshTick])

  if (error && !status) {
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

      {loading && <p className="state inline-state">Refreshing after sync...</p>}

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
