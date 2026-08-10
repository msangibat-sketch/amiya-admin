import { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';
import * as XLSX from 'xlsx';

const GENERATION_SERVICE_URL = import.meta.env.VITE_GENERATION_SERVICE_URL;

// ---------------------------------------------------------------------
// Brand theme, lifted directly from amiyapublishing.com's own CSS
// variables (--terra, --cream, etc.) and Google Fonts import (Comfortaa
// for headings/buttons, Nunito for body text), so the dashboard matches
// the storefront instead of looking like a generic admin tool.
// ---------------------------------------------------------------------
const THEME = {
  terra: '#D4845A',
  terraDeep: '#B8673D',
  terraLight: '#F0B48A',
  cream: '#FDF6EE',
  cream2: '#FBF0E2',
  warm: '#F5E6D0',
  text: '#3D2B1F',
  textMid: '#6B4C38',
  textSoft: '#A07858',
  gold: '#D4A843',
  danger: '#C0533A',
  shadow: 'rgba(61,43,31,0.10)',
  shadowDeep: 'rgba(61,43,31,0.20)',
  border: 'rgba(212,132,90,0.18)',
};

const heading = { fontFamily: "'Comfortaa', cursive", fontWeight: 700, color: THEME.text, margin: 0 };

const pageWrap = {
  minHeight: '100vh',
  background: 'linear-gradient(180deg,#FEF4EC 0%,#FDE8D8 10%,#FAE0CC 18%,#F8D4BC 26%,#F5C9A8 34%,#F2C4B0 42%,#F5C8C8 50%,#F2BEBE 58%,#EDB8C8 66%,#E8B4D4 74%,#DDB0D8 82%,#D4AFDC 90%,#CBAEE0 100%)',
  backgroundAttachment: 'fixed',
  fontFamily: "'Nunito', sans-serif",
  color: THEME.text,
  padding: '48px 24px 80px',
};

const card = {
  background: '#fff',
  borderRadius: 20,
  padding: 28,
  boxShadow: `0 4px 24px ${THEME.shadow}`,
  border: `1.5px solid ${THEME.border}`,
};

const inputStyle = {
  display: 'block', width: '100%', padding: '11px 14px', marginBottom: 14,
  borderRadius: 12, border: `1.5px solid ${THEME.border}`,
  fontFamily: "'Nunito', sans-serif", fontSize: 14, color: THEME.text,
  background: THEME.cream, boxSizing: 'border-box',
};

const labelStyle = { fontSize: 13, fontWeight: 600, color: THEME.textMid, marginBottom: 4, display: 'block' };

function buttonStyle(variant = 'primary', disabled = false) {
  const base = {
    fontFamily: "'Comfortaa', cursive", fontWeight: 700, fontSize: 13,
    padding: '11px 26px', borderRadius: 100, cursor: disabled ? 'default' : 'pointer',
    border: 'none', transition: 'all 0.15s', opacity: disabled ? 0.55 : 1,
  };
  if (variant === 'primary') {
    return { ...base, background: THEME.terra, color: '#fff', boxShadow: `0 6px 20px rgba(212,132,90,0.35)` };
  }
  if (variant === 'secondary') {
    return { ...base, background: '#fff', color: THEME.terra, border: `2px solid ${THEME.terra}` };
  }
  if (variant === 'danger') {
    return { ...base, background: 'transparent', color: THEME.danger, border: `1.5px solid rgba(192,83,58,0.4)`, padding: '9px 20px' };
  }
  if (variant === 'ghost') {
    return { ...base, background: 'transparent', color: THEME.textMid, boxShadow: 'none', padding: '9px 16px' };
  }
  return base;
}

function Button({ variant = 'primary', disabled, children, ...props }) {
  return (
    <button {...props} disabled={disabled} style={buttonStyle(variant, disabled)}>
      {children}
    </button>
  );
}

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

const STATUS_COLORS = {
  new: THEME.textSoft,
  generating: THEME.gold,
  ready: THEME.terra,
  sent_to_print: '#7A8FA6',
  shipped: '#6B9E78',
  delivered: '#4A8F5C',
};

function StatusPill({ status }) {
  const color = STATUS_COLORS[status] || THEME.textSoft;
  return (
    <span style={{
      display: 'inline-block', fontFamily: "'Comfortaa', cursive", fontWeight: 700,
      fontSize: 11, letterSpacing: '0.03em', padding: '5px 14px', borderRadius: 100,
      background: `${color}1A`, color,
    }}>
      {statusLabel(status)}
    </span>
  );
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
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setSending(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOtp({ email });
    setSending(false);
    if (error) {
      console.error('signInWithOtp error:', error);
      setError(error.message);
    } else {
      setSent(true);
    }
  }

  return (
    <div style={pageWrap}>
      <div style={{ maxWidth: 380, margin: '100px auto 0', ...card, textAlign: 'center' }}>
        <h2 style={{ ...heading, fontSize: 24, marginBottom: 20 }}>Amiya Admin</h2>
        {sent ? (
          <p style={{ color: THEME.textMid }}>Check your email for a login link.</p>
        ) : (
          <form onSubmit={handleLogin}>
            <input
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
            />
            <Button type="submit" disabled={sending} style={{ ...buttonStyle('primary', sending), width: '100%' }}>
              {sending ? 'Sending…' : 'Send login link'}
            </Button>
            {error && <p style={{ color: THEME.danger, fontSize: 13, marginTop: 10 }}>{error}</p>}
          </form>
        )}
      </div>
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
    <div style={{ marginBottom: 16 }}>
      <label style={labelStyle}>Letter variants</label>
      <div style={{ borderRadius: 14, overflow: 'hidden', border: `1.5px solid ${THEME.border}` }}>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', background: '#fff' }}>
          <thead>
            <tr style={{ textAlign: 'left', background: THEME.cream2 }}>
              <th style={{ padding: '8px 10px', color: THEME.textMid, fontWeight: 700 }}>Letter</th>
              <th style={{ padding: '8px 10px', color: THEME.textMid, fontWeight: 700 }}>Key</th>
              <th style={{ padding: '8px 10px', color: THEME.textMid, fontWeight: 700 }}>Case</th>
              <th style={{ padding: '8px 10px', color: THEME.textMid, fontWeight: 700 }}>Occurrence</th>
              <th style={{ padding: '8px 10px', color: THEME.textMid, fontWeight: 700 }}>Variant</th>
            </tr>
          </thead>
          <tbody>
            {letters.map((t, i) => {
              const occLabel = ['', '1st', '2nd', '3rd'][t.occIndex] || `${t.occIndex}th`;
              const selected = variants[i];
              const animalName = animalNames[`${t.key}-${selected}`];
              return (
                <tr key={i} style={{ borderTop: `1px solid ${THEME.border}` }}>
                  <td style={{ padding: '8px 10px', fontSize: 16, fontWeight: 700, color: THEME.terra }}>{t.char}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'monospace', color: THEME.textSoft }}>{t.key}-{t.case}</td>
                  <td style={{ padding: '8px 10px', color: THEME.textMid }}>{t.case === 'u' ? 'Upper' : 'Lower'}</td>
                  <td style={{ padding: '8px 10px', color: THEME.textSoft }}>{occLabel}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      {[1, 2, 3, 4, 5].map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => onChange(i, v)}
                          style={{
                            width: 26, height: 26, borderRadius: '50%',
                            border: `1.5px solid ${variants[i] === v ? THEME.terra : THEME.border}`,
                            background: variants[i] === v ? THEME.terra : '#fff',
                            color: variants[i] === v ? '#fff' : THEME.textMid,
                            fontWeight: 700, fontSize: 12, cursor: 'pointer',
                          }}
                        >
                          {v}
                        </button>
                      ))}
                      <span style={{ marginLeft: 6, color: animalName ? THEME.textMid : THEME.danger, fontStyle: animalName ? 'normal' : 'italic', fontSize: 12 }}>
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

  const sectionHeading = { ...heading, fontSize: 16, marginTop: 28, marginBottom: 12 };

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 560, margin: '0 auto', ...card }}>
      <h2 style={{ ...heading, fontSize: 24, marginBottom: 24 }}>New Order</h2>

      <label style={labelStyle}>Order number</label>
      <input style={inputStyle} required value={form.order_number}
             onChange={(e) => update('order_number', e.target.value)}
             placeholder="e.g. ORD-0001" />

      <label style={labelStyle}>Child's name</label>
      <input style={inputStyle} required value={form.child_name}
             onChange={(e) => update('child_name', e.target.value)} />

      <LetterVariantPicker tokens={tokens} variants={variantValues} onChange={setVariant} animalNames={animalNames} />

      <label style={labelStyle}>Gender</label>
      <select style={inputStyle} value={form.gender} onChange={(e) => update('gender', e.target.value)}>
        <option value="girl">Girl</option>
        <option value="boy">Boy</option>
      </select>

      <label style={labelStyle}>Tier</label>
      <select style={inputStyle} value={form.tier} onChange={(e) => update('tier', e.target.value)}>
        <option value="essential">Essential</option>
        <option value="signature">Signature</option>
        <option value="magical">Magical</option>
      </select>

      <label style={labelStyle}>Dedication text</label>
      <textarea style={{ ...inputStyle, height: 100, fontFamily: "'Nunito', sans-serif" }} value={form.dedication_text}
                onChange={(e) => update('dedication_text', e.target.value)} />

      <label style={labelStyle}>Photo URL (e.g. an ImgBB link)</label>
      <input style={inputStyle} value={form.photo_url}
             onChange={(e) => update('photo_url', e.target.value)} />

      <h3 style={sectionHeading}>Shipping</h3>
      <label style={labelStyle}>Recipient name</label>
      <input style={inputStyle} value={form.recipient_name}
             onChange={(e) => update('recipient_name', e.target.value)} />

      <label style={labelStyle}>Phone</label>
      <input style={inputStyle} value={form.phone}
             onChange={(e) => update('phone', e.target.value)} />

      <label style={labelStyle}>Province</label>
      <input style={inputStyle} value={form.province}
             onChange={(e) => update('province', e.target.value)} />

      <label style={labelStyle}>City</label>
      <input style={inputStyle} value={form.city}
             onChange={(e) => update('city', e.target.value)} />

      <label style={labelStyle}>Street address</label>
      <input style={inputStyle} value={form.street_address}
             onChange={(e) => update('street_address', e.target.value)} />

      <h3 style={sectionHeading}>Financials (optional, can fill in later)</h3>
      <label style={labelStyle}>Selling price</label>
      <input style={inputStyle} type="number" value={form.selling_price}
             onChange={(e) => update('selling_price', e.target.value)} />

      <label style={labelStyle}>Cost</label>
      <input style={inputStyle} type="number" value={form.cost}
             onChange={(e) => update('cost', e.target.value)} />

      {error && <p style={{ color: THEME.danger, fontSize: 13 }}>{error}</p>}

      <div style={{ marginTop: 20, display: 'flex', gap: 10 }}>
        <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create Order'}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
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
      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}
                style={{ ...inputStyle, width: 'auto', marginBottom: 0, padding: '9px 14px' }}>
          <option value="all">All statuses</option>
          {allStatusOptions.map((s) => (
            <option key={s} value={s}>{statusLabel(s)}</option>
          ))}
        </select>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="secondary" onClick={exportToExcel} disabled={!orders.length}>
            Export to Excel
          </Button>
          <Button onClick={onNewOrder}>+ New Order</Button>
        </div>
      </div>
      <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
        <table width="100%" cellPadding={0} style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', background: THEME.cream2 }}>
              <th style={{ padding: '12px 16px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Order #</th>
              <th style={{ padding: '12px 16px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Child</th>
              <th style={{ padding: '12px 16px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Tier</th>
              <th style={{ padding: '12px 16px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Status</th>
              <th style={{ padding: '12px 16px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} onClick={() => onSelect(o)}
                  style={{ borderTop: `1px solid ${THEME.border}`, cursor: 'pointer' }}
                  onMouseEnter={(e) => e.currentTarget.style.background = THEME.cream}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                <td style={{ padding: '14px 16px', fontWeight: 600 }}>{o.order_number}</td>
                <td style={{ padding: '14px 16px' }}>{o.child_name} ({o.gender})</td>
                <td style={{ padding: '14px 16px', color: THEME.textMid }}>{o.tier}</td>
                <td style={{ padding: '14px 16px' }}><StatusPill status={o.status} /></td>
                <td style={{ padding: '14px 16px', color: THEME.textSoft, fontSize: 13 }}>{new Date(o.created_at).toLocaleDateString()}</td>
                <td style={{ padding: '14px 16px' }}>
                  <Button variant="danger" onClick={(e) => handleDelete(e, o)}>
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
    <div style={{ marginTop: 20 }}>
      <p style={{ ...heading, fontSize: 14, marginBottom: 8 }}>Letter variants chosen</p>
      <div style={{ borderRadius: 12, overflow: 'hidden', border: `1.5px solid ${THEME.border}` }}>
        <table style={{ fontSize: 13, borderCollapse: 'collapse', width: '100%', background: '#fff' }}>
          <thead>
            <tr style={{ textAlign: 'left', background: THEME.cream2 }}>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Letter</th>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Key</th>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Case</th>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Occurrence</th>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Variant</th>
              <th style={{ padding: '6px 10px', color: THEME.textMid, fontWeight: 700 }}>Animal</th>
            </tr>
          </thead>
          <tbody>
            {letters.map((t, i) => {
              const v = letterVariantEntries[i];
              const occLabel = ['', '1st', '2nd', '3rd'][t.occIndex] || `${t.occIndex}th`;
              const animalName = v ? animalNames[`${v.key}-${v.variant}`] : null;
              return (
                <tr key={i} style={{ borderTop: `1px solid ${THEME.border}` }}>
                  <td style={{ padding: '6px 10px', fontWeight: 700, color: THEME.terra }}>{t.char}</td>
                  <td style={{ padding: '6px 10px', fontFamily: 'monospace', color: THEME.textSoft }}>{t.key}-{t.case}</td>
                  <td style={{ padding: '6px 10px' }}>{t.case === 'u' ? 'Upper' : 'Lower'}</td>
                  <td style={{ padding: '6px 10px', color: THEME.textSoft }}>{occLabel}</td>
                  <td style={{ padding: '6px 10px' }}>{v ? v.variant : '—'}</td>
                  <td style={{ padding: '6px 10px' }}>{animalName || '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
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
    <div style={{ marginTop: 20, padding: 18, borderRadius: 16, background: THEME.cream2, maxWidth: 320 }}>
      <p style={{ ...heading, fontSize: 14, marginBottom: 12 }}>Financials</p>
      <label style={labelStyle}>Selling price</label>
      <input type="number" style={{ ...inputStyle, marginBottom: 10 }}
             value={sellingPrice} onChange={(e) => setSellingPrice(e.target.value)} />
      <label style={labelStyle}>Cost</label>
      <input type="number" style={{ ...inputStyle, marginBottom: 10 }}
             value={cost} onChange={(e) => setCost(e.target.value)} />
      <p style={{ fontSize: 14, marginBottom: 14 }}>
        <strong style={{ color: THEME.text }}>Profit:</strong>{' '}
        <span style={{ color: THEME.terra, fontWeight: 700 }}>{profit === null ? '—' : profit.toLocaleString()}</span>
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save financials'}</Button>
        {justSaved && <span style={{ color: '#4A8F5C', fontSize: 13, fontWeight: 600 }}>✓ Saved</span>}
      </div>
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

  const selectStyle = { ...inputStyle, width: 'auto', marginBottom: 0, display: 'inline-block', padding: '7px 12px' };

  return (
    <div>
      <Button variant="ghost" onClick={onBack} style={{ ...buttonStyle('ghost'), paddingLeft: 0, marginBottom: 8 }}>&larr; Back to orders</Button>
      <h2 style={{ ...heading, fontSize: 26, marginBottom: 20 }}>{order.order_number} — {order.child_name}</h2>

      <div style={{ ...card, display: 'flex', gap: 40 }}>
        <div style={{ flex: 1 }}>
          <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Gender:</strong> {order.gender}</p>
          <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Tier:</strong> {order.tier}</p>
          <p style={{ margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong style={{ color: THEME.textMid }}>Status:</strong>
            <select value={order.status} onChange={(e) => handleStatusChange(e.target.value)} style={selectStyle}>
              {!STATUS_VALUES.includes(order.status) && (
                <option value={order.status}>{statusLabel(order.status)}</option>
              )}
              {STATUS_VALUES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
            </select>
          </p>
          <p style={{ margin: '16px 0 4px' }}><strong style={{ color: THEME.textMid }}>Dedication:</strong></p>
          <p style={{ whiteSpace: 'pre-wrap', maxWidth: 400, color: THEME.text, background: THEME.cream, padding: 12, borderRadius: 10, fontSize: 14 }}>{order.dedication_text}</p>
          <p style={{ marginTop: 16 }}><strong style={{ color: THEME.textMid }}>Shipping:</strong> {order.recipient_name}, {order.street_address}, {order.city}, {order.province} — {order.phone}</p>

          <LetterVariantsSummary order={order} animalNames={animalNames} />
          <FinancialsPanel order={order} />
        </div>
        <div>
          {order.photo_url && <img src={order.photo_url} alt="Child" width={200} style={{ borderRadius: 16, boxShadow: `0 4px 20px ${THEME.shadow}` }} />}
        </div>
      </div>

      <div style={{ marginTop: 24, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button onClick={handleGenerate} disabled={generating}>
          {generating ? 'Generating…' : 'Generate Book'}
        </Button>
        <Button onClick={handleGenerateCover} disabled={generatingCover} variant="secondary">
          {generatingCover ? 'Generating…' : 'Generate Cover'}
        </Button>
        <Button variant="danger" onClick={handleDelete}>Delete order</Button>
      </div>
      {error && <p style={{ color: THEME.danger, fontSize: 13, marginTop: 10 }}>{error}</p>}
      {coverError && <p style={{ color: THEME.danger, fontSize: 13, marginTop: 10 }}>{coverError}</p>}

      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {order.print_pdf_url && (
          <a href={order.print_pdf_url} target="_blank" rel="noreferrer" style={{ color: THEME.terra, fontWeight: 600, textDecoration: 'none' }}>
            Download print PDF →
          </a>
        )}
        {order.digital_pages_url && (
          <a href={order.digital_pages_url} target="_blank" rel="noreferrer" style={{ color: THEME.terra, fontWeight: 600, textDecoration: 'none' }}>
            Digital pages PDF (for Heyzine) →
          </a>
        )}
        {order.cover_pdf_url && (
          <a href={order.cover_pdf_url} target="_blank" rel="noreferrer" style={{ color: THEME.terra, fontWeight: 600, textDecoration: 'none' }}>
            Download cover PDF →
          </a>
        )}
      </div>
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
    <div style={pageWrap}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        <h1 style={{ ...heading, fontSize: 30, marginBottom: 28 }}>Amiya Publishing — Orders</h1>
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
    </div>
  );
}
