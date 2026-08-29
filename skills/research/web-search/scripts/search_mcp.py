#!/usr/bin/env python3
import sys
import json
import os
import time
import asyncio
import urllib.parse
import urllib.request
import requests
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from mcp.server.fastmcp import FastMCP
from concurrent.futures import ThreadPoolExecutor

# Define thread-safe SOCKS5 residential proxy settings
PROXIES = {
    "http": "socks5h://100.87.89.52:1080",
    "https": "socks5h://100.87.89.52:1080"
}


# Initialize FastMCP
mcp = FastMCP("web")

# Desktop browser headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br"
}

# Mapping of engine display titles
ENGINE_TITLES = {
    "yahoo_tw": "🌐 Yahoo 台灣搜尋結果",
    "duckduckgo": "🦆 DuckDuckGo 搜尋結果",
    "wikipedia_zh": "📚 維基百科（中文）搜尋結果",
    "wikipedia_en": "📚 Wikipedia (English) Search Results",
    "sogou": "🔍 搜狗搜尋結果",
    "yahoo_global": "🌐 Yahoo Global 搜尋結果",
    "baidu": "🇨🇳 百度 搜尋結果",
}

# Registered engine functions
ENGINES = {}

def register_engine(name):
    def decorator(func):
        ENGINES[name] = func
        return func
    return decorator

# Map aliases to actual registered engines
ALIAS_MAP = {
    "ddg": "duckduckgo",
    "duckduckgo": "duckduckgo",
    "wikipedia": "wikipedia_zh",
    "wikipedia_zh": "wikipedia_zh",
    "wikipedia_en": "wikipedia_en",
    "yahoo_tw": "yahoo_tw",
    "yahoo_global": "yahoo_global",
    "sogou": "sogou",
    "baidu": "baidu",
}

def _get_soup(html_text):
    """
    Robust BeautifulSoup parsing with automatic lxml fallback to html.parser
    """
    try:
        return BeautifulSoup(html_text, "lxml")
    except Exception:
        return BeautifulSoup(html_text, "html.parser")

def _get_url_html(url, params=None, headers=None, timeout=10):
    """
    Robust requests-based helper using full headers and SOCKS5 proxy, with direct fallback.
    """
    merged_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": HEADERS["Accept"],
        "Accept-Language": HEADERS["Accept-Language"]
    }
    if headers:
        merged_headers.update(headers)
        
    try:
        r = requests.get(
            url,
            params=params,
            headers=merged_headers,
            proxies=PROXIES,
            timeout=timeout
        )
        if r.status_code == 200:
            return r.status_code, r.text
    except Exception:
        pass

    try:
        r = requests.get(
            url,
            params=params,
            headers=merged_headers,
            timeout=timeout
        )
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

def execute_with_fallback(query, limit, engine_list):
    """
    Run search engines in sequence until one succeeds and returns non-empty results.
    """
    for engine_name in engine_list:
        if engine_name in ENGINES:
            try:
                res = ENGINES[engine_name](query, limit, use_fallback=False)
                if res.get("success") and res.get("results"):
                    return res
            except Exception:
                continue
    return {"success": False, "error": "All fallback search engines failed."}

@register_engine("yahoo_global")
def _search_yahoo_global(query, limit=5, use_fallback=True):
    url = "https://search.yahoo.com/search"
    params = {"p": query}
    fallback_chain = ["yahoo_tw", "wikipedia_zh", "wikipedia_en"]
    
    try:
        code, html = _get_url_html(url, params=params, timeout=10)
        if code != 200:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": f"Yahoo Global returned status code {code}"}
        
        soup = _get_soup(html)
        items = soup.find_all("div", class_="compText")
        if not items:
            items = soup.find_all("div", class_="algo") or soup.find_all("div", class_="algo-srv")
            
        results = []
        for item in items[:limit]:
            title_elem = item.find("h3") or item.find("a")
            title = title_elem.text.strip() if title_elem else "No Title"
            
            link_elem = item.find("a")
            link = "No Link"
            if link_elem and "href" in link_elem.attrs:
                link = str(link_elem["href"])
                ru_match = re.search(r'/RU=([^/]+)/', link)
                if ru_match:
                    link = urllib.parse.unquote(ru_match.group(1))
            
            snippet_elem = item.find("div", class_="compText") or item.find("span", class_="fc-26th")
            snippet = snippet_elem.text.strip() if snippet_elem else ""
            if not snippet:
                p = item.find("p")
                if p:
                    snippet = p.text.strip()
            if not snippet:
                snippet = item.text.strip()[:200]
                
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet
            })
            
        if not results and use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
            
        return {"success": True, "results": results}
    except Exception as e:
        if use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
        return {"success": False, "error": str(e)}

