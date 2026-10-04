import { useEffect, useState } from 'react';
import { getDriverTrip, recordDelivery, signInWithPassword, supabase, syncOperations } from './api';

type Screen = 'route' | 'stop' | 'offline' | 'sync';
const OFFLINE_RECORD_KEY = 'waypoint.driver.offline-delivery.v1';
const OFFLINE_QUEUE_KEY = 'waypoint.driver.sync-queue.v1';

function Auth({ onComplete }: { onComplete: () => void }) {
  const [email, setEmail] = useState('driver@waypoint.demo');
  const [password, setPassword] = useState('WaypointDemo2026!');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submitPassword = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await signInWithPassword(email, password);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed. Check email and password.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-mobile">
      <Header title="Driver sign in" sub="Waypoint secure access" />
      <main>
        <Card>
          <p className="section-label">DRIVER CREDENTIALS</p>
          <h2>Sign in to assigned route</h2>
          <p style={{ color: '#889096', fontSize: 13, margin: '4px 0 16px' }}>
            Enter your driver email and password to access vehicle route and offline delivery records.
          </p>
          <form onSubmit={submitPassword}>
            <label style={{ display: 'grid', gap: 6, margin: '12px 0 6px', fontSize: 13, fontWeight: 600 }}>
              Email
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="driver@waypoint.demo"
                type="email"
                required
                autoComplete="email"
              />
            </label>
            <label style={{ display: 'grid', gap: 6, margin: '6px 0 16px', fontSize: 13, fontWeight: 600 }}>
              Password
              <input
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                type="password"
                required
                autoComplete="current-password"
              />
            </label>
            {error && <p className="error-text" style={{ color: '#e5484d', margin: '0 0 12px', fontSize: 13 }}>{error}</p>}
            <button
              className="primary full"
              type="submit"
              disabled={busy || !email || !password}
            >
              {busy ? 'Signing in…' : 'Sign in to vehicle'} <span>→</span>
            </button>
          </form>
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.08)', fontSize: 12, color: '#889096' }}>
            <span style={{ display: 'block', marginBottom: 6, fontWeight: 600 }}>Quick Fill Demo:</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="secondary"
                style={{ fontSize: 11, padding: '4px 8px' }}
                onClick={() => { setEmail('driver@waypoint.demo'); setPassword('WaypointDemo2026!'); }}
              >
                driver@waypoint.demo
              </button>
              <button
                type="button"
                className="secondary"
                style={{ fontSize: 11, padding: '4px 8px' }}
                onClick={() => { setEmail('driver@waypoint.lk'); setPassword('waypoint123'); }}
              >
                driver@waypoint.lk
              </button>
            </div>
          </div>
        </Card>
      </main>
    </div>
  );
}

function Header({ title, sub, offline = false }: { title: string; sub: string; offline?: boolean }) {
  return (
    <header>
      <div className="topline">
        <span className="brand-dot">W</span>
        <span>WAYPOINT DRIVER</span>
        <span className={`connection ${offline ? 'bad' : ''}`}><i />{offline ? 'Offline' : 'Online'}</span>
      </div>
      <small>{sub}</small>
      <h1>{title}</h1>
    </header>
  );
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

function Route({ go }: { go: (s: Screen) => void }) {
  const [tripId, setTripId] = useState('');
  const [liveStops, setLiveStops] = useState<Array<{ id: string; n: number; name: string; district: string; window: string; status: string }>>([]);
  const [state, setState] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    getDriverTrip().then(trip => {
      if (!trip) throw new Error('No driver trip is available.');
      setTripId(trip.id);
      setLiveStops(trip.stops.sort((a, b) => a.sequence_number - b.sequence_number).map(stop => ({
        id: stop.id,
        n: stop.sequence_number,
        name: `Outlet ${stop.outlet_id}`,
        district: `Stop ${stop.sequence_number}`,
        window: stop.planned_arrival_time ?? 'Backend scheduled',
        status: stop.status,
      })));
      setState('success');
    }).catch(e => {
      setError(e instanceof Error ? e.message : 'Unable to load driver route.');
      setState('error');
    });
  }, []);

  if (state === 'loading') return <><Header title="Today's route" sub="Loading backend trip…" /><main><Card>Loading assigned route…</Card></main></>;
  if (state === 'error') return <><Header title="Today's route" sub="Driver workspace" /><main><Card><p className="error-text">{error}</p><button className="secondary" onClick={() => window.location.reload()}>Retry</button></Card></main></>;

  const openStop = (stop: { id: string }) => {
    localStorage.setItem('waypoint.driver.stop-id', stop.id);
    go('stop');
  };

  return (
    <>
      <Header title="Today's route" sub="Assigned backend trip" />
      <div className="hero-stats">
        <div><small>STOPS</small><b>{liveStops.length} total</b></div>
        <div><small>TRIP</small><b>{tripId.slice(0, 8)}</b></div>
        <div><small>STATE</small><b>Live</b></div>
      </div>
      <main>
        <p className="section-label">Delivery sequence</p>
        {liveStops.map((s, i) => (
          <Card className={i === 0 && s.status === 'pending' ? 'next' : ''} key={s.id}>
            <div className="stop-top">
              <span className="number">{s.n}</span>
              <div>
                <b>{s.name}</b>
                <small>{s.district}</small>
              </div>
              <strong>{s.status}<small>status</small></strong>
            </div>
            <div className="window">◷ Arrival <b>{s.window}</b></div>
            <button className="primary" style={{ marginTop: 10 }} onClick={() => openStop(s)}>
              {s.status === 'delivered' ? 'View stop ✓' : 'Open stop →'}
            </button>
          </Card>
        ))}
        <div className="safety">ⓘ Record delivery only when safely stopped. Do not use the app while driving.</div>
      </main>
      <Nav screen="route" go={go} />
    </>
  );
}

