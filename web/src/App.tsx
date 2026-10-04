import { useEffect, useState } from 'react';
import { SwipeToAction } from './components/SwipeToAction';
import { apiConfigError } from './api/client';
import { getCurrentUser, signInWithPassword, signOut } from './api/auth';
import { supabase } from './api/supabase';
import type { UserProfile } from './api/types';
import { createOrder, listOrders, submitOrder } from './api/orders';
import { confirmPlan, generatePlan, getCapacityOutlook } from './api/planning';
import { acknowledgeTrip, completeTrip, departTrip, getTrip, listTrips } from './api/trips';
import { confirmReceipt, listOutletDeliveries, recordDelivery, recordPod, recordShortfall } from './api/deliveries';
import { syncOperations } from './api/sync';

type Role = 'Store Manager' | 'Dispatcher' | 'Loader' | 'Driver';
type Screen =
  | 'Orders' | 'Confirmed' | 'Deferral' | 'Receipt'
  | 'Queue' | 'Allocate' | 'Board' | 'Capacity'
  | 'Load list' | 'Shortfall' | 'Plan changed'
  | 'Route' | 'Deliver stop' | 'Offline & sync';

const OFFLINE_QUEUE_KEY = 'waypoint.driver.sync-queue.v1';
const items = [
  { name: 'Anchor Full Cream Milk 1L', sku: 'FRESH-MLK-001', price: 285, qty: 12 },
  { name: 'Maliban Cream Cracker 200g', sku: 'FRESH-BSC-014', price: 120, qty: 6 },
  { name: 'Basmati Rice 1kg', sku: 'FRESH-RCE-009', price: 490, qty: 4 },
  { name: 'Elephant House Ginger Beer 400ml', sku: 'FRESH-BEV-033', price: 95, qty: 8 },
  { name: 'Dil Foods Coconut Milk 400ml', sku: 'FRESH-CKG-007', price: 210, qty: 3 },
];

const roleScreens: Record<Role, Screen[]> = {
  'Store Manager': ['Orders', 'Confirmed', 'Deferral', 'Receipt'],
  Dispatcher: ['Queue', 'Allocate', 'Board', 'Capacity'],
  Loader: ['Load list', 'Shortfall', 'Plan changed'],
  Driver: ['Route', 'Deliver stop', 'Offline & sync', 'Board'],
};

const displayRole = (role: UserProfile['role']): Role =>
  ({ store_manager: 'Store Manager', dispatcher: 'Dispatcher', loader: 'Loader', driver: 'Driver' })[role] as Role;

const roleAccounts = [
  { role: 'Store Manager', email: 'storemanager@waypoint.lk' },
  { role: 'Dispatcher', email: 'dispatcher@waypoint.lk' },
  { role: 'Loader', email: 'loader@waypoint.lk' },
  { role: 'Driver', email: 'driver@waypoint.lk' },
];

function Auth({ onSignedIn }: { onSignedIn: (profile: UserProfile) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const configuredError = apiConfigError();

  const handleLogin = async () => {
    setBusy(true);
    setError('');
    try {
      await signInWithPassword(email, password);
      onSignedIn(await getCurrentUser());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign-in failed. Check your email and password.');
    } finally {
      setBusy(false);
    }
  };

  const quickLogin = (accountEmail: string) => {
    setEmail(accountEmail);
    setPassword('waypoint123');
  };

  return (
    <main className="auth">
      <div className="auth-art">
        <div className="brand-mark">W</div>
        <p className="eyebrow">WAYPOINT GROUP</p>
        <h1>
          Move the morning<br />
          <em>with confidence.</em>
        </h1>
        <p className="muted light">One operational rhythm from outlet order to confirmed receipt across all 4 roles.</p>
        <div className="route-art">
          <span>DC</span><i /><span>01</span><i /><span>02</span><i /><span>03</span>
        </div>
      </div>
      <section className="auth-card">
        <p className="eyebrow">CONTROL TOWER</p>
        <h2>Sign in to your account</h2>
        <p className="muted">Select a seeded role or enter credentials to continue.</p>
        <div className="role-hints">
          <p className="role-hints-label">Quick login (click to fill):</p>
          <div className="role-hint-chips">
            {roleAccounts.map(a => (
              <button key={a.email} className="role-chip" type="button" onClick={() => quickLogin(a.email)}>
                <span className="role-chip-dot" />
                {a.role}
              </button>
            ))}
          </div>
        </div>
        <label>
          Email
          <input value={email} onChange={e => setEmail(e.target.value)} placeholder="you@waypoint.lk" type="email" />
        </label>
        <label>
          Password
          <div className="password-wrap">
            <input
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              type={showPassword ? 'text' : 'password'}
              onKeyDown={e => e.key === 'Enter' && email && password && handleLogin()}
            />
            <button className="pw-toggle" type="button" onClick={() => setShowPassword(!showPassword)}>
              {showPassword ? '◉' : '○'}
            </button>
          </div>
        </label>
        <button className="primary full" disabled={busy || !email || !password} onClick={handleLogin}>
          {busy ? 'Signing in…' : 'Sign in'} <span>→</span>
        </button>
        {configuredError && <small className="error-text">{configuredError}</small>}
        {error && <small className="error-text">{error}</small>}
      </section>
    </main>
  );
}

function Shell({ role, profile, onSignOut }: { role: Role; profile: UserProfile; onSignOut: () => void }) {
  const [screen, setScreen] = useState<Screen>(roleScreens[role][0]);
  const [toast, setToast] = useState('');
  const [qty, setQty] = useState(items.map(x => x.qty));
  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3000);
  };
  useEffect(() => setScreen(roleScreens[role][0]), [role]);

  return (
    <div className="app-shell">
      <aside>
        <div className="side-brand">
          <div className="brand-mark small">W</div>
          <span>WAYPOINT</span>
        </div>
        <div className="workspace">
          <span className="dot" />Fresh network<strong>{role}</strong>
        </div>
        <nav>
          {roleScreens[role].map(item => (
            <button className={item === screen ? 'active' : ''} key={item} onClick={() => setScreen(item)}>
              <span className="nav-icon">{icon(item)}</span>
              {label(item)}
            </button>
          ))}
        </nav>
        <div className="side-bottom">
          <div className="network">
            <span className="dot" />All systems operational
          </div>
          <button className="profile" onClick={onSignOut}>
            <span className="avatar">{role[0]}</span>
            <span>
              <b>{profile.full_name}</b>
              <small>Sign out</small>
            </span>
            <span>↗</span>
          </button>
        </div>
      </aside>
      <section className="main">
        <header>
          <div>
            <p className="eyebrow">{role.toUpperCase()} / {profile.email}</p>
            <h1>{title(screen)}</h1>
          </div>
          <div className="header-actions">
            <span className="live"><i />Live workspace</span>
            <button className="icon-button" onClick={() => notify('Notifications are clear')}>♡</button>
          </div>
        </header>
        <div className="content">
          {screenView(screen, setScreen, qty, setQty, notify, profile)}
        </div>
        {toast && <div className="toast">✓ {toast}</div>}
      </section>
    </div>
  );
}

