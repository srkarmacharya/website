// Reads data/math-plan.md at build time. That file is a copy of the note
// "Math study plan.md" in Saurya's Obsidian vault, refreshed by the daily
// workflow. Each task line looks like:
//   - [ ] Wk 1–2 · what to study · [resource](https://link)
// with an optional note on an indented line underneath.
import fs from 'node:fs';
import path from 'node:path';

export interface Link { label: string; url: string }
export interface Item {
  phase: string;
  weekLabel: string;
  from: number | null;
  to: number | null;
  topic: string;
  links: Link[];
  note: string;
  done: boolean;
}
export interface Phase { name: string; items: Item[]; done: number; total: number }
export interface Plan {
  start: Date | null;
  week: number | null; // current week number, 1-based; null before the start date
  phases: Phase[];
  items: Item[];
  done: number;
  total: number;
  thisWeek: Item[];
  upNext: Item[];
  behind: Item[];
}

const FILE = path.resolve('data', 'math-plan.md');
const LINK = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

export function loadPlan(today = new Date()): Plan {
  const text = fs.existsSync(FILE) ? fs.readFileSync(FILE, 'utf8') : '';
  const lines = text.split(/\r?\n/);

  let start: Date | null = null;
  if (lines[0]?.trim() === '---') {
    for (let i = 1; i < lines.length && lines[i].trim() !== '---'; i++) {
      const m = lines[i].match(/^start:\s*(\d{4}-\d{2}-\d{2})/);
      if (m) start = new Date(m[1] + 'T00:00:00+05:45');
    }
  }

  const items: Item[] = [];
  let phase = 'Plan';
  for (const line of lines) {
    const h = line.match(/^##\s+(.+?)\s*$/);
    if (h) { phase = h[1]; continue; }
    const t = line.match(/^[-*]\s+\[([ xX])\]\s+(.*)$/);
    if (t) {
      let rest = t[2].trim();
      let from: number | null = null, to: number | null = null, weekLabel = '';
      const w = rest.match(/^Wk\s*(\d+)(?:\s*[–-]\s*(\d+))?/i);
      if (w) {
        from = +w[1]; to = w[2] ? +w[2] : from;
        weekLabel = from === to ? `Week ${from}` : `Weeks ${from}–${to}`;
        rest = rest.slice(w[0].length);
      }
      const links = [...rest.matchAll(LINK)].map((m) => ({ label: m[1], url: m[2] }));
      const topic = rest.replace(LINK, '').split('·').map((s) => s.trim()).filter(Boolean).join(' · ');
      items.push({ phase, weekLabel, from, to, topic, links, note: '', done: t[1] !== ' ' });
      continue;
    }
    const n = line.match(/^\s+[-*]\s+(.+)$/);
    if (n && items.length) {
      const last = items[items.length - 1];
      last.note = last.note ? `${last.note} ${n[1].trim()}` : n[1].trim();
    }
  }

  const byName = new Map<string, Phase>();
  for (const it of items) {
    if (!byName.has(it.phase)) byName.set(it.phase, { name: it.phase, items: [], done: 0, total: 0 });
    const p = byName.get(it.phase)!;
    p.items.push(it); p.total++; if (it.done) p.done++;
  }

  let week: number | null = null;
  if (start) {
    const days = Math.floor((today.getTime() - start.getTime()) / 864e5);
    week = days >= 0 ? Math.floor(days / 7) + 1 : null;
  }
  const inWeek = (it: Item, wk: number) => it.from !== null && it.from <= wk && wk <= (it.to ?? it.from);
  const thisWeek = week ? items.filter((it) => inWeek(it, week!)) : [];
  const behind = week ? items.filter((it) => !it.done && it.to !== null && it.to < week!) : [];
  const upNext = items
    .filter((it) => !it.done && !thisWeek.includes(it) && !behind.includes(it))
    .sort((a, b) => (a.from ?? 1e9) - (b.from ?? 1e9))
    .slice(0, 3);

  return {
    start, week, phases: [...byName.values()], items,
    done: items.filter((i) => i.done).length, total: items.length,
    thisWeek, upNext, behind,
  };
}
