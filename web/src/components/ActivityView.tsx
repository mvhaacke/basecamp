// Recharts works by composing chart primitives as JSX children.
// ResponsiveContainer fills available width; LineChart holds axes, tooltip, and Line series.
// Each Line's `yAxisId` ties it to a specific hidden YAxis — letting HR, power, and pace
// each use their own scale without distorting the others.
import { useEffect, useMemo, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Activity, ActivityDetail } from '../types'
import {
  API_BASE,
  formatDurationMinutes,
  formatElapsedHms,
  formatPace,
  numberOrDash,
  toValidNumber,
  velocityToPace,
} from '../utils'
import { Card } from './Card'

// Sport sets for deciding which metrics to show in the detail panel.
const BIKE_SPORTS = new Set(['Ride', 'VirtualRide', 'MountainBikeRide', 'GravelRide', 'EBikeRide'])
const RUN_SPORTS = new Set(['Run', 'TrailRun', 'VirtualRun', 'TreadmillRun'])

export function ActivityView({ refreshTick }: { refreshTick: number }) {
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
        setSelectedId((current) => {
          if (current && items.some((item) => item.id === current)) return current
          return items[0]?.id ?? null
        })
      })
      .catch((err: Error) => setError(err.message))
  }, [refreshTick])

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

  // useMemo: zip the parallel stream arrays into one data array for Recharts.
  // Only recomputes when `detail` changes, not on parent re-renders.
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
          <article className="panel activity-headline">
            <p>{detail.sport_type ?? 'Activity'}</p>
            <h2>{detail.name ?? 'Untitled activity'}</h2>
            <span>{new Date(detail.start_date).toLocaleString()}</span>
          </article>

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
            <div className="chart-legend">
              {hasHrStream && <span className="legend-item hr">Heart Rate</span>}
              {hasPowerStream && <span className="legend-item power">Power</span>}
              {hasPaceStream && <span className="legend-item pace">Pace</span>}
            </div>

            {chartData.length > 0 && (hasHrStream || hasPowerStream || hasPaceStream) ? (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                  <XAxis
                    dataKey="time"
                    tickFormatter={(value) => formatElapsedHms(Number(value))}
                    minTickGap={48}
                  />
                  <YAxis yAxisId="hr" hide />
                  <YAxis yAxisId="power" hide />
                  <YAxis yAxisId="pace" hide reversed />
                  <Tooltip
                    formatter={(value, name) => {
                      const metric = String(name).toLowerCase()
                      if (metric === 'hr' || metric === 'heart rate') return [`${Math.round(Number(value))} bpm`, 'Heart Rate']
                      if (metric === 'watts' || metric === 'power') return [`${Math.round(Number(value))} W`, 'Power']
                      if (metric === 'pace') return [formatPace(Number(value)), 'Pace']
                      return [String(Math.round(Number(value))), String(name)]
                    }}
                    labelFormatter={(value) => formatElapsedHms(Number(value))}
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
              <p className="state">No stream data available for this activity yet.</p>
            )}
          </div>
        </>
      )}
    </section>
  )
}
