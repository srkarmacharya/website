// Reads data/math-plan.md at build time: a public maths self-study plan.
// Each task line looks like:
//   - [ ] Wk 1–2 · what to study · [resource](https://link)
// with an optional note on an indented line underneath, grouped under
// "## Phase" headings. Tick marks are ignored: the site shows the plan only.
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
}
export interface Phase { name: string; items: Item[]; from: number | null; to: number | null }
export interface Plan { phases: Phase[]; items: Item[]; totalWeeks: number }

const FILE = path.resolve('data', 'math-plan.md');
const LINK = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

export function loadPlan(): Plan {
  const text = fs.existsSync(FILE) ? fs.readFileSync(FILE, 'utf8') : '';
  const items: Item[] = [];
  let phase = 'Plan';
  for (const line of text.split(/\r?\n/)) {
    const h = line.match(/^##\s+(.+?)\s*$/);
    if (h) { phase = h[1]; continue; }
    const t = line.match(/^[-*]\s+\[[ xX]\]\s+(.*)$/);
    if (t) {
      let rest = t[1].trim();
      let from: number | null = null, to: number | null = null, weekLabel = '';
      const w = rest.match(/^Wk\s*(\d+)(?:\s*[–-]\s*(\d+))?/i);
      if (w) {
        from = +w[1]; to = w[2] ? +w[2] : from;
        weekLabel = from === to ? `Week ${from}` : `Weeks ${from}–${to}`;
        rest = rest.slice(w[0].length);
      }
      const links = [...rest.matchAll(LINK)].map((m) => ({ label: m[1], url: m[2] }));
      const topic = rest.replace(LINK, '').split('·').map((s) => s.trim()).filter(Boolean).join(' · ');
      items.push({ phase, weekLabel, from, to, topic, links, note: '' });
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
    if (!byName.has(it.phase)) byName.set(it.phase, { name: it.phase, items: [], from: null, to: null });
    const p = byName.get(it.phase)!;
    p.items.push(it);
    if (it.from !== null) p.from = p.from === null ? it.from : Math.min(p.from, it.from);
    if (it.to !== null) p.to = p.to === null ? it.to : Math.max(p.to, it.to);
  }
  return { phases: [...byName.values()], items, totalWeeks: Math.max(0, ...items.map((i) => i.to ?? 0)) };
}
