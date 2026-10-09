const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
const inrCompact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', notation: 'compact', maximumFractionDigits: 2 });
const qty = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 6 });
const dateFmt = new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function money(value: string | null | undefined, compact = false): string {
  if (value === null || value === undefined || value === '') return '—';
  return (compact ? inrCompact : inr).format(Number(value));
}

export function quantity(value: string | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return qty.format(Number(value));
}

export function percent(value: string | null | undefined, signed = false): string {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  const sign = signed && n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

export function date(value: string | null | undefined): string {
  if (!value) return '—';
  return dateFmt.format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

const ACRONYMS = new Set(['ETF', 'REIT', 'GSEC', 'HNI', 'KYC']);

export function humanize(value: string): string {
  return value
    .split('_')
    .map((w) => (ACRONYMS.has(w) ? (w === 'GSEC' ? 'G-Sec' : w) : w.charAt(0) + w.slice(1).toLowerCase()))
    .join(' ');
}

/** Sign class for gains/losses: colour is never the only cue (values also carry +/−). */
export function signClass(value: string | null | undefined): string {
  if (!value) return '';
  const n = Number(value);
  return n > 0 ? 'positive' : n < 0 ? 'negative' : '';
}
