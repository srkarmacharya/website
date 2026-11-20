# sauryakarmacharya.com.np

Personal website of Saurya Karmacharya: research explainers, opinions, and a daily dashboard of prices in Nepal.

Built with [Astro](https://astro.build) as a static site. Hosted on Cloudflare Workers (static assets, configured in `wrangler.jsonc`), which rebuilds and redeploys automatically whenever this repository changes.

## How it fits together

```
GitHub repo ──push──▶ Cloudflare Workers Builds: `npm run build` + `npx wrangler deploy` ──▶ www.sauryakarmacharya.com.np
     ▲
     └── GitHub Action (daily, 12:32 Nepal time) fetches new prices into data/ and commits them
```

## Everyday edits (no coding needed)

You can edit any file directly on github.com: open it, click the pencil icon, make the change and press **Commit changes**. The live site updates about a minute later.

| To change… | Edit this file |
|---|---|
| Home page intro text | `src/pages/index.astro` |
| About page (bio, experience, education) | `src/pages/about.astro` |
| A research explainer | `src/content/research/<name>.md` |
| Add an opinion piece | Copy `src/content/opinions/example-draft.md`, rename it, set `draft: false` |
| Email / social links | `src/lib/site.ts` |
| CV download | Replace `public/cv/Saurya_Karmacharya_CV.pdf` |
| Profile photo | Replace `public/img/saurya.jpg` (square, about 480×480 px) |
| Which items appear in each chart | `src/lib/series.ts` (the `CURRENCIES`, `BULLION`, `VEGETABLES`, `FRUITS` lists) |

## Dashboard data

All data lives in plain CSV files in `data/`, so anyone can download and reuse it:

| File | Source | Columns |
|---|---|---|
| `forex.csv` | [Nepal Rastra Bank Forex API](https://www.nrb.org.np/api-docs-v1) | date, iso3, name, unit, buy, sell |
| `bullion.csv` | [FENEGOSIDA](https://www.fenegosida.org/) | date, item, unit, price |
| `kalimati.csv` | [Kalimati Market](https://kalimatimarket.gov.np/price) | date, commodity, unit, min, max, avg |
| `headlines.json` | Google News RSS | title, source, link, date |

The updater is `scripts/update_data.py`, run by `.github/workflows/update-data.yml`. Each source is fetched independently. If one fails, the others are still saved, and the run is marked failed so GitHub emails you.

**Run it manually:** go to the repo's **Actions** tab → **Update dashboard data** → **Run workflow**. To backfill exchange-rate history, enter a start date such as `2020-01-01` in the box.

Kalimati and FENEGOSIDA have no official API, so their pages are read directly. If either site changes its layout, that source's step will start failing. The fix is usually a small change in `update_bullion()` or `update_kalimati()`.

## Local development (optional)

```bash
npm install
npm run dev          # http://localhost:4321
pip install -r scripts/requirements.txt
python scripts/update_data.py
```

## Licence

Text and research summaries © Saurya Karmacharya. Price data belongs to the respective publishers (NRB, FENEGOSIDA, Kalimati Market). It is republished here for reference, with attribution.