function icon(s: Screen) {
  return ({
    Orders: '＋',
    Confirmed: '✓',
    Deferral: '!',
    Receipt: '□',
    Queue: '≡',
    Allocate: '◈',
    Board: '◉',
    Capacity: '⌁',
    'Load list': '▤',
    Shortfall: '△',
    'Plan changed': '↻',
    Route: '⌂',
    'Deliver stop': '＋',
    'Offline & sync': '⚡',
  } as Record<Screen, string>)[s] || '•';
}

function label(s: Screen) {
  return ({
    Orders: 'Place order',
    Confirmed: 'Confirmed order',
    Deferral: 'Deferral notice',
    Receipt: 'Confirm receipt',
    Queue: 'Order queue',
    Allocate: 'Plan & allocate',
    Board: 'Live delivery board',
    Capacity: 'Capacity outlook',
    'Load list': 'Load list',
    Shortfall: 'Flag shortfall',
    'Plan changed': 'Plan changed',
    Route: 'Driver route',
    'Deliver stop': 'Record delivery',
    'Offline & sync': 'Offline & sync',
  } as Record<Screen, string>)[s] || s;
}

function title(s: Screen) {
  return label(s);
}

function Kpi({ label, value, sub, tone = '' }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}

function Status({ children, tone = 'green' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`status ${tone}`}>{children}</span>;
}

function screenView(
  screen: Screen,
  setScreen: (s: Screen) => void,
  qty: number[],
  setQty: (q: number[]) => void,
  notify: (m: string) => void,
  profile: UserProfile
) {
  if (screen === 'Orders') return <Orders qty={qty} setQty={setQty} notify={notify} profile={profile} />;
  if (screen === 'Confirmed') return <Confirmed />;
  if (screen === 'Deferral') return <Deferral profile={profile} />;
  if (screen === 'Receipt') return <Receipt profile={profile} notify={notify} />;
  if (screen === 'Queue') return <Queue />;
  if (screen === 'Allocate') return <Allocate notify={notify} />;
  if (screen === 'Board') return <Board />;
  if (screen === 'Capacity') return <Capacity />;
  if (screen === 'Load list') return <LoadList notify={notify} goScreen={setScreen} />;
  if (screen === 'Shortfall') return <Shortfall notify={notify} />;
  if (screen === 'Plan changed') return <PlanChanged notify={notify} />;
  if (screen === 'Route') return <DriverRoute notify={notify} goScreen={setScreen} profile={profile} />;
  if (screen === 'Deliver stop') return <DriverDeliverStop notify={notify} goScreen={setScreen} />;
  return <DriverOfflineSync notify={notify} />;
}

/* ─────────────────────────────────────────────────────────────
   STORE MANAGER SCREENS
   ───────────────────────────────────────────────────────────── */

