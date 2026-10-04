import { useEffect, useRef, useState } from 'react';
import { SwipeToAction } from './components/SwipeToAction';
import { apiConfigError } from './api/client';
import { getCurrentUser, detectRoleFromEmail, getRoleMeta, signInWithPassword, signOut, signUpWithPassword } from './api/auth';
import { supabase } from './api/supabase';
import type { UserProfile } from './api/types';
import { createOrder, listOrders, submitOrder } from './api/orders';
import { generatePlan, getCapacityOutlook } from './api/planning';
import { acknowledgeTrip, getTrip, listTrips } from './api/trips';
import { confirmReceipt, listOutletDeliveries, recordShortfall } from './api/deliveries';

type Role = 'Store Manager' | 'Dispatcher' | 'Loader' | 'Driver';
type Screen = 'Orders' | 'Confirmed' | 'Deferral' | 'Receipt' | 'Queue' | 'Allocate' | 'Board' | 'Capacity' | 'Load list' | 'Shortfall' | 'Plan changed';
const items = [{ name: 'Anchor Full Cream Milk 1L', sku: 'FRESH-MLK-001', price: 285, qty: 12 }, { name: 'Maliban Cream Cracker 200g', sku: 'FRESH-BSC-014', price: 120, qty: 6 }, { name: 'Basmati Rice 1kg', sku: 'FRESH-RCE-009', price: 490, qty: 4 }, { name: 'Elephant House Ginger Beer 400ml', sku: 'FRESH-BEV-033', price: 95, qty: 8 }, { name: 'Dil Foods Coconut Milk 400ml', sku: 'FRESH-CKG-007', price: 210, qty: 3 }];
const stops = ['Highland Mart — Kandy', 'Green Valley Store — Peradeniya', 'Midlands Supermart — Gampola', 'North Central Mart — Kurunegala'];
const roleScreens: Record<Role, Screen[]> = { 'Store Manager': ['Orders', 'Confirmed', 'Deferral', 'Receipt'], Dispatcher: ['Queue', 'Allocate', 'Board', 'Capacity'], Loader: ['Load list', 'Shortfall', 'Plan changed'], Driver: ['Board'] };
const displayRole = (role: UserProfile['role']): Role => ({ store_manager: 'Store Manager', dispatcher: 'Dispatcher', loader: 'Loader', driver: 'Driver' })[role] as Role;

interface WebRoleCard {
  key: 'dispatcher' | 'loader' | 'store_manager';
  role: Role;
  name: string;
  email: string;
  title: string;
  icon: string;
  badgeTone: 'cyan' | 'amber' | 'emerald';
  hint: string;
  workspacesCount: number;
  workspaces: string[];
  description: string;
  assignment: string;
}

const WEB_ROLES: WebRoleCard[] = [
  {
    key: 'dispatcher',
    role: 'Dispatcher',
    name: 'Sunil Jayawardena',
    email: 'dispatcher@waypoint.lk',
    title: 'Dispatcher',
    icon: '◈',
    badgeTone: 'cyan',
    hint: 'Control Tower · 4 workspaces',
    workspacesCount: 4,
    workspaces: ['Order Queue', 'Plan & Allocate', 'Live Board', 'Capacity Outlook'],
    description: 'Constraint-aware fleet planning, route optimization & dispatch control',
    assignment: 'Control Tower · Peliyagoda & Kandy',
  },
  {
    key: 'loader',
    role: 'Loader',
    name: 'Kamal Perera',
    email: 'loader@waypoint.lk',
    title: 'Loader',
    icon: '▤',
    badgeTone: 'amber',
    hint: 'Peliyagoda Bay · 3 workspaces',
    workspacesCount: 3,
    workspaces: ['Load List', 'Flag Shortfall', 'Plan Changed'],
    description: 'Reverse-unload pallet sequencing & depot loading verification',
    assignment: 'Depot Loading Bay 4 · Peliyagoda',
  },
  {
    key: 'store_manager',
    role: 'Store Manager',
    name: 'Nimal Fernando',
    email: 'storemanager@waypoint.lk',
    title: 'Store Manager',
    icon: '＋',
    badgeTone: 'emerald',
    hint: 'Outlet OUT001 · 4 workspaces',
    workspacesCount: 4,
    workspaces: ['Place Order', 'Confirmed Orders', 'Deferral Notices', 'Confirm Receipt'],
    description: 'Daily order submissions, cutoff tracking & verified delivery sign-offs',
    assignment: 'Assigned Outlet OUT001 · Highland Mart',
  },
];

const EyeIcon = ({ open }: { open: boolean }) => open ? (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
) : (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

const UserIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: 6 }}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const MailIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: 6 }}>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
    <polyline points="22,6 12,13 2,6" />
  </svg>
);

const LockIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle', marginRight: 6 }}>
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

