import { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';
import * as XLSX from 'xlsx';

const GENERATION_SERVICE_URL = import.meta.env.VITE_GENERATION_SERVICE_URL;

// 'generating' is a transient, auto-set status during book generation --
// it's not something an admin picks manually, so it's excluded from
// STATUS_VALUES (the manual dropdown) but still has a label for display
// in case an order gets stuck there (e.g. a crashed generation call).
const STATUS_VALUES = ['new', 'ready', 'sent_to_print', 'shipped', 'delivered'];
const STATUS_LABELS = {
  new: 'New',
  generating: 'Generating…',
  ready: 'Generated',
  sent_to_print: 'Sent to print',
  shipped: 'Shipped',
  delivered: 'Delivered',
};

function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

function useAnimalNames() {
  const [animalNames, setAnimalNames] = useState({});
  useEffect(() => {
    if (!GENERATION_SERVICE_URL) return;
    fetch(`${GENERATION_SERVICE_URL}/animal-names`)
      .then((res) => (res.ok ? res.json() : {}))
      .then(setAnimalNames)
      .catch(() => setAnimalNames({}));
  }, []);
  return animalNames;
}

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

const CYRILLIC_MAP = {
  'А':'a','Б':'b','В':'v','Г':'g','Д':'d','Е':'ye','Ё':'yo','Ж':'j','З':'z',
  'И':'i','Й':'iy','К':'k','Л':'l','М':'m','Н':'n','О':'o','Ө':'q','П':'p',
  'Р':'r','С':'s','Т':'t','У':'u','Ү':'w','Ф':'f','Х':'kh','Ц':'ts','Ч':'ch',
  'Ш':'sh','Щ':'sch','Ь':',','Э':'e','Ю':'yu','Я':'ya'
};

function parseNameTokens(raw) {
  const tokens = [];
  const keyOccCount = {};
  let afterHyphenOrStart = true;
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (ch === '-') { tokens.push({ type: 'hyphen' }); afterHyphenOrStart = true; continue; }
    const upper = ch.toUpperCase();
    if (!CYRILLIC_MAP[upper]) continue;
    const key = CYRILLIC_MAP[upper];
    const letterCase = afterHyphenOrStart ? 'u' : 'l';
    afterHyphenOrStart = false;
    const kc = key + '-' + letterCase;
    keyOccCount[kc] = (keyOccCount[kc] || 0) + 1;
    tokens.push({ type: 'letter', char: upper, key, case: letterCase, occIndex: keyOccCount[kc] });
  }
  return tokens;
}