function Stop({ go }: { go: (s: Screen) => void }) {
  const [outcome, setOutcome] = useState('delivered');
  const [recipient, setRecipient] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const saveOfflineRecord = async () => {
    setBusy(true);
    const stopId = localStorage.getItem('waypoint.driver.stop-id') || 'backend-stop-id';
    const operationId = crypto.randomUUID();
    const payload = {
      trip_stop_id: stopId,
      outcome,
      recipient_name: recipient || (outcome === 'delivered' ? 'Store Manager' : undefined),
      notes: notes || undefined,
      delivered_at: new Date().toISOString(),
      offline_operation_id: operationId,
    };
    const operation = {
      operation_id: operationId,
      operation: 'complete_delivery',
      occurred_at: new Date().toISOString(),
      payload,
    };

    try {
      if (navigator.onLine) {
        await recordDelivery(payload);
      } else {
        throw new Error('offline');
      }
    } catch {
      const queue = JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || '[]');
      localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify([...queue, operation]));
    }

    localStorage.setItem(OFFLINE_RECORD_KEY, JSON.stringify({
      operation_id: operationId,
      outcome,
      recordedAt: new Date().toISOString(),
      status: 'Saved locally',
    }));
    setBusy(false);
    go('offline');
  };

  return (
    <>
      <Header title="Record delivery" sub="Backend trip stop" />
      <div className="notice">Record the outcome only when safely stopped.</div>
      <main>
        <Card>
          <div className="detail"><b>Assigned stop</b><span>Ready to record</span></div>
          <p className="section-label">What happened at this stop?</p>
          {[
            ['delivered', 'Delivered', 'Capture recipient and proof', '✓'],
            ['attempted', 'Attempted', 'No one available', '!'],
            ['refused', 'Refused', 'Outlet refused delivery', '×'],
          ].map(x => (
            <button className={`outcome ${outcome === x[0] ? `chosen ${x[0]}` : ''}`} key={x[0]} onClick={() => setOutcome(x[0])}>
              <span>{x[3]}</span>
              <b>{x[1]}</b>
              <small>{x[2]}</small>
            </button>
          ))}
          <label style={{ display: 'grid', gap: 6, margin: '14px 0 8px', fontSize: 13, fontWeight: 600 }}>
            Recipient name
            <input value={recipient} onChange={e => setRecipient(e.target.value)} placeholder="e.g. Nimal Fernando" />
          </label>
          <label style={{ display: 'grid', gap: 6, margin: '8px 0 14px', fontSize: 13, fontWeight: 600 }}>
            Notes (optional)
            <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes regarding delivery..." />
          </label>
          <button className="primary full" disabled={busy} onClick={() => void saveOfflineRecord()}>
            {busy ? 'Recording…' : 'Confirm and record'}
          </button>
        </Card>
      </main>
      <Nav screen="stop" go={go} />
    </>
  );
}

