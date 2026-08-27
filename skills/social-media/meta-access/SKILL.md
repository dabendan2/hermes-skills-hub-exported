---
name: meta-access
description: Use when searching FB/IG/Threads or fetching Meta posts.
---

# Meta Access

Single CLI executable (`scripts/meta_access.py`) for fetching posts, search results, comments, and media from Meta platforms (Facebook, Instagram, Threads) using auto-refreshed session cookies.

## Trigger
- Fetching posts, search results, or media from Facebook, Instagram, or Threads.

## Cookie File Locations
若需手動更新或匯出 Cookie，請儲存為 JSON 格式至：
- **Facebook**: `~/.cache/meta_access/facebook_cookies.json`
- **Instagram**: `~/.cache/meta_access/instagram_cookies.json`
- **Threads**: `~/.cache/meta_access/threads_cookies.json`

*(Scripts automatically load and refresh cookies at these paths during execution. When receiving browser JSON cookie exports containing `sessionid`, `ds_user_id`, `csrftoken`, write directly to the JSON path; `ensure_ig_netscape_cookies()` handles automatic conversion to Netscape format.)*

## Pitfalls & Platform Limitations
- **Facebook**:
  1. **User-Agent Block (HTTP 400)**: Desktop Chrome User-Agents sent via plain HTTP GET requests (like `requests`) are frequently rejected with `HTTP 400 Bad Request` by FB. Use a Mobile User-Agent (e.g. iOS Safari) for static HTTP requests.
  2. **Dynamic JS & Private Group Boundaries**: FB post search and group feeds use React/Comet SPA rendering. Static HTTP GET scripts return unrendered JS shells or `not_found`. In addition, private/restricted ticket exchange groups require an approved logged-in account joined to that group; unjoined accounts (even with valid cookies) render `目前無法查看此內容`. When full rendering or group interaction is needed, use Playwright/Chromium with logged-in cookies. Fall back to search engine queries (`site:facebook.com/groups/ <keywords>`) for indexed public content.
- **Instagram**: Global tag search (`-k`), user handle search (`--scope`), and single Post/Reel URL extractions currently encounter upstream `yt-dlp` / Instagram API `HTTP Error 400` or `Unable to extract data` errors. Inform users of this limitation and rely on FB / Threads for active queries when IG extraction fails.

## Unified CLI Interface (`scripts/meta_access.py`)

Executable script with shebang (`#!/usr/bin/env python3`). Always invoke with `python3 ~/.hermes/skills/social-media/meta-access/scripts/meta_access.py` to ensure proper execution. Mandatory platform parameter `-p` / `--platform <fb|ig|threads>`.

| Mode | Command Structure | Description |
| :--- | :--- | :--- |
| **0. Verify Cookies** | `scripts/meta_access.py --verify [-p fb\|ig\|threads\|all]` | 快速驗證 Cookie 檔案是否存在且 Session 是否仍然有效 |
| **1. Global Search** | `scripts/meta_access.py -p <fb\|ig\|threads> -k <keywords...>` | 全站/標籤關鍵字搜尋 (未帶 `--scope` 與 URL 時) |
| **2. Scoped Search** | `scripts/meta_access.py -p <fb\|ig\|threads> --scope <handle_or_id> [-k <keywords...>]` | 指定帳號/專頁/社團範疇 + 次級關鍵字過濾 |
| **3. Fetch URL** | `scripts/meta_access.py -p <fb\|ig\|threads> <url>` | 指定單一 Post / Reel / Thread 網址抓取內文與留言 |

### Common Optional Flags
- `-p` / `--platform`: **必填** 平台類別 (`fb` \| `ig` \| `threads`)。
- `-k` / `--keywords`: 關鍵字/搜尋詞（支援多個）。未指定 `--scope` 與 URL 時作為 Global Search 搜尋詞，指定 `--scope` 時作為次級過濾詞。
- `-l` / `--limit`: 限制回傳最大貼文/留言筆數 (預設 `10`)。
- `-d` / `--download`: 顯式指定下載影片/圖片媒體檔案至 `--output-dir` (預設 `False`)。
- `--no-comments`: 不抓取留言/評論。
- `-o` / `--output-dir`: 媒體檔輸出與快取目錄 (預設 `~/.cache/meta_access/`)。
- `-f` / `--force-refresh`: 強制忽略快取從網路抓取。

---

## Command Examples

```bash
# 0. Verify Cookies
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py --verify
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p fb --verify

# 1. Fetch URL
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p ig "https://www.instagram.com/reel/DbKWLq0EaCy/" -d
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p threads "https://www.threads.net/@zuck/post/CuC25sSsp2d" -l 5
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p fb "https://www.facebook.com/groups/1048117176928629"

# 2. Scoped Search
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p fb --scope Passionsisters -k 班表 8月 -d
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p ig --scope passionsisters_official -k 班表
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p threads --scope zuck -k Muse

# 3. Global Search
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p fb -k "中職班表" -l 5
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p ig -k "日清泡麵" -l 5
~/.hermes/skills/social-media/meta-access/scripts/meta_access.py -p threads -k "Meta" -l 10
```
