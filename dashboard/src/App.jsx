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
  pending_payment: 'Pending payment',
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

function buildLetterVariants(tokens, variantValues) {
  let letterIdx = 0;
  return tokens
    .filter((t) => t.type === 'letter' || t.type === 'hyphen')
    .map((t) => {
      if (t.type === 'hyphen') {
        return { key: '-', case: null, variant: null };
      }
      const v = { key: t.key, case: t.case, variant: String(variantValues[letterIdx] || 1) };
      letterIdx += 1;
      return v;
    });
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
                  <td style={{ padding: '6px 10px', fontSize: 16, fontWeight: 700, color: THEME.terra }}>{t.char}</td>
                  <td style={{ fontFamily: 'monospace', color: THEME.textSoft }}>{t.key}-{t.case}</td>
                  <td>{t.case === 'u' ? 'Upper' : 'Lower'}</td>
                  <td style={{ color: THEME.textSoft }}>{occLabel}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
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
                      <span style={{ marginLeft: 8, color: animalName ? THEME.textMid : THEME.danger, fontStyle: animalName ? 'normal' : 'italic', fontSize: 12 }}>
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

    const letter_variants = buildLetterVariants(tokens, variantValues);

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
        <option value="premium">Premium</option>
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
    // pending_payment = customer reached checkout but hasn't (yet, or
    // ever) completed payment -- excluded from the default "all" view so
    // abandoned carts don't clutter the real order list. Still fully
    // visible by explicitly selecting that filter.
    if (filter === 'all') query = query.neq('status', 'pending_payment');
    else query = query.eq('status', filter);
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
        'Email': o.email,
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

  const allStatusOptions = ['pending_payment', ...STATUS_VALUES, 'generating'];

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

function LetterVariantsSection({ order, animalNames }) {
  const tokens = parseNameTokens(order.child_name);
  const letters = tokens.filter((t) => t.type === 'letter');
  const initialEntries = (order.letter_variants || []).filter((v) => v.key !== '-');
  const initialComplete = letters.length > 0 && initialEntries.length === letters.length
    && initialEntries.every((v) => v.variant != null);

  // Track the latest saved variants locally, rather than only reading
  // order.letter_variants -- this way the read-only view reflects a save
  // immediately, without depending on the parent's order prop refreshing.
  const [savedEntries, setSavedEntries] = useState(initialEntries);
  const [editing, setEditing] = useState(!initialComplete);
  const [variantValues, setVariantValues] = useState(() =>
    letters.map((t, i) => Number(initialEntries[i]?.variant) || 1)
  );
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  if (!letters.length) return null;

  function setVariant(idx, val) {
    setVariantValues((v) => {
      const copy = [...v];
      copy[idx] = val;
      return copy;
    });
  }

  async function handleSave() {
    setSaving(true);
    const letter_variants = buildLetterVariants(tokens, variantValues);
    await supabase.from('orders').update({ letter_variants }).eq('id', order.id);
    setSaving(false);
    setEditing(false);
    setSavedEntries(letter_variants.filter((v) => v.key !== '-'));
    setJustSaved(true);
    setTimeout(() => setJustSaved(false), 2500);
  }

  const hasAllVariantsSet = savedEntries.length === letters.length && savedEntries.every((v) => v.variant != null);

  if (editing) {
    return (
      <div style={{ marginTop: 20 }}>
        <p style={{ ...heading, fontSize: 14, marginBottom: 8 }}>Letter variants</p>
        <LetterVariantPicker tokens={tokens} variants={variantValues} onChange={setVariant} animalNames={animalNames} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save letter variants'}</Button>
          {hasAllVariantsSet && (
            <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <p style={{ ...heading, fontSize: 14, margin: 0 }}>Letter variants chosen</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {justSaved && <span style={{ color: '#4A8F5C', fontSize: 13, fontWeight: 600 }}>✓ Saved</span>}
          <Button variant="secondary" onClick={() => setEditing(true)}>Edit variants</Button>
        </div>
      </div>
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
              const v = savedEntries[i];
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

// Editing the child's name. Letter variants are picked per letter of the
// name, so a new name clears them -- they must be picked again (and the
// book regenerated, if it was already generated with the old name).
function ChildNameSection({ order, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(order.child_name || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const hadVariants = (order.letter_variants || []).length > 0;
  const changed = name.trim() !== order.child_name;

  async function handleSave() {
    const newName = name.trim();
    if (!newName) { setError('Name can\'t be empty'); return; }
    if (!parseNameTokens(newName).some((t) => t.type === 'letter')) {
      setError('Use Cyrillic letters only'); return;
    }
    setSaving(true);
    setError(null);
    const patch = { child_name: newName, letter_variants: [] };
    const { error: err } = await supabase.from('orders').update(patch).eq('id', order.id);
    setSaving(false);
    if (err) { setError(err.message); return; }
    setEditing(false);
    onChanged(patch);
  }

  if (!editing) {
    return (
      <p style={{ margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <strong style={{ color: THEME.textMid }}>Child name:</strong> {order.child_name}
        <Button variant="ghost" onClick={() => { setName(order.child_name || ''); setEditing(true); }}>Edit</Button>
      </p>
    );
  }

  return (
    <div style={{ margin: '0 0 12px', padding: 14, borderRadius: 14, background: THEME.cream2, maxWidth: 400 }}>
      <label style={labelStyle}>Child name</label>
      <input style={{ ...inputStyle, marginBottom: 8 }} value={name} maxLength={30}
             onChange={(e) => setName(e.target.value)} autoFocus />
      {changed && hadVariants && (
        <p style={{ fontSize: 12, color: THEME.danger, margin: '0 0 8px' }}>
          Saving a new name clears the letter variants — you'll pick them again for the new letters.
          {order.print_pdf_url ? ' Regenerate the book and cover afterwards.' : ''}
        </p>
      )}
      {error && <p style={{ fontSize: 12, color: THEME.danger, margin: '0 0 8px' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 10 }}>
        <Button onClick={handleSave} disabled={saving || !changed}>{saving ? 'Saving…' : 'Save name'}</Button>
        <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
      </div>
    </div>
  );
}

function DedicationSection({ order }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(order.dedication_text || '');
  const [savedText, setSavedText] = useState(order.dedication_text || '');
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    await supabase.from('orders').update({ dedication_text: text }).eq('id', order.id);
    setSaving(false);
    setEditing(false);
    setSavedText(text);
    setJustSaved(true);
    setTimeout(() => setJustSaved(false), 2500);
  }

  function handleCancel() {
    setText(savedText);
    setEditing(false);
  }

  if (editing) {
    return (
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <strong style={{ color: THEME.textMid }}>Dedication:</strong>
          <span style={{ fontSize: 12, color: THEME.textSoft }}>{text.length} / 1200</span>
        </div>
        <textarea
          value={text}
          maxLength={1200}
          onChange={(e) => setText(e.target.value)}
          style={{ ...inputStyle, minHeight: 110, maxWidth: 400, marginBottom: 8 }}
        />
        <div style={{ display: 'flex', gap: 10 }}>
          <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save dedication'}</Button>
          <Button variant="ghost" onClick={handleCancel}>Cancel</Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <strong style={{ color: THEME.textMid }}>Dedication:</strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {justSaved && <span style={{ color: '#4A8F5C', fontSize: 13, fontWeight: 600 }}>✓ Saved</span>}
          <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
        </div>
      </div>
      <p style={{ whiteSpace: 'pre-wrap', maxWidth: 400, color: THEME.text, background: THEME.cream, padding: 12, borderRadius: 10, fontSize: 14 }}>{savedText}</p>
    </div>
  );
}

// Mirrors the standalone URL Generator tool's exact encoding logic
// (variants grouped by key+case in occurrence order, dot-notation for
// repeats, whole group skipped if every occurrence is the default variant
// 1) -- built from data already on the order, so nothing needs re-typing.
function buildVariantsUrlParam(tokens, letterVariantEntries) {
  const letters = tokens.filter((t) => t.type === 'letter');
  const groups = {};
  letters.forEach((t, i) => {
    const kc = `${t.key}-${t.case}`;
    if (!groups[kc]) groups[kc] = [];
    groups[kc].push(Number(letterVariantEntries[i]?.variant) || 1);
  });
  const parts = [];
  for (const [kc, vals] of Object.entries(groups)) {
    if (vals.length === 1) {
      if (vals[0] === 1) continue;
      parts.push(`${kc}:${vals[0]}`);
    } else {
      if (vals.every((x) => x === 1)) continue;
      parts.push(`${kc}:${vals.join('.')}`);
    }
  }
  return parts.join(',');
}

function getNameUrlVal(tokens) {
  return tokens.map((t) => (t.type === 'hyphen' ? '-' : t.case === 'u' ? t.char : t.char.toLowerCase())).join('');
}

// Same resize approach as the checkout site's onPhoto handler -- caps
// the longest side at 2000px and re-encodes as JPEG q0.85, comfortably
// covering the 140mm print photo box at true 300dpi (needs ~1654px)
// while keeping the upload small and reliable.
function resizeImageFile(file, maxDim, quality) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > maxDim || height > maxDim) {
          if (width > height) { height = Math.round(height * (maxDim / width)); width = maxDim; }
          else { width = Math.round(width * (maxDim / height)); height = maxDim; }
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = () => resolve(e.target.result); // fall back to the original rather than fail
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

function PhotoSection({ order }) {
  const [photoUrl, setPhotoUrl] = useState(order.photo_url);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [justUploaded, setJustUploaded] = useState(false);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const dataUrl = await resizeImageFile(file, 2000, 0.85);
      const base64 = dataUrl.split(',')[1];
      const contentType = dataUrl.split(';')[0].split(':')[1];

      const res = await fetch(`${GENERATION_SERVICE_URL}/upload-photo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_number: order.order_number,
          image_base64: base64,
          content_type: contentType,
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.detail || `upload failed (${res.status})`);
      }
      const result = await res.json();

      await supabase.from('orders').update({ photo_url: result.photo_url }).eq('id', order.id);
      setPhotoUrl(result.photo_url);
      setJustUploaded(true);
      setTimeout(() => setJustUploaded(false), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = ''; // allow re-selecting the same file again if needed
    }
  }

  return (
    <div>
      {photoUrl && (
        <img src={photoUrl} alt="Child" width={200}
             style={{ borderRadius: 16, boxShadow: `0 4px 20px ${THEME.shadow}`, display: 'block', marginBottom: 10 }} />
      )}
      <label style={{ ...buttonStyle('secondary', uploading), display: 'inline-block', cursor: uploading ? 'default' : 'pointer' }}>
        {uploading ? 'Uploading…' : photoUrl ? 'Replace photo' : 'Upload photo'}
        <input type="file" accept="image/*" onChange={handleFileChange} disabled={uploading} style={{ display: 'none' }} />
      </label>
      {justUploaded && <p style={{ color: '#4A8F5C', fontSize: 13, fontWeight: 600, marginTop: 6 }}>✓ Saved</p>}
      {error && <p style={{ color: THEME.danger, fontSize: 13, marginTop: 6 }}>{error}</p>}
    </div>
  );
}

function DigitalBookUrlSection({ order }) {
  const [from, setFrom] = useState('');
  const [book, setBook] = useState(order.heyzine_book_id || '');
  const [copied, setCopied] = useState(false);

  const tokens = parseNameTokens(order.child_name);
  const letters = tokens.filter((t) => t.type === 'letter');
  const letterVariantEntries = (order.letter_variants || []).filter((v) => v.key !== '-');
  const variantsComplete = letters.length > 0 && letterVariantEntries.length === letters.length
    && letterVariantEntries.every((v) => v.variant != null);

  if (!letters.length) return null;

  if (!variantsComplete) {
    return (
      <div style={{ marginTop: 20 }}>
        <p style={{ ...heading, fontSize: 14, marginBottom: 4 }}>Digital book preview link</p>
        <p style={{ fontSize: 13, color: THEME.textSoft, fontStyle: 'italic' }}>
          Set letter variants above first -- the preview link needs to know which art each letter uses.
        </p>
      </div>
    );
  }

  const animal = order.gender === 'boy' ? 'Арслан' : 'Цагаан баавгай';
  const variants = buildVariantsUrlParam(tokens, letterVariantEntries);
  const p = new URLSearchParams();
  p.set('name', getNameUrlVal(tokens));
  p.set('gender', order.gender);
  p.set('animal', animal);
  if (from.trim()) p.set('from', from.trim());
  if (book.trim()) p.set('book', book.trim());
  p.set('hearts', '1');
  if (variants) p.set('variants', variants);
  const url = 'https://book.amiyapublishing.com/?' + p.toString();

  function handleCopy() {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{ marginTop: 20, padding: 18, borderRadius: 16, background: THEME.cream2, maxWidth: 420 }}>
      <p style={{ ...heading, fontSize: 14, marginBottom: 12 }}>Digital book preview link</p>

      <label style={labelStyle}>From (optional)</label>
      <input style={{ ...inputStyle, marginBottom: 10 }} value={from} onChange={(e) => setFrom(e.target.value)} />

      <label style={labelStyle}>Heyzine Book ID (auto-filled after Generate Book; edit if needed)</label>
      <input style={{ ...inputStyle, marginBottom: 10 }} value={book} onChange={(e) => setBook(e.target.value)} />

      <p style={{ fontSize: 12, color: THEME.textSoft, wordBreak: 'break-all', background: '#fff',
                  padding: 10, borderRadius: 8, marginBottom: 10, border: `1px solid ${THEME.border}` }}>
        {url}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Button variant="secondary" onClick={handleCopy}>{copied ? '✓ Copied' : 'Copy link'}</Button>
        <a href={url} target="_blank" rel="noreferrer" style={{ color: THEME.terra, fontWeight: 600, fontSize: 13, textDecoration: 'none' }}>
          Open preview →
        </a>
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

function OrderDetail({ order, onBack, onUpdated, onChanged, animalNames }) {
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
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(`Generation failed (${res.status}): ${errBody?.detail || 'unknown error'}`);
      }
      const result = await res.json();

      await supabase.from('orders').update({
        status: 'ready',
        print_pdf_url: result.print_pdf_url,
        digital_pages_url: result.digital_pages_url,
        ...(result.heyzine_book_id ? { heyzine_book_id: result.heyzine_book_id } : {}),
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
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(`Cover generation failed (${res.status}): ${errBody?.detail || 'unknown error'}`);
      }
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
          <ChildNameSection order={order} onChanged={onChanged} />
          <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Gender:</strong> {order.gender}</p>
          <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Tier:</strong> {order.tier}</p>
          {order.promo_code && (
            <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Code used:</strong> {order.promo_code}
              {order.discount_amount != null && <span style={{ color: THEME.textSoft }}> (−₮{Number(order.discount_amount).toLocaleString('en-US')})</span>}</p>
          )}
          <p style={{ margin: '0 0 8px' }}><strong style={{ color: THEME.textMid }}>Email:</strong> {order.email || '—'}</p>
          <p style={{ margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong style={{ color: THEME.textMid }}>Status:</strong>
            <select value={order.status} onChange={(e) => handleStatusChange(e.target.value)} style={selectStyle}>
              {!STATUS_VALUES.includes(order.status) && (
                <option value={order.status}>{statusLabel(order.status)}</option>
              )}
              {STATUS_VALUES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
            </select>
          </p>
          <DedicationSection order={order} />
          <p style={{ marginTop: 16 }}><strong style={{ color: THEME.textMid }}>Shipping:</strong> {order.recipient_name}, {order.street_address}, {order.city}, {order.province} — {order.phone}</p>

          <LetterVariantsSection order={order} animalNames={animalNames} />
          <FinancialsPanel order={order} />
          <DigitalBookUrlSection order={order} />
        </div>
        <div>
          <PhotoSection order={order} />
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

// =====================================================================
// Codes & gift cards
// Reads/writes the promo_codes table that the checkout site uses.
//   type 'percent'   -> discount codes you create here
//   type 'gift_card' -> bought on the website (or made here by hand)
// =====================================================================
const SITE_URL = 'https://amiyapublishing.com';
const TIER_SHORT = { signature: 'Signature', premium: 'Premium' };
const CODE_STATUS = {
  active:   { label: 'Active',   color: '#4A8F5C' },
  used:     { label: 'Used',     color: THEME.textSoft },
  disabled: { label: 'Disabled', color: THEME.danger },
  pending_payment: { label: 'Not paid', color: THEME.gold },
};
// Same alphabet as the website: no 0/O, 1/I/L, so printed codes can't be mistyped
const GIFT_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
function newGiftCode() {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return 'AMIYA-GIFT-' + Array.from(bytes, (b) => GIFT_ALPHABET[b % GIFT_ALPHABET.length]).join('');
}
const thStyle = { padding: '10px 14px', color: THEME.textMid, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', textAlign: 'left' };
const tdStyle = { padding: '12px 14px', fontSize: 13, verticalAlign: 'top' };
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString() : '—');
const fmtMnt = (n) => (n == null ? '—' : '₮' + Number(n).toLocaleString('en-US'));

function CodeStatusPill({ status }) {
  const st = CODE_STATUS[status] || { label: status, color: THEME.textSoft };
  return (
    <span style={{ display: 'inline-block', fontFamily: "'Comfortaa', cursive", fontWeight: 700, fontSize: 11,
                   padding: '4px 12px', borderRadius: 100, background: `${st.color}1A`, color: st.color }}>
      {st.label}
    </span>
  );
}

function NewDiscountCodeForm({ onCreated }) {
  const [code, setCode] = useState('');
  const [percent, setPercent] = useState('');
  const [expires, setExpires] = useState('');
  const [maxUses, setMaxUses] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleCreate(e) {
    e.preventDefault();
    const c = code.trim().toUpperCase().replace(/\s+/g, '');
    const pct = Number(percent);
    if (!/^[A-Z0-9-]{3,30}$/.test(c)) { setError('Code: 3–30 letters/numbers (Latin), no spaces'); return; }
    if (!(pct >= 1 && pct <= 100)) { setError('Percent must be between 1 and 100'); return; }
    if (maxUses !== '' && !(Number(maxUses) >= 1)) { setError('Max uses must be 1 or more, or empty for unlimited'); return; }
    setSaving(true); setError(null);
    const { error: err } = await supabase.from('promo_codes').insert([{
      code: c,
      type: 'percent',
      percent: pct,
      // the code works until the end of that day, Ulaanbaatar time
      expires_at: expires ? `${expires}T23:59:59+08:00` : null,
      max_uses: maxUses === '' ? null : Number(maxUses),
      note: note.trim() || null,
    }]);
    setSaving(false);
    if (err) { setError(err.code === '23505' ? 'That code already exists' : err.message); return; }
    setCode(''); setPercent(''); setExpires(''); setMaxUses(''); setNote('');
    onCreated();
  }

  return (
    <form onSubmit={handleCreate} style={{ ...card, marginBottom: 20 }}>
      <p style={{ ...heading, fontSize: 16, marginBottom: 14 }}>New discount code</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0 14px' }}>
        <div><label style={labelStyle}>Code</label>
          <input style={{ ...inputStyle, textTransform: 'uppercase' }} value={code} onChange={(e) => setCode(e.target.value)} placeholder="NAMAR15" /></div>
        <div><label style={labelStyle}>Percent off</label>
          <input style={inputStyle} type="number" min="1" max="100" value={percent} onChange={(e) => setPercent(e.target.value)} placeholder="15" /></div>
        <div><label style={labelStyle}>Last day (optional)</label>
          <input style={inputStyle} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} /></div>
        <div><label style={labelStyle}>Max orders (optional)</label>
          <input style={inputStyle} type="number" min="1" value={maxUses} onChange={(e) => setMaxUses(e.target.value)} placeholder="Unlimited" /></div>
      </div>
      <label style={labelStyle}>Note (optional)</label>
      <input style={inputStyle} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Sarnai's Instagram followers" />
      {error && <p style={{ color: THEME.danger, fontSize: 13, margin: '0 0 10px' }}>{error}</p>}
      <Button type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create code'}</Button>
      <p style={{ fontSize: 12, color: THEME.textSoft, margin: '10px 0 0' }}>
        Takes the percent off the book price (not the long-name fee). One code per order; customers can type it in any case.
      </p>
    </form>
  );
}

function NewGiftCardForm({ onCreated }) {
  const [tier, setTier] = useState('premium');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);

  async function handleCreate(e) {
    e.preventDefault();
    if (!from.trim() || !to.trim()) { setError('Fill in From and To'); return; }
    setSaving(true); setError(null);
    for (let attempt = 0; attempt < 4; attempt++) {
      const code = newGiftCode();
      const { error: err } = await supabase.from('promo_codes').insert([{
        code, type: 'gift_card', tier, status: 'active', max_uses: 1,
        from_name: from.trim(), to_name: to.trim(),
        activated_at: new Date().toISOString(),
        note: note.trim() || 'Made in dashboard',
      }]);
      if (!err) {
        setSaving(false); setCreated(code); setFrom(''); setTo(''); setNote('');
        onCreated();
        return;
      }
      if (err.code !== '23505') { setSaving(false); setError(err.message); return; }
    }
    setSaving(false); setError('Could not create a unique code, try again');
  }

  return (
    <form onSubmit={handleCreate} style={{ ...card, marginBottom: 20 }}>
      <p style={{ ...heading, fontSize: 16, marginBottom: 6 }}>Make a gift card by hand</p>
      <p style={{ fontSize: 12, color: THEME.textSoft, margin: '0 0 14px' }}>
        For giveaways or cards paid outside the website. Cards bought on the website appear below automatically.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0 14px' }}>
        <div><label style={labelStyle}>Package</label>
          <select style={inputStyle} value={tier} onChange={(e) => setTier(e.target.value)}>
            <option value="premium">Premium</option>
            <option value="signature">Signature</option>
          </select></div>
        <div><label style={labelStyle}>From (Хэнээс)</label>
          <input style={inputStyle} value={from} maxLength={40} onChange={(e) => setFrom(e.target.value)} /></div>
        <div><label style={labelStyle}>To (Хэнд)</label>
          <input style={inputStyle} value={to} maxLength={40} onChange={(e) => setTo(e.target.value)} /></div>
      </div>
      <label style={labelStyle}>Note (optional)</label>
      <input style={inputStyle} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Instagram giveaway October" />
      {error && <p style={{ color: THEME.danger, fontSize: 13, margin: '0 0 10px' }}>{error}</p>}
      <Button type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create gift card'}</Button>
      {created && (
        <p style={{ fontSize: 13, margin: '12px 0 0' }}>
          ✓ Created <strong>{created}</strong> —{' '}
          <a href={`${SITE_URL}/?gift=${created}`} target="_blank" rel="noreferrer" style={{ color: THEME.terra, fontWeight: 600 }}>
            open the card to download
          </a>
        </p>
      )}
    </form>
  );
}

function CodesPage() {
  const [view, setView] = useState('gift_card');
  const [rows, setRows] = useState([]);
  const [showUnpaid, setShowUnpaid] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [copied, setCopied] = useState(null);

  useEffect(() => { load(); }, [view]);

  async function load() {
    const { data, error } = await supabase.from('promo_codes').select('*')
      .eq('type', view).order('created_at', { ascending: false });
    setLoadError(error ? error.message : null);
    setRows(data || []);
  }

  async function setStatus(row, status) {
    await supabase.from('promo_codes').update({ status }).eq('id', row.id);
    load();
  }

  function copyLink(code) {
    navigator.clipboard.writeText(`${SITE_URL}/?gift=${code}`).then(() => {
      setCopied(code); setTimeout(() => setCopied(null), 2000);
    });
  }

  const visible = rows.filter((r) => showUnpaid || r.status !== 'pending_payment');
  const sold = rows.filter((r) => r.type === 'gift_card' && r.code && r.price_paid != null);
  const soldTotal = sold.reduce((sum, r) => sum + (r.price_paid || 0), 0);
  const tabBtn = (v, label) => (
    <button type="button" onClick={() => setView(v)}
            style={{ ...buttonStyle(view === v ? 'primary' : 'secondary'), padding: '9px 20px' }}>{label}</button>
  );

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {tabBtn('gift_card', 'Gift cards')}
        {tabBtn('percent', 'Discount codes')}
      </div>

      {loadError && (
        <div style={{ ...card, marginBottom: 20, color: THEME.danger, fontSize: 13 }}>
          Couldn't load codes: {loadError}. If it says "permission denied", run
          <code> schema/migration_promo_codes_dashboard.sql</code> in Supabase's SQL editor.
        </div>
      )}

      {view === 'percent' ? (
        <>
          <NewDiscountCodeForm onCreated={load} />
          <div style={{ ...card, padding: 0, overflow: 'auto' }}>
            <table width="100%" style={{ borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: THEME.cream2 }}>
                <th style={thStyle}>Code</th><th style={thStyle}>Off</th><th style={thStyle}>Used</th>
                <th style={thStyle}>Last day</th><th style={thStyle}>Status</th><th style={thStyle}>Note</th><th style={thStyle}></th>
              </tr></thead>
              <tbody>
                {visible.map((r) => {
                  const expired = r.expires_at && new Date(r.expires_at) <= new Date();
                  return (
                    <tr key={r.id} style={{ borderTop: `1px solid ${THEME.border}` }}>
                      <td style={{ ...tdStyle, fontWeight: 700, fontFamily: 'monospace', fontSize: 14 }}>{r.code}</td>
                      <td style={tdStyle}>{r.percent}%</td>
                      <td style={tdStyle}>{r.used_count}{r.max_uses != null ? ` / ${r.max_uses}` : ''} orders</td>
                      <td style={{ ...tdStyle, color: expired ? THEME.danger : THEME.text }}>
                        {r.expires_at ? new Date(r.expires_at).toLocaleDateString() + (expired ? ' (ended)' : '') : 'No end'}
                      </td>
                      <td style={tdStyle}><CodeStatusPill status={r.status} /></td>
                      <td style={{ ...tdStyle, color: THEME.textSoft, maxWidth: 200 }}>{r.note || ''}</td>
                      <td style={tdStyle}>
                        {r.status === 'active' && <Button variant="danger" onClick={() => setStatus(r, 'disabled')}>Turn off</Button>}
                        {r.status === 'disabled' && <Button variant="secondary" onClick={() => setStatus(r, 'active')}>Turn on</Button>}
                      </td>
                    </tr>
                  );
                })}
                {!visible.length && <tr><td colSpan={7} style={{ ...tdStyle, color: THEME.textSoft, textAlign: 'center', padding: 24 }}>No discount codes yet</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <>
          <div style={{ ...card, marginBottom: 20, display: 'flex', gap: 40, flexWrap: 'wrap' }}>
            <div><div style={{ fontSize: 12, color: THEME.textSoft, fontWeight: 700, textTransform: 'uppercase' }}>Sold on website</div>
              <div style={{ ...heading, fontSize: 24, color: THEME.terra }}>{sold.length}</div></div>
            <div><div style={{ fontSize: 12, color: THEME.textSoft, fontWeight: 700, textTransform: 'uppercase' }}>Total paid</div>
              <div style={{ ...heading, fontSize: 24, color: THEME.terra }}>{fmtMnt(soldTotal)}</div></div>
            <div><div style={{ fontSize: 12, color: THEME.textSoft, fontWeight: 700, textTransform: 'uppercase' }}>Not used yet</div>
              <div style={{ ...heading, fontSize: 24, color: THEME.terra }}>{rows.filter((r) => r.status === 'active').length}</div></div>
          </div>
          <NewGiftCardForm onCreated={load} />
          <label style={{ fontSize: 13, color: THEME.textMid, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <input type="checkbox" checked={showUnpaid} onChange={(e) => setShowUnpaid(e.target.checked)} />
            Show unpaid attempts (someone opened the payment QR but didn't pay)
          </label>
          <div style={{ ...card, padding: 0, overflow: 'auto' }}>
            <table width="100%" style={{ borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: THEME.cream2 }}>
                <th style={thStyle}>Code</th><th style={thStyle}>Package</th><th style={thStyle}>From → To</th>
                <th style={thStyle}>Buyer</th><th style={thStyle}>Paid</th><th style={thStyle}>Status</th><th style={thStyle}></th>
              </tr></thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.id} style={{ borderTop: `1px solid ${THEME.border}` }}>
                    <td style={{ ...tdStyle, fontWeight: 700, fontFamily: 'monospace', fontSize: 13 }}>
                      {r.code || '—'}
                      <div style={{ fontFamily: "'Nunito', sans-serif", fontWeight: 400, color: THEME.textSoft, fontSize: 12 }}>{fmtDate(r.activated_at || r.created_at)}</div>
                    </td>
                    <td style={tdStyle}>{TIER_SHORT[r.tier] || r.tier}</td>
                    <td style={tdStyle}>{r.from_name} → {r.to_name}</td>
                    <td style={{ ...tdStyle, color: THEME.textMid }}>
                      {r.buyer_phone || ''}{r.buyer_email ? <div style={{ fontSize: 12 }}>{r.buyer_email}</div> : null}
                      {!r.buyer_phone && !r.buyer_email && <span style={{ color: THEME.textSoft }}>{r.note || '—'}</span>}
                    </td>
                    <td style={tdStyle}>{fmtMnt(r.price_paid)}</td>
                    <td style={tdStyle}>
                      <CodeStatusPill status={r.status} />
                      {r.used_order_number && <div style={{ fontSize: 12, color: THEME.textSoft, marginTop: 4 }}>on {r.used_order_number}</div>}
                    </td>
                    <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                      {r.code && (
                        <Button variant="ghost" onClick={() => copyLink(r.code)}>{copied === r.code ? '✓ Copied' : 'Copy link'}</Button>
                      )}
                      {r.status === 'active' && <Button variant="danger" onClick={() => setStatus(r, 'disabled')}>Turn off</Button>}
                      {r.status === 'disabled' && <Button variant="secondary" onClick={() => setStatus(r, 'active')}>Turn on</Button>}
                    </td>
                  </tr>
                ))}
                {!visible.length && <tr><td colSpan={7} style={{ ...tdStyle, color: THEME.textSoft, textAlign: 'center', padding: 24 }}>No gift cards yet</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [showNewOrder, setShowNewOrder] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [page, setPage] = useState('orders');
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
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 28 }}>
          <h1 style={{ ...heading, fontSize: 30 }}>Amiya Publishing — {page === 'codes' ? 'Codes & gift cards' : 'Orders'}</h1>
          <div style={{ display: 'flex', gap: 6 }}>
            <Button variant={page === 'orders' ? 'primary' : 'ghost'} onClick={() => { setPage('orders'); setSelectedOrder(null); setShowNewOrder(false); }}>Orders</Button>
            <Button variant={page === 'codes' ? 'primary' : 'ghost'} onClick={() => setPage('codes')}>Codes & gift cards</Button>
          </div>
        </div>
        {page === 'codes' ? (
          <CodesPage />
        ) : showNewOrder ? (
          <NewOrderForm
            onCreated={() => { setShowNewOrder(false); setRefreshKey((k) => k + 1); }}
            onCancel={() => setShowNewOrder(false)}
          />
        ) : selectedOrder ? (
          <OrderDetail
            key={`${selectedOrder.id}-${selectedOrder.child_name}`}
            order={selectedOrder}
            onChanged={(patch) => setSelectedOrder((o) => ({ ...o, ...patch }))}
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
