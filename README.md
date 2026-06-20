https://0xtrvkc.github.io/BTC-Daily-Short-Call-Premium-Income-Checklist/

# 🎮 BTC Daily Short Call — Premium Income Checklist

A single-file, mobile-first pre-trade checklist for selling daily BTC short
call options on Bybit, styled like an original **Game Boy (DMG)** screen —
2-bit, 4-shade green LCD palette, pixel font, the works.

No build step, no framework, no dependencies beyond a Google Fonts CDN link.
Open `index.html` in a browser and it works.

> ⚠️ **Educational use only.** This is a personal trading checklist, not
> financial advice. Options trading carries substantial risk of loss. Nothing
> here is a recommendation to buy or sell anything.

---

## What it does

Sixteen+ pre-trade modules walk you through a BTC short-call premium-selling
routine: macro calendar risk, IV/HV ratio, funding rate, liquidation regime,
strike/delta selection, stop-loss placement, position sizing, and timing —
ending with a settlement reminder. Check items off as you go and the app:

- tracks **overall progress** with a chunky, stepped pixel progress bar
- flags a **hard SKIP** the moment any no-trade condition is ticked
- shows **ALL CHECKS PASSED** once everything is done and nothing is skipped
- lights up a small **status LED** in the header — green for go, blinking red
  for skip — modeled on the real DMG hardware's power light
- includes a collapsible **daily schedule** (Thailand time) that highlights
  whatever step you should be on right now

## Features

- 🎨 **True 4-shade monochrome theme** — every surface, border, and tag pulls
  from 4 CSS variables. A live 🎮 button (bottom-right) swaps the whole app
  to a grayscale "Game Boy Pocket" palette and remembers your choice.
- 📱 **Mobile-first** — 2-column stat grid that grows to 4 on wider screens,
  large pixel-style checkboxes, tap-friendly headers, horizontally-scrollable
  formula tables so nothing breaks on a 360px screen.
- 🤖 **Live automation hooks** on 3 modules (see below) — pulls real funding
  rate and liquidation data, with manual fallbacks if a fetch fails.
- 🧩 **Modular by design** — every module is a clearly commented, self-contained
  block (`MODULE N` ... `END MODULE N`). Add, remove, or reorder modules and
  the progress counter, skip logic, and automation helper all keep working
  with zero changes elsewhere.
- 🗂️ **Single file** — everything (HTML, CSS, JS) lives in `index.html`.
  Easy to host anywhere, including GitHub Pages.

## Quick start

```bash
git clone https://github.com/0xtrvkc/BTC-Daily-Short-Call-Premium-Income-Checklist.git
cd BTC-Daily-Short-Call-Premium-Income-Checklist
open index.html   # or just double-click it
```

Or deploy straight to GitHub Pages:

1. Push this repo to GitHub.
2. **Settings → Pages → Deploy from branch → `main` / `root`**.
3. Visit `https://<your-username>.github.io/<your-repo>/`.

## The checklist at a glance

| Part | Module | Check | Hard skip? | Automated? |
|---|---|---|:-:|:-:|
| A | 1 | Macro calendar (FOMC/CPI/NFP) | ✅ | ⚙️ via `data/macro.json` |
| A | 2 | IV/HV ratio | ✅ | — |
| A | 3 | ATM straddle range | — | — |
| A | 4 | Funding rate | ✅ | ✅ live (Bybit API) |
| A | 5 | BTC rally yesterday | ✅ | — |
| A | 6 | Real-time liquidation cascade | ✅ | — |
| A | 6B | Liquidation 24h tiers | ✅ | ✅ live (CoinGlass) |
| A | 6C | Combination read (price/vol/OI/liq) | ✅ | — |
| A | 6D | Macro view declaration | — | — |
| B | 7 | Delta selection (0.13–0.15) | — | — |
| B | 8 | Resistance cross-check | — | — |
| B | 9 | ATR distance | — | — |
| B | 9B | SD distance | ✅ | — |
| B | 10 | Max pain | — | — |
| C | 11 | Stop-loss (index price) | — | — |
| C | 12 | Position sizing | — | — |
| C | 13 | Consecutive losses | ✅ | — |
| D | 14 | Entry timing window | — | — |
| D | 14B | Pin risk exit (13:30 TH) | — | — |
| D | 15 | Mid-day check | — | — |
| D | 16 | Early close | — | — |

## Automation

Three modules try to fetch live data automatically. All have manual
fallbacks, so nothing is required to use the checklist day one.

**Module 4 — Funding Rate.** Calls Bybit's public ticker endpoint directly
(no key, no proxy). Works out of the box.

**Module 6B — Liquidation 24h.** Tries CoinGlass through a public CORS proxy,
then falls back to a manual number input with a "Check" button if the fetch
is blocked.

**Module 1 — Macro Calendar.** Looks for `data/macro.json` on this repo's
GitHub Pages site:

```
https://0xtrvkc.github.io/BTC-Daily-Short-Call-Premium-Income-Checklist/data/macro.json
```

This file is **not generated automatically yet** — you need a GitHub Action
(or any scheduled job) that writes it daily in this shape:

```json
{
  "date": "2026-06-20",
  "skip": false,
  "event_count": 0,
  "events": [{ "time": "14:30", "event": "FOMC Rate Decision" }],
  "summary": "Calendar clear — no high-impact USD events today"
}
```

If you fork this and rename the repo or change your username, update the two
constants at the top of Module 1's automation script:

```js
const GITHUB_USER = "0xtrvkc";
const REPO_NAME   = "BTC-Daily-Short-Call-Premium-Income-Checklist";
```

## Customizing the look

Colors are not scattered through the CSS — they all come from 4 variables
near the top of `index.html`, in a block clearly marked
`PALETTE — CAN EDIT`:

```css
:root {
  --gb-1: #9bbc0f; /* lightest — screen background */
  --gb-2: #8bac0f; /* light    — panels, header bars */
  --gb-3: #306230; /* dark     — mid accents, dim text */
  --gb-4: #0f380f; /* darkest  — borders, primary text */
}
```

Want grayscale permanently instead of green? Comment out that block and
uncomment the grayscale one right below it — no other edits needed. (Or just
use the runtime 🎮 toggle if you want both available.)

## Editing the checklist content

Every module follows the same pattern, and the comments tell you what's
safe to touch:

```html
<!-- //////////  MODULE N — NAME  ////////// -->
<!-- CAN EDIT: item-body content, labels, rule-row text -->
<!-- DO NOT EDIT: id="item-mN", id="cb-mN", id="skip-mN", data-skip="true" -->
```

The IDs are load-bearing — the progress counter, skip detector, and
automation helper (`setModuleResult()`) all find modules by `id^="cb-m"`, so
renaming them silently breaks the count. Everything else — wording, rules,
formulas, links — is yours to edit freely.

## Project structure

```
.
├── index.html        # the entire app — HTML, CSS, and JS inline
└── data/
    └── macro.json     # optional, powers Module 1's automation (see above)
```

## License

Personal project, provided as-is. Use, fork, and modify freely for your own
trading workflow.

---

*Not financial advice. Trade at your own risk.*
