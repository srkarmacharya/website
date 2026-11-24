# Project notes: sauryakarmacharya.com.np

A running record of decisions, setup and to-dos for Saurya Karmacharya's website.
The most recent changes come first. Update this file whenever something changes.

_Last updated: 2026-11-24_

---

## Current status (20 Nov 2026)

**The site is live** at https://www.sauryakarmacharya.com.np (the bare domain works too). Blogger no longer serves the domain.
The daily data update ran successfully, with a green ✓ for all sources.

| Part | Status |
|---|---|
| Home, About, Research (5 explainers), Opinions (4 pieces), Dashboard | ✅ Live |
| Exchange rates (NRB) | ✅ About 13 months of history, updated daily |
| Gold and silver (FENEGOSIDA) | ✅ 1 year of history from FENEGOSIDA's own feed, updated daily |
| Kalimati vegetables and fruits | ✅ Collecting since 20 Nov 2026. Lines appear from the 2nd day |
| NEPSE index and sub-indices | ✅ Collecting since 19 Nov 2026. Lines appear from the 2nd trading day |
| Economy headlines (Google News) | ✅ Updated daily |
| Study plan page (`/study-plan/`) | ✅ Built. Syncing from the vault needs the `VAULT_TOKEN` secret (see to-dos) |

## Open to-dos

- [ ] **Saurya:** create a fine-grained GitHub token with read-only **Contents** access to `obsidian-vault` only, and save it in this repo as the Actions secret `VAULT_TOKEN`. Until then, the study plan page shows the copy in `data/math-plan.md`.

