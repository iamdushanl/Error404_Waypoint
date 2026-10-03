import { useEffect, useState } from 'react';
import { SwipeToAction } from './components/SwipeToAction';
import { supabase } from './supabaseClient';

type Role = 'Store Manager' | 'Dispatcher' | 'Loader';
type Screen = 'Orders' | 'Confirmed' | 'Deferral' | 'Receipt' | 'Queue' | 'Allocate' | 'Board' | 'Capacity' | 'Load list' | 'Shortfall' | 'Plan changed';
const items = [{ name: 'Anchor Full Cream Milk 1L', sku: 'FRESH-MLK-001', price: 285, qty: 12 }, { name: 'Maliban Cream Cracker 200g', sku: 'FRESH-BSC-014', price: 120, qty: 6 }, { name: 'Basmati Rice 1kg', sku: 'FRESH-RCE-009', price: 490, qty: 4 }, { name: 'Elephant House Ginger Beer 400ml', sku: 'FRESH-BEV-033', price: 95, qty: 8 }, { name: 'Dil Foods Coconut Milk 400ml', sku: 'FRESH-CKG-007', price: 210, qty: 3 }];
const stops = ['Highland Mart — Kandy', 'Green Valley Store — Peradeniya', 'Midlands Supermart — Gampola', 'North Central Mart — Kurunegala'];
const roleScreens: Record<Role, Screen[]> = { 'Store Manager': ['Orders', 'Confirmed', 'Deferral', 'Receipt'], Dispatcher: ['Queue', 'Allocate', 'Board', 'Capacity'], Loader: ['Load list', 'Shortfall', 'Plan changed'] };

const LOADER_PIN = '1234';

function LoaderPinScreen({ onSuccess, onBack }: { onSuccess: () => void; onBack: () => void }) {
  const [pin, setPin] = useState('');
  const [shake, setShake] = useState(false);
  const [error, setError] = useState('');

  const handleKey = (k: string) => {
    if (pin.length >= 4) return;
    const next = pin + k;
    setPin(next);
    setError('');
    if (next.length === 4) {
      if (next === LOADER_PIN) {
        onSuccess();
      } else {
        setShake(true);
        setError('Incorrect PIN. Try again.');
        setTimeout(() => { setPin(''); setShake(false); }, 600);
      }
    }
  };

  const handleDelete = () => { setPin(p => p.slice(0, -1)); setError(''); };

  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '⌫'];

  return (
    <main className="auth">
      <div className="auth-art">
        <div className="brand-mark">W</div>
        <p className="eyebrow">WAYPOINT FRESH</p>
        <h1>Loader<br /><em>access only.</em></h1>
        <p className="muted light">Enter your 4-digit PIN to access the loader dashboard.</p>
        <div className="route-art"><span>DC</span><i /><span>01</span><i /><span>02</span><i /><span>03</span></div>
      </div>
      <section className="auth-card">
        <button className="pin-back" onClick={onBack}>← Back</button>
        <p className="eyebrow">LOADER VERIFICATION</p>
        <h2>Enter your PIN</h2>
        <p className="muted">Demo PIN is <strong>1234</strong></p>
        <div className={`pin-dots ${shake ? 'pin-shake' : ''}`}>
          {[0, 1, 2, 3].map(i => <div key={i} className={`pin-dot ${pin.length > i ? 'filled' : ''}`} />)}
        </div>
        {error && <p className="pin-error">{error}</p>}
        <div className="pin-pad">
          {keys.map((k, i) => k === '' ? <div key={i} /> : (
            <button
              key={i}
              className={`pin-key ${k === '⌫' ? 'pin-del' : ''}`}
              onClick={() => k === '⌫' ? handleDelete() : handleKey(k)}
              disabled={k !== '⌫' && pin.length >= 4}
            >{k}</button>
          ))}
        </div>
        <small className="muted">Backend-ready boundary: replace LOADER_PIN with a server-side PIN verification.</small>
      </section>
    </main>
  );
}