function LetterVariantPicker({ tokens, variants, onChange, animalNames }) {
  const letters = tokens.filter((t) => t.type === 'letter');
  if (!letters.length) return null;

  return (
    <div style={{ marginBottom: 10 }}>
      <label>Letter variants</label>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
            <th style={{ padding: '4px 8px 4px 0' }}>Letter</th>
            <th>Key</th>
            <th>Case</th>
            <th>Occurrence</th>
            <th>Variant</th>
          </tr>
        </thead>
        <tbody>
          {letters.map((t, i) => {
            const occLabel = ['', '1st', '2nd', '3rd'][t.occIndex] || `${t.occIndex}th`;
            const selected = variants[i];
            const animalName = animalNames[`${t.key}-${selected}`];
            return (
              <tr key={i} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '6px 8px 6px 0', fontSize: 16, fontWeight: 600 }}>{t.char}</td>
                <td style={{ fontFamily: 'monospace', color: '#777' }}>{t.key}-{t.case}</td>
                <td>{t.case === 'u' ? 'Upper' : 'Lower'}</td>
                <td style={{ color: '#777' }}>{occLabel}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {[1, 2, 3, 4, 5].map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => onChange(i, v)}
                        style={{
                          width: 28, height: 28, borderRadius: 6,
                          border: '1px solid #ccc',
                          background: variants[i] === v ? '#333' : '#fff',
                          color: variants[i] === v ? '#fff' : '#333',
                          cursor: 'pointer',
                        }}
                      >
                        {v}
                      </button>
                    ))}
                    <span style={{ marginLeft: 8, color: animalName ? '#333' : '#c66', fontStyle: animalName ? 'normal' : 'italic' }}>
                      {animalName || 'no art for this variant?'}
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function NewOrderForm({ onCreated, onCancel }) {
  const animalNames = useAnimalNames();
  const [form, setForm] = useState({
    order_number: '',
    child_name: '',
    gender: 'girl',
    tier: 'essential',
    dedication_text: '',
    photo_url: '',
    recipient_name: '',
    phone: '',
    province: '',
    city: '',
    street_address: '',
    selling_price: '',
    cost: '',
  });
  const [tokens, setTokens] = useState([]);
  const [variantValues, setVariantValues] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
    if (field === 'child_name') {
      const newTokens = parseNameTokens(value);
      const newLetters = newTokens.filter((t) => t.type === 'letter');
      // Reset variants to default (1) on any name edit -- simpler and more
      // reliable than trying to preserve selections across edits, which
      // was prone to mismatches for repeated letters.
      setTokens(newTokens);
      setVariantValues(newLetters.map(() => 1));
    }
  }

  function setVariant(idx, val) {
    setVariantValues((v) => {
      const copy = [...v];
      copy[idx] = val;
      return copy;
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    let letterIdx = 0;
    const letter_variants = tokens
      .filter((t) => t.type === 'letter' || t.type === 'hyphen')
      .map((t) => {
        if (t.type === 'hyphen') {
          return { key: '-', case: null, variant: null };
        }
        const v = { key: t.key, case: t.case, variant: String(variantValues[letterIdx] || 1) };
        letterIdx += 1;
        return v;
      });

    const { error } = await supabase.from('orders').insert([{
      ...form,
      selling_price: form.selling_price === '' ? null : Number(form.selling_price),
      cost: form.cost === '' ? null : Number(form.cost),
      letter_variants,
      status: 'new',
    }]);
    setSaving(false);
    if (error) {
      setError(error.message);
    } else {
      onCreated();
    }
  }

  const inputStyle = { display: 'block', width: '100%', padding: 6, marginBottom: 10 };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 480 }}>
      <h2>New Order</h2>

      <label>Order number</label>
      <input style={inputStyle} required value={form.order_number}
             onChange={(e) => update('order_number', e.target.value)}
             placeholder="e.g. ORD-0001" />

      <label>Child's name</label>
      <input style={inputStyle} required value={form.child_name}
             onChange={(e) => update('child_name', e.target.value)} />

      <LetterVariantPicker tokens={tokens} variants={variantValues} onChange={setVariant} animalNames={animalNames} />


      <label>Gender</label>
      <select style={inputStyle} value={form.gender} onChange={(e) => update('gender', e.target.value)}>
        <option value="girl">Girl</option>
        <option value="boy">Boy</option>
      </select>

      <label>Tier</label>
      <select style={inputStyle} value={form.tier} onChange={(e) => update('tier', e.target.value)}>
        <option value="essential">Essential</option>
        <option value="signature">Signature</option>
        <option value="magical">Magical</option>
      </select>

      <label>Dedication text</label>
      <textarea style={{ ...inputStyle, height: 100 }} value={form.dedication_text}
                onChange={(e) => update('dedication_text', e.target.value)} />

      <label>Photo URL (e.g. an ImgBB link)</label>
      <input style={inputStyle} value={form.photo_url}
             onChange={(e) => update('photo_url', e.target.value)} />

      <h3>Shipping</h3>
      <label>Recipient name</label>
      <input style={inputStyle} value={form.recipient_name}
             onChange={(e) => update('recipient_name', e.target.value)} />

      <label>Phone</label>
      <input style={inputStyle} value={form.phone}
             onChange={(e) => update('phone', e.target.value)} />

      <label>Province</label>
      <input style={inputStyle} value={form.province}
             onChange={(e) => update('province', e.target.value)} />

      <label>City</label>
      <input style={inputStyle} value={form.city}
             onChange={(e) => update('city', e.target.value)} />

      <label>Street address</label>
      <input style={inputStyle} value={form.street_address}
             onChange={(e) => update('street_address', e.target.value)} />

      <h3>Financials (optional, can fill in later)</h3>
      <label>Selling price</label>
      <input style={inputStyle} type="number" value={form.selling_price}
             onChange={(e) => update('selling_price', e.target.value)} />

      <label>Cost</label>
      <input style={inputStyle} type="number" value={form.cost}
             onChange={(e) => update('cost', e.target.value)} />

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create Order'}</button>{' '}
      <button type="button" onClick={onCancel}>Cancel</button>
    </form>
  );
}

