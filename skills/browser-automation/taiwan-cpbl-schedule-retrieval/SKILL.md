---
name: taiwan-cpbl-schedule-retrieval
description: Procedures for retrieving and parsing official CPBL (Chinese Professional Baseball League) schedules using direct PDF access and layout-aware text extraction.
version: 1.0.0
author: Hermes
---

# Taiwan CPBL Schedule Retrieval

Strategies for obtaining the most accurate CPBL game information. While direct PDF retrieval serves as the Single Source of Truth (SSOT) for the **monthly baseline schedule**, real-time changes (e.g., rainouts, reschedules, actual starting pitchers, active scores) must be retrieved directly from the live website using browser/Vue extraction.

## Official PDF URL Pattern (Monthly Baseline)
The league publishes monthly schedules in PDF format with a predictable URL structure:
`https://www.cpbl.com.tw/files/GameDets/{YEAR}/{KIND}/CPBL%E4%B8%80%E8%BB%8D%E4%BE%8B%E8%a1%8c%e8%b3%bd_{YEAR}{MONTH}.pdf`

- **YEAR**: 4-digit year (e.g., `2026`).
- **MONTH**: 2-digit month (e.g., `06`).
- **KIND**: Series type. Use `A` for Regular Season (一軍例行賽).

## Real-Time Live Status Retrieval (Vue API Extraction)
Because CPBL is a heavily dynamic site powered by Vue.js, the most reliable and structural way to extract today's live match states, scores, pitchers, and postponements is to inspect the rendered Vue application state.

### 1. Load the Homepage
Use `browser_navigate` to load the CPBL home page:
`https://cpbl.com.tw/` (Always use the naked domain to avoid the `www.` 404 routing issue).

### 2. Direct State Extraction via Console
Evaluate JavaScript in the page context via `browser_console` on the homepage (`https://cpbl.com.tw/`) to dump the fully populated Vue reactive arrays directly as structured JSON. Note that `app.GameADetail` on the homepage contains real-time score updates (`VisitingTotalScore`, `HomeTotalScore`) and live at-bat details (`CurtBatting`: `InningSeq`, `VisitingHomeType`, `OutCnt`, `HitterName`, `PitcherName`, base runners), whereas `/schedule/getgamedatas` only holds static schedule baselines.

```javascript
// Extract 一軍 (First Team) live games and detailed inning state
JSON.stringify(app.GameADetail)

// Extract 二軍 (Second Team) live games
JSON.stringify(app.GameDDetail)
```
The returned JSON contains fields such as `VisitingFirstMover`/`HomeFirstMover` (starting pitchers), `VisitingTotalScore`/`HomeTotalScore` (live score), `CurtBatting` (live inning, outs, ball/strike count, hitter/pitcher), `GameStatus` (`1` for scheduled, `2` for in-progress, `6` for cancelled/postponed), and `WeatherDesc`.

### 3. Automated Probe Script
The skill includes a pre-packaged script `scripts/cpbl_vue_probe.py` to automate this extraction by querying the homepage Vue state (`app.GameADetail`) and fallback schedule APIs via Playwright.

**Prerequisites:**
- Playwright python package installed: `pip install playwright`
- Playwright browser binaries downloaded: `playwright install chromium`

**How to Run:**
```bash
# Query all live & scheduled games
python3 scripts/cpbl_vue_probe.py

# Query games for a specific date (e.g., 2026-08-25)
python3 scripts/cpbl_vue_probe.py -d 2026-08-25

# Query only games currently in progress
python3 scripts/cpbl_vue_probe.py --live
```
This produces clean JSON output containing live scores, inning status, ball-strike/out counts, batter, pitcher, and base runner positions.

### 4. Continuous Monitoring (Watchdog Cron Job Pattern)
When a user asks to be notified of any real-time updates (e.g., rainouts, postponements, or score changes), deploy a lightweight, zero-LLM-token background cron job using the `no_agent=True` watchdog pattern:
1. Write a monitoring script (placed under `~/.hermes/scripts/cpbl_watcher.py`) that uses Playwright to extract `app.GameADetail`, filters for the specific game of interest, and compares its current state against a cached JSON state file (e.g., `/home/ubuntu/workspace/cpbl_g168_state.json`).
2. **First-run behavior**: If the cache file does not exist, save the current state and exit silently (empty `stdout`).
3. **Change-detection behavior**: If the current state differs from the cache (e.g., `GameStatus` changes from `1` to `6`, or `IsGameStop` toggles, or weather updates), print a clear markdown notification to `stdout`, then save the new state.
4. **Deploy the job**: Run `cronjob(action='create', name='...', schedule='every 15m', script='cpbl_watcher.py', no_agent=True)`. Because `no_agent=True`, the runner skips the LLM entirely and runs the script directly. Empty output from your script means complete silence, whereas any text printed to `stdout` triggers automatic delivery to the origin user channel.

