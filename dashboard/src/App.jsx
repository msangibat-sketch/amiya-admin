import { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';

const GENERATION_SERVICE_URL = import.meta.env.VITE_GENERATION_SERVICE_URL;

const STATUS_FLOW = ['new', 'generating', 'ready', 'packed', 'shipped', 'delivered'];

function LoginScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    const { error } = await supabase.auth.signInWithOtp({ email });
    if (!error) setSent(true);
  }

  return (
    <div style={{ maxWidth: 360, margin: '80px auto', fontFamily: 'sans-serif' }}>
      <h2>Amiya Admin</h2>
      {sent ? (
        <p>Check your email for a login link.</p>
      ) : (
        <form onSubmit={handleLogin}>
          <input
            type="email"
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: '100%', padding: 8, marginBottom: 8 }}
          />
          <button type="submit" style={{ width: '100%', padding: 8 }}>
            Send login link
          </button>
        </form>
      )}
    </div>
  );
}

function OrderList({ onSelect }) {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    loadOrders();
  }, [filter]);

  async function loadOrders() {
    let query = supabase.from('orders').select('*').order('created_at', { ascending: false });
    if (filter !== 'all') query = query.eq('status', filter);
    const { data } = await query;
    setOrders(data || []);
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All statuses</option>
          {STATUS_FLOW.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <table width="100%" cellPadding={8} style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
            <th>Order #</th>
            <th>Child</th>
            <th>Tier</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} onClick={() => onSelect(o)}
                style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}>
              <td>{o.order_number}</td>
              <td>{o.child_name} ({o.gender})</td>
              <td>{o.tier}</td>
              <td>{o.status}</td>
              <td>{new Date(o.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrderDetail({ order, onBack, onUpdated }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      await supabase.from('orders').update({ status: 'generating' }).eq('id', order.id);

      const res = await fetch(`${GENERATION_SERVICE_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_number: order.order_number,
          child_name: order.child_name,
          gender: order.gender,
          tier: order.tier,
          dedication_text: order.dedication_text,
          photo_url: order.photo_url,
          letter_variants: order.letter_variants,
        }),
      });
      if (!res.ok) throw new Error(`Generation failed: ${res.status}`);
      const result = await res.json();

      await supabase.from('orders').update({
        status: 'ready',
        print_pdf_url: result.print_pdf_url,
        digital_pages_url: result.digital_pages_url,
      }).eq('id', order.id);

      onUpdated();
    } catch (err) {
      setError(err.message);
      await supabase.from('orders').update({ status: 'new' }).eq('id', order.id);
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatusChange(newStatus) {
    await supabase.from('orders').update({ status: newStatus }).eq('id', order.id);
    onUpdated();
  }

  return (
    <div>
      <button onClick={onBack}>&larr; Back to orders</button>
      <h2>{order.order_number} — {order.child_name}</h2>

      <div style={{ display: 'flex', gap: 40 }}>
        <div>
          <p><strong>Gender:</strong> {order.gender}</p>
          <p><strong>Tier:</strong> {order.tier}</p>
          <p><strong>Status:</strong>{' '}
            <select value={order.status} onChange={(e) => handleStatusChange(e.target.value)}>
              {STATUS_FLOW.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </p>
          <p><strong>Dedication:</strong></p>
          <p style={{ whiteSpace: 'pre-wrap', maxWidth: 400 }}>{order.dedication_text}</p>
          <p><strong>Shipping:</strong> {order.recipient_name}, {order.street_address}, {order.city}, {order.province} — {order.phone}</p>
        </div>
        <div>
          {order.photo_url && <img src={order.photo_url} alt="Child" width={200} />}
        </div>
      </div>

      <hr />

      <button onClick={handleGenerate} disabled={generating}>
        {generating ? 'Generating…' : 'Generate Book'}
      </button>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {order.print_pdf_url && (
        <p><a href={order.print_pdf_url} target="_blank" rel="noreferrer">Download print PDF</a></p>
      )}
      {order.digital_pages_url && (
        <p><a href={order.digital_pages_url} target="_blank" rel="noreferrer">Digital pages folder</a></p>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  if (!session) return <LoginScreen />;

  return (
    <div style={{ maxWidth: 900, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>Amiya Publishing — Orders</h1>
      {selectedOrder ? (
        <OrderDetail
          order={selectedOrder}
          onBack={() => setSelectedOrder(null)}
          onUpdated={() => { setRefreshKey((k) => k + 1); setSelectedOrder(null); }}
        />
      ) : (
        <OrderList key={refreshKey} onSelect={setSelectedOrder} />
      )}
    </div>
  );
}
