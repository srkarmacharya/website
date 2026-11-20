// Reads the CSV history files in /data at build time and shapes them into
// chart-ready series. Edit the CATEGORY lists below to change what is charted.
import fs from 'node:fs';
import path from 'node:path';

export interface Series { key: string; name: string; unit: string; values: (number | null)[] }
export interface Category {
  id: string;
  title: string;
  subtitle: string;
  source: string;
  sourceUrl: string;
  dates: string[];
  series: Series[];
  updated: string | null;
}

const DATA_DIR = path.resolve('data');

function readCsv(file: string): Record<string, string>[] {
  const p = path.join(DATA_DIR, file);
  if (!fs.existsSync(p)) return [];
  const text = fs.readFileSync(p, 'utf8').trim();
  if (!text) return [];
  const [head, ...rows] = text.split(/\r?\n/);
  const cols = parseLine(head);
  return rows.filter(Boolean).map((r) => {
    const cells = parseLine(r);
    const o: Record<string, string> = {};
    cols.forEach((c, i) => (o[c] = cells[i] ?? ''));
    return o;
  });
}

function parseLine(line: string): string[] {
  const out: string[] = [];
  let cur = '', q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') q = false;
      else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ',') { out.push(cur); cur = ''; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

/** Build aligned series: one shared date axis, each series' value per date (or null). */
function build(
  rows: { date: string; key: string; value: number }[],
  defs: { key: string; name: string; unit: string }[],
) {
  const dates = [...new Set(rows.map((r) => r.date))].sort();
  const idx = new Map(dates.map((d, i) => [d, i]));
  const series: Series[] = defs.map((d) => ({ ...d, values: new Array(dates.length).fill(null) }));
  const sIdx = new Map(series.map((s, i) => [s.key, i]));
  for (const r of rows) {
    const si = sIdx.get(r.key);
    const di = idx.get(r.date);
    if (si === undefined || di === undefined || !Number.isFinite(r.value)) continue;
    series[si].values[di] = r.value;
  }
  const kept = series.filter((s) => s.values.some((v) => v !== null));
  return { dates, series: kept, updated: dates.length ? dates[dates.length - 1] : null };
}

// ---------- Currencies (Nepal Rastra Bank) ----------
const CURRENCIES = [
  { key: 'USD', name: 'US dollar' },
  { key: 'EUR', name: 'Euro' },
  { key: 'GBP', name: 'UK pound' },
  { key: 'SAR', name: 'Saudi riyal' },
  { key: 'QAR', name: 'Qatari riyal' },
  { key: 'MYR', name: 'Malaysian ringgit' },
];

function currencies(): Category {
  const rows = readCsv('forex.csv')
    .map((r) => ({ date: r.date, key: r.iso3, value: Number(r.buy) / (Number(r.unit) || 1) }));
  const b = build(rows, CURRENCIES.map((c) => ({ ...c, unit: 'NPR per unit' })));
  return {
    id: 'currencies', title: 'Currencies', subtitle: 'NPR per unit · official buying rate',
    source: 'Nepal Rastra Bank', sourceUrl: 'https://www.nrb.org.np/forex/', ...b,
  };
}

// ---------- Bullion (FENEGOSIDA) ----------
const BULLION = [
  { key: 'fine_gold', name: 'Fine gold' },
  { key: 'tejabi_gold', name: 'Tejabi gold' },
  { key: 'silver', name: 'Silver' },
];

function bullion(): Category {
  const rows = readCsv('bullion.csv')
    .filter((r) => r.unit === 'tola')
    .map((r) => ({ date: r.date, key: r.item, value: Number(r.price) }));
  const b = build(rows, BULLION.map((c) => ({ ...c, unit: 'NPR per tola' })));
  return {
    id: 'bullion', title: 'Bullion', subtitle: 'NPR per tola',
    source: 'FENEGOSIDA', sourceUrl: 'https://www.fenegosida.org/', ...b,
  };
}

// ---------- Kalimati (vegetables & fruits) ----------
// Kalimati's item names vary slightly over time, so each chart line matches a pattern.
const VEGETABLES = [
  { key: 'tomato', name: 'Tomato (big)', match: /^tomato big/ },
  { key: 'potato', name: 'Potato (red)', match: /^potato red( long)?$/ },
  { key: 'onion', name: 'Onion (dry)', match: /^onion dry/ },
  { key: 'cauliflower', name: 'Cauliflower', match: /^cauli(flower)? local/ },
  { key: 'cabbage', name: 'Cabbage', match: /^cabbage( local)?$/ },
  { key: 'carrot', name: 'Carrot', match: /^carrot( local)?$/ },
];
const FRUITS = [
  { key: 'apple', name: 'Apple (Fuji)', match: /^apple fuji/ },
  { key: 'banana', name: 'Banana', match: /^banana( local)?$/ },
  { key: 'orange', name: 'Orange', match: /^orange( nepali)?$/ },
  { key: 'pomegranate', name: 'Pomegranate', match: /^pomegranate/ },
  { key: 'papaya', name: 'Papaya', match: /^papaya( nepali)?$/ },
  { key: 'lime', name: 'Lime', match: /^lime/ },
];

function kalimati(defs: typeof VEGETABLES, id: string, title: string): Category {
  const raw = readCsv('kalimati.csv');
  const rows: { date: string; key: string; value: number; unit: string }[] = [];
  for (const r of raw) {
    const n = norm(r.commodity);
    const d = defs.find((x) => x.match.test(n));
    if (d) rows.push({ date: r.date, key: d.key, value: Number(r.avg), unit: r.unit });
  }
  // keep the first matching variant per date+item
  const seen = new Set<string>();
  const dedup = rows.filter((r) => { const k = r.date + r.key; if (seen.has(k)) return false; seen.add(k); return true; });
  const unitOf = (k: string) => dedup.find((r) => r.key === k)?.unit || 'kg';
  const b = build(dedup, defs.map((d) => ({ key: d.key, name: d.name, unit: `NPR per ${unitOf(d.key).toLowerCase().replace(/\.$/, '')}` })));
  return {
    id, title, subtitle: 'NPR, daily wholesale average', source: 'Kalimati Fruits and Vegetable Market',
    sourceUrl: 'https://kalimatimarket.gov.np/', ...b,
  };
}

export function loadCategories(): Category[] {
  return [
    currencies(),
    bullion(),
    kalimati(VEGETABLES, 'vegetables', 'Vegetables'),
    kalimati(FRUITS, 'fruits', 'Fruits'),
  ];
}

export interface Headline { title: string; source: string; link: string; date: string }
export function loadHeadlines(): { items: Headline[]; updated: string | null } {
  const p = path.join(DATA_DIR, 'headlines.json');
  if (!fs.existsSync(p)) return { items: [], updated: null };
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return { items: [], updated: null }; }
}