function Offline({ go }: { go: (s: Screen) => void }) {
  return (
    <>
      <Header title="Delivery saved" sub="Driver local log" offline />
      <div className="offline-alert">
        <b>No signal · Kandy corridor dead zone simulation</b>
        <span>Deliveries waiting to sync. Records are saved locally on device.</span>
      </div>
      <main>
        <Card className="saved">
          <div className="saved-title"><span>▣</span><b>Delivery saved locally</b><em>SYNC PENDING</em></div>
          <div className="data-grid">
            <div><small>Status</small><b className="green-text">✓ Captured</b></div>
            <div><small>Storage</small><b>Local queue</b></div>
            <div><small>Reconcile</small><b>Via /api/v1/sync</b></div>
            <div><small>Operation</small><b>Stable UUID</b></div>
          </div>
        </Card>
        <button className="primary full" onClick={() => go('sync')}>Open sync screen →</button>
      </main>
      <Nav screen="offline" go={go} />
    </>
  );
}

function Sync({ go }: { go: (s: Screen) => void }) {
  const [state, setState] = useState('pending');
  const [count, setCount] = useState(0);

  useEffect(() => {
    const queue = JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || '[]');
    setCount(queue.length);
  }, []);

  const completeSync = async () => {
    const queue = JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || '[]');
    if (!queue.length) {
      localStorage.removeItem(OFFLINE_RECORD_KEY);
      go('route');
      return;
    }
    setState('syncing');
    try {
      const result = await syncOperations(queue);
      if (result.failed_count) {
        setState('failed');
        return;
      }
      localStorage.removeItem(OFFLINE_QUEUE_KEY);
      localStorage.removeItem(OFFLINE_RECORD_KEY);
      setCount(0);
      setState('synced');
    } catch {
      setState('failed');
    }
  };

  return (
    <>
      <Header title="Offline sync" sub="Driver records remain safe on device" offline={count > 0} />
      <main className="sync-main">
        <div className="sync-icon">{state === 'synced' ? '✓' : '◉'}</div>
        <h2>{state === 'failed' ? 'Sync failed' : state === 'syncing' ? 'Syncing…' : state === 'synced' ? 'All records synced' : 'Sync pending'}</h2>
        <p>{state === 'failed' ? 'The operation remains queued. Retry when connected.' : 'Persistent operations use the same operation_id on every retry.'}</p>
        <Card>
          <div className="result"><span>Queued operations</span><b>{count}</b></div>
          <div className="result"><span>Storage</span><b className="green-text">On device (LocalStorage)</b></div>
        </Card>
        <button className="primary full" disabled={state === 'syncing'} onClick={() => void completeSync()}>
          {state === 'synced' ? 'Return to route' : count > 0 ? `Sync ${count} operations now` : 'Check sync status'}
        </button>
      </main>
      <Nav screen="sync" go={go} />
    </>
  );
}

function Nav({ screen, go }: { screen: Screen; go: (s: Screen) => void }) {
  return (
    <nav className="bottom-nav">
      <button className={screen === 'route' ? 'active' : ''} onClick={() => go('route')}>⌂<small>Route</small></button>
      <button className={screen === 'stop' ? 'active' : ''} onClick={() => go('stop')}>＋<small>Deliver</small></button>
      <button className={screen === 'offline' || screen === 'sync' ? 'active' : ''} onClick={() => go('sync')}>◉<small>Sync</small></button>
    </nav>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>(() => localStorage.getItem(OFFLINE_RECORD_KEY) ? 'offline' : 'route');
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    if (!supabase) {
      setAuthenticated(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => setAuthenticated(Boolean(data.session)));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthenticated(Boolean(session));
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  if (authenticated === null) return <div className="phone-app"><main>Loading session…</main></div>;
  if (!authenticated) return <Auth onComplete={() => setAuthenticated(true)} />;
  return (
    <div className="phone-app">
      {screen === 'route' && <Route go={setScreen} />}
      {screen === 'stop' && <Stop go={setScreen} />}
      {screen === 'offline' && <Offline go={setScreen} />}
      {screen === 'sync' && <Sync go={setScreen} />}
    </div>
  );
}
