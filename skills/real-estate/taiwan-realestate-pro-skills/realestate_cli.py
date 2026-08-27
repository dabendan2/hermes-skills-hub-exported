#!/usr/bin/env python3
"""
Taiwan Real Estate Active Listing CLI Scraper (Yungching)
Licensed under MIT License.
"""

import sys
import os
import argparse
import requests
from bs4 import BeautifulSoup
import re
import time

# Ensure output is encoded in UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def verify_residential_status(url):
    """
    Deeper check to verify if the property is purely residential
    and not commercial/office space.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return False, "Link broken (404/expired)"
        
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text()
        
        # Check office keywords
        office_kws = ["一般事務所", "辦公室", "辦公用", "商業用", "一般商業區"]
        found_kws = [kw for kw in office_kws if kw in text]
        if found_kws:
            return False, f"Office keywords detected: {', '.join(found_kws)}"
            
        return True, "Residential verified"
    except Exception as e:
        return False, f"Verification failed: {str(e)}"

def search_yungching(district, max_price, max_age, min_net_area, exclude_office):
    # Yungching URL format for multiple filters
    url = f"https://buy.yungching.com.tw/list/台北市-{district}_c/-{max_price}_price/0-{max_age}_age"
    
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return results
        
        soup = BeautifulSoup(r.text, 'html.parser')
        items = soup.find_all(class_='search-result-list-item')
        
        for item in items:
            a_tag = item.find('a', class_='link')
            if not a_tag:
                continue
            href = a_tag['href'].strip('/')
            link = f"https://buy.yungching.com.tw/{href}"
            
            # Title
            title_el = item.find('h3') or item.find('img')
            title = title_el.get('alt') if (title_el and title_el.name == 'img') else (title_el.get_text(strip=True) if title_el else "無標題")
            
            # Info
            info_el = item.find(class_='info-wrapper')
            info_text = info_el.get_text(" | ", strip=True) if info_el else ""
            
            # Price
            price_el = item.find(class_='price-wrapper')
            price_text = price_el.get_text(" | ", strip=True) if price_el else ""
            
            # Parse Net Area
            net_area = 0.0
            net_match = re.search(r'主\+陽\s*(\d+\.?\d*)', info_text)
            if net_match:
                net_area = float(net_match.group(1))
                
            # Filter by min net area
            if net_area < min_net_area:
                continue
                
            # Parse Age
            age = 0.0
            age_match = re.search(r'(\d+\.?\d*)\s*年', info_text)
            if age_match:
                age = float(age_match.group(1))
                
            # Check parking
            has_parking = any(kw in info_text or kw in title or kw in price_text for kw in ["車位", "平車", "車", "機械", "平面"])
            
            # Deep residential validation if requested
            if exclude_office:
                is_residential, reason = verify_residential_status(link)
                if not is_residential:
                    continue # Skip office properties
                    
            results.append({
                'district': district,
                'title': title,
                'link': link,
                'price_text': price_text.split('|')[-1].strip(),
                'net_area': net_area,
                'age': age,
                'has_parking': has_parking,
                'info_summary': info_text[:120]
            })
            time.sleep(0.5) # Polite scraping delay
            
    except Exception as e:
        sys.stderr.write(f"Error querying {district}: {str(e)}\n")
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Taiwan Real Estate CLI Scraper (Yungching)")
    parser.add_argument("--districts", default="內湖區,南港區,松山區", help="Comma-separated district names")
    parser.add_argument("--price", type=int, default=3000, help="Max price in Wan (e.g. 3000)")
    parser.add_argument("--age", type=int, default=10, help="Max age in years (e.g. 10)")
    parser.add_argument("--net-area", type=float, default=15.0, help="Min net area (主+陽) in pings")
    parser.add_argument("--exclude-office", action="store_true", default=True, help="Exclude commercial office properties")
    
    args = parser.parse_args()
    
    target_districts = [d.strip() for d in args.districts.split(",")]
    
    print("=" * 60)
    print(f"🔍 篩選條件: 價格 <= {args.price}萬 | 屋齡 <= {args.age}年 | 實坪 >= {args.net_area}坪")
    print(f"📍 搜尋區域: {', '.join(target_districts)}")
    print("=" * 60)
    
    all_hits = []
    for dist in target_districts:
        hits = search_yungching(dist, args.price, args.age, args.net_area, args.exclude_office)
        all_hits.extend(hits)
        
    if not all_hits:
        print("\n❌ 找不到符合條件的純住宅物件。")
        return
        
    print(f"\n✨ 找到 {len(all_hits)} 個符合條件的物件：\n")
    print(f"| {'區域':<4} | {'房屋名稱':<22} | {'價格':<7} | {'屋齡':<4} | {'實坪':<5} | {'車位':<4} |")
    print("|" + "-"*6 + "|" + "-"*24 + "|" + "-"*9 + "|" + "-"*6 + "|" + "-"*7 + "|" + "-"*6 + "|")
    for h in all_hits:
        parking_str = "有" if h['has_parking'] else "無"
        title_trunc = h['title'][:20] + ".." if len(h['title']) > 20 else h['title']
        print(f"| {h['district']:<5} | {title_trunc:<22} | {h['price_text']:<7} | {h['age']:<4.1f}年 | {h['net_area']:<5.2f}坪 | {parking_str:<4} |")
        print(f"  👉 網址: {h['link']}")
        print(f"  📝 摘要: {h['info_summary']}")
        print("-" * 60)

if __name__ == "__main__":
    main()