function Auth({ onSignIn }: { onSignIn: (role: Role, userId: string) => void }) {
  const [role, setRole] = useState<Role>('Store Manager');
  const [showPin, setShowPin] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSignIn = async () => {
    if (role === 'Loader') { setShowPin(true); return; }
    
    setIsLoading(true);
    let email = 'manager@waypoint.demo';
    if (role === 'Dispatcher') email = 'dispatcher@waypoint.demo';
    
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password: 'WaypointDemo2026!'
      });
      if (error) throw error;
      if (data.user) {
        onSignIn(role, data.user.id);
      }
    } catch (err) {
      console.error(err);
      alert('Login failed. Did you seed the database?');
    } finally {
      setIsLoading(false);
    }
  };

  if (showPin) return <LoaderPinScreen onSuccess={() => onSignIn('Loader', 'loader-mock-id')} onBack={() => setShowPin(false)} />;

  return <main className="auth"><div className="auth-art"><div className="brand-mark">W</div><p className="eyebrow">WAYPOINT FRESH</p><h1>Move the morning<br /><em>with confidence.</em></h1><p className="muted light">One operational rhythm from outlet order to confirmed receipt.</p><div className="route-art"><span>DC</span><i /><span>01</span><i /><span>02</span><i /><span>03</span></div></div><section className="auth-card"><p className="eyebrow">CONTROL TOWER</p><h2>Sign in (Supabase Connected)</h2><p className="muted">Select a role to sign in automatically with your seeded demo credentials.</p><label>Preview role<select value={role} onChange={e => setRole(e.target.value as Role)}>{Object.keys(roleScreens).map(r => <option key={r}>{r}</option>)}</select></label><button className="primary full" onClick={handleSignIn} disabled={isLoading}>{isLoading ? 'Signing in...' : 'Sign in as ' + role + ' <span>→</span>'}</button></section></main>;
}

function Shell({ role, userId, onSignOut }: { role: Role; userId: string; onSignOut: () => void }) { const [screen, setScreen] = useState<Screen>(roleScreens[role][0]); const [toast, setToast] = useState(''); const [qty, setQty] = useState(items.map(x => x.qty)); const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2400); }; useEffect(() => setScreen(roleScreens[role][0]), [role]); return <div className="app-shell"><aside><div className="side-brand"><div className="brand-mark small">W</div><span>WAYPOINT</span></div><div className="workspace"><span className="dot" />Fresh network<strong>{role}</strong></div><nav>{roleScreens[role].map(item => <button className={item === screen ? 'active' : ''} key={item} onClick={() => setScreen(item)}><span className="nav-icon">{icon(item)}</span>{label(item)}</button>)}</nav><div className="side-bottom"><div className="network"><span className="dot" />All systems operational</div><button className="profile" onClick={onSignOut}><span className="avatar">{role[0]}</span><span><b>{role === 'Dispatcher' ? 'Perera, D.' : role}</b><small>Sign out</small></span><span>↗</span></button></div></aside><section className="main"><header><div><p className="eyebrow">{role.toUpperCase()} / TUESDAY 14 JANUARY 2026</p><h1>{title(screen)}</h1></div><div className="header-actions"><span className="live"><i />Live workspace</span><button className="icon-button" onClick={() => notify('Notifications are clear')}>♡</button></div></header><div className="content">{screenView(screen, qty, setQty, notify, userId)}</div>{toast && <div className="toast">✓ {toast}</div>}</section></div> }
function icon(s: Screen) { return ({ Orders: '＋', Confirmed: '✓', Deferral: '!', Receipt: '□', Queue: '≡', Allocate: '◈', Board: '◉', Capacity: '⌁', 'Load list': '▤', Shortfall: '△', 'Plan changed': '↻' } as Record<Screen, string>)[s]; }
function label(s: Screen) { return ({ Orders: 'Place order', Confirmed: 'Confirmed order', Deferral: 'Deferral notice', Receipt: 'Confirm receipt', Queue: 'Order queue', Allocate: 'Plan & allocate', Board: 'Live delivery board', Capacity: 'Capacity outlook', 'Load list': 'Load list', Shortfall: 'Flag shortfall', 'Plan changed': 'Plan changed' } as Record<Screen, string>)[s]; }
function title(s: Screen) { return label(s); }
function Kpi({ label, value, sub, tone = '' }: { label: string; value: string; sub: string; tone?: string }) { return <div className="kpi"><span>{label}</span><strong className={tone}>{value}</strong><small>{sub}</small></div> }
function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) { return <div className={`panel ${className}`}>{children}</div> }
function Status({ children, tone = 'green' }: { children: React.ReactNode; tone?: string }) { return <span className={`status ${tone}`}>{children}</span> }
function screenView(screen: Screen, qty: number[], setQty: (q: number[]) => void, notify: (m: string) => void, userId: string) { if (screen === 'Orders') return <Orders qty={qty} setQty={setQty} notify={notify} userId={userId} />; if (screen === 'Confirmed') return <Confirmed />; if (screen === 'Deferral') return <Deferral notify={notify} />; if (screen === 'Receipt') return <Receipt notify={notify} />; if (screen === 'Queue') return <Queue />; if (screen === 'Allocate') return <Allocate notify={notify} />; if (screen === 'Board') return <Board />; if (screen === 'Capacity') return <Capacity />; if (screen === 'Load list') return <LoadList notify={notify} />; if (screen === 'Shortfall') return <Shortfall notify={notify} />; return <PlanChanged notify={notify} />; }
// TODO: Replace mock state with Supabase fetch once backend is connected.
const MOCK_CATALOG = [
  { id: '1', sku: 'FRESH-MLK-001', name: 'Anchor Full Cream Milk 1L', price: 285 },
  { id: '2', sku: 'FRESH-BSC-014', name: 'Maliban Cream Cracker 200g', price: 120 },
  { id: '3', sku: 'FRESH-RCE-009', name: 'Basmati Rice 1kg', price: 490 },
  { id: '4', sku: 'FRESH-BEV-033', name: 'Elephant House Ginger Beer 400ml', price: 95 },
  { id: '5', sku: 'FRESH-CKG-007', name: 'Dil Foods Coconut Milk 400ml', price: 210 },
  { id: '6', sku: 'FRESH-TEA-002', name: 'Dilmah Ceylon Tea 400g', price: 1100 }
];