function Orders({ qty, setQty, notify, profile }: { qty: number[]; setQty: (q: number[]) => void; notify: (m: string) => void; profile: UserProfile }) {
  const total = items.reduce((sum, item, i) => sum + item.price * qty[i], 0);
  const [busy, setBusy] = useState(false);
  const [orderDate, setOrderDate] = useState('2026-10-03');
  const [error, setError] = useState('');

  const placeOrder = async () => {
    if (!profile.outlet_id) {
      setError('Your account has no outlet assigned.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const order = await createOrder({
        outlet_id: profile.outlet_id,
        brand: 'Fresh',
        requested_date: orderDate,
        temp_requirement: 'chilled',
        items: items.map((item, i) => ({
          sku: item.sku,
          description: item.name,
          quantity: qty[i],
          weight_kg: 1,
          volume_m3: 0.01,
          temp_requirement: 'ambient',
        })),
      });
      await submitOrder(order.id);
      notify(`Order ${order.id.slice(0, 8)} submitted to dispatch!`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Order submission failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="banner warning">◷ Order cutoff in <b>1h 24m</b> · Fresh orders close at 4:00 PM for next-morning delivery (before 8 AM).</div>
      {error && <div className="banner critical">{error}</div>}
      <div className="section-head">
        <div>
          <span className="overline">{profile.outlet_id ?? 'ASSIGNED OUTLET'}</span>
          <h2>Prepare Fresh order</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
            <span>Target date:</span>
            <input type="date" value={orderDate} onChange={e => setOrderDate(e.target.value)} />
          </label>
          <Status>{busy ? 'Saving…' : 'Ready'}</Status>
        </div>
      </div>
      <Panel>
        <div className="table-head">
          <span>Product</span>
          <span>Unit price</span>
          <span>Quantity</span>
          <span>Subtotal</span>
        </div>
        {items.map((item, i) => (
          <div className="product-row" key={item.sku}>
            <div>
              <b>{item.name}</b>
              <small>{item.sku}</small>
            </div>
            <span>Rs. {item.price}</span>
            <div className="stepper">
              <button onClick={() => setQty(qty.map((v, j) => j === i ? Math.max(0, v - 1) : v))}>−</button>
              <b>{qty[i]}</b>
              <button onClick={() => setQty(qty.map((v, j) => j === i ? v + 1 : v))}>+</button>
            </div>
            <strong>Rs. {(item.price * qty[i]).toLocaleString()}</strong>
          </div>
        ))}
        <div className="total">
          <span>Order total</span>
          <strong>Rs. {total.toLocaleString()}</strong>
        </div>
      </Panel>
      <div className="action-row">
        <button className="secondary" onClick={() => notify('Draft changes are local until submitted')}>Save draft</button>
        <button className="primary" disabled={busy} onClick={placeOrder}>
          {busy ? 'Submitting…' : 'Submit order'} <span>→</span>
        </button>
      </div>
    </>
  );
}

function Confirmed() {
  return (
    <div className="narrow">
      <div className="success-block">
        <div className="check">✓</div>
        <div>
          <Status>Confirmed</Status>
          <h2>Order is on its way into planning</h2>
          <p>The dispatcher has captured your order into the optimization queue.</p>
        </div>
      </div>
      <Panel>
        <div className="meta-grid">
          <div><small>Reference</small><b>WPF-2026-08741</b></div>
          <div><small>Estimated arrival</small><b>Tomorrow · 05:30–07:45 AM</b></div>
          <div><small>Brand</small><b>Waypoint Fresh</b></div>
          <div><small>Target Depot</small><b>Peliyagoda</b></div>
        </div>
      </Panel>
      <Panel>
        <h3>Items ordered</h3>
        {items.map(i => (
          <div className="line" key={i.sku}>
            <span>{i.name}</span>
            <b>×{i.qty}</b>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function Deferral({ profile }: { profile: UserProfile }) {
  const [orders, setOrders] = useState<Array<{ id: string; status: string; requested_date: string; notes: string | null }>>([]);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');

  useEffect(() => {
    if (!profile.outlet_id) {
      setState('empty');
      return;
    }
    listOrders(`?status=deferred&limit=100`)
      .then(result => {
        setOrders(result.data);
        setState(result.data.length ? 'success' : 'empty');
      })
      .catch(() => setState('error'));
  }, [profile.outlet_id]);

  return (
    <div className="narrow">
      {state === 'loading' && <Panel>Loading deferred orders…</Panel>}
      {state === 'error' && <Panel><p className="error-text">Unable to load deferred orders.</p></Panel>}
      {state === 'empty' && (
        <Panel>
          <h3>No deferred deliveries</h3>
          <p className="muted">All orders for your outlet have been allocated or delivered without deferrals.</p>
        </Panel>
      )}
      {state === 'success' && (
        <>
          {orders.map(order => (
            <div className="warning-block" key={order.id}>
              <div className="alert-icon">!</div>
              <div>
                <Status tone="amber">Deferred</Status>
                <h2>Order {order.id.slice(0, 8)} was deferred</h2>
                <p>{order.notes || 'Capacity constraint reached on refrigerated vehicle fleet.'}</p>
                <small>Requested date · {order.requested_date}</small>
              </div>
            </div>
          ))}
          <Panel>
            <h3>What this means for your store</h3>
            <ul className="clean-list">
              <li>Deferred items will not arrive on the first morning run.</li>
              <li>The planning engine prioritizes consecutively deferred orders on the next operating cycle.</li>
              <li>Emergency stock replenishment can be coordinated via Peliyagoda dispatch.</li>
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}

function Receipt({ profile, notify }: { profile: UserProfile; notify: (m: string) => void }) {
  const [deliveries, setDeliveries] = useState<Array<{ id: string; outcome: string; trip_stop_id: string; delivered_at: string | null }>>([]);
  const [selected, setSelected] = useState('');
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [submitting, setSubmitting] = useState(false);

  const load = () =>
    profile.outlet_id
      ? listOutletDeliveries(profile.outlet_id)
          .then(result => {
            const delivered = result.filter(item => item.outcome === 'delivered');
            setDeliveries(delivered);
            setSelected(delivered[0]?.id ?? '');
            setState(delivered.length ? 'success' : 'empty');
          })
          .catch(() => setState('error'))
      : Promise.resolve(setState('empty'));

  useEffect(() => {
    void load();
  }, [profile.outlet_id]);

  const confirm = async () => {
    if (!selected) return;
    setSubmitting(true);
    try {
      await confirmReceipt(selected, {
        items_received: {
          'FRESH-MLK-001': 12,
          'FRESH-BSC-014': 6,
        },
        issues_noted: 'All items received in good condition at outlet counter.',
      });
      notify('Receipt confirmed by backend!');
      await load();
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Receipt confirmation failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="banner warning">Confirm goods received at the dock after driver completes handover.</div>
      {state === 'loading' && <Panel>Loading delivery records…</Panel>}
      {state === 'error' && (
        <Panel>
          <p className="error-text">Unable to load deliveries.</p>
          <button className="secondary" onClick={() => void load()}>Retry</button>
        </Panel>
      )}
      {state === 'empty' && (
        <Panel>
          <h3>No delivered shipments awaiting confirmation</h3>
          <p className="muted">Once the driver marks a stop delivered, the shipment will appear here for receipt sign-off.</p>
        </Panel>
      )}
      {state === 'success' && (
        <>
          <div className="section-head">
            <div>
              <span className="overline">{profile.outlet_id}</span>
              <h2>Confirm delivery receipt</h2>
            </div>
            <Status>{deliveries.length} delivered shipments</Status>
          </div>
          <Panel>
            <label style={{ display: 'grid', gap: 8 }}>
              Select delivery to confirm
              <select value={selected} onChange={e => setSelected(e.target.value)}>
                {deliveries.map(delivery => (
                  <option key={delivery.id} value={delivery.id}>
                    Delivery {delivery.id.slice(0, 8)} · Delivered at {delivery.delivered_at ? new Date(delivery.delivered_at).toLocaleTimeString() : 'Recent'}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted" style={{ marginTop: 12 }}>Items count and seal condition will be submitted to the backend audit log.</p>
          </Panel>
          <button className="primary" disabled={submitting || !selected} onClick={() => void confirm()}>
            {submitting ? 'Confirming…' : 'Confirm receipt'} <span>→</span>
          </button>
        </>
      )}
    </>
  );
}

/* ─────────────────────────────────────────────────────────────
   DISPATCHER SCREENS
   ───────────────────────────────────────────────────────────── */

function Queue() {
  const [rows, setRows] = useState<Array<{ id: string; brand: string; total_weight_kg: number; total_volume_m3: number; status: string; outlet_id: string }>>([]);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [error, setError] = useState('');

  const load = async () => {
    setState('loading');
    try {
      const result = await listOrders('?limit=100');
      setRows(result.data);
      setState(result.data.length ? 'success' : 'empty');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load orders.');
      setState('error');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <div className="kpi-grid">
        <Kpi label="Open orders" value={state === 'success' ? String(rows.length) : '—'} sub="In database" />
        <Kpi label="Submitted" value={state === 'success' ? String(rows.filter(r => r.status === 'submitted').length) : '—'} sub="Ready to plan" />
        <Kpi label="Allocated" value={state === 'success' ? String(rows.filter(r => r.status === 'allocated').length) : '—'} sub="Assigned to trips" />
        <Kpi label="Deferred" value={state === 'success' ? String(rows.filter(r => r.status === 'deferred').length) : '—'} sub="Capacity limited" tone="amber" />
      </div>
      {state === 'loading' && <Panel>Loading orders…</Panel>}
      {state === 'error' && (
        <Panel>
          <p className="error-text">{error}</p>
          <button className="secondary" onClick={() => void load()}>Retry</button>
        </Panel>
      )}
      {state === 'empty' && <Panel>No orders found.</Panel>}
      {state === 'success' && (
        <Panel className="table-panel">
          <div className="table-head queue-grid">
            <span>Order / Outlet</span>
            <span>Brand</span>
            <span>Weight / volume</span>
            <span>Status</span>
            <span>Priority</span>
          </div>
          {rows.map(row => (
            <div className="table-row queue-grid" key={row.id}>
              <div>
                <b>{row.outlet_id}</b>
                <small>{row.id.slice(0, 8)}</small>
              </div>
              <Status>{row.brand}</Status>
              <span>{row.total_weight_kg} kg / {row.total_volume_m3} m³</span>
              <Status tone={row.status === 'deferred' ? 'amber' : row.status === 'submitted' ? 'blue' : 'green'}>
                {row.status}
              </Status>
              <span>{row.brand === 'Fresh' ? 'High (8 AM)' : 'Standard'}</span>
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}

function Allocate({ notify }: { notify: (m: string) => void }) {
  const [depot, setDepot] = useState<'Peliyagoda' | 'Kandy'>('Peliyagoda');
  const [planDate, setPlanDate] = useState('2026-10-03');
  const [plan, setPlan] = useState<Awaited<ReturnType<typeof generatePlan>> | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const run = async () => {
    setState('loading');
    setError('');
    setConfirmed(false);
    try {
      const result = await generatePlan({ plan_date: planDate, depot, dry_run: false });
      setPlan(result);
      setState('success');
      notify(`Plan generated: ${result.trips.length} trips, ${result.deferred_orders.length} deferred`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Plan generation failed.');
      setState('error');
    }
  };

  const handleConfirm = async () => {
    if (!plan?.plan_id) return;
    setConfirming(true);
    try {
      await confirmPlan(plan.plan_id);
      setConfirmed(true);
      notify('Delivery plan confirmed! Loaders and Drivers can now view and execute it.');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Plan confirmation failed');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <>
      <div className="banner warning">
        Constraint engine enforces: Brand & district isolation, Reefer refrigeration, Van access restrictions, Home depot, Trip counts (≤2), and Fresh 270m / Style-Tech 480m time budgets.
      </div>
      <div className="section-head">
        <div>
          <span className="overline">DISPATCH OPTIMIZATION ENGINE</span>
          <h2>Generate constraint-aware delivery plan</h2>
        </div>
        <div className="action-row" style={{ alignItems: 'center' }}>
          <button className="secondary" type="button" onClick={() => setPlanDate('2026-10-03')}>
            Use Walkthrough Date (2026-10-03)
          </button>
          <select value={depot} onChange={e => setDepot(e.target.value as 'Peliyagoda' | 'Kandy')}>
            <option>Peliyagoda</option>
            <option>Kandy</option>
          </select>
          <input type="date" value={planDate} onChange={e => setPlanDate(e.target.value)} />
          <button className="primary" disabled={state === 'loading'} onClick={() => void run()}>
            {state === 'loading' ? 'Optimizing…' : 'Generate plan'} <span>→</span>
          </button>
        </div>
      </div>
      {state === 'error' && (
        <Panel>
          <p className="error-text">{error}</p>
          <button className="secondary" onClick={() => void run()}>Retry</button>
        </Panel>
      )}
      {state === 'idle' && (
        <Panel>
          <h3>Ready to plan</h3>
          <p className="muted">Click "Generate plan" to run the greedy constructive allocation engine with complete constraint verification.</p>
        </Panel>
      )}
      {plan && (
        <>
          <div className="kpi-grid">
            <Kpi label="Total orders" value={String(plan.metrics.total_orders)} sub="Submitted orders" />
            <Kpi label="Served" value={String(plan.metrics.served_orders)} sub="Allocated to trips" />
            <Kpi label="Deferred" value={String(plan.metrics.deferred_orders)} sub="Reason recorded" tone={Number(plan.metrics.deferred_orders) > 0 ? 'amber' : ''} />
            <Kpi label="Trips created" value={String(plan.metrics.trips_created)} sub={`${plan.metrics.vehicles_used} vehicles`} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '20px 0 10px' }}>
            <h3>Generated trips ({plan.trips.length})</h3>
            {plan.plan_id && (
              <button
                className="primary"
                disabled={confirmed || confirming}
                onClick={() => void handleConfirm()}
                style={{ background: confirmed ? '#22935d' : undefined }}
              >
                {confirmed ? '✓ Plan Confirmed' : confirming ? 'Confirming…' : 'Confirm Plan for Warehouse & Fleet →'}
              </button>
            )}
          </div>

          <Panel>
            {plan.trips.map(trip => (
              <div className="line" key={`${trip.vehicle_id}-${trip.trip_number}`}>
                <span>
                  <b>{trip.vehicle_id} · Trip #{trip.trip_number}</b>
                  <small>{trip.brand} brand · {trip.district} district · {trip.orders.length} orders</small>
                </span>
                <span>
                  {trip.total_weight_kg} kg · {trip.total_volume_m3} m³ · {trip.estimated_distance_km} km · {trip.estimated_duration_min} min
                </span>
              </div>
            ))}
          </Panel>

          <Panel>
            <h3>Deferred orders & explainability</h3>
            {plan.deferred_orders.length === 0 ? (
              <p className="muted">Zero deferrals — 100% of candidate demand successfully accommodated within fleet capacity.</p>
            ) : (
              plan.deferred_orders.map(order => (
                <div className="line" key={order.order_id}>
                  <span>
                    <b>Order {order.order_id.slice(0, 8)}</b>
                    <small>{order.reason_detail}</small>
                  </span>
                  <Status tone="amber">{order.reason_code}</Status>
                </div>
              ))
            )}
          </Panel>
        </>
      )}
    </>
  );
}

function Board() {
  const [trips, setTrips] = useState<Array<{ id: string; vehicle_id: string; brand: string; district: string; status: string; total_weight_kg: number; total_volume_m3: number }>>([]);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [error, setError] = useState('');

  const load = async () => {
    setState('loading');
    try {
      const result = await listTrips('?limit=100');
      setTrips(result.data);
      setState(result.data.length ? 'success' : 'empty');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load trips.');
      setState('error');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <div className="kpi-grid">
        <Kpi label="Trips" value={state === 'success' ? String(trips.length) : '—'} sub="Total routes" />
        <Kpi label="Planned" value={state === 'success' ? String(trips.filter(t => t.status === 'planned').length) : '—'} sub="Loading / Staging" />
        <Kpi label="In transit" value={state === 'success' ? String(trips.filter(t => ['departed', 'in_transit'].includes(t.status)).length) : '—'} sub="On road" tone="blue" />
        <Kpi label="Completed" value={state === 'success' ? String(trips.filter(t => t.status === 'completed').length) : '—'} sub="Delivered" tone="green" />
      </div>
      {state === 'loading' && <Panel>Loading trips…</Panel>}
      {state === 'error' && (
        <Panel>
          <p className="error-text">{error}</p>
          <button className="secondary" onClick={() => void load()}>Retry</button>
        </Panel>
      )}
      {state === 'empty' && (
        <Panel>
          <h3>No active trips on the board</h3>
          <p className="muted">Generate and confirm a plan from the "Plan & allocate" tab to populate the board.</p>
        </Panel>
      )}
      {state === 'success' && (
        <Panel className="table-panel">
          <div className="table-head board-grid">
            <span>Vehicle</span>
            <span>Brand / District</span>
            <span>Payload</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {trips.map(trip => (
            <div className="table-row board-grid" key={trip.id}>
              <b className="mono">{trip.vehicle_id}</b>
              <span>{trip.brand} · {trip.district}</span>
              <span>{trip.total_weight_kg} kg / {trip.total_volume_m3} m³</span>
              <Status tone={trip.status === 'completed' ? 'green' : trip.status === 'in_transit' || trip.status === 'departed' ? 'blue' : 'amber'}>
                {trip.status}
              </Status>
              <small>Trip {trip.id.slice(0, 6)}</small>
            </div>
          ))}
        </Panel>
      )}
    </>
  );
}

function Capacity() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getCapacityOutlook>>>([]);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');

  useEffect(() => {
    getCapacityOutlook('2026-10-03', 7)
      .then(result => {
        setRows(result);
        setState(result.length ? 'success' : 'empty');
      })
      .catch(() => setState('error'));
  }, []);

  return (
    <>
      <div className="section-head">
        <div>
          <span className="overline">DEMAND & CAPACITY OUTLOOK</span>
          <h2>Forward fleet capacity projection</h2>
        </div>
      </div>
      {state === 'loading' && <Panel>Loading capacity outlook…</Panel>}
      {state === 'error' && <Panel><p className="error-text">Unable to load capacity outlook.</p></Panel>}
      {state === 'empty' && <Panel>No capacity outlook data available.</Panel>}
      {state === 'success' && (
        <Panel>
          <div className="capacity-list" style={{ display: 'grid', gap: 12 }}>
            {rows.map(row => (
              <div className="line" key={row.date} style={{ alignItems: 'center' }}>
                <div>
                  <b>{row.date}</b>
                  <small>{row.order_count} orders · {row.demand_weight_kg} kg aggregate demand</small>
                </div>
                <div>
                  <Status tone={row.capacity_gap_kg ? 'amber' : 'green'}>
                    {row.vehicle_count} vehicles ({row.reefer_count} reefer)
                  </Status>
                </div>
                <strong style={{ color: row.capacity_gap_kg ? '#a63b38' : '#0f5c52' }}>
                  {row.capacity_gap_kg ? `Shortage: ${row.capacity_gap_kg} kg` : 'Full capacity available'}
                </strong>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}

/* ─────────────────────────────────────────────────────────────
   LOADER SCREENS
   ───────────────────────────────────────────────────────────── */

function LoadList({ notify, goScreen }: { notify: (m: string) => void; goScreen: (s: Screen) => void }) {
  const [trip, setTrip] = useState<Awaited<ReturnType<typeof getTrip>> | null>(null);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    listTrips('?limit=5')
      .then(result => {
        const availableTrip = result.data.find(t => t.status === 'planned' || t.status === 'loading') || result.data[0];
        if (availableTrip) {
          getTrip(availableTrip.id).then(value => {
            localStorage.setItem('waypoint.loader.trip-id', value.id);
            if (value.stops[0]) localStorage.setItem('waypoint.loader.stop-id', value.stops[0].id);
            setTrip(value);
            setState('success');
          });
        } else {
          setState('empty');
        }
      })
      .catch(e => {
        setError(e instanceof Error ? e.message : 'Unable to load trip.');
        setState('error');
      });
  }, []);

  const acknowledge = async () => {
    if (!trip) return;
    try {
      await acknowledgeTrip(trip.id, 'loader');
      setTrip({ ...trip, loader_acknowledged: true });
      notify('Trip acknowledged by warehouse loader');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Acknowledge failed');
    }
  };

  const handleFlagShortfall = (stopId: string) => {
    localStorage.setItem('waypoint.loader.stop-id', stopId);
    goScreen('Shortfall');
  };

  if (state === 'loading') return <Panel>Loading assigned trip…</Panel>;
  if (state === 'error') return <Panel><p className="error-text">{error}</p></Panel>;
  if (state === 'empty' || !trip) {
    return (
      <Panel>
        <h3>No trips assigned to dock</h3>
        <p className="muted">Once dispatch confirms a plan, the vehicle loading sequences will appear here.</p>
      </Panel>
    );
  }

  const orderedStops = [...trip.stops].sort((a, b) => a.load_position - b.load_position);

  return (
    <>
      <div className="dark-banner">
        <div>
          <span className="overline">VEHICLE {trip.vehicle_id} · {trip.depot} DOCK</span>
          <h2>Load in reverse-unload order</h2>
          <p>Pack first stops at the door (highest load position). Stops are sequenced below.</p>
        </div>
        <Status tone={trip.loader_acknowledged ? 'green' : 'amber'}>
          {trip.loader_acknowledged ? 'Acknowledged' : 'Review required'}
        </Status>
      </div>

      {orderedStops.map(stop => (
        <SwipeToAction key={stop.id}>
          <Panel className={`stop-card ${stop.status === 'loaded' ? 'loaded' : stop.status === 'shortfall' ? 'shortfall' : ''}`}>
            <div className="stop-number">{stop.load_position}</div>
            <div className="stop-copy">
              <div className="card-line">
                <div>
                  <b>Outlet {stop.outlet_id}</b>
                  <small>Load position #{stop.load_position} · Delivery sequence stop #{stop.sequence_number}</small>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Status tone={stop.status === 'shortfall' ? 'amber' : 'blue'}>{stop.status}</Status>
                  <button className="secondary" style={{ height: 32, padding: '0 10px', fontSize: 11 }} onClick={() => handleFlagShortfall(stop.id)}>
                    Flag shortfall
                  </button>
                </div>
              </div>
              <p>Order {stop.order_id.slice(0, 8)} · Target arrival {stop.planned_arrival_time ?? '06:00 AM'}</p>
            </div>
          </Panel>
        </SwipeToAction>
      ))}

      <div className="action-row" style={{ marginTop: 20 }}>
        <button className="primary" disabled={trip.loader_acknowledged} onClick={() => void acknowledge()}>
          {trip.loader_acknowledged ? '✓ Load List Acknowledged' : 'Acknowledge trip load'} <span>→</span>
        </button>
      </div>
    </>
  );
}

function Shortfall({ notify }: { notify: (m: string) => void }) {
  const [issueType, setIssueType] = useState<'missing' | 'damaged' | 'wrong_item'>('missing');
  const [missingQty, setMissingQty] = useState(6);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    const tripId = localStorage.getItem('waypoint.loader.trip-id');
    const stopId = localStorage.getItem('waypoint.loader.stop-id');
    if (!tripId || !stopId) {
      setError('Please open a trip stop before recording a shortfall.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await recordShortfall(tripId, stopId, {
        issue_type: issueType,
        sku: 'FRESH-MLK-001',
        description: 'Anchor Full Cream Milk 1L',
        expected_quantity: 12,
        actual_quantity: 12 - missingQty,
        notes: notes || undefined,
      });
      notify('Shortfall recorded in backend!');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Shortfall could not be recorded.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <div className="banner warning">Record the affected quantity before vehicle departure.</div>
      {error && <div className="banner critical">{error}</div>}
      <Panel>
        <span className="overline">STEP 1 · ISSUE TYPE</span>
        <div className="choice-grid">
          <button className={issueType === 'missing' ? 'selected' : ''} onClick={() => setIssueType('missing')}>
            <b>Missing</b>
            <small>Stock not available</small>
          </button>
          <button className={issueType === 'damaged' ? 'selected' : ''} onClick={() => setIssueType('damaged')}>
            <b>Damaged</b>
            <small>Unfit for dispatch</small>
          </button>
          <button className={issueType === 'wrong_item' ? 'selected' : ''} onClick={() => setIssueType('wrong_item')}>
            <b>Wrong item</b>
            <small>Incorrect SKU</small>
          </button>
        </div>
      </Panel>
      <Panel>
        <span className="overline">STEP 2 · AFFECTED ITEM</span>
        <h3>Anchor Full Cream Milk 1L</h3>
        <p className="muted">SKU: FRESH-MLK-001 · Expected 12 units</p>
        <div className="quantity">
          <span>Units missing:</span>
          <button type="button" onClick={() => setMissingQty(Math.max(1, missingQty - 1))}>−</button>
          <b>{missingQty}</b>
          <button type="button" onClick={() => setMissingQty(missingQty + 1)}>+</button>
        </div>
      </Panel>
      <Panel>
        <span className="overline">NOTES</span>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Dock notes regarding shortfall..." />
      </Panel>
      <button className="primary full" disabled={busy} onClick={() => void submit()}>
        {busy ? 'Recording…' : `Confirm shortfall · ${missingQty} missing`}
      </button>
    </div>
  );
}

function PlanChanged({ notify }: { notify: (m: string) => void }) {
  return (
    <div className="narrow">
      <div className="critical-block">
        <Status tone="red">Plan changed</Status>
        <h2>The load list has changed</h2>
        <p>Dispatcher updated the routing sequence before departure. Please re-verify vehicle loading.</p>
      </div>
      <Panel>
        <div className="meta-grid">
          <div><small>Notification</small><b>Sequence altered</b></div>
          <div><small>When</small><b>Just now</b></div>
          <div><small>Dispatcher</small><b>Peliyagoda Central</b></div>
          <div><small>Priority</small><b>High</b></div>
        </div>
      </Panel>
      <button className="primary full" onClick={() => notify('Updated load list acknowledged')}>
        Acknowledge & continue
      </button>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   DRIVER SCREENS (Web Console implementation)
   ───────────────────────────────────────────────────────────── */

function DriverRoute({ notify, goScreen, profile }: { notify: (m: string) => void; goScreen: (s: Screen) => void; profile: UserProfile }) {
  const [trip, setTrip] = useState<Awaited<ReturnType<typeof getTrip>> | null>(null);
  const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => {
    setState('loading');
    listTrips('?limit=5')
      .then(res => {
        const myTrip = res.data.find(t => t.vehicle_id === profile.vehicle_id) || res.data[0];
        if (myTrip) {
          getTrip(myTrip.id).then(full => {
            setTrip(full);
            setState('success');
          });
        } else {
          setState('empty');
        }
      })
      .catch(e => {
        setError(e instanceof Error ? e.message : 'Failed to load driver trip.');
        setState('error');
      });
  };

  useEffect(() => {
    load();
  }, [profile.vehicle_id]);

  const handleAcknowledge = async () => {
    if (!trip) return;
    setBusy(true);
    try {
      await acknowledgeTrip(trip.id, 'driver');
      setTrip({ ...trip, driver_acknowledged: true });
      notify('Trip acknowledged by driver');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Acknowledge failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDepart = async () => {
    if (!trip) return;
    setBusy(true);
    try {
      await departTrip(trip.id);
      setTrip({ ...trip, status: 'departed' });
      notify('Trip departed from depot! Live tracking active.');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Depart failed');
    } finally {
      setBusy(false);
    }
  };

  const handleComplete = async () => {
    if (!trip) return;
    setBusy(true);
    try {
      await completeTrip(trip.id);
      setTrip({ ...trip, status: 'completed' });
      notify('Trip completed! All stops concluded.');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Trip completion failed');
    } finally {
      setBusy(false);
    }
  };

  const deliverStop = (stopId: string) => {
    localStorage.setItem('waypoint.driver.stop-id', stopId);
    goScreen('Deliver stop');
  };

  if (state === 'loading') return <Panel>Loading assigned driver route…</Panel>;
  if (state === 'error') return <Panel><p className="error-text">{error}</p></Panel>;
  if (state === 'empty' || !trip) {
    return (
      <Panel>
        <h3>No trip currently assigned</h3>
        <p className="muted">When dispatch allocates trips to vehicle {profile.vehicle_id || 'VEH035'}, your route will appear here.</p>
      </Panel>
    );
  }

  const sortedStops = [...trip.stops].sort((a, b) => a.sequence_number - b.sequence_number);

  return (
    <>
      <div className="dark-banner">
        <div>
          <span className="overline">VEHICLE {trip.vehicle_id} · {trip.depot}</span>
          <h2>{trip.brand} Delivery Route — {trip.district}</h2>
          <p>Total payload: {trip.total_weight_kg} kg · {trip.total_distance_km} km · {trip.estimated_duration_min} min</p>
        </div>
        <Status tone={trip.status === 'completed' ? 'green' : trip.status === 'departed' || trip.status === 'in_transit' ? 'blue' : 'amber'}>
          {trip.status}
        </Status>
      </div>

      <div className="action-row" style={{ justifyContent: 'flex-start', margin: '0 0 16px', gap: 10 }}>
        <button className="secondary" disabled={busy || trip.driver_acknowledged} onClick={() => void handleAcknowledge()}>
          {trip.driver_acknowledged ? '✓ Driver Acknowledged' : '1. Acknowledge route'}
        </button>
        <button
          className="primary"
          disabled={busy || !trip.driver_acknowledged || trip.status !== 'planned'}
          onClick={() => void handleDepart()}
        >
          {trip.status === 'planned' ? '2. Depart from depot →' : '✓ Departed depot'}
        </button>
        <button
          className="secondary"
          disabled={busy || !['departed', 'in_transit'].includes(trip.status)}
          onClick={() => void handleComplete()}
        >
          3. Complete trip ✓
        </button>
      </div>

      <Panel>
        <div className="table-head">
          <span>Stop sequence</span>
          <span>Outlet ID</span>
          <span>Planned Arrival</span>
          <span>Status</span>
        </div>
        {sortedStops.map(stop => (
          <div className="table-row" key={stop.id} style={{ alignItems: 'center' }}>
            <div>
              <b>Stop #{stop.sequence_number}</b>
              <small>Load position #{stop.load_position}</small>
            </div>
            <span>{stop.outlet_id}</span>
            <span>{stop.planned_arrival_time ?? '06:00 AM'}</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Status tone={stop.status === 'delivered' ? 'green' : stop.status === 'attempted' ? 'amber' : 'blue'}>
                {stop.status}
              </Status>
              <button className="primary" style={{ height: 32, padding: '0 12px', fontSize: 12 }} onClick={() => deliverStop(stop.id)}>
                {stop.status === 'delivered' ? 'View stop' : 'Deliver →'}
              </button>
            </div>
          </div>
        ))}
      </Panel>
    </>
  );
}

function DriverDeliverStop({ notify, goScreen }: { notify: (m: string) => void; goScreen: (s: Screen) => void }) {
  const [stopId, setStopId] = useState('');
  const [outcome, setOutcome] = useState<'delivered' | 'attempted' | 'refused'>('delivered');
  const [recipient, setRecipient] = useState('Nimal Fernando');
  const [notes, setNotes] = useState('');
  const [simulateOffline, setSimulateOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const sid = localStorage.getItem('waypoint.driver.stop-id') || '';
    setStopId(sid);
  }, []);

  const handleRecord = async () => {
    if (!stopId) {
      setError('No stop selected. Please pick a stop from your route.');
      return;
    }
    setBusy(true);
    setError('');
    const operationId = crypto.randomUUID();
    const payload = {
      trip_stop_id: stopId,
      outcome,
      recipient_name: outcome === 'delivered' ? recipient : undefined,
      notes: notes || undefined,
      delivered_at: new Date().toISOString(),
      offline_operation_id: operationId,
    };

    if (simulateOffline) {
      // Queue offline
      const queue = JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || '[]');
      queue.push({
        operation_id: operationId,
        operation: 'complete_delivery',
        occurred_at: new Date().toISOString(),
        payload,
      });
      localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
      notify('Delivery saved to OFFLINE queue! Records are safe on device.');
      setBusy(false);
      goScreen('Offline & sync');
      return;
    }

    try {
      const delivery = await recordDelivery(payload);
      if (outcome === 'delivered') {
        try {
          await recordPod(delivery.id, {
            recipient_name: recipient,
            recorded_at: new Date().toISOString(),
          });
        } catch {
          // POD is optional if already recorded
        }
      }
      notify(`Delivery recorded successfully (${outcome})!`);
      goScreen('Route');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delivery record failed. If trip is not departed yet, mark departed first.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="narrow">
      <div className="banner warning">Record stop outcome safely once vehicle has docked at the store.</div>
      {error && <div className="banner critical">{error}</div>}
      <Panel>
        <span className="overline">STOP IDENTIFIER</span>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
          <b>{stopId ? `Trip Stop: ${stopId.slice(0, 8)}` : 'Select a stop from Driver Route'}</b>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={simulateOffline} onChange={e => setSimulateOffline(e.target.checked)} />
            <b>Simulate Hill Country Offline</b>
          </label>
        </div>
      </Panel>
      <Panel>
        <span className="overline">DELIVERY OUTCOME</span>
        <div className="choice-grid">
          <button className={outcome === 'delivered' ? 'selected' : ''} onClick={() => setOutcome('delivered')}>
            <b>✓ Delivered</b>
            <small>Handover complete</small>
          </button>
          <button className={outcome === 'attempted' ? 'selected' : ''} onClick={() => setOutcome('attempted')}>
            <b>! Attempted</b>
            <small>Store closed / no recipient</small>
          </button>
          <button className={outcome === 'refused' ? 'selected' : ''} onClick={() => setOutcome('refused')}>
            <b>× Refused</b>
            <small>Outlet rejected goods</small>
          </button>
        </div>
      </Panel>
      {outcome === 'delivered' && (
        <Panel>
          <span className="overline">PROOF OF DELIVERY</span>
          <label style={{ display: 'grid', gap: 6, margin: '10px 0' }}>
            Recipient name
            <input value={recipient} onChange={e => setRecipient(e.target.value)} placeholder="Store Manager Name" />
          </label>
          <div className="photo">⌾ Digital signature & photo captured</div>
        </Panel>
      )}
      <Panel>
        <span className="overline">DELIVERY NOTES</span>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Unloading notes, bay access, or traffic delays..." />
      </Panel>
      <div className="action-row">
        <button className="secondary" onClick={() => goScreen('Route')}>Cancel</button>
        <button className="primary" disabled={busy} onClick={() => void handleRecord()}>
          {busy ? 'Recording…' : simulateOffline ? 'Save to Offline Queue' : 'Confirm and record delivery'} <span>→</span>
        </button>
      </div>
    </div>
  );
}

function DriverOfflineSync({ notify }: { notify: (m: string) => void }) {
  const [queue, setQueue] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const loadQueue = () => {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    setQueue(raw ? JSON.parse(raw) : []);
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleSync = async () => {
    if (!queue.length) return;
    setSyncing(true);
    setSyncResult(null);
    try {
      const resp = await syncOperations(queue);
      setSyncResult(`Sync completed: ${resp.applied_count} applied, ${resp.duplicate_count} duplicates, ${resp.failed_count} failed.`);
      localStorage.removeItem(OFFLINE_QUEUE_KEY);
      loadQueue();
      notify('All offline operations reconciled with backend!');
    } catch (e) {
      setSyncResult(e instanceof Error ? e.message : 'Sync failed. Retry when internet connectivity returns.');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="narrow">
      <div className="banner warning">
        Reconciliation engine guarantees idempotency via stable UUID <code>operation_id</code> across repeated sync replays.
      </div>
      <Panel>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3>Queued offline operations</h3>
            <p className="muted">Operations stored in device memory ready for server reconciliation.</p>
          </div>
          <Status tone={queue.length > 0 ? 'amber' : 'green'}>
            {queue.length} items queued
          </Status>
        </div>
      </Panel>
      {queue.map(op => (
        <Panel key={op.operation_id}>
          <div className="line">
            <div>
              <b>{op.operation}</b>
              <small>ID: {op.operation_id}</small>
              <small>Time: {new Date(op.occurred_at).toLocaleTimeString()}</small>
            </div>
            <Status tone="amber">Pending Sync</Status>
          </div>
        </Panel>
      ))}
      {syncResult && (
        <Panel>
          <p><b>{syncResult}</b></p>
        </Panel>
      )}
      <button className="primary full" disabled={syncing || queue.length === 0} onClick={() => void handleSync()}>
        {syncing ? 'Syncing to backend…' : queue.length > 0 ? `Sync ${queue.length} operations now →` : 'Queue empty — All synced ✓'}
      </button>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   ROOT APP COMPONENT
   ───────────────────────────────────────────────────────────── */

export default function App() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const client = supabase;
    if (!client) {
      setLoading(false);
      return;
    }
    const load = async () => {
      try {
        const session = (await client.auth.getSession()).data.session;
        if (session) setProfile(await getCurrentUser());
      } finally {
        setLoading(false);
      }
    };
    void load();

    const { data } = client.auth.onAuthStateChange((_event, session) => {
      if (!session) setProfile(null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  if (loading) return <div className="loading-screen">Loading your Waypoint session…</div>;
  if (!profile) return <Auth onSignedIn={setProfile} />;

  return (
    <Shell
      role={displayRole(profile.role)}
      profile={profile}
      onSignOut={async () => {
        await signOut();
        setProfile(null);
      }}
    />
  );
}