- [ ] **Saurya:** proofread the 5 research explainers (`src/content/research/*.md`) for accuracy, and decide whether to state his role on each paper.
- [ ] **Saurya:** proofread the 4 Opinions pieces, and confirm their dates (the original blogs show day and month but no year, so the years are inferred).
- [ ] **Saurya:** check with CIMMYT/Rupantar comms that plain-language versions with a link back are fine (an unchanged copy may need permission).
- [ ] Optional: remove the custom domain from Blogger (Blogger → Settings → Custom domain).
- [ ] Optional: delete the leftover Google verification record `mipgyfxqwl5…` (CNAME) in Cloudflare DNS.
- [ ] Optional: redirect `sauryakarmacharya.com.np` → `www.` (Cloudflare Redirect Rules). Today both addresses serve the site, and the pages declare `www` as their main (canonical) address.
- [ ] Optional: replace the Saudi and Qatari riyals in the currency chart. Both are pegged to the US dollar, so their lines sit on top of the USD line. Candidates: UAE dirham, Kuwaiti dinar, Japanese yen, Korean won.
- [ ] Optional: backfill Kalimati prices from Open Data Nepal (CSV files covering 2013–2023).
- [ ] Optional: backfill older NEPSE history (ShareSansar's "Datewise indices" pages, or the `nepse-data-api` library).
- [ ] Optional: backfill older NRB exchange rates. Run the workflow with a start date such as `2016-01-01`.

---

## How it all fits together

```
GitHub: srkarmacharya/website (branch main)
   │  every push (code edits, or the daily data commit)
   ▼
Cloudflare Workers Builds: npm run build → npx wrangler deploy
   ▼
Worker "sauryakarmacharya" serves dist/ as static files
   ▼
www.sauryakarmacharya.com.np  ·  sauryakarmacharya.com.np  ·  sauryakarmacharya.sr-karmacharya.workers.dev
```

A GitHub Action, **"Update dashboard data"**, runs daily at 06:47 UTC (12:32 Nepal time). It fetches new data into `data/` and commits it, and that commit triggers a redeploy.

### Accounts and settings
- **GitHub:** user `srkarmacharya`, repo `website` (public). The Claude GitHub app has access to this repo.
- **Cloudflare:** account `sr.karmacharya@gmail.com`, account ID `4cc82482e48be38470f5f2310048990c`.
  - Worker project: `sauryakarmacharya`, with static assets configured in `wrangler.jsonc`.
  - Build settings: build `npm run build`, deploy `npx wrangler deploy`, root `/`, branch `main`.
  - Custom domains on the Worker: `www.sauryakarmacharya.com.np` and `sauryakarmacharya.com.np`.
  - Tip: if the normal browser shows "No access" on Workers & Pages, use an InPrivate window. It's a cached-login problem.
- **Domain:** `sauryakarmacharya.com.np`, registered at register.com.np, with DNS on Cloudflare (Free plan).
  - Removed on 20 Nov 2026: 4 A records (216.239.32/34/36/38.21) and the CNAME `www` → ghs.google.com (Blogger).
- **Oracle Cloud VM:** not used. A static site doesn't need a server.

---

## Site content

- **Framework:** Astro 7, static output. Fonts: Newsreader (headings) and Inter (body), self-hosted.
- **Design:** "Scholar", modelled on Pascal Michaillat's academic site but with **no buttons** (text links only). Dark by default with a Light/Dark toggle. Green accent (#5fb39a dark, #2f6f62 light).
- **Menu:** Home · About · Research · Opinions · Dashboard (plus a 404 page).
- **Headline:** "A student of rural livelihoods, asking how Nepal's farmers, migrants and markets *shape one another*."
- **Bio line:** Socioeconomic Research Coordinator at CIMMYT, Nepal (Rupantar project, funded by ACIAR, since Jan 2024).
- **Contact on site:** sr.karmacharya@gmail.com (main) and s.karmacharya@cgiar.org (work, on About), LinkedIn, Google Scholar, Instagram. There's no X account.
- **About page** mentions lightly that he plays music, with a link to Instagram.
- **Public CV:** `public/cv/Saurya_Karmacharya_CV.pdf`, trimmed from the August 2026 CV. The phone number and referees' contact details are removed, and it ends "References available on request".
- **Photo:** `public/img/saurya.jpg` (480×480 crop).

### Opinions (`src/content/opinions/`)
Plain-language rewrites of Saurya's own Rupantar blog posts. Each links to its original. The `kind: project` field shows a **Project blog** tag; `kind: opinion` is a personal view.
| File | Title on site | Original (rupantarfoodsystems.com) | Date used | Kind |
|---|---|---|---|---|
| `dairy-farming-sunsari.md` | More milk, same old market… | Scaling Up Improved Dairy Farming: Initial Lessons from Sunsari | 11 Nov 2025 (year inferred) | project |
| `mechanization-migration-morang.md` | Machines in the fields, young people on the move… | The Nexus of Mechanization and Out-Migration… Morang | 2 Dec 2025 (year inferred) | project |
| `gulf-conflict-nepal-food-system.md` | Why a war far away could reach a farmer's field in Nepal | Why a Conflict Thousands of Miles Away Could Shake Nepal's Food System | 19 Mar 2026 (year inferred) | opinion (written in a personal capacity) |
| `zero-tillage-maize-pandav.md` | Sowing without ploughing: one farmer's first try | Farming Through Uncertainty: A Smallholder's Experience in Rupantar | 24 Mar 2026 (year inferred) | project |

To add one: copy `example-draft.md`, fill in `title`, `date`, `summary`, `kind`, and `originalTitle`/`originalUrl`/`originalSource` if it was first published elsewhere, then set `draft: false`.

### Research explainers (`src/content/research/`)
| File | Plain-language title | Paper |
|---|---|---|
| `fallow-land-food-insecurity.md` | When fields sit empty, families go hungry | Narayanarao et al. 2026, *Sustainable Futures* 11:101683 |
| `crop-diversification-nepal.md` | Thirty years of trying to grow more than rice | Adhikari et al. 2026, *Agric. Environment & Sustainability* 1(3):100026 |
| `farmer-information-systems.md` | Where farmers get their advice, and where they wish they could | Karki et al. 2025, *J. Agric. Educ. & Extension* 31(5):725–755 |
| `crop-diversification-eigp.md` | Averages can hide the monoculture next door | Nandi et al. 2025, *Farming System* 3(2):100138 |
| `information-matters.md` | Who farmers listen to, and why it shapes what they grow | Timsina et al. 2026, *J. Agric. Educ. & Extension*, 1–27 (online). **Written from the abstract only.** |

---

## Dashboard data (`data/`)

| File | Source | How it's read | History |
|---|---|---|---|
| `forex.csv` | Nepal Rastra Bank | Official API `nrb.org.np/api/forex/v1/rates` | From 16 Oct 2025 |
| `bullion.csv` | FENEGOSIDA | Its JSON feed `api.fenegosida.org/.../Dashboard/today` and `WeeklyChartRate?weekmonthyear=365`. If the feed fails, the script reads the rendered web page in headless Chromium. Units: `tola` and `10g` | From 20 Nov 2025 |
| `kalimati.csv` | Kalimati Market | HTML table at `kalimatimarket.gov.np/price` (English names) | From 20 Nov 2026 |
| `nepse.csv` | NEPSE via ShareSansar | HTML table at `sharesansar.com/market`. If that fails, the `nepse-data-api` library | From 19 Nov 2026 |
| `headlines.json` | Google News RSS | Search for Nepal economy topics over the last 4 days | Latest 15 only |

- **Charts:** Currencies (USD, EUR, GBP, SAR, QAR, MYR), Bullion (fine gold, silver), Vegetables (tomato, potato, onion, cauliflower, cabbage, carrot), Fruits (Fuji apple, Nepali banana, orange, pomegranate, papaya, lime), and NEPSE (NEPSE Index, Banking, Hydropower, Microfinance, Development banks, Finance). Edit the lists in `src/lib/series.ts`.
- **Chart behaviour:** every line is indexed to 100 at the start of the chosen period (1M/6M/1Y/All). Hovering shows only the nearest line, highlighted, with its actual price. Clicking a legend name hides or shows that line.
- **On failure:** each source runs separately, so if one fails the others are still saved, and the run shows a red ✗ (GitHub emails the owner). Some failures save a diagnostic file to `data/_debug/` for troubleshooting.
- **NEPSE quirks:** the market trades Sunday–Thursday. On Fridays and Saturdays the figures are dated to the previous Thursday, and unchanged values (holidays) aren't added as a new day.

---

## Study plan (`/study-plan/`)

- **Source:** the note `Math study plan.md` in the private repo `srkarmacharya/obsidian-vault`. Saurya ticks boxes in Obsidian; the obsidian-git plugin pushes the note.
- **Sync:** the daily workflow copies that note to `data/math-plan.md` using the `VAULT_TOKEN` secret, and the data commit redeploys the site. Without the secret, the step is skipped and the last copy stays.
- **Format the page expects:** `## Phase` headings, task lines `- [ ] Wk 1–2 · topic · [resource](url)`, an optional indented note line under a task, and `start: YYYY-MM-DD` in the frontmatter (the current week is worked out from it, in Nepal time).
- **Code:** `src/lib/studyplan.ts` (parser), `src/pages/study-plan.astro`, `src/components/PlanRow.astro`. Linked in the main menu as "Study plan".

---

## Change log

### 24 Nov 2026
- Added the Study plan page: overall and per-topic progress, this week, anything still open from earlier weeks, up next, and the full plan with links. It reads a copy of the Obsidian note, refreshed daily.

### 20 Nov 2026 (evening)
- Added 4 Opinions pieces: plain-language rewrites of Saurya's Rupantar blogs, with a "Project blog" tag and a link back to each original.
- The Opinions page now shows summaries and tags, and the home page links to all opinions.
- Confirmed that the daily update uses no AI: it's a fixed-rule Python script run by GitHub Actions.

### 20 Nov 2026
- Decided on hosting: a static site in his own GitHub repo, deployed by Cloudflare. The Oracle VM isn't needed.
- Chose the design through canvas mockups (options A–E) and picked option E, "Scholar". Saurya set dark mode as the default and a green accent.
- Built the site: home, about (with CV), 5 research explainers, opinions, dashboard.
- Set up Cloudflare Workers Builds connected to GitHub (`wrangler.jsonc` added), and switched DNS from Blogger to the Worker.
- Dashboard: NRB, Kalimati and headlines worked on the first run. FENEGOSIDA turned out to be a JavaScript app, so it's now read from its JSON feed, with a 1-year backfill.
- Charts: the hover tooltip now shows only the nearest line. Charts with a single day of data show a "collecting since…" note.
- Added NEPSE (index plus sub-indices) as a fifth, full-width chart.
- Fixed NEPSE dates (Friday re-dated to Thursday) and number precision. Life Insurance was swapped for Finance, because ShareSansar's market page doesn't list it.