@register_engine("duckduckgo")
def _search_ddg(query, limit=5, use_fallback=True):
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    fallback_chain = ["yahoo_tw", "yahoo_global", "wikipedia_zh"]
    
    merged_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/x-www-form-urlencoded"
    }
    req = urllib.request.Request(url, data=data, headers=merged_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.getcode()
            if code != 200:
                if use_fallback:
                    return execute_with_fallback(query, limit, fallback_chain)
                return {"success": False, "error": f"DDG returned status code {code}"}
            
            html_text = response.read().decode('utf-8', errors='ignore')
            soup = _get_soup(html_text)
            results = []
            links = soup.find_all('a', class_='result-link')
            for link in links[:limit]:
                title = link.get_text(strip=True)
                href_val = link.get('href')
                href = ""
                if href_val and isinstance(href_val, str):
                    href = href_val
                    if href.startswith('//'):
                        href = 'https:' + href
                    if "/l/?" in href or "uddg=" in href:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if 'uddg' in qs:
                            href = qs['uddg'][0]
                
                parent_tr = link.find_parent('tr')
                snippet = ""
                if parent_tr:
                    snippet_tr = parent_tr.find_next_sibling('tr')
                    if snippet_tr:
                        snippet_td = snippet_tr.find('td', class_='result-snippet')
                        if snippet_td:
                            snippet = snippet_td.get_text(strip=True)
                            
                results.append({
                    "title": title,
                    "link": href,
                    "snippet": snippet
                })
                
            if not results and use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
                
            return {"success": True, "results": results}
    except Exception as e:
        if use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
        return {"success": False, "error": str(e)}

@register_engine("sogou")
def _search_sogou(query, limit=5, use_fallback=True):
    url = "https://www.sogou.com/web"
    params = {"query": query}
    fallback_chain = ["baidu", "yahoo_tw", "wikipedia_zh"]
    
    try:
        code, html = _get_url_html(url, params=params, timeout=10)
        if code != 200:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": f"Sogou returned status code {code}"}
        
        soup = _get_soup(html)
        title_text = soup.title.text if soup.title else ""
        if "验证" in title_text or "captcha" in html.lower():
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": "Sogou captcha verification triggered."}
            
        items = soup.find_all("div", class_="vrwrap") or soup.find_all("div", class_="rb")
        results = []
        for item in items[:limit]:
            title_elem = item.find("h3")
            if not title_elem:
                continue
            title = title_elem.text.strip()
            
            link_elem = item.find("a")
            link = "No Link"
            if link_elem and "href" in link_elem.attrs:
                link_val = link_elem["href"]
                if isinstance(link_val, str):
                    link = link_val
                    if link.startswith("/link?"):
                        link = "https://www.sogou.com" + link
            
            snippet_elem = item.find("div", class_="space-txt") or item.find("p") or item.find("div", class_="ft") or item.find("div", class_="text-layout")
            snippet = snippet_elem.text.strip() if snippet_elem else ""
            if not snippet:
                snippet = item.text.strip()[:200]
                
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet
            })
            
        if not results and use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
            
        return {"success": True, "results": results}
    except Exception as e:
        if use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
        return {"success": False, "error": str(e)}