## Static PDF Extraction Workflow (For Baseline Research)

### 1. Download the PDF
Use `curl` via the `terminal` tool to fetch the file directly.
```bash
curl -O -L "https://www.cpbl.com.tw/files/GameDets/2026/A/CPBL%E4%B8%80%E8%BB%8D%E4%BE%8B%E8%a1%8c%e8%b3%bd_202606.pdf"
```

### 2. Layout-Aware Conversion
Convert the PDF to text using the `-layout` flag to preserve column alignment, which is critical for mapping dates to game details.
```bash
pdftotext -layout "CPBL%E4%B8%80%E8%BB%8D%E4%BE%8B%E8%a1%8c%e8%b3%bd_202606.pdf" schedule.txt
```

### 3. Parsing with Grep
Search for the specific date pattern (e.g., `6/17`). Use `-C` or `-A` flags to see the surrounding context (teams and location).
```bash
grep -C 5 "6/17" schedule.txt
```

## Live Status and Fast Probes

When the official website's dynamic loading causes browser tools to timeout, use `curl` for "fast probes" of the homepage or specific game pages. The HTML often contains enough metadata (team names, scores, pitcher names) to answer "who is playing today" or "what is the score" without full rendering.

### Direct Vue State Extraction via Browser Console

If you load the official website `https://cpbl.com.tw` in a browser session, the site's dynamic schedule widget is driven by a Vue.js application instance (`app`). You can extract the complete, highly accurate, and fully structured live game details directly from the frontend state using the browser console.

Execute the following JavaScript expressions in the browser context:
- **First Team Games (一軍):** `JSON.stringify(app.GameADetail)`
- **Second Team Games (二軍):** `JSON.stringify(app.GameDDetail)`

This payload returns rich, structured JSON including:
- Matchup information (`VisitingTeamName` vs. `HomeTeamName`, team scores, current innings).
- Game status (`GameStatus`: 1 for Scheduled, 2 for In Progress, 6 for Cancelled/Postponed).
- Starting pitchers (`VisitingFirstMover`, `HomeFirstMover`).
- Stadium abbreviations (`FieldAbbe`).
- Precise local weather text (`WeatherDesc`).

### Fast Matchup Check
Search the homepage for team names to verify today's starters or matchups.
```bash
curl -s "https://www.cpbl.com.tw/" | grep -iE "味全|台鋼|中信|統一|樂天|富邦"
```

### Context-Aware Schedule Parsing
When searching the `schedule.txt` (from `pdftotext`), use line numbers to isolate specific game blocks.
```bash
# Find the line number for today's date
grep -n "5/19" schedule.txt
# Extract the following 10 lines for game details
sed -n '81,91p' schedule.txt
```

## Pitfalls
- **Browser Timeouts & Heavy Page**: The official CPBL site is notoriously heavy and can exceed standard limits. If you only need static schedules, try terminal-based PDF retrieval first. If you need live status, navigate using the browser tool and directly query the Vue state.
- **PDF Out-of-Date Pitfall**: The PDF schedule is a static snapshot compiled prior to the start of the month. It **does not** reflect game postponements due to weather ("延賽"), reschedules, or dynamically added doubleheaders. Always cross-reference PDF baseline data with the live website's `app.GameADetail` array to ensure real-world truth.
- **Doubleheaders**: Watch for multiple entries for the same date (e.g., Game 108 and 109 on 5/19). PDF alignment and the live `GameADetail` are the only ways to reliably distinguish them.
- **Environment Constraints**: `execute_code` environments may lack `beautifulsoup4` or `lxml`. Prefer `grep`, `sed`, and `awk` for parsing `curl` output.
- **Location Mapping**: 
  - 天母: Taipei (Wei Chuan Dragons Home)
  - 新莊: New Taipei (Fubon Guardians Home)
  - 大巨蛋: Taipei Dome
  - 洲際: Taichung
  - 桃園: Rakuten Taoyuan Stadium
  - 亞太主: Tainan (Unified Lions)
  - 花蓮: Hualien (Occasional neutral site)
- **Stadium Parking & Arrival (Logistics)**:
  For spectator logistics, parking spots, and arrival strategies at major stadiums like Tianmu and Xinzhuang, see the reference documentation in [references/stadium_parking.md](references/stadium_parking.md).
- **Domain Routing/404 Pitfall**: `www.cpbl.com.tw` returns `404 Not Found` for certain inner pages (e.g., `/team?ClubNo=...` or `/team?TeamNo=...`). However, the naked domain `cpbl.com.tw` works perfectly. When scraping or fetching any inner pages, **always strip `www.` and use `https://cpbl.com.tw/`** to avoid routing errors.
  - 花蓮: Hualien (Occasional neutral site)
