#!/usr/bin/env python3
"""
Meta Access - Unified CLI Tool for Meta Platforms (Facebook, Instagram, Threads)

Single source of truth for Meta platform data extraction via:
1. Fetch URL: <url>
2. Scoped Search: --scope <handle> [-k <keywords>]
3. Global Search: -k <keywords>
"""

import os
import sys
import json
import re
import argparse
import subprocess
import requests

DEFAULT_CACHE_DIR = os.path.expanduser("~/.cache/meta_access")

COOKIE_FILES = {
    "fb": os.path.join(DEFAULT_CACHE_DIR, "facebook_cookies.json"),
    "ig": os.path.join(DEFAULT_CACHE_DIR, "instagram_cookies.json"),
    "threads": os.path.join(DEFAULT_CACHE_DIR, "threads_cookies.json")
}

def load_cookies(platform):
    cookie_path = COOKIE_FILES.get(platform)
    if not cookie_path or not os.path.exists(cookie_path):
        fallbacks = [
            os.path.join(DEFAULT_CACHE_DIR, "cookies.json"),
            os.path.expanduser(f"~/.hermes/{platform}_cookies.json")
        ]
        for fb in fallbacks:
            if os.path.exists(fb):
                cookie_path = fb
                break
        else:
            raise FileNotFoundError(f"找不到 {platform.upper()} Cookie 檔案: {cookie_path}")

    with open(cookie_path, "r", encoding="utf-8") as f:
        return json.load(f), cookie_path

def save_refreshed_cookies(platform, orig_cookies, session, save_path):
    """自動將 HTTP 響應中刷新的 Cookie 寫回存檔"""
    try:
        cookie_map = {c['name']: c for c in orig_cookies}
        has_changes = False

        for ck in session.cookies:
            if ck.name in cookie_map:
                if cookie_map[ck.name].get('value') != ck.value:
                    cookie_map[ck.name]['value'] = ck.value
                    if ck.expires:
                        cookie_map[ck.name]['expirationDate'] = ck.expires
                    has_changes = True
            else:
                default_domain = f".{platform}.com" if platform != "threads" else ".threads.net"
                cookie_map[ck.name] = {
                    "name": ck.name,
                    "value": ck.value,
                    "domain": ck.domain or default_domain,
                    "hostOnly": False,
                    "path": ck.path or "/",
                    "secure": ck.secure,
                    "httpOnly": 'httponly' in getattr(ck, '_rest', {}),
                    "sameSite": "no_restriction",
                    "session": False,
                    "expirationDate": ck.expires
                }
                has_changes = True

        if has_changes:
            refreshed_list = list(cookie_map.values())
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(refreshed_list, f, ensure_ascii=False, indent=4)
            print(f"🔄 {platform.upper()} Cookie 已自動刷新覆寫至：{save_path}", file=sys.stderr)
            if platform == "ig":
                ensure_ig_netscape_cookies()
    except Exception as e:
        print(f"⚠️ 刷新 {platform.upper()} Cookie 覆寫失敗: {e}", file=sys.stderr)