@register_engine("baidu")
def _search_baidu(query, limit=5, use_fallback=True):
    url = "https://www.baidu.com/s"
    params = {"wd": query}
    fallback_chain = ["sogou", "yahoo_tw", "wikipedia_zh"]
    
    try:
        code, html = _get_url_html(url, params=params, timeout=10)
        if code != 200:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": f"Baidu returned status code {code}"}
        
        soup = _get_soup(html)
        title_text = soup.title.text if soup.title else ""
        if "验证" in title_text or "安全验证" in title_text:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": "Baidu verification triggered."}
            
        results = []
        for r in soup.find_all('div', class_=re.compile(r'result|c-container')):
            h3 = r.find('h3')
            if h3:
                a = h3.find('a')
                if a:
                    title = a.text.strip()
                    link_val = a.get('href', '')
                    link = ""
                    if link_val and isinstance(link_val, str):
                        link = link_val
                        if not link.startswith('http'):
                            if link.startswith('/'):
                                link = "https://www.baidu.com" + link
                    
                    abstract = ""
                    abs_div = r.find('div', class_='c-abstract') or r.find('span', class_='content-right_8Zs40')
                    if abs_div:
                        abstract = abs_div.text.strip()
                        
                    results.append({
                        "title": title,
                        "link": link,
                        "snippet": abstract
                    })
                    
        if not results and use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
            
        return {"success": True, "results": results}
    except Exception as e:
        if use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
        return {"success": False, "error": str(e)}

@register_engine("yahoo_tw")
def _search_yahoo_tw(query, limit=5, use_fallback=True):
    url = "https://tw.search.yahoo.com/search"
    params = {"p": query}
    fallback_chain = ["yahoo_global", "duckduckgo", "wikipedia_zh"]
    
    try:
        code, html = _get_url_html(url, params=params, timeout=10)
        if code != 200:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": False, "error": f"Yahoo TW returned status code {code}"}
        
        # Detect block page / temporary error
        if "暫時性的問題" in html or "重新搜尋" in html or "未找到與" in html or "did not match any documents" in html:
            if use_fallback:
                return execute_with_fallback(query, limit, fallback_chain)
            return {"success": True, "results": []}
            
        soup = _get_soup(html)
        items = soup.find_all("div", class_="algo")
        if not items:
            items = soup.find_all("div", class_="compText")
        
        results = []
        for item in items[:limit]:
            link_elem = item.find("a")
            if not link_elem or "href" not in link_elem.attrs:
                continue
                
            link = str(link_elem["href"])
            # Filter out non-organic footer/navigation links
            if any(k in link for k in ["help.yahoo.com", "guce.yahoo.com", "yahoo.uservoice.com"]) or link == "https://tw.yahoo.com/":
                continue
                
            title_elem = item.find("h3") or item.find("a")
            title = title_elem.text.strip() if title_elem else "No Title"
            
            # Decrypt Yahoo redirect URL if present
            ru_match = re.search(r'/RU=([^/]+)/', link)
            if ru_match:
                link = urllib.parse.unquote(ru_match.group(1))
            
            if link.startswith("https://tw.search.yahoo.com"):
                continue
            
            snippet_elem = item.find("div", class_="compText") or item.find("span", class_="fc-26th")
            snippet = snippet_elem.text.strip() if snippet_elem else ""
            if not snippet:
                p = item.find("p")
                if p:
                    snippet = p.text.strip()
            if not snippet:
                snippet = item.text.strip()[:200]
            
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet
            })
            
        if not results and use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
                
        return {"success": True, "results": results}
    except Exception as e:
        if use_fallback:
            return execute_with_fallback(query, limit, fallback_chain)
        return {"success": False, "error": str(e)}

@register_engine("wikipedia_zh")
def _search_wikipedia_zh(query, limit=3, use_fallback=True):
    return _search_wikipedia(query, lang="zh", limit=limit)

@register_engine("wikipedia_en")
def _search_wikipedia_en(query, limit=3, use_fallback=True):
    return _search_wikipedia(query, lang="en", limit=limit)

