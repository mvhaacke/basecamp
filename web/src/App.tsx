// useCallback: wraps a function so its reference stays stable across renders.
//   Without it, fetchSyncState would be a new function object on every render,
//   causing the useEffect below to loop (effect depends on the function, function is new, repeat).
// useRef: stores a mutable value that persists across renders without triggering re-renders.
//   Used here to track the last seen `last_finished_at` without causing extra renders.
import { useCallback, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
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

  const triggerSync = useCallback(async (reason: string, streams = false) => {
    // flushSync forces React to commit this state update synchronously — before the fetch starts.
    // Without it, React 18's automatic batching might delay the re-render until after the response
    // arrives, making the button appear unresponsive on fast localhost connections.
    flushSync(() => setTriggeringSync(true))
    try {
      // stream_limit=25 keeps the web button fast — deep backfill is a CLI job
      // force=true on manual clicks — the cooldown is for automatic background triggers, not user intent
      const streamParam = streams ? '&include_streams=true&stream_limit=25' : ''
      const response = await fetch(
        `${API_BASE}/api/sync?reason=${encodeURIComponent(reason)}&force=true${streamParam}`,
        { method: 'POST' },
      )
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
            <div className="header-identity">
              <img src="/basecamp.png" alt="Basecamp" className="header-logo" />
              <div>
                <h1>Basecamp</h1>
                <p className="subtitle">Your training journal</p>
              </div>
            </div>
          </div>

          <div className={`sync-panel ${syncTone}`}>
            <p className="sync-label">Data Sync</p>
            <p className="sync-state">{syncState ? syncState.status_message : 'Checking sync status...'}</p>
            <p className="sync-meta">{formatSyncMeta(syncState)}</p>
            <div className="sync-buttons">
              <button
                className="sync-button"
                onClick={() => void triggerSync('manual')}
                disabled={triggeringSync || syncState?.running === true}
                title="Sync activities and wellness data"
              >
                {triggeringSync || syncState?.running ? 'Syncing...' : 'Sync now'}
              </button>
              <button
                className="sync-button sync-button-streams"
                onClick={() => void triggerSync('manual', true)}
                disabled={triggeringSync || syncState?.running === true}
                title="Sync and fetch time-series stream data for the 25 most recent activities"
              >
                {triggeringSync || syncState?.running ? '...' : '+ streams'}
              </button>
            </div>
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