def ensure_ig_netscape_cookies():
    json_path = COOKIE_FILES["ig"]
    txt_path = os.path.join(DEFAULT_CACHE_DIR, "instagram_cookies.txt")
    if not os.path.exists(json_path):
        return txt_path

    with open(json_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c.get("domain", ".instagram.com")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        expiration = int(c.get("expirationDate", 0))
        name = c.get("name", "")
        value = c.get("value", "")
        if name:
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")

    os.makedirs(os.path.dirname(txt_path), exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return txt_path

# ==================== FACEBOOK ENGINE ====================

def decode_fb_text(raw_text):
    if not raw_text:
        return ""
    try:
        cleaned = raw_text.replace('"', '\\"')
        return json.loads(f'"{cleaned}"')
    except Exception:
        return raw_text

def extract_fb_posts(html_text, keywords=None, page_handle=""):
    posts = []
    matches = list(re.finditer(r'\"message\":\{\"text\":\"([^\"]+)\"\}', html_text))

    for idx, m in enumerate(matches, start=1):
        raw_text = m.group(1)
        decoded_text = decode_fb_text(raw_text)

        if keywords:
            if not any(kw in raw_text or kw in decoded_text for kw in keywords if kw):
                continue

        pos = m.start()
        chunk = html_text[max(0, pos - 4000):min(len(html_text), pos + 15000)]

        image_uris = re.findall(r'\"image\":\{\"uri\":\"(https:[^\"]+)\"', chunk)
        image_uris += re.findall(r'\"photo\":\{\"id\":\"[^\"]+\",\"image\":\{\"uri\":\"(https:[^\"]+)\"', chunk)
        image_uris += re.findall(r'\"large_share_image\":\{\"uri\":\"(https:[^\"]+)\"', chunk)

        clean_images = list(set([u.replace('\\/', '/') for u in image_uris]))

        post_url = None
        pfbids = re.findall(r'pfbid[a-zA-Z0-9]+', chunk)
        post_ids = re.findall(r'\"post_id\":\"(\d+)\"', chunk)

        if pfbids:
            post_url = f"https://www.facebook.com/{page_handle}/posts/{pfbids[0]}"
        elif post_ids:
            post_url = f"https://www.facebook.com/{page_handle}/posts/{post_ids[0]}"
        else:
            post_url = f"https://www.facebook.com/{page_handle}"

        posts.append({
            "index": len(posts) + 1,
            "text": decoded_text,
            "post_url": post_url,
            "image_urls": clean_images
        })

    return posts

def fetch_facebook(target_or_url=None, scope=None, keywords=None, output_dir=DEFAULT_CACHE_DIR, download_media=False, force_refresh=False, limit=10):
    mode = "fetch_url"
    clean_handle = ""

    if scope:
        mode = "scoped_search"
        raw = str(scope).strip('/')
        clean_handle = raw if not raw.startswith("http") else re.sub(r'^https?://(www\.|m\.)?facebook\.com/', '', raw).strip('/')
    elif target_or_url:
        raw = str(target_or_url).strip('/')
        clean_handle = re.sub(r'^https?://(www\.|m\.)?facebook\.com/', '', raw).strip('/')
    elif keywords:
        mode = "global_search"
        search_query = " ".join(keywords)
        clean_handle = f"search/posts/?q={requests.utils.quote(search_query)}"
    else:
        raise ValueError("必須提供 <url>、--scope 或 -k/--keywords 參數")

    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', clean_handle).lower()

    if keywords and not force_refresh and not download_media:
        kw_tag = "_".join([re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', k) for k in keywords if k]).lower()
        prefix = f"{sanitized}_{kw_tag}_" if kw_tag else f"{sanitized}_"
        cached_imgs = sorted([
            os.path.join(output_dir, f) for f in os.listdir(output_dir)
            if f.startswith(prefix) and f.endswith(".png")
        ])
        if cached_imgs:
            return {
                "status": "cached",
                "platform": "fb",
                "mode": mode,
                "target": clean_handle,
                "keywords": keywords,
                "cached_images": cached_imgs
            }

    orig_cookies, cookie_path = load_cookies("fb")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    })
    for c in orig_cookies:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.facebook.com'))

    fetch_url = f"https://www.facebook.com/{clean_handle}/"
    res = session.get(fetch_url)
    save_refreshed_cookies("fb", orig_cookies, session, cookie_path)

    if res.status_code != 200:
        raise RuntimeError(f"無法存取 Facebook 目標 ({fetch_url})，HTTP 狀態碼: {res.status_code}")

    posts = extract_fb_posts(res.text, keywords=keywords, page_handle=clean_handle)

    if limit and posts:
        posts = posts[:limit]

    if not posts:
        return {
            "status": "not_found",
            "platform": "fb",
            "mode": mode,
            "target": clean_handle,
            "keywords": keywords
        }

    for post in posts:
        downloaded = []
        if download_media and post["image_urls"]:
            kw_tag = "_".join([re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', k) for k in (keywords or []) if k])
            prefix = f"{sanitized}_{kw_tag}_" if kw_tag else f"{sanitized}_post_{post['index']}_"

            for img_idx, img_url in enumerate(post["image_urls"], start=1):
                img_res = session.get(img_url)
                if img_res.status_code == 200:
                    filename = f"{prefix}{img_idx}.png"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(img_res.content)
                    downloaded.append(filepath)
        post["downloaded_images"] = downloaded

    return {
        "status": "success",
        "platform": "fb",
        "mode": mode,
        "target": clean_handle,
        "keywords": keywords,
        "total_posts": len(posts),
        "downloaded_images": posts[0].get("downloaded_images", []) if posts else [],
        "posts": posts
    }

# ==================== INSTAGRAM ENGINE ====================

def shortcode_to_media_id(shortcode):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    for letter in shortcode:
        media_id = (media_id * 64) + alphabet.index(letter)
    return str(media_id)

def extract_shortcode(url):
    m = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(2)
    return url.strip('/')

def fetch_ig_comments(shortcode):
    orig_cookies, _ = load_cookies("ig")
    session = requests.Session()
    for c in orig_cookies:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.instagram.com'))

    csrf_token = next((c['value'] for c in orig_cookies if c['name'] == 'csrftoken'), '')
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'X-IG-App-ID': '936619743392459',
        'X-ASBD-ID': '198387',
        'X-CSRFToken': csrf_token,
        'Accept': '*/*',
        'Accept-Language': 'zh-TW,zh-Hant;q=0.9',
        'Sec-Fetch-Site': 'same-origin'
    }

    media_id = shortcode_to_media_id(shortcode)
    api_url = f"https://www.instagram.com/api/v1/media/{media_id}/comments/"

    try:
        res = session.get(api_url, headers=headers, timeout=15)
        save_refreshed_cookies("ig", orig_cookies, session, COOKIE_FILES["ig"])
        if res.status_code == 200:
            data = res.json()
            formatted = []
            for c in data.get("comments", []):
                u = c.get("user", {})
                formatted.append({
                    "id": c.get("pk"),
                    "username": u.get("username"),
                    "full_name": u.get("full_name"),
                    "text": c.get("text"),
                    "like_count": c.get("comment_like_count", 0),
                    "created_at": c.get("created_at")
                })
            return formatted
    except Exception as e:
        print(f"⚠️ 擷取 IG 留言失敗: {e}", file=sys.stderr)
    return []

def fetch_instagram(target_or_url=None, scope=None, keywords=None, output_dir=DEFAULT_CACHE_DIR, download_media=False, get_comments=True, limit=10):
    cookie_txt = ensure_ig_netscape_cookies()
    mode = "fetch_url"
    target_url = None

    if scope:
        mode = "scoped_search"
        target_url = f"https://www.instagram.com/{str(scope).strip('@').strip('/')}/"
    elif target_or_url:
        if str(target_or_url).startswith("http"):
            target_url = str(target_or_url)
        else:
            mode = "scoped_search"
            target_url = f"https://www.instagram.com/{str(target_or_url).strip('@').strip('/')}/"
    elif keywords:
        mode = "global_search"
        tag_query = "".join([re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', k) for k in keywords if k])
        target_url = f"https://www.instagram.com/explore/tags/{requests.utils.quote(tag_query)}/"
    else:
        raise ValueError("必須提供 <url>、--scope 或 -k/--keywords 參數")

    out_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "--cookies", cookie_txt, "--dump-json", "--no-playlist", target_url]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(proc.stdout)
    except Exception as e:
        err_msg = getattr(e, "stderr", str(e))
        raise RuntimeError(f"Instagram 資料抓取失敗 ({target_url}): {err_msg}")

    post_id = info.get("id")
    ext = info.get("ext", "mp4")
    media_path = os.path.join(output_dir, f"{post_id}.{ext}")

    if download_media:
        download_cmd = ["yt-dlp", "--cookies", cookie_txt, "-o", out_template, "--no-playlist", target_url]
        subprocess.run(download_cmd, capture_output=True, text=True, check=True)

    comments = []
    if get_comments:
        shortcode = extract_shortcode(target_url)
        comments = fetch_ig_comments(shortcode)
        if limit and comments:
            comments = comments[:limit]

    return {
        "status": "success",
        "platform": "ig",
        "mode": mode,
        "post_id": post_id,
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "uploader_id": info.get("uploader_id", ""),
        "url": target_url,
        "media_path": media_path if (download_media and os.path.exists(media_path)) else None,
        "like_count": info.get("like_count"),
        "comments_count": len(comments),
        "comments": comments
    }

# ==================== THREADS ENGINE ====================

def extract_threads_posts_obj(obj, posts=None):
    if posts is None:
        posts = []
    if isinstance(obj, dict):
        if 'post' in obj and isinstance(obj['post'], dict):
            posts.append(obj['post'])
        if 'thread_items' in obj and isinstance(obj['thread_items'], list):
            for ti in obj['thread_items']:
                if isinstance(ti, dict) and 'post' in ti:
                    posts.append(ti['post'])
        for v in obj.values():
            extract_threads_posts_obj(v, posts)
    elif isinstance(obj, list):
        for item in obj:
            extract_threads_posts_obj(item, posts)
    return posts

def get_threads_media_urls(post):
    urls = []
    if not isinstance(post, dict):
        return urls
    img_v2 = post.get('image_versions2', {})
    if isinstance(img_v2, dict) and 'candidates' in img_v2 and img_v2['candidates']:
        urls.append(img_v2['candidates'][0]['url'])
    vids = post.get('video_versions', [])
    if isinstance(vids, list) and vids:
        urls.append(vids[0]['url'])
    carousel = post.get('carousel_media') or []
    if isinstance(carousel, list):
        for item in carousel:
            urls.extend(get_threads_media_urls(item))
    return list(set(urls))

def fetch_threads(target_or_url=None, scope=None, keywords=None, output_dir=DEFAULT_CACHE_DIR, download_media=False, get_comments=True, limit=10):
    orig_cookies, cookie_path = load_cookies("threads")
    mode = "fetch_url"
    target_url = None

    if scope:
        mode = "scoped_search"
        target_url = f"https://www.threads.net/@{str(scope).strip('@').strip('/')}"
    elif target_or_url:
        if str(target_or_url).startswith("http"):
            target_url = str(target_or_url)
        else:
            mode = "scoped_search"
            target_url = f"https://www.threads.net/@{str(target_or_url).strip('@').strip('/')}"
    elif keywords:
        mode = "global_search"
        search_query = " ".join(keywords)
        target_url = f"https://www.threads.net/search?q={requests.utils.quote(search_query)}"
    else:
        raise ValueError("必須提供 <url>、--scope 或 -k/--keywords 參數")

    session = requests.Session()
    for c in orig_cookies:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.threads.net'))
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.threads.com'))

    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'X-IG-App-ID': '238260118697367',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    res = session.get(target_url, headers=headers, timeout=20)
    save_refreshed_cookies("threads", orig_cookies, session, cookie_path)

    if res.status_code != 200:
        raise RuntimeError(f"無法存取 Threads 頁面 ({target_url})，HTTP 狀態碼: {res.status_code}")

    script_contents = re.findall(r'<script[^>]*>(.*?)</script>', res.text)
    all_raw_posts = []

    for s in script_contents:
        if 'ScheduledServerJS' in s or 'thread_items' in s:
            try:
                data = json.loads(s)
                extracted = extract_threads_posts_obj(data)
                if extracted:
                    all_raw_posts.extend(extracted)
            except Exception:
                pass

    if not all_raw_posts:
        raise RuntimeError(f"無法解析 Threads 貼文資料: {target_url}")

    dedup = {}
    for p in all_raw_posts:
        pk = str(p.get('pk') or p.get('id') or '')
        if pk and pk not in dedup:
            caption = p.get('caption')
            text = caption.get('text') if isinstance(caption, dict) and caption else (p.get('text') or '')
            if keywords and mode == "scoped_search":
                if not any(kw.lower() in text.lower() for kw in keywords if kw):
                    continue
            dedup[pk] = p

    posts_list = list(dedup.values())
    if limit and posts_list:
        posts_list = posts_list[:limit]

    if not posts_list:
        return {
            "status": "not_found",
            "platform": "threads",
            "mode": mode,
            "target_url": target_url,
            "keywords": keywords
        }

    main_post = posts_list[0]
    comments_raw = posts_list[1:] if (get_comments and len(posts_list) > 1) else []

    main_user = main_post.get('user', {})
    main_caption = main_post.get('caption')
    main_text = main_caption.get('text') if isinstance(main_caption, dict) and main_caption else (main_post.get('text') or '')
    main_media_urls = get_threads_media_urls(main_post)

    downloaded_files = []
    if download_media and main_media_urls:
        post_pk = main_post.get('pk') or main_post.get('id') or 'media'
        for idx, m_url in enumerate(main_media_urls, 1):
            try:
                m_res = session.get(m_url, timeout=30)
                if m_res.status_code == 200:
                    ext = "mp4" if ".mp4" in m_url.lower() or "video" in m_res.headers.get("Content-Type", "") else "png"
                    filename = f"threads_{post_pk}_{idx}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(m_res.content)
                    downloaded_files.append(filepath)
            except Exception as e:
                print(f"⚠️ 下載 Threads 媒體失敗: {e}", file=sys.stderr)

    formatted_comments = []
    if get_comments:
        for c in comments_raw:
            c_user = c.get('user', {})
            c_caption = c.get('caption')
            c_text = c_caption.get('text') if isinstance(c_caption, dict) and c_caption else (c.get('text') or '')
            formatted_comments.append({
                "id": str(c.get('pk') or c.get('id') or ''),
                "username": c_user.get('username'),
                "full_name": c_user.get('full_name'),
                "text": c_text,
                "like_count": c.get('like_count', 0),
                "created_at": c.get('taken_at') or c.get('created_at')
            })

    return {
        "status": "success",
        "platform": "threads",
        "mode": mode,
        "post_id": str(main_post.get('pk') or main_post.get('id') or ''),
        "code": main_post.get('code'),
        "username": main_user.get('username'),
        "full_name": main_user.get('full_name'),
        "text": main_text,
        "like_count": main_post.get('like_count', 0),
        "reply_count": main_post.get('reply_count', 0),
        "url": target_url,
        "media_urls": main_media_urls,
        "downloaded_media": downloaded_files if download_media else [],
        "comments_count": len(formatted_comments),
        "comments": formatted_comments,
        "total_posts": len(posts_list)
    }

# ==================== VERIFICATION ====================

def verify_cookie_session(platform):
    cookie_path = COOKIE_FILES.get(platform)
    if not cookie_path or not os.path.exists(cookie_path):
        return {
            "valid": False,
            "user_id": None,
            "cookie_file": cookie_path,
            "error": "Cookie file not found"
        }

    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        cookie_dict = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}
    except Exception as e:
        return {
            "valid": False,
            "user_id": None,
            "cookie_file": cookie_path,
            "error": f"Failed to parse cookie file: {e}"
        }

    user_id = cookie_dict.get("c_user") if platform == "fb" else cookie_dict.get("ds_user_id")

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }

    try:
        if platform == "fb":
            r = requests.get("https://mbasic.facebook.com/me", headers=headers, cookies=cookie_dict, allow_redirects=False, timeout=10)
            if r.status_code in (200, 302):
                loc = r.headers.get("Location", "")
                if "login" in loc or "checkpoint" in loc:
                    return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": f"Redirected to {loc}"}
                return {"valid": True, "user_id": user_id, "cookie_file": cookie_path, "message": "Active session verified"}
            return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": f"HTTP {r.status_code}"}

        elif platform == "ig":
            r = requests.get("https://www.instagram.com/", headers=headers, cookies=cookie_dict, allow_redirects=True, timeout=10)
            if "login" in r.url:
                return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": "Redirected to login page"}
            if r.status_code == 200:
                return {"valid": True, "user_id": user_id, "cookie_file": cookie_path, "message": "Active session verified"}
            return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": f"HTTP {r.status_code}"}

        elif platform == "threads":
            r = requests.get("https://www.threads.net/", headers=headers, cookies=cookie_dict, allow_redirects=True, timeout=10)
            if "login" in r.url:
                return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": "Redirected to login page"}
            if r.status_code == 200:
                return {"valid": True, "user_id": user_id, "cookie_file": cookie_path, "message": "Active session verified"}
            return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": f"HTTP {r.status_code}"}

        else:
            return {"valid": False, "user_id": None, "cookie_file": cookie_path, "error": f"Unknown platform: {platform}"}

    except Exception as e:
        return {"valid": False, "user_id": user_id, "cookie_file": cookie_path, "error": str(e)}

def verify_all_cookies(target_platform=None):
    platforms = [target_platform] if target_platform and target_platform != "all" else ["fb", "ig", "threads"]
    results = {}
    all_valid = True
    for p in platforms:
        res = verify_cookie_session(p)
        results[p] = res
        if not res.get("valid"):
            all_valid = False
    return {
        "status": "success" if all_valid else "warning",
        "action": "verify_cookies",
        "all_valid": all_valid,
        "results": results
    }

# ==================== MAIN CLI ====================

def main():
    parser = argparse.ArgumentParser(description="Meta Access - 統一 Meta 平台 (FB, IG, Threads) 資料存取工具")
    parser.add_argument("target_or_url", nargs="?", default=None, help="目標網址或路徑")
    parser.add_argument("--platform", "-p", choices=["fb", "ig", "threads", "all"], default=None, help="指定平台類別 (fb|ig|threads|all)")
    parser.add_argument("--verify", action="store_true", help="快速驗證 Cookie 檔案效期與 Session 有效性")
    parser.add_argument("--scope", default=None, help="2. Scoped Search: 指定帳號/專頁/社團 Scope")
    parser.add_argument("--keywords", "-k", nargs="+", help="關鍵字 (未帶 --scope 時自動作為 Global Search 搜尋詞，帶 --scope 時作為次級過濾詞)")
    parser.add_argument("--limit", "-l", type=int, default=10, help="限制回傳最大筆數 (預設: 10)")
    parser.add_argument("--download", "-d", action="store_true", help="顯式指定下載影片/圖片媒體檔案")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_CACHE_DIR, help="媒體檔輸出與快取目錄")
    parser.add_argument("--no-comments", action="store_true", help="不抓取留言/評論")
    parser.add_argument("--force-refresh", "-f", action="store_true", help="忽略快取強制刷新")

    args = parser.parse_args()

    try:
        if args.verify:
            result = verify_all_cookies(args.platform)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        if not args.platform or args.platform == "all":
            parser.error("非 --verify 模式下必須指定 --platform (fb|ig|threads)")

        platform = args.platform.lower()

        if platform == "fb":
            result = fetch_facebook(
                target_or_url=args.target_or_url,
                scope=args.scope,
                keywords=args.keywords,
                output_dir=args.output_dir,
                download_media=args.download,
                force_refresh=args.force_refresh,
                limit=args.limit
            )
        elif platform == "ig":
            result = fetch_instagram(
                target_or_url=args.target_or_url,
                scope=args.scope,
                keywords=args.keywords,
                output_dir=args.output_dir,
                download_media=args.download,
                get_comments=not args.no_comments,
                limit=args.limit
            )
        elif platform == "threads":
            result = fetch_threads(
                target_or_url=args.target_or_url,
                scope=args.scope,
                keywords=args.keywords,
                output_dir=args.output_dir,
                download_media=args.download,
                get_comments=not args.no_comments,
                limit=args.limit
            )
        else:
            raise ValueError(f"未知的平台類別: {platform}")

        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        err_out = {"status": "error", "error": str(e)}
        print(json.dumps(err_out, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