function Auth({ onSignedIn }: { onSignedIn: (profile: UserProfile) => void }) {
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [selectedRoleKey, setSelectedRoleKey] = useState<'dispatcher' | 'loader' | 'store_manager'>('dispatcher');

  const configuredError = apiConfigError();

  const detectedRole = detectRoleFromEmail(email);
  const hasEmail = email.trim().length > 0;

  // Active role key for UI highlighting (matches typed email if provided, otherwise matches selectedRoleKey)
  const activeRoleKey: 'dispatcher' | 'loader' | 'store_manager' = hasEmail
    ? (detectedRole === 'driver' ? 'dispatcher' : (detectedRole as 'dispatcher' | 'loader' | 'store_manager'))
    : selectedRoleKey;

  const currentRoleMeta = getRoleMeta(activeRoleKey);
  const activeRoleCard = WEB_ROLES.find(r => r.key === activeRoleKey) || WEB_ROLES[0];

  // Real-time password strength calculation for registration
  const getStrengthScore = (pw: string) => {
    if (!pw) return 0;
    let score = 0;
    if (pw.length >= 6) score++;
    if (pw.length >= 8) score++;
    if (/[0-9]/.test(pw) && /[a-zA-Z]/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw) || /[A-Z]/.test(pw)) score++;
    return score;
  };
  const pwStrength = getStrengthScore(password);
  const pwStrengthLabels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong'];

  const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword;
  const passwordsMismatch = confirmPassword.length > 0 && password !== confirmPassword;

  const handleLogin = async () => {
    if (!email || !password) return;
    setBusy(true);
    setError('');
    setSuccessMsg('');
    try {
      await signInWithPassword(email, password);
      onSignedIn(await getCurrentUser());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign-in failed. Check your email and password.');
    } finally {
      setBusy(false);
    }
  };

  const handleRegister = async () => {
    if (!email || !password || !fullName) {
      setError('Please fill in your name, email, and password.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match. Please verify both fields.');
      return;
    }
    setBusy(true);
    setError('');
    setSuccessMsg('');
    try {
      await signUpWithPassword(email, password, fullName);
      try {
        const user = await getCurrentUser();
        onSignedIn(user);
      } catch {
        setSuccessMsg(`Account created successfully for ${fullName}! Your role is configured as ${currentRoleMeta.displayTitle}. You can now sign in.`);
        setMode('signin');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Registration failed. Please check your credentials.');
    } finally {
      setBusy(false);
    }
  };

  const handleSelectRole = (r: WebRoleCard) => {
    setSelectedRoleKey(r.key);
    setEmail(r.email);
    setPassword('WaypointDemo2026!');
    setConfirmPassword('WaypointDemo2026!');
    setFullName(r.name);
    setError('');
  };

  return (
    <main className="auth">
      <div className="auth-art">
        <div className="brand-mark">W</div>
        <div className="brand-header-strip">
          <p className="eyebrow">WAYPOINT FRESH LOGISTICS</p>
          <span className="live-pill"><i /> LIVE CONSOLE</span>
        </div>
        <h1>Move the morning<br /><em>with confidence.</em></h1>
        <p className="muted light">
          Constraint-aware fleet planning, reverse-load pallet sequencing, and verified store delivery receipts.
        </p>

        {/* 3 Operational Web Roles: Dispatcher, Loader, Store Manager */}
        <div className="hero-role-previews">
          {WEB_ROLES.map(r => {
            const isMatch = activeRoleKey === r.key;
            return (
              <button
                key={r.key}
                type="button"
                className={`hero-role-card role-tone-${r.badgeTone} ${isMatch ? 'active' : ''}`}
                onClick={() => handleSelectRole(r)}
                aria-pressed={isMatch}
              >
                <div className="hero-card-header">
                  <span className="hero-role-icon">{r.icon}</span>
                  <strong>{r.title}</strong>
                  {isMatch && <span className="active-dot-pulse" />}
                  {isMatch && <span className="hero-active-pill">Selected</span>}
                </div>
                <div className="hero-card-sub">
                  <span>{r.hint}</span>
                </div>
                <p className="hero-card-desc">{r.description}</p>
                <div className="hero-role-tags">
                  {r.workspaces.map(w => (
                    <span key={w} className="hero-tag">{w}</span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>

        <div className="route-art">
          <span className="route-stop"><i className="route-dot pulse" /> DC Peliyagoda</span>
          <i className="route-connector" />
          <span className="route-stop"><i className="route-dot" /> 01 Kandy</span>
          <i className="route-connector" />
          <span className="route-stop"><i className="route-dot" /> 02 Peradeniya</span>
          <i className="route-connector" />
          <span className="route-stop"><i className="route-dot" /> 03 Gampola</span>
        </div>
      </div>

      <section className="auth-card">
        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab ${mode === 'signin' ? 'active' : ''}`}
            onClick={() => { setMode('signin'); setError(''); setSuccessMsg(''); }}
          >
            <span>🔐</span> Sign in
          </button>
          <button
            type="button"
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => { setMode('register'); setError(''); setSuccessMsg(''); }}
          >
            <span>✨</span> Create account
          </button>
        </div>

        <p className="eyebrow">{mode === 'signin' ? 'OPERATIONAL ACCESS' : 'NEW STAFF ONBOARDING'}</p>
        <h2>{mode === 'signin' ? 'Sign in to your workspace' : 'Create your staff account'}</h2>
        <p className="muted">
          {mode === 'signin'
            ? 'Access your role-based logistics dashboard with your credentials.'
            : 'Register your account for real-time dispatch, bay, or store operations.'}
        </p>

        {successMsg && (
          <div className="auth-success-banner">
            <div>✓</div>
            <div>
              <h4>Account ready</h4>
              <p>{successMsg}</p>
            </div>
          </div>
        )}

        {/* Interactive Role Switcher Pills (Driver removed, no demo auto-fill text) */}
        <div className="role-selector-bar">
          <span className="selector-title">SELECT OPERATIONAL STATION</span>
          <div className="role-selector-pills">
            {WEB_ROLES.map(r => {
              const isSelected = activeRoleKey === r.key;
              return (
                <button
                  key={r.key}
                  type="button"
                  className={`role-select-pill ${isSelected ? `active tone-${r.badgeTone}` : ''}`}
                  onClick={() => handleSelectRole(r)}
                >
                  <span className="pill-icon">{r.icon}</span>
                  <span>{r.title}</span>
                  {isSelected && <span className="pill-check">✓</span>}
                </button>
              );
            })}
          </div>
        </div>

        {mode === 'register' && (
          <label>
            <span className="label-heading"><UserIcon /> Full name</span>
            <input
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              placeholder="e.g. Sunil Jayawardena"
              type="text"
              autoComplete="name"
            />
          </label>
        )}

        <label>
          <span className="label-heading"><MailIcon /> Email address</span>
          <input
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@waypoint.lk (e.g. dispatcher@, loader@, store@)"
            type="email"
            autoComplete="email"
          />
        </label>

        {/* Interactive Live Role Card (Only shown when email is present - NO annoying fallback guide prompt!) */}
        {hasEmail && (
          <div className={`role-detector role-${activeRoleKey}`}>
            <div className="role-detector-head">
              <span className="role-tag-badge">{currentRoleMeta.icon} {currentRoleMeta.displayTitle} Station</span>
              <span className="live-status-pill"><i className="status-dot" /> Active</span>
            </div>
            <p className="role-detector-desc">{currentRoleMeta.description}</p>
            <div className="role-detector-meta">
              <span><b>Station:</b> {currentRoleMeta.tagline}</span>
              <span>·</span>
              <span><b>Node:</b> {currentRoleMeta.assignment}</span>
            </div>
          </div>
        )}

        <label>
          <span className="label-heading"><LockIcon /> Password</span>
          <div className="password-wrap">
            <input
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              type={showPassword ? 'text' : 'password'}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  if (mode === 'signin' && email && password) handleLogin();
                  if (mode === 'register' && email && password && confirmPassword) handleRegister();
                }
              }}
            />
            <button
              className="pw-toggle"
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              <EyeIcon open={showPassword} />
            </button>
          </div>
        </label>

        {mode === 'register' && password.length > 0 && (
          <div className="pw-strength">
            <div className="pw-meter-bars">
              <div className={`pw-meter-bar ${pwStrength >= 1 ? `active-${pwStrength}` : ''}`} />
              <div className={`pw-meter-bar ${pwStrength >= 2 ? `active-${pwStrength}` : ''}`} />
              <div className={`pw-meter-bar ${pwStrength >= 3 ? `active-${pwStrength}` : ''}`} />
              <div className={`pw-meter-bar ${pwStrength >= 4 ? `active-${pwStrength}` : ''}`} />
            </div>
            <div className="pw-strength-label">
              <span>Security strength</span>
              <strong>{pwStrengthLabels[pwStrength]}</strong>
            </div>
          </div>
        )}

        {mode === 'register' && (
          <label>
            <span className="label-heading"><LockIcon /> Confirm password</span>
            <div className="password-wrap">
              <input
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                type={showConfirmPassword ? 'text' : 'password'}
                autoComplete="new-password"
                onKeyDown={e => {
                  if (e.key === 'Enter' && email && password && confirmPassword) handleRegister();
                }}
              />
              <button
                className="pw-toggle"
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
              >
                <EyeIcon open={showConfirmPassword} />
              </button>
            </div>
            {passwordsMatch && (
              <span className="pw-match-badge ok">✓ Passwords match</span>
            )}
            {passwordsMismatch && (
              <span className="pw-match-badge bad">✕ Passwords do not match yet</span>
            )}
          </label>
        )}

        {mode === 'signin' && (
          <label className="auth-remember">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={e => setRememberMe(e.target.checked)}
            />
            Keep me signed in on this station
          </label>
        )}

        <button
          className="primary full auth-submit"
          disabled={busy || !email || !password || (mode === 'register' && (!fullName || !confirmPassword || passwordsMismatch))}
          onClick={mode === 'signin' ? handleLogin : handleRegister}
        >
          {busy ? (
            <span className="btn-loading">
              <span className="spinner" />
              {mode === 'signin' ? 'Signing in…' : 'Creating account…'}
            </span>
          ) : (
            <span>
              {mode === 'signin'
                ? `Sign in to ${activeRoleCard.title} Workspace`
                : `Register as ${activeRoleCard.title} Staff`}{' '}
              <span className="btn-arrow">→</span>
            </span>
          )}
        </button>

        <div className="auth-footer-toggle">
          {mode === 'signin' ? (
            <span>
              Need a new staff account?{' '}
              <button type="button" onClick={() => { setMode('register'); setError(''); }}>
                Create account
              </button>
            </span>
          ) : (
            <span>
              Already registered?{' '}
              <button type="button" onClick={() => { setMode('signin'); setError(''); }}>
                Sign in
              </button>
            </span>
          )}
        </div>

        {configuredError && <small className="error-text">{configuredError}</small>}
        {error && <small className="error-text">{error}</small>}
      </section>
    </main>
  );
}


function Shell({ role, profile, onSignOut }: { role: Role; profile: UserProfile; onSignOut: () => void }) { const [screen, setScreen] = useState<Screen>(roleScreens[role][0]); const [toast, setToast] = useState(''); const [qty, setQty] = useState(items.map(x => x.qty)); const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2400); }; useEffect(() => setScreen(roleScreens[role][0]), [role]); return <div className="app-shell"><aside><div className="side-brand"><div className="brand-mark small">W</div><span>WAYPOINT</span></div><div className="workspace"><span className="dot" />Fresh network<strong>{role}</strong></div><nav>{roleScreens[role].map(item => <button className={item === screen ? 'active' : ''} key={item} onClick={() => setScreen(item)}><span className="nav-icon">{icon(item)}</span>{label(item)}</button>)}</nav><div className="side-bottom"><div className="network"><span className="dot" />All systems operational</div><button className="profile" onClick={onSignOut}><span className="avatar">{role[0]}</span><span><b>{profile.full_name}</b><small>Sign out</small></span><span>↗</span></button></div></aside><section className="main"><header><div><p className="eyebrow">{role.toUpperCase()} / {profile.email}</p><h1>{title(screen)}</h1></div><div className="header-actions"><span className="live"><i />Live workspace</span><button className="icon-button" onClick={() => notify('Notifications are clear')}>♡</button></div></header><div className="content">{screenView(screen, qty, setQty, notify, profile)}</div>{toast && <div className="toast">✓ {toast}</div>}</section></div> }
function icon(s: Screen) { return ({ Orders: '＋', Confirmed: '✓', Deferral: '!', Receipt: '□', Queue: '≡', Allocate: '◈', Board: '◉', Capacity: '⌁', 'Load list': '▤', Shortfall: '△', 'Plan changed': '↻' } as Record<Screen, string>)[s]; }
function label(s: Screen) { return ({ Orders: 'Place order', Confirmed: 'Confirmed order', Deferral: 'Deferral notice', Receipt: 'Confirm receipt', Queue: 'Order queue', Allocate: 'Plan & allocate', Board: 'Live delivery board', Capacity: 'Capacity outlook', 'Load list': 'Load list', Shortfall: 'Flag shortfall', 'Plan changed': 'Plan changed' } as Record<Screen, string>)[s]; }
function title(s: Screen) { return label(s); }
function Kpi({ label, value, sub, tone = '' }: { label: string; value: string; sub: string; tone?: string }) { return <div className="kpi"><span>{label}</span><strong className={tone}>{value}</strong><small>{sub}</small></div> }
function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) { return <div className={`panel ${className}`}>{children}</div> }
function Status({ children, tone = 'green' }: { children: React.ReactNode; tone?: string }) { return <span className={`status ${tone}`}>{children}</span> }
function screenView(screen: Screen, qty: number[], setQty: (q: number[]) => void, notify: (m: string) => void, profile: UserProfile) { if (screen === 'Orders') return <Orders qty={qty} setQty={setQty} notify={notify} profile={profile} />; if (screen === 'Confirmed') return <Confirmed />; if (screen === 'Deferral') return <Deferral profile={profile} />; if (screen === 'Receipt') return <Receipt profile={profile} notify={notify} />; if (screen === 'Queue') return <Queue />; if (screen === 'Allocate') return <Allocate notify={notify} />; if (screen === 'Board') return <Board />; if (screen === 'Capacity') return <Capacity />; if (screen === 'Load list') return <LoadList notify={notify} />; if (screen === 'Shortfall') return <Shortfall notify={notify} />; return <PlanChanged notify={notify} />; }
function Orders({ qty, setQty, notify, profile }: { qty: number[]; setQty: (q: number[]) => void; notify: (m: string) => void; profile: UserProfile }) { const total = items.reduce((sum, item, i) => sum + item.price * qty[i], 0); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const placeOrder = async () => { if (!profile.outlet_id) { setError('Your account has no outlet assigned.'); return; } setBusy(true); setError(''); try { const order = await createOrder({ outlet_id: profile.outlet_id, brand: 'Fresh', requested_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10), temp_requirement: 'chilled', items: items.map((item, i) => ({ sku: item.sku, description: item.name, quantity: qty[i], weight_kg: 1, volume_m3: 0.01, temp_requirement: 'ambient' })) }); await submitOrder(order.id); notify('Order submitted to dispatch'); } catch (e) { setError(e instanceof Error ? e.message : 'Order submission failed.'); } finally { setBusy(false); } }; return <><div className="banner warning">◷ Order cutoff in <b>1h 24m</b> · Fresh orders close at 4:00 PM for next-morning delivery</div>{error && <div className="banner critical">{error}</div>}<div className="section-head"><div><span className="overline">{profile.outlet_id ?? 'ASSIGNED OUTLET'}</span><h2>Prepare tomorrow's Fresh order</h2></div><Status>{busy ? 'Saving…' : 'Ready'}</Status></div><Panel><div className="table-head"><span>Product</span><span>Unit price</span><span>Quantity</span><span>Subtotal</span></div>{items.map((item, i) => <div className="product-row" key={item.sku}><div><b>{item.name}</b><small>{item.sku}</small></div><span>Rs. {item.price}</span><div className="stepper"><button onClick={() => setQty(qty.map((v, j) => j === i ? Math.max(0, v - 1) : v))}>−</button><b>{qty[i]}</b><button onClick={() => setQty(qty.map((v, j) => j === i ? v + 1 : v))}>+</button></div><strong>Rs. {(item.price * qty[i]).toLocaleString()}</strong></div>)}<div className="total"><span>Order total</span><strong>Rs. {total.toLocaleString()}</strong></div></Panel><div className="action-row"><button className="secondary" onClick={() => notify('Draft changes are local until submitted')}>Save draft</button><button className="primary" disabled={busy} onClick={placeOrder}>{busy ? 'Submitting…' : 'Submit order'} <span>→</span></button></div></> }
function Confirmed() { return <div className="narrow"><div className="success-block"><div className="check">✓</div><div><Status>Confirmed</Status><h2>Order is on its way into planning</h2><p>We will notify you if anything changes before delivery.</p></div></div><Panel><div className="meta-grid"><div><small>Reference</small><b>WPF-2026-08741</b></div><div><small>Estimated arrival</small><b>Tomorrow · 05:30–07:45 AM</b></div><div><small>Brand</small><b>Waypoint Fresh</b></div><div><small>Placed at</small><b>Today, 3:12 PM</b></div></div></Panel><Panel><h3>Items ordered</h3>{items.map(i => <div className="line" key={i.sku}><span>{i.name}</span><b>×{i.qty}</b></div>)}</Panel></div> }
function Deferral({ profile }: { profile: UserProfile }) { const [orders, setOrders] = useState<Array<{ id: string; status: string; requested_date: string; notes: string | null }>>([]); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); useEffect(() => { if (!profile.outlet_id) { setState('empty'); return; } listOrders(`?status=deferred&limit=100`).then(result => { setOrders(result.data); setState(result.data.length ? 'success' : 'empty'); }).catch(() => setState('error')); }, [profile.outlet_id]); return <div className="narrow">{state === 'loading' && <Panel>Loading deferred orders…</Panel>}{state === 'error' && <Panel><p className="error-text">Unable to load deferred orders.</p></Panel>}{state === 'empty' && <Panel><h3>No deferred deliveries</h3><p className="muted">Your outlet has no backend orders currently marked deferred.</p></Panel>}{state === 'success' && <>{orders.map(order => <div className="warning-block" key={order.id}><div className="alert-icon">!</div><div><Status tone="amber">Deferred</Status><h2>Delivery {order.id.slice(0, 8)} was deferred</h2><p>{order.notes || 'Available delivery capacity was insufficient for the requested run.'}</p><small>Requested date · {order.requested_date}</small></div></div>)}<Panel><h3>What this means for your store</h3><ul className="clean-list"><li>Deferred items will not arrive on the original run.</li><li>The backend will assign the order to a later feasible plan.</li><li>Check the order status for the next confirmed delivery window.</li></ul></Panel></>}</div> }
function Receipt({ profile, notify }: { profile: UserProfile; notify: (m: string) => void }) { const [deliveries, setDeliveries] = useState<Array<{ id: string; outcome: string; trip_stop_id: string; delivered_at: string | null }>>([]); const [selected, setSelected] = useState(''); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); const load = () => profile.outlet_id ? listOutletDeliveries(profile.outlet_id).then(result => { const delivered = result.filter(item => item.outcome === 'delivered'); setDeliveries(delivered); setSelected(delivered[0]?.id ?? ''); setState(delivered.length ? 'success' : 'empty'); }).catch(() => setState('error')) : Promise.resolve(setState('empty')); useEffect(() => { void load(); }, [profile.outlet_id]); const confirm = async () => { if (!selected) return; try { await confirmReceipt(selected, { items_received: {}, issues_noted: 'Confirmed from Waypoint receipt screen.' }); notify('Receipt confirmed by backend'); await load(); } catch (e) { notify(e instanceof Error ? e.message : 'Receipt confirmation failed'); } }; return <><div className="banner warning">Confirm only after the backend delivery record is visible.</div>{state === 'loading' && <Panel>Loading delivery records…</Panel>}{state === 'error' && <Panel><p className="error-text">Unable to load deliveries.</p><button className="secondary" onClick={() => void load()}>Retry</button></Panel>}{state === 'empty' && <Panel>No delivered records are ready for receipt confirmation.</Panel>}{state === 'success' && <><div className="section-head"><div><span className="overline">{profile.outlet_id}</span><h2>Confirm delivery receipt</h2></div><Status>{deliveries.length} delivered</Status></div><Panel><label>Delivery<select value={selected} onChange={e => setSelected(e.target.value)}>{deliveries.map(delivery => <option key={delivery.id} value={delivery.id}>{delivery.id} · {delivery.delivered_at || 'time unavailable'}</option>)}</select></label><p className="muted">Items received are submitted to the backend with this receipt.</p></Panel><button className="primary" onClick={() => void confirm()}>Confirm receipt <span>→</span></button></>}</> }
function Queue() { const [rows, setRows] = useState<Array<{ id: string; brand: string; total_weight_kg: number; total_volume_m3: number; status: string; outlet_id: string }>>([]); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); const [error, setError] = useState(''); const load = async () => { setState('loading'); try { const result = await listOrders('?limit=100'); setRows(result.data); setState(result.data.length ? 'success' : 'empty'); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load orders.'); setState('error'); } }; useEffect(() => { void load(); }, []); return <><div className="kpi-grid"><Kpi label="Open orders" value={state === 'success' ? String(rows.filter(r => !['confirmed', 'delivered'].includes(r.status)).length) : '—'} sub="From backend" /><Kpi label="Submitted" value={state === 'success' ? String(rows.filter(r => r.status === 'submitted').length) : '—'} sub="Ready to plan" /><Kpi label="Allocated" value={state === 'success' ? String(rows.filter(r => r.status === 'allocated').length) : '—'} sub="Assigned to trips" /><Kpi label="Deferred" value={state === 'success' ? String(rows.filter(r => r.status === 'deferred').length) : '—'} sub="Needs attention" tone="amber" /></div>{state === 'loading' && <Panel>Loading orders…</Panel>}{state === 'error' && <Panel><p className="error-text">{error}</p><button className="secondary" onClick={() => void load()}>Retry</button></Panel>}{state === 'empty' && <Panel>No orders found.</Panel>}{state === 'success' && <Panel className="table-panel"><div className="table-head queue-grid"><span>Order</span><span>Brand</span><span>Weight / volume</span><span>Date</span><span>Status</span></div>{rows.map(row => <div className="table-row queue-grid" key={row.id}><div><b>{row.outlet_id}</b><small>{row.id}</small></div><Status>{row.brand}</Status><span>{row.total_weight_kg} kg / {row.total_volume_m3} m³</span><span>{row.status}</span><Status tone={row.status === 'deferred' ? 'amber' : row.status === 'submitted' ? 'blue' : 'green'}>{row.status}</Status></div>)}</Panel>}</> }
function Allocate({ notify }: { notify: (m: string) => void }) { const [depot, setDepot] = useState<'Peliyagoda' | 'Kandy'>('Peliyagoda'); const [planDate, setPlanDate] = useState(new Date(Date.now() + 86400000).toISOString().slice(0, 10)); const [plan, setPlan] = useState<Awaited<ReturnType<typeof generatePlan>> | null>(null); const [state, setState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle'); const [error, setError] = useState(''); const run = async () => { setState('loading'); setError(''); try { const result = await generatePlan({ plan_date: planDate, depot, dry_run: false }); setPlan(result); setState('success'); notify('Plan generated from backend'); } catch (e) { setError(e instanceof Error ? e.message : 'Plan generation failed.'); setState('error'); } }; return <><div className="banner warning">The allocation engine owns capacity, temperature, window, depot, trip, and fuel constraints.</div><div className="section-head"><div><span className="overline">DISPATCH PLAN</span><h2>Generate a constraint-aware plan</h2></div><div className="action-row"><select value={depot} onChange={e => setDepot(e.target.value as 'Peliyagoda' | 'Kandy')}><option>Peliyagoda</option><option>Kandy</option></select><input type="date" value={planDate} onChange={e => setPlanDate(e.target.value)} /><button className="primary" disabled={state === 'loading'} onClick={() => void run()}>{state === 'loading' ? 'Generating…' : 'Generate plan'} <span>→</span></button></div></div>{state === 'error' && <Panel><p className="error-text">{error}</p><button className="secondary" onClick={() => void run()}>Retry</button></Panel>}{state === 'idle' && <Panel>Choose a depot and date, then generate a plan from the backend.</Panel>}{plan && <><div className="kpi-grid"><Kpi label="Total orders" value={String(plan.metrics.total_orders)} sub="Submitted for date" /><Kpi label="Served" value={String(plan.metrics.served_orders)} sub="Allocated" /><Kpi label="Deferred" value={String(plan.metrics.deferred_orders)} sub="Backend reason recorded" tone="amber" /><Kpi label="Trips" value={String(plan.metrics.trips_created)} sub="Vehicles used" /></div><Panel><h3>Generated trips</h3>{plan.trips.map(trip => <div className="line" key={`${trip.vehicle_id}-${trip.trip_number}`}><span><b>{trip.vehicle_id}</b><small>{trip.brand} · {trip.district} · {trip.orders.length} orders</small></span><span>{trip.total_weight_kg} kg · {trip.estimated_distance_km} km · {trip.estimated_duration_min} min</span></div>)}</Panel><Panel><h3>Deferred orders and reasons</h3>{plan.deferred_orders.length === 0 ? <p>No deferred orders.</p> : plan.deferred_orders.map(order => <div className="line" key={order.order_id}><span><b>{order.order_id}</b><small>{order.reason_detail}</small></span><Status tone="amber">{order.reason_code}</Status></div>)}</Panel></>}</> }
function Board() { const [trips, setTrips] = useState<Array<{ id: string; vehicle_id: string; brand: string; district: string; status: string; total_weight_kg: number; total_volume_m3: number }>>([]); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); const [error, setError] = useState(''); const load = async () => { setState('loading'); try { const result = await listTrips('?limit=100'); setTrips(result.data); setState(result.data.length ? 'success' : 'empty'); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load trips.'); setState('error'); } }; useEffect(() => { void load(); }, []); return <><div className="kpi-grid"><Kpi label="Trips" value={state === 'success' ? String(trips.length) : '—'} sub="From backend" /><Kpi label="Planned" value={state === 'success' ? String(trips.filter(t => t.status === 'planned').length) : '—'} sub="Awaiting departure" /><Kpi label="In transit" value={state === 'success' ? String(trips.filter(t => ['departed', 'in_transit'].includes(t.status)).length) : '—'} sub="Active routes" /><Kpi label="Completed" value={state === 'success' ? String(trips.filter(t => t.status === 'completed').length) : '—'} sub="Closed trips" tone="slate" /></div>{state === 'loading' && <Panel>Loading trips…</Panel>}{state === 'error' && <Panel><p className="error-text">{error}</p><button className="secondary" onClick={() => void load()}>Retry</button></Panel>}{state === 'empty' && <Panel>No trips found.</Panel>}{state === 'success' && <Panel className="table-panel"><div className="table-head board-grid"><span>Vehicle</span><span>Brand / district</span><span>Capacity</span><span>Status</span><span>Trip</span></div>{trips.map(trip => <div className="table-row board-grid" key={trip.id}><b className="mono">{trip.vehicle_id}</b><span>{trip.brand} · {trip.district}</span><span>{trip.total_weight_kg} kg / {trip.total_volume_m3} m³</span><span>{trip.status}</span><Status tone={trip.status === 'completed' ? 'green' : trip.status === 'deferred' ? 'amber' : 'blue'}>{trip.status}</Status></div>)}</Panel>}</> }
function Capacity() { const [rows, setRows] = useState<Awaited<ReturnType<typeof getCapacityOutlook>>>([]); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); useEffect(() => { getCapacityOutlook(new Date().toISOString().slice(0, 10)).then(result => { setRows(result); setState(result.length ? 'success' : 'empty'); }).catch(() => setState('error')); }, []); return <><div className="section-head"><div><span className="overline">BACKEND CAPACITY OUTLOOK</span><h2>Demand against available fleet</h2></div></div>{state === 'loading' && <Panel>Loading capacity outlook…</Panel>}{state === 'error' && <Panel><p className="error-text">Unable to load capacity outlook.</p></Panel>}{state === 'empty' && <Panel>No capacity outlook data is available.</Panel>}{state === 'success' && <Panel><div className="capacity-list">{rows.map(row => <div className="forecast" key={row.date}><b>{row.date}</b><span>{row.order_count} orders · {row.demand_weight_kg} kg demand</span><strong className={row.capacity_gap_kg ? 'red' : 'green'}>{row.capacity_gap_kg ? `${row.capacity_gap_kg} kg shortage` : 'No gap'}</strong><Status tone={row.capacity_gap_kg ? 'amber' : 'green'}>{row.vehicle_count} vehicles · {row.reefer_count} reefer</Status></div>)}</div></Panel>}</> }
function LoadList({ notify }: { notify: (m: string) => void }) { const [trip, setTrip] = useState<Awaited<ReturnType<typeof getTrip>> | null>(null); const [state, setState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading'); const [error, setError] = useState(''); useEffect(() => { listTrips('?status=planned&limit=1').then(result => result.data[0] ? getTrip(result.data[0].id).then(value => { localStorage.setItem('waypoint.loader.trip-id', value.id); if (value.stops[0]) localStorage.setItem('waypoint.loader.stop-id', value.stops[0].id); setTrip(value); setState('success'); }) : setState('empty')).catch(e => { setError(e instanceof Error ? e.message : 'Unable to load trip.'); setState('error'); }); }, []); const acknowledge = async () => { if (!trip) return; try { await acknowledgeTrip(trip.id, 'loader'); setTrip({ ...trip, loader_acknowledged: true }); notify('Trip acknowledged'); } catch (e) { notify(e instanceof Error ? e.message : 'Acknowledge failed'); } }; if (state === 'loading') return <Panel>Loading assigned trip…</Panel>; if (state === 'error') return <Panel><p className="error-text">{error}</p></Panel>; if (state === 'empty' || !trip) return <Panel>No confirmed trip is assigned to this depot.</Panel>; const orderedStops = [...trip.stops].sort((a, b) => a.load_position - b.load_position); return <><div className="dark-banner"><div><span className="overline">VEHICLE · {trip.vehicle_id} · {trip.depot}</span><h2>Load in reverse-unload order</h2><p>Backend-provided load positions are shown below.</p></div><Status tone={trip.loader_acknowledged ? 'green' : 'amber'}>{trip.loader_acknowledged ? 'Acknowledged' : 'Review required'}</Status></div>{orderedStops.map(stop => <SwipeToAction key={stop.id} onSwipeRight={() => setTrip({ ...trip, stops: trip.stops.map(s => s.id === stop.id ? { ...s, status: 'loaded' } : s) })}><Panel className={`stop-card ${stop.status === 'loaded' ? 'loaded' : stop.status === 'shortfall' ? 'shortfall' : ''}`}><div className="stop-number">{stop.status === 'loaded' ? '✓' : stop.status === 'shortfall' ? '!' : stop.load_position}</div><div className="stop-copy"><div className="card-line"><div><b>Outlet {stop.outlet_id}</b><small>Load position {stop.load_position} · Delivery stop {stop.sequence_number}</small></div><Status tone={stop.status === 'shortfall' ? 'amber' : 'blue'}>{stop.status}</Status></div><p>Order {stop.order_id} · Planned arrival {stop.planned_arrival_time ?? 'Not scheduled'}</p></div></Panel></SwipeToAction>)}<div className="action-row"><button className="secondary" onClick={() => notify('Open Flag shortfall after selecting the affected backend stop')}>Flag shortfall</button><button className="primary" disabled={trip.loader_acknowledged} onClick={() => void acknowledge()}>{trip.loader_acknowledged ? 'Acknowledged' : 'Acknowledge trip'} <span>→</span></button></div></> }
function Shortfall({ notify }: { notify: (m: string) => void }) {
  const EXPECTED = 12;
  type IssueType = 'missing' | 'damaged' | 'wrong_item';
  const issueOptions: { type: IssueType; icon: string; label: string; sub: string }[] = [
    { type: 'missing',    icon: '▣', label: 'Missing',    sub: 'Stock not available' },
    { type: 'damaged',    icon: '▧', label: 'Damaged',    sub: 'Cannot dispatch'     },
    { type: 'wrong_item', icon: '△', label: 'Wrong item', sub: 'Incorrect SKU'       },
  ];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [issueType, setIssueType] = useState<IssueType>('missing');
  const [affectedQty, setAffectedQty] = useState(6);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const handlePhoto = (e: { target: HTMLInputElement }) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => setPhotoPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  };
  const actualQty = EXPECTED - affectedQty;
  const issueLabel = issueOptions.find(o => o.type === issueType)?.label ?? 'Missing';
  const unitLabel = issueType === 'wrong_item' ? 'Wrong units' : issueType === 'damaged' ? 'Damaged units' : 'Units missing';
  const submit = async () => {
    const tripId = localStorage.getItem('waypoint.loader.trip-id');
    const stopId  = localStorage.getItem('waypoint.loader.stop-id');
    if (!tripId || !stopId) { setError('Open a backend trip before recording a shortfall.'); return; }
    if (affectedQty < 1) { setError('Affected quantity must be at least 1.'); return; }
    setBusy(true); setError('');
    try {
      await recordShortfall(tripId, stopId, {
        issue_type: issueType,
        sku: 'FRESH-MLK-001',
        description: 'Anchor Full Cream Milk 1L',
        expected_quantity: EXPECTED,
        actual_quantity: issueType === 'wrong_item' ? (EXPECTED - affectedQty) : actualQty,
        notes: notes || undefined,
      });
      notify(`${issueLabel} recorded — ${affectedQty} unit${affectedQty !== 1 ? 's' : ''}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Shortfall could not be recorded.');
    } finally { setBusy(false); }
  };
  return <div className="narrow">
    <div className="banner warning">Record the affected quantity before the vehicle leaves.</div>
    {error && <div className="banner critical">{error}</div>}

    {/* Step 1 */}
    <Panel>
      <span className="overline">STEP 1 · ISSUE TYPE</span>
      <div className="choice-grid">
        {issueOptions.map(o => (
          <button key={o.type} className={issueType === o.type ? 'selected' : ''} onClick={() => setIssueType(o.type)}>
            {o.icon}<b>{o.label}</b><small>{o.sub}</small>
          </button>
        ))}
      </div>
    </Panel>

    {/* Step 2 */}
    <Panel>
      <span className="overline">STEP 2 · AFFECTED ITEM</span>
      <h3>Anchor Full Cream Milk 1L</h3>
      <p className="muted">Expected {EXPECTED} units · {issueType !== 'wrong_item' ? `Received ${actualQty} units · ` : ''}Gampola stop</p>
      <div className="quantity" style={{ alignItems: 'center', gap: 12 }}>
        <span>{unitLabel}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="secondary" style={{ width: 36, height: 36, padding: 0, fontSize: 20, lineHeight: 1 }}
            onClick={() => setAffectedQty(q => Math.max(1, q - 1))}>−</button>
          <b style={{ minWidth: 28, textAlign: 'center', fontSize: 20 }}>{affectedQty}</b>
          <button className="secondary" style={{ width: 36, height: 36, padding: 0, fontSize: 20, lineHeight: 1 }}
            onClick={() => setAffectedQty(q => Math.min(EXPECTED, q + 1))}>+</button>
        </div>
      </div>
    </Panel>

    {/* Evidence */}
    <Panel>
      <span className="overline">EVIDENCE</span>
      <input ref={fileInputRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={handlePhoto} />
      {photoPreview
        ? <div className="photo photo-preview" onClick={() => fileInputRef.current?.click()} style={{ cursor: 'pointer', padding: 0, overflow: 'hidden' }}>
            <img src={photoPreview} alt="Evidence" style={{ width: '100%', maxHeight: 200, objectFit: 'cover', borderRadius: 8 }} />
            <span style={{ display: 'block', textAlign: 'center', padding: '6px 0', fontSize: 12, color: 'var(--muted)' }}>Tap to change photo</span>
          </div>
        : <div className="photo" style={{ cursor: 'pointer' }} onClick={() => fileInputRef.current?.click()}>⌾<span>Attach photo of empty crate / shelf</span></div>
      }
      <textarea placeholder="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)} />
    </Panel>

    <button className="primary full" disabled={busy} onClick={() => void submit()}>
      {busy ? 'Recording…' : `Confirm ${issueLabel.toLowerCase()} · ${affectedQty} unit${affectedQty !== 1 ? 's' : ''}`}
    </button>
  </div>;
}
function PlanChanged({ notify }: { notify: (m: string) => void }) { return <div className="narrow"><div className="critical-block"><Status tone="red">Plan changed</Status><h2>The load list has changed</h2><p>Dispatcher Perera added Midlands Supermart — Gampola before departure. Re-verify your load.</p></div><Panel><div className="meta-grid"><div><small>What</small><b>New stop added · Gampola</b></div><div><small>When</small><b>06:42 AM today</b></div><div><small>Who</small><b>Dispatcher Perera</b></div><div><small>Action</small><b>Load position 2</b></div></div></Panel><Panel className="highlight-panel"><Status tone="amber">New stop</Status><h3>Midlands Supermart — Gampola</h3><p>Anchor Milk × 12 · Maliban Crackers × 6 · Basmati × 4 · Ginger Beer × 8</p></Panel><button className="primary full" onClick={() => notify('Updated load list acknowledged')}>Acknowledge & continue</button></div> }
export default function App() { const [profile, setProfile] = useState<UserProfile | null>(null); const [loading, setLoading] = useState(true); useEffect(() => { const client = supabase; if (!client) { setLoading(false); return; } const load = async () => { try { const session = (await client.auth.getSession()).data.session; if (session) setProfile(await getCurrentUser()); } finally { setLoading(false); } }; void load(); const { data } = client.auth.onAuthStateChange((_event, session) => { if (!session) setProfile(null); }); return () => data.subscription.unsubscribe(); }, []); if (loading) return <div className="loading-screen">Loading your Waypoint session…</div>; if (!profile) return <Auth onSignedIn={setProfile} />; return <Shell role={displayRole(profile.role)} profile={profile} onSignOut={async () => { await signOut(); setProfile(null); }} />; }
