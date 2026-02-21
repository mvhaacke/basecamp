// useCallback: wraps a function so its reference stays stable across renders.
//   Without it, fetchSyncState would be a new function object on every render,
//   causing the useEffect below to loop (effect depends on the function, function is new, repeat).
// useRef: stores a mutable value that persists across renders without triggering re-renders.
//   Used here to track the last seen `last_finished_at` without causing extra renders.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { SyncSnapshot, SyncTriggerResponse, TabKey } from './types'
import { API_BASE, formatSyncMeta } from './utils'
import { ActivityView } from './components/ActivityView'
import { CalendarView } from './components/CalendarView'
import { StatusView } from './components/StatusView'

export function App() {
  const [tab, setTab] = useState<TabKey>('status')
  const [syncState, setSyncState] = useState<SyncSnapshot | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [triggeringSync, setTriggeringSync] = useState(false)
  // useRef: tracks which sync completion we've already seen so we can detect new ones.
  const seenFinishedAt = useRef<string | null>(null)

  // useCallback: stable reference lets the useEffect dependency array stay correct.
  const fetchSyncState = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/sync`)
      if (!response.ok) throw new Error('Could not load sync status')
      const snapshot: SyncSnapshot = await response.json()
      setSyncState(snapshot)
      setSyncError(null)

      if (snapshot.last_finished_at != null) {
        if (seenFinishedAt.current == null) {
          seenFinishedAt.current = snapshot.last_finished_at
        } else if (seenFinishedAt.current !== snapshot.last_finished_at) {
          seenFinishedAt.current = snapshot.last_finished_at
          // Increment the tick to tell child views that fresh data is available.
          setRefreshTick((value) => value + 1)
        }
      }
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : 'Unknown sync status error')
    }
  }, [])

  const triggerSync = useCallback(async (reason: string) => {
    setTriggeringSync(true)
    try {
      const response = await fetch(`${API_BASE}/api/sync?reason=${encodeURIComponent(reason)}&force=false`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Could not trigger sync')
      const payload: SyncTriggerResponse = await response.json()
      setSyncState(payload.state)
      setSyncError(null)
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : 'Unknown sync trigger error')
    } finally {
      setTriggeringSync(false)
    }
  }, [])

  // Poll sync status every 10 seconds; clear the interval on unmount.
  useEffect(() => {
    void fetchSyncState()
    const interval = window.setInterval(() => {
      void fetchSyncState()
    }, 10000)
    return () => window.clearInterval(interval)
  }, [fetchSyncState])

  // Kick off a sync when the app first opens.
  useEffect(() => {
    void triggerSync('app_open')
  }, [triggerSync])

  const syncTone = syncState?.running ? 'running' : syncState?.last_error ? 'warning' : 'ok'

  return (
    <div className="app-shell">
      <div className="container">
        <header className="header panel">
          <div className="header-main">
            <p className="eyebrow">Training Intelligence</p>
            <h1>Basecamp Journal</h1>
            <p className="subtitle">Strava and Garmin sync automatically in the background when the app opens.</p>
          </div>

          <div className={`sync-panel ${syncTone}`}>
            <p className="sync-label">Data Sync</p>
            <p className="sync-state">{syncState ? syncState.status_message : 'Checking sync status...'}</p>
            <p className="sync-meta">{formatSyncMeta(syncState)}</p>
            <button
              className="sync-button"
              onClick={() => void triggerSync('manual')}
              disabled={triggeringSync || syncState?.running === true}
              title="Run sync now"
            >
              {syncState?.running ? 'Syncing...' : 'Sync now'}
            </button>
          </div>
        </header>

        {(syncError || syncState?.last_error) && (
          <p className="sync-warning" title={syncState?.last_error ?? undefined}>
            Sync warning: {syncError ?? syncState?.last_error}
          </p>
        )}

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

        {tab === 'status' && <StatusView refreshTick={refreshTick} />}
        {tab === 'calendar' && <CalendarView refreshTick={refreshTick} />}
        {tab === 'activity' && <ActivityView refreshTick={refreshTick} />}
      </div>
    </div>
  )
}