function OrderList({ onSelect, onNewOrder }) {
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

  async function handleDelete(e, order) {
    e.stopPropagation(); // don't trigger the row's onSelect
    const confirmed = window.confirm(
      `Delete order ${order.order_number} (${order.child_name})? This can't be undone.`
    );
    if (!confirmed) return;
    await supabase.from('orders').delete().eq('id', order.id);
    loadOrders();
  }

  function exportToExcel() {
    // Flatten each order into a single row. letter_variants is a JSONB
    // array in the DB, so it's turned into a short readable string here
    // (e.g. "kh-u-1, a-l-1, n-l-1") rather than dumping raw JSON into a cell.
    const rows = orders.map((o) => {
      const lettersStr = (o.letter_variants || [])
        .map((v) => (v.key === '-' ? '-' : `${v.key}-${v.case}-${v.variant}`))
        .join(', ');
      const hasFinancials = o.selling_price != null && o.cost != null;
      return {
        'Order #': o.order_number,
        'Child name': o.child_name,
        'Gender': o.gender,
        'Tier': o.tier,
        'Status': statusLabel(o.status),
        'Letter variants': lettersStr,
        'Dedication text': o.dedication_text,
        'Recipient name': o.recipient_name,
        'Phone': o.phone,
        'Province': o.province,
        'City': o.city,
        'Street address': o.street_address,
        'Selling price': o.selling_price ?? '',
        'Cost': o.cost ?? '',
        'Profit': hasFinancials ? o.selling_price - o.cost : '',
        'Print PDF URL': o.print_pdf_url || '',
        'Digital pages URL': o.digital_pages_url || '',
        'Created': new Date(o.created_at).toLocaleString(),
      };
    });

    const worksheet = XLSX.utils.json_to_sheet(rows);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Orders');

    const dateStr = new Date().toISOString().slice(0, 10);
    const filterSuffix = filter === 'all' ? 'all' : filter;
    XLSX.writeFile(workbook, `amiya-orders-${filterSuffix}-${dateStr}.xlsx`);
  }

  const allStatusOptions = [...STATUS_VALUES, 'generating'];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All statuses</option>
          {allStatusOptions.map((s) => (
            <option key={s} value={s}>{statusLabel(s)}</option>
          ))}
        </select>
        <div>
          <button onClick={exportToExcel} disabled={!orders.length} style={{ marginRight: 8 }}>
            Export to Excel
          </button>
          <button onClick={onNewOrder}>+ New Order</button>
        </div>
      </div>
      <table width="100%" cellPadding={8} style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
            <th>Order #</th>
            <th>Child</th>
            <th>Tier</th>
            <th>Status</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} onClick={() => onSelect(o)}
                style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}>
              <td>{o.order_number}</td>
              <td>{o.child_name} ({o.gender})</td>
              <td>{o.tier}</td>
              <td>{statusLabel(o.status)}</td>
              <td>{new Date(o.created_at).toLocaleDateString()}</td>
              <td>
                <button onClick={(e) => handleDelete(e, o)} style={{ color: '#c33' }}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LetterVariantsSummary({ order, animalNames }) {
  const tokens = parseNameTokens(order.child_name);
  const letters = tokens.filter((t) => t.type === 'letter');
  const variants = order.letter_variants || [];
  // letter_variants includes hyphen placeholders too, so line it up by
  // filtering to just the letter entries in the same order.
  const letterVariantEntries = variants.filter((v) => v.key !== '-');

  if (!letters.length || !letterVariantEntries.length) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <p><strong>Letter variants chosen:</strong></p>
      <table style={{ fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
            <th style={{ padding: '4px 8px 4px 0' }}>Letter</th>
            <th style={{ padding: '4px 8px' }}>Key</th>
            <th style={{ padding: '4px 8px' }}>Case</th>
            <th style={{ padding: '4px 8px' }}>Occurrence</th>
            <th style={{ padding: '4px 8px' }}>Variant</th>
            <th style={{ padding: '4px 8px' }}>Animal</th>
          </tr>
        </thead>
        <tbody>
          {letters.map((t, i) => {
            const v = letterVariantEntries[i];
            const occLabel = ['', '1st', '2nd', '3rd'][t.occIndex] || `${t.occIndex}th`;
            const animalName = v ? animalNames[`${v.key}-${v.variant}`] : null;
            return (
              <tr key={i} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '4px 8px 4px 0', fontWeight: 600 }}>{t.char}</td>
                <td style={{ padding: '4px 8px', fontFamily: 'monospace', color: '#777' }}>{t.key}-{t.case}</td>
                <td style={{ padding: '4px 8px' }}>{t.case === 'u' ? 'Upper' : 'Lower'}</td>
                <td style={{ padding: '4px 8px', color: '#777' }}>{occLabel}</td>
                <td style={{ padding: '4px 8px' }}>{v ? v.variant : '—'}</td>
                <td style={{ padding: '4px 8px' }}>{animalName || '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FinancialsPanel({ order }) {
  const [sellingPrice, setSellingPrice] = useState(order.selling_price ?? '');
  const [cost, setCost] = useState(order.cost ?? '');
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const profit = (sellingPrice !== '' && cost !== '')
    ? Number(sellingPrice) - Number(cost)
    : null;

  async function handleSave() {
    setSaving(true);
    setJustSaved(false);
    await supabase.from('orders').update({
      selling_price: sellingPrice === '' ? null : Number(sellingPrice),
      cost: cost === '' ? null : Number(cost),
    }).eq('id', order.id);
    setSaving(false);
    setJustSaved(true);
    setTimeout(() => setJustSaved(false), 2500);
  }

  return (
    <div style={{ marginTop: 12, padding: 12, border: '1px solid #eee', borderRadius: 6, maxWidth: 320 }}>
      <p style={{ marginTop: 0 }}><strong>Financials</strong></p>
      <label>Selling price</label>
      <input type="number" style={{ display: 'block', width: '100%', padding: 6, marginBottom: 8 }}
             value={sellingPrice} onChange={(e) => setSellingPrice(e.target.value)} />
      <label>Cost</label>
      <input type="number" style={{ display: 'block', width: '100%', padding: 6, marginBottom: 8 }}
             value={cost} onChange={(e) => setCost(e.target.value)} />
      <p>
        <strong>Profit:</strong>{' '}
        {profit === null ? '—' : profit.toLocaleString()}
      </p>
      <button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save financials'}</button>
      {justSaved && <span style={{ marginLeft: 8, color: 'green' }}>✓ Saved</span>}
    </div>
  );
}

function OrderDetail({ order, onBack, onUpdated, animalNames }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [generatingCover, setGeneratingCover] = useState(false);
  const [coverError, setCoverError] = useState(null);

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

  async function handleGenerateCover() {
    // Independent of the interior book -- can be generated any time,
    // doesn't touch order status, doesn't require /generate to have run.
    setGeneratingCover(true);
    setCoverError(null);
    try {
      const res = await fetch(`${GENERATION_SERVICE_URL}/generate-cover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_number: order.order_number,
          child_name: order.child_name,
          gender: order.gender,
        }),
      });
      if (!res.ok) throw new Error(`Cover generation failed: ${res.status}`);
      const result = await res.json();

      await supabase.from('orders').update({
        cover_pdf_url: result.cover_pdf_url,
      }).eq('id', order.id);

      onUpdated();
    } catch (err) {
      setCoverError(err.message);
    } finally {
      setGeneratingCover(false);
    }
  }

  async function handleDelete() {
    const confirmed = window.confirm(
      `Delete order ${order.order_number} (${order.child_name})? This can't be undone.`
    );
    if (!confirmed) return;
    await supabase.from('orders').delete().eq('id', order.id);
    onBack();
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
              {!STATUS_VALUES.includes(order.status) && (
                <option value={order.status}>{statusLabel(order.status)}</option>
              )}
              {STATUS_VALUES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
            </select>
          </p>
          <p><strong>Dedication:</strong></p>
          <p style={{ whiteSpace: 'pre-wrap', maxWidth: 400 }}>{order.dedication_text}</p>
          <p><strong>Shipping:</strong> {order.recipient_name}, {order.street_address}, {order.city}, {order.province} — {order.phone}</p>

          <LetterVariantsSummary order={order} animalNames={animalNames} />
          <FinancialsPanel order={order} />
        </div>
        <div>
          {order.photo_url && <img src={order.photo_url} alt="Child" width={200} />}
        </div>
      </div>

      <hr />

      <button onClick={handleGenerate} disabled={generating}>
        {generating ? 'Generating…' : 'Generate Book'}
      </button>{' '}
      <button onClick={handleGenerateCover} disabled={generatingCover}>
        {generatingCover ? 'Generating…' : 'Generate Cover'}
      </button>{' '}
      <button onClick={handleDelete} style={{ color: '#c33' }}>Delete order</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {coverError && <p style={{ color: 'red' }}>{coverError}</p>}

      {order.print_pdf_url && (
        <p><a href={order.print_pdf_url} target="_blank" rel="noreferrer">Download print PDF</a></p>
      )}
      {order.digital_pages_url && (
        <p><a href={order.digital_pages_url} target="_blank" rel="noreferrer">Digital pages PDF (for Heyzine)</a></p>
      )}
      {order.cover_pdf_url && (
        <p><a href={order.cover_pdf_url} target="_blank" rel="noreferrer">Download cover PDF</a></p>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [showNewOrder, setShowNewOrder] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const animalNames = useAnimalNames();

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
      {showNewOrder ? (
        <NewOrderForm
          onCreated={() => { setShowNewOrder(false); setRefreshKey((k) => k + 1); }}
          onCancel={() => setShowNewOrder(false)}
        />
      ) : selectedOrder ? (
        <OrderDetail
          order={selectedOrder}
          onBack={() => { setSelectedOrder(null); setRefreshKey((k) => k + 1); }}
          onUpdated={() => { setRefreshKey((k) => k + 1); setSelectedOrder(null); }}
          animalNames={animalNames}
        />
      ) : (
        <OrderList key={refreshKey} onSelect={setSelectedOrder} onNewOrder={() => setShowNewOrder(true)} />
      )}
    </div>
  );
}