type OrderItem = typeof MOCK_CATALOG[0] & { qty: number };

function Orders({ notify, qty, setQty, userId }: { notify: (m: string) => void; qty?: number[]; setQty?: (q: number[]) => void; userId: string }) {
  // TODO: Replace mock state with Supabase fetch once backend is connected.
  const [activeOrderItems, setActiveOrderItems] = useState<OrderItem[]>(() => {
    try {
      const saved = localStorage.getItem('waypoint-draft-items');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem('waypoint-draft-items', JSON.stringify(activeOrderItems));
  }, [activeOrderItems]);

  const [showCatalog, setShowCatalog] = useState(false);
  const [search, setSearch] = useState('');

  const total = activeOrderItems.reduce((sum, item) => sum + item.price * item.qty, 0);

  const handleAddItem = (product: typeof MOCK_CATALOG[0]) => {
    setActiveOrderItems(prev => {
      const existing = prev.find(item => item.id === product.id);
      if (existing) {
        return prev.map(item => item.id === product.id ? { ...item, qty: item.qty + 1 } : item);
      }
      return [...prev, { ...product, qty: 1 }];
    });
    setShowCatalog(false);
    setSearch('');
  };

  const updateQty = (id: string, delta: number) => {
    setActiveOrderItems(prev => prev.map(item => {
      if (item.id === id) {
        return { ...item, qty: Math.max(0, item.qty + delta) };
      }
      return item;
    }));
  };

  const handleSaveDraft = async () => {
    if (activeOrderItems.length === 0) {
      notify('Order is empty');
      return;
    }
    
    notify('Saving draft to database...');
    
    // 1. Create order
    const { data: orderData, error: orderError } = await supabase.from('orders').insert({
      outlet_id: 'OUT001', // Harcoded for demo
      brand: 'Fresh',
      requested_date: new Date().toISOString().split('T')[0],
      status: 'draft',
      temp_requirement: 'ambient',
      total_weight_kg: 0,
      total_volume_m3: 0,
      created_by: userId
    }).select().single();

    if (orderError || !orderData) {
      console.error(orderError);
      notify('Failed to save draft order');
      return;
    }

    // 2. Add items
    const insertItems = activeOrderItems.filter(i => i.qty > 0).map(item => ({
      order_id: orderData.id,
      sku: item.sku,
      description: item.name,
      quantity: item.qty,
      weight_kg: 1, 
      volume_m3: 0.1, 
      temp_requirement: 'ambient'
    }));
    
    if (insertItems.length > 0) {
      const { error: itemsError } = await supabase.from('order_items').insert(insertItems);
      if (itemsError) {
        console.error(itemsError);
        notify('Failed to save draft items');
        return;
      }
    }

    notify('Draft saved to database successfully!');
    setActiveOrderItems([]); 
  };

  const filteredCatalog = MOCK_CATALOG.filter(item =>
    item.name.toLowerCase().includes(search.toLowerCase()) ||
    item.sku.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <div className="banner warning">◷ Order cutoff in <b>1h 24m</b> · Fresh orders close at 4:00 PM for next-morning delivery</div>
      <div className="section-head">
        <div>
          <span className="overline">MIDLANDS SUPERMART · GAMPOLA</span>
          <h2>Prepare tomorrow's Fresh order</h2>
        </div>
        <Status>Draft</Status>
      </div>
      <Panel>
        <div style={{ position: 'relative', marginBottom: '24px', paddingLeft: '8px' }}>
          <button
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: '#065F46',
              fontWeight: 600,
              fontSize: '13px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              textAlign: 'left',
              lineHeight: 1.2,
              letterSpacing: '0.02em'
            }}
            onClick={() => setShowCatalog(!showCatalog)}
          >
            <span style={{ fontSize: '18px', fontWeight: 400 }}>+</span>
            <span>Add Item</span>
          </button>
          {showCatalog && (
            <div style={{ position: 'absolute', top: '40px', left: 0, background: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', padding: '12px', zIndex: 10, width: '320px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search products..."
                style={{ padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '4px', outline: 'none', fontSize: '14px', boxSizing: 'border-box', width: '100%' }}
              />
              <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {filteredCatalog.map(product => (
                  <div
                    key={product.id}
                    onClick={() => handleAddItem(product)}
                    style={{ padding: '8px', cursor: 'pointer', borderRadius: '4px', display: 'flex', flexDirection: 'column' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <b style={{ fontSize: '14px', color: '#0f172a' }}>{product.name}</b>
                    <small style={{ fontSize: '12px', color: '#64748b' }}>{product.sku} · Rs. {product.price}</small>
                  </div>
                ))}
                {filteredCatalog.length === 0 && <div style={{ padding: '8px', fontSize: '13px', color: '#64748b' }}>No products found.</div>}
              </div>
            </div>
          )}
        </div>
        <div className="table-head">
          <span>Product</span>
          <span>Unit price</span>
          <span>Quantity</span>
          <span>Subtotal</span>
        </div>
        {activeOrderItems.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
            No items added to the draft yet. Click "Add Item" to start.
          </div>
        ) : (
          activeOrderItems.map(item => (
            <div className="product-row" key={item.sku}>
              <div>
                <b>{item.name}</b>
                <small>{item.sku}</small>
              </div>
              <span>Rs. {item.price}</span>
              <div className="stepper">

                <button onClick={() => updateQty(item.id, -1)}>-</button>
                <input
                  type="text"
                  inputMode="numeric"
                  value={item.qty === 0 ? '' : item.qty}
                  placeholder="0"
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val >= 0) {
                      updateQty(item.id, val - item.qty);
                    } else if (e.target.value === '') {
                      updateQty(item.id, -item.qty);
                    }
                  }}
                  style={{ 
                    width: '40px', 
                    textAlign: 'center', 
                    border: 'none', 
                    outline: 'none',
                    fontWeight: 'bold',
                    fontSize: '14px',
                    fontFamily: 'inherit',
                    padding: '0',
                    background: 'transparent'
                  }} 
                />
                <button onClick={() => updateQty(item.id, 1)}>+</button>
              </div>
              <strong>Rs. {(item.price * item.qty).toLocaleString()}</strong>
            </div>
          ))
        )}
        <div className="total">
          <span>Order total</span>
          <strong>Rs. {total.toLocaleString()}</strong>
        </div>
      </Panel>
      <div className="action-row">
        <button className="secondary" onClick={handleSaveDraft}>Save draft</button>
        <button className="primary" onClick={() => notify('Order WPF-2026-08741 placed')}>Place order <span>→</span></button>
      </div>
    </>
  );
}
function Confirmed() { return <div className="narrow"><div className="success-block"><div className="check">✓</div><div><Status>Confirmed</Status><h2>Order is on its way into planning</h2><p>We will notify you if anything changes before delivery.</p></div></div><Panel><div className="meta-grid"><div><small>Reference</small><b>WPF-2026-08741</b></div><div><small>Estimated arrival</small><b>Tomorrow · 05:30–07:45 AM</b></div><div><small>Brand</small><b>Waypoint Fresh</b></div><div><small>Placed at</small><b>Today, 3:12 PM</b></div></div></Panel><Panel><h3>Items ordered</h3>{items.map(i => <div className="line" key={i.sku}><span>{i.name}</span><b>×{i.qty}</b></div>)}</Panel></div> }
function Deferral({ notify }: { notify: (m: string) => void }) { return <div className="narrow"><div className="warning-block"><div className="alert-icon">!</div><div><Status tone="amber">Deferred</Status><h2>Today's delivery has been deferred</h2><p>Available delivery capacity was insufficient to include this order in this morning's run.</p></div></div><Panel><h3>What this means for your store</h3><ul className="clean-list"><li>Deferred items will not arrive today.</li><li>No action is needed; the order carries to the next run.</li><li>We will confirm when tomorrow's delivery is locked in.</li></ul></Panel><div className="next-run"><small>Next expected delivery</small><b>Tomorrow · 05:30–07:45 AM</b><span>Before your store opens</span></div><button className="secondary" onClick={() => notify('Dispatcher contact request sent')}>Contact dispatcher</button></div> }
function ReportIssueModal({ onClose, onSubmit }: { onClose: () => void, onSubmit: (data: any) => void }) {
  const [issueType, setIssueType] = useState('Damaged in transit');
  const [notes, setNotes] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setPhoto(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleSubmit = () => {
    // TODO: Replace local console.log with Supabase Storage upload for the image and database insert for the issue record.
    console.log("Issue Reported Payload:", { issueType, notes, photo });
    onSubmit({ issueType, notes, photo });
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
      <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', width: '100%', maxWidth: '420px', boxShadow: '0 10px 25px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h3 style={{ margin: 0, fontSize: '20px', color: '#0f172a', fontWeight: 600 }}>Report Issue</h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>Issue Type</label>
          <select value={issueType} onChange={e => setIssueType(e.target.value)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px', outline: 'none', color: '#0f172a' }}>
            <option>Damaged in transit</option>
            <option>Loading shortfall</option>
            <option>Wrong item</option>
            <option>Temperature problem</option>
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>Photo Evidence</label>
          <div style={{ border: '2px dashed #cbd5e1', borderRadius: '8px', padding: '16px', textAlign: 'center', position: 'relative', background: '#f8fafc', transition: 'background 0.2s', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '120px' }}>
            <input type="file" accept="image/*" onChange={handleFileChange} style={{ opacity: 0, position: 'absolute', inset: 0, cursor: 'pointer', zIndex: 2 }} />
            {previewUrl ? (
              <img src={previewUrl} alt="Preview" style={{ maxHeight: '120px', maxWidth: '100%', objectFit: 'contain', borderRadius: '4px', position: 'relative', zIndex: 3 }} />
            ) : (
              <div style={{ color: '#64748b', fontSize: '14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '28px' }}>📸</span>
                <span>Click or drag to upload photo</span>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>Notes (optional)</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Add a note..." style={{ padding: '10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px', minHeight: '80px', resize: 'vertical', outline: 'none', color: '#0f172a' }} />
        </div>

        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '8px' }}>
          <button onClick={onClose} style={{ padding: '10px 16px', borderRadius: '6px', border: '1px solid #cbd5e1', background: 'white', cursor: 'pointer', fontWeight: 600, color: '#475569', fontSize: '14px' }}>Cancel</button>
          <button onClick={handleSubmit} style={{ padding: '10px 16px', borderRadius: '6px', border: 'none', background: '#065F46', color: 'white', cursor: 'pointer', fontWeight: 600, fontSize: '14px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>Submit Issue & Confirm</button>
        </div>
      </div>
    </div>
  );
}

function Receipt({ notify }: { notify: (m: string) => void }) {
  const receipt = [12, 6, 4, 8, 3];
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <div className="banner warning">! 1 item has a quantity mismatch · shortfall was reported by the warehouse before departure</div>
      <div className="section-head">
        <div>
          <span className="overline">WPF-2026-08741 · MIDLANDS SUPERMART</span>
          <h2>Confirm delivery receipt</h2>
        </div>
        <Status tone="amber">1 discrepancy</Status>
      </div>
      <Panel>
        <div className="table-head receipt-grid">
          <span>Item</span>
          <span>Expected</span>
          <span>Received</span>
          <span>State</span>
        </div>
        {items.map((item, i) => (
          <div className={`product-row receipt-grid ${i === 0 ? 'mismatch' : ''}`} key={item.sku}>
            <b>{item.name}</b>
            <span>{item.qty}</span>
            <input defaultValue={receipt[i]} type="number" />
            <Status tone={i === 0 ? 'amber' : 'green'}>{i === 0 ? 'Short 6' : 'Matches'}</Status>
          </div>
        ))}
      </Panel>
      <div className="action-row">
        <button className="secondary" onClick={() => setIsModalOpen(true)}>Report issue</button>
        <button className="primary" onClick={() => notify('Receipt confirmed with discrepancy')}>Confirm receipt <span>→</span></button>
      </div>
      {isModalOpen && (
        <ReportIssueModal
          onClose={() => setIsModalOpen(false)}
          onSubmit={() => {
            setIsModalOpen(false);
            notify('Issue logged successfully (Console)');
          }}
        />
      )}
    </>
  );
}
function Queue() { const rows = [['Midlands Supermart — Gampola', 'Fresh', '165 kg / 0.6 m³', 'Assigned', 'High'], ['Highland Mart — Kandy', 'Fresh', '280 kg / 1.0 m³', 'Assigned', 'High'], ['Shoreline Store — Galle Fort', 'Fresh', '310 kg / 1.1 m³', 'Review', 'High'], ['Digital World — Bambalapitiya', 'Tech', '260 kg / 1.8 m³', 'Pending', 'Normal']]; return <><div className="kpi-grid"><Kpi label="Open orders" value="18" sub="3 high priority" /><Kpi label="Assigned" value="4" sub="Trip 1 · WP-CAB-9241" /><Kpi label="Vehicles active" value="14" sub="of 18 available" /><Kpi label="Require review" value="2" sub="Needs attention" tone="amber" /></div><Panel className="table-panel"><div className="table-head queue-grid"><span>Outlet</span><span>Brand</span><span>Volume</span><span>Trip</span><span>Status</span></div>{rows.map((r, i) => <div className="table-row queue-grid" key={r[0]}><div><b>{r[0]}</b><small>{i === 0 ? 'WPF-2026-08741' : 'Delivery window · 06:00–10:00 AM'}</small></div><Status>{r[1]}</Status><span>{r[2]}</span><span>{r[3] === 'Assigned' ? 'Trip 1' : '—'}</span><Status tone={r[3] === 'Review' ? 'amber' : r[3] === 'Pending' ? 'slate' : 'green'}>{r[3]}</Status></div>)}</Panel></> }
function Allocate({ notify }: { notify: (m: string) => void }) { return <><div className="banner warning">! Shoreline Store has been deferred two consecutive days · Find a compatible vehicle before publishing.</div><div className="split"><div><div className="section-head compact"><h2>Unassigned orders</h2><Status tone="red">4</Status></div>{['Shoreline Store — Galle Fort', 'Style Hub — One Galle Face', 'Digital World — Bambalapitiya', 'Fashion Point — Negombo'].map((x, i) => <Panel className="order-card" key={x}><div className="card-line"><b>{x}</b><Status tone={i === 0 ? 'amber' : 'green'}>{i === 0 ? '2nd deferral' : 'Pending'}</Status></div><p className="muted">{[310, 90, 260, 75][i]} kg · {['Chilled', 'Mall access', 'Ambient', 'Ambient'][i]}</p><div className="mini-actions"><button onClick={() => notify(`${x} assigned to WP-CAB-9241`)}>Serve</button><button onClick={() => notify(`${x} deferred to next run`)}>Defer</button></div></Panel>)}</div><div><div className="section-head compact"><h2>Vehicle capacity</h2><span className="muted">Drag orders to assign</span></div>{[['WP-CAB-9241', 'Rohan Silva', 71, 'Refrigerated'], ['WP-KV-3318', 'Perera, R.', 95, 'Van-class'], ['WP-NT-1102', 'Silva, M.', 32, 'Van-class']].map(v => <Panel className="vehicle-card" key={v[0]}><div className="card-line"><div><b className="mono">{v[0]}</b><small>{v[1]} · Kandy–Gampola corridor</small></div><Status>{v[3]}</Status></div><div className="capacity"><span>Weight <b>{Number(v[2])}%</b></span><i><em style={{ width: `${Number(v[2])}%` }} /></i></div><div className="capacity"><span>Volume <b>{Math.max(Number(v[2]) - 12, 18)}%</b></span><i><em style={{ width: `${Math.max(Number(v[2]) - 12, 18)}%` }} /></i></div></Panel>)}</div></div></> }
function Board() { return <><div className="kpi-grid"><Kpi label="On route" value="3" sub="Moving to window" /><Kpi label="Delayed" value="1" sub="Intervention suggested" tone="amber" /><Kpi label="At risk" value="1" sub="Window may breach" tone="red" /><Kpi label="Offline" value="1" sub="Last seen 07:14 AM" tone="slate" /></div><Panel className="table-panel"><div className="table-head board-grid"><span>Vehicle</span><span>Driver & route</span><span>Current destination</span><span>Progress</span><span>Status</span></div>{[['WP-CAB-9241', 'Rohan Silva · Kandy–Gampola', 'Midlands Supermart — Gampola', '2 of 4 stops', 'Offline'], ['WP-KV-3318', 'Perera, R. · Southern Route', 'Shoreline Store — Galle Fort', '1 of 5 stops', 'Delayed'], ['WP-NT-1102', 'Silva, M. · North Western', 'Digital World — Kurunegala', '4 of 7 stops', 'On route'], ['WP-JF-4401', 'Fernando, A. · Western Suburbs', 'Fashion Point — Negombo', '0 of 4 stops', 'On route']].map(r => <div className={`table-row board-grid ${r[4] === 'Offline' ? 'offline-row' : ''}`} key={r[0]}><b className="mono">{r[0]}</b><span>{r[1]}</span><div><b>{r[2]}</b>{r[4] === 'Offline' && <small>Signal lost · Kandy corridor dead zone</small>}</div><span>{r[3]}</span><Status tone={r[4] === 'On route' ? 'green' : r[4] === 'Delayed' ? 'amber' : 'slate'}>{r[4]}</Status></div>)}</Panel></> }
function Capacity() { return <><div className="section-head"><div><span className="overline">5-DAY FORWARD PLANNING</span><h2>Demand against available fleet</h2></div><button className="secondary">Export outlook</button></div><Panel><div className="capacity-list">{[['Wed 15 Jan', '22 orders · 4,200 kg', 'No gap', 'Low', 'green'], ['Thu 16 Jan', '28 orders · 5,800 kg', '800 kg shortage', 'Medium', 'amber'], ['Fri 17 Jan', '34 orders · 6,900 kg', '2,100 kg shortage', 'High', 'red'], ['Sat 18 Jan', '18 orders · 3,400 kg', 'No gap', 'Low', 'green']].map(r => <div className="forecast" key={r[0]}><b>{r[0]}</b><span>{r[1]}</span><strong className={r[4]}>{r[2]}</strong><Status tone={r[4]}>{r[3]}</Status></div>)}</div></Panel></> }
function LoadList({ notify }: { notify: (m: string) => void }) { return <><div className="dark-banner"><div><span className="overline">VEHICLE · WP-CAB-9241 · PELIYAGODA DC</span><h2>Load in reverse-unload order</h2><p>Last delivery first, so the first stop is accessible when unloading.</p></div><Status tone="amber">Not ready · 1 shortfall</Status></div>{stops.slice().reverse().map((stop, i) => <SwipeToAction key={stop}><Panel className={`stop-card ${i === 0 ? 'loaded' : i === 1 ? 'shortfall' : ''}`}><div className="stop-number">{i === 0 ? '✓' : i === 1 ? '!' : i + 1}</div><div className="stop-copy"><div className="card-line"><div><b>{stop}</b><small>Load position {i + 1} · Delivery stop {4 - i}</small></div><Status tone="blue">Chilled</Status></div><p>{i === 1 ? 'Anchor Milk 1L × 12 · 6 units missing · WPF-2026-08741' : 'Anchor Milk 1L × 18 · Basmati Rice × 8 · Ginger Beer × 12'}</p>{i === 1 && <strong className="amber-text">Shortfall must be recorded before departure.</strong>}</div></Panel></SwipeToAction>)}<div className="action-row"><button className="secondary" onClick={() => notify('Shortfall screen opened')}>Flag shortfall</button><button className="primary" onClick={() => notify('Load list marked complete')}>Mark all loaded <span>→</span></button></div></> }
function Shortfall({ notify }: { notify: (m: string) => void }) { return <div className="narrow"><div className="banner warning">Record the affected quantity before the vehicle leaves.</div><Panel><span className="overline">STEP 1 · ISSUE TYPE</span><div className="choice-grid"><button className="selected">▣<b>Missing</b><small>Stock not available</small></button><button>▧<b>Damaged</b><small>Cannot dispatch</small></button><button>△<b>Wrong item</b><small>Incorrect SKU</small></button></div></Panel><Panel><span className="overline">STEP 2 · AFFECTED ITEM</span><h3>Anchor Full Cream Milk 1L</h3><p className="muted">Expected 12 units · Received 6 units · Gampola stop</p><div className="quantity"><span>Units missing</span><button>−</button><b>6</b><button>+</button></div></Panel><Panel><span className="overline">EVIDENCE</span><div className="photo">⌾<span>Attach photo of empty crate / shelf</span></div><textarea placeholder="Notes (optional)" /></Panel><button className="primary full" onClick={() => notify('Shortfall WPF-2026-08741 recorded')}>Confirm shortfall · 6 missing</button></div> }
function PlanChanged({ notify }: { notify: (m: string) => void }) { return <div className="narrow"><div className="critical-block"><Status tone="red">Plan changed</Status><h2>The load list has changed</h2><p>Dispatcher Perera added Midlands Supermart — Gampola before departure. Re-verify your load.</p></div><Panel><div className="meta-grid"><div><small>What</small><b>New stop added · Gampola</b></div><div><small>When</small><b>06:42 AM today</b></div><div><small>Who</small><b>Dispatcher Perera</b></div><div><small>Action</small><b>Load position 2</b></div></div></Panel><Panel className="highlight-panel"><Status tone="amber">New stop</Status><h3>Midlands Supermart — Gampola</h3><p>Anchor Milk × 12 · Maliban Crackers × 6 · Basmati × 4 · Ginger Beer × 8</p></Panel><button className="primary full" onClick={() => notify('Updated load list acknowledged')}>Acknowledge & continue</button></div> }
export default function App() {
  const [role, setRole] = useState<Role | null>(() => localStorage.getItem('waypoint-role') as Role | null);
  const [userId, setUserId] = useState<string | null>(() => localStorage.getItem('waypoint-userId'));
  
  const signIn = (next: Role, uid: string) => {
    localStorage.setItem('waypoint-role', next);
    localStorage.setItem('waypoint-userId', uid);
    setRole(next);
    setUserId(uid);
  };
  
  if (!role || !userId) return <Auth onSignIn={signIn} />;
  
  return <Shell role={role} userId={userId} onSignOut={() => {
    localStorage.removeItem('waypoint-role');
    localStorage.removeItem('waypoint-userId');
    setRole(null);
    setUserId(null);
    supabase.auth.signOut();
  }} />;
}