def _search_wikipedia(query, lang="zh", limit=3):
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json"
    }
    headers = {
        "User-Agent": "HermesWebSearchMCP/1.1 (contact: admin@hermes.agent)"
    }
    r = None
    try:
        r = requests.get(url, params=params, headers=headers, proxies=PROXIES, timeout=10)
    except Exception:
        r = None

    if r is None or r.status_code != 200:
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
        except Exception as e:
            return {"success": False, "error": str(e)}

    if r is None or r.status_code != 200:
        return {"success": False, "error": f"Wikipedia ({lang}) returned status code {getattr(r, 'status_code', 'N/A')}"}

    try:
        data = r.json()
        search_items = data.get("query", {}).get("search", [])
        results = []
        for item in search_items[:limit]:
            title = item.get("title")
            snippet_raw = item.get("snippet", "")
            soup = _get_soup(snippet_raw)
            snippet = soup.get_text()
            link = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}"
            label = "📚 維基百科" if lang == "zh" else "📚 Wikipedia (EN)"
            results.append({
                "title": f"{label}: {title}",
                "link": link,
                "snippet": snippet
            })
        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _format_markdown_results(res, engine_title):
    md = []
    md.append(f"### {engine_title}")
    if res["success"]:
        if not res["results"]:
            md.append("找不到任何搜尋結果。\n")
        for idx, item in enumerate(res["results"]):
            md.append(f"{idx+1}. **[{item['title']}]({item['link']})**")
            md.append(f"   *摘要*: {item['snippet']}\n")
    else:
        md.append(f"搜尋發生錯誤: {res['error']}\n")
    return "\n".join(md)

@mcp.tool()
async def reverse_image_search(image_input: str, limit: int = 5) -> str:
    """
    Perform a real reverse image search (以圖搜圖 / 圖片反向搜尋) strictly using the PicImageSearch library.
    Queries verified working search engines (Baidu, Ascii2D, SauceNAO, Iqdb) and extracts real matching source pages.
    """
    img_url = image_input if (image_input.startswith("http://") or image_input.startswith("https://")) else None
    temp_file = None

    if img_url:
        try:
            r = requests.get(img_url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"})
            if r.status_code == 200:
                temp_file = f"/tmp/mcp_reverse_search_{int(time.time())}.jpg"
                with open(temp_file, "wb") as f:
                    f.write(r.content)
                target_file = temp_file
            else:
                return f"工具錯誤: 無法下載目標圖片 (HTTP {r.status_code}): {image_input}"
        except Exception as e:
            return f"工具錯誤: 下載目標圖片失敗: {str(e)}"
    else:
        if not os.path.exists(image_input):
            return f"工具錯誤: 無效的圖片路徑: {image_input}"
        target_file = image_input

    results = []
    try:
        from PicImageSearch import BaiDu, Ascii2D, SauceNAO, Iqdb, Network
        async with Network() as client:
            # 1. 百度識圖 (BaiDu)
            try:
                baidu = BaiDu(client=client)
                res = await baidu.search(file=target_file)
                if res and hasattr(res, "raw") and res.raw:
                    for item in res.raw:
                        url = getattr(item, "url", None) or getattr(item, "origin_url", None)
                        if url and url.startswith("http"):
                            title = getattr(item, "title", "") or f"來源網頁 ({url[:35]}...)"
                            results.append({"engine": "百度識圖", "title": title, "url": url})
            except Exception:
                pass

            # 2. Ascii2D
            try:
                ascii2d = Ascii2D(client=client)
                res = await ascii2d.search(file=target_file)
                if res and hasattr(res, "raw") and res.raw:
                    for item in res.raw:
                        url = getattr(item, "url", None) or getattr(item, "origin_url", None)
                        if url and url.startswith("http"):
                            title = getattr(item, "title", "") or getattr(item, "author", "") or f"來源網頁 ({url[:35]}...)"
                            results.append({"engine": "Ascii2D", "title": title, "url": url})
            except Exception:
                pass

            # 3. SauceNAO
            try:
                saucenao = SauceNAO(client=client)
                res = await saucenao.search(file=target_file)
                if res and hasattr(res, "raw") and res.raw:
                    for item in res.raw:
                        url = getattr(item, "url", None) or getattr(item, "origin_url", None)
                        if url and url.startswith("http"):
                            title = getattr(item, "title", "") or getattr(item, "author", "") or f"來源網頁 ({url[:35]}...)"
                            results.append({"engine": "SauceNAO", "title": title, "url": url})
            except Exception:
                pass

            # 4. Iqdb
            try:
                iqdb = Iqdb(client=client)
                res = await iqdb.search(file=target_file)
                if res and hasattr(res, "raw") and res.raw:
                    for item in res.raw:
                        url = getattr(item, "url", None) or getattr(item, "origin_url", None)
                        if url and url.startswith("http"):
                            title = getattr(item, "title", "") or f"來源網頁 ({url[:35]}...)"
                            results.append({"engine": "Iqdb", "title": title, "url": url})
            except Exception:
                pass
    except Exception as e:
        return f"工具錯誤: 執行 PicImageSearch 發生例外 - {str(e)}"
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

    if not results:
        return "工具錯誤: 搜圖引擎未能匹配到對應的視覺原圖/來源網頁。"

    md = []
    md.append(f"## 🔍 以圖搜圖結果 (PicImageSearch Reverse Search Results)\n")
    md.append(f"**目標圖片**: `{image_input}`\n")
    md.append("### 🖼️ 視覺特徵比對來源網頁 (Extracted Visual Matches)")

    seen = set()
    count = 0
    for res in results:
        if res['url'] not in seen:
            seen.add(res['url'])
            count += 1
            md.append(f"{count}. **[{res['engine']}] {res['title']}**")
            md.append(f"   - 來源網頁: {res['url']}\n")
            if count >= limit * 2:
                break

    return "\n".join(md)

@mcp.tool()
def search(query: str, limit: int = 5, engines: str = "yahoo_tw,duckduckgo,wikipedia_zh,wikipedia_en,sogou,baidu") -> str:
    """
    Combined search across multiple engines.
    engines parameter is a comma-separated list of engines to query (options: yahoo_tw, duckduckgo, wikipedia_zh, wikipedia_en, sogou, baidu).
    Defaults to 'yahoo_tw,duckduckgo,wikipedia_zh,wikipedia_en,sogou,baidu'.
    """
    md = []
    md.append(f"## 🔍 聯合搜尋字詞: `{query}`\n")
    
    # Parse engines list and map to registered engines
    requested_engines = [e.strip().lower() for e in engines.split(",") if e.strip()]
    engine_list = []
    for eng in requested_engines:
        mapped = ALIAS_MAP.get(eng)
        if mapped and mapped in ENGINES:
            if mapped not in engine_list:  # Deduplicate
                engine_list.append(mapped)
        elif eng in ENGINES:
            if eng not in engine_list:
                engine_list.append(eng)
                
    if not engine_list:
        return "⚠️ 未指定任何有效的搜尋引擎。"
        
    # Run searches concurrently using ThreadPoolExecutor
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(engine_list), 5)) as executor:
        future_to_engine = {
            executor.submit(ENGINES[engine], query, limit): engine
            for engine in engine_list
        }
        for future in future_to_engine:
            engine = future_to_engine[future]
            try:
                results[engine] = future.result()
            except Exception as e:
                results[engine] = {"success": False, "error": str(e)}
                
    # Format and group outputs in the specified order
    for engine in engine_list:
        if engine in results:
            res = results[engine]
            engine_title = ENGINE_TITLES.get(engine, f"🌐 {engine.capitalize()} 搜尋結果")
            md.append(_format_markdown_results(res, engine_title))
            
    return "\n".join(md)

if __name__ == "__main__":
    # If run directly as a script (e.g. for testing), run a simple test query
    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
        print(search(test_query, limit=3))
    else:
        mcp.run()
