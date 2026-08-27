#!/usr/bin/env python3
import json
import sys
import argparse
from collections import defaultdict

def analyze_community(file_path, keywords):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter transactions
    matched = []
    for x in data:
        bldg = x.get("building", "") or ""
        addr = x.get("address", "") or ""
        if any(kw in bldg or kw in addr for kw in keywords):
            matched.append(x)
            
    if not matched:
        print(f"No transactions found matching keywords: {keywords}")
        return

    # Sort chronologically
    matched.sort(key=lambda x: x.get("txnDate", ""))

    total_txns = len(matched)
    prices = [x["totalPriceWan"] for x in matched]
    unit_prices = [x["siteAdjUnitPrice"] for x in matched if x.get("siteAdjUnitPrice")]
    areas = [x["totalAreaPing"] for x in matched]
    
    # Yearly trends
    yearly_data = defaultdict(list)
    for x in matched:
        date = x.get("txnDate", "")
        if date and len(date) >= 4:
            year = date[:4]
            if x.get("siteAdjUnitPrice"):
                yearly_data[year].append(x["siteAdjUnitPrice"])

    # Layout distributions
    layouts = defaultdict(int)
    for x in matched:
        lay = x.get("layout") or "未知"
        layouts[lay] += 1

    print(f"## 🏢 社區交易數據分析報告 ({', '.join(keywords)})")
    print(f"- **總交易筆數**：{total_txns} 筆")
    if prices:
        print(f"- **總價區間**：{min(prices)} 萬 ～ {max(prices)} 萬")
    if unit_prices:
        avg_unit = sum(unit_prices) / len(unit_prices)
        print(f"- **單價區間**：{min(unit_prices):.2f} 萬/坪 ～ {max(unit_prices):.2f} 萬/坪")
        print(f"- **歷史均價**：{avg_unit:.2f} 萬/坪")
    if areas:
        print(f"- **坪數區間**：{min(areas):.2f} 坪 ～ {max(areas):.2f} 坪")

    print("\n### 📈 歷年單價走勢 (年均價)")
    print("| 年份 | 交易筆數 | 平均單價 (萬/坪) |")
    print("|---|---|---|")
    for yr in sorted(yearly_data.keys()):
        yr_prices = yearly_data[yr]
        avg_yr = sum(yr_prices) / len(yr_prices) if yr_prices else 0
        print(f"| {yr} 年 | {len(yr_prices)} 筆 | {avg_yr:.2f} 萬/坪 |")

    print("\n### 🏠 常見格局分布")
    for lay, count in sorted(layouts.items(), key=lambda x: x[1], reverse=True):
        print(f"- **{lay}**：{count} 筆")

    print("\n### 📋 最新 10 筆明細")
    print("| 交易年月 | 樓層 | 總價 (萬) | 單價 (萬/坪) | 總坪數 | 格局 |")
    print("|---|---|---|---|---|---|")
    for m in matched[-10:][::-1]:
        date = m.get("txnDate", "未知")
        floor = m.get("floor", "未知")
        price = m.get("totalPriceWan", 0)
        unit = m.get("siteAdjUnitPrice", 0)
        area = m.get("totalAreaPing", 0)
        lay = m.get("layout") or "未知"
        print(f"| {date} | {floor} | {price} | {unit:.2f} | {area:.2f} | {lay} |")

def main():
    parser = argparse.ArgumentParser(description="Analyze real estate JSON query outputs.")
    parser.add_argument("file", help="Path to lvr JSON file")
    parser.add_argument("keywords", nargs="+", help="Keywords to match (e.g. 馥華城峰)")
    args = parser.parse_args()
    analyze_community(args.file, args.keywords)

if __name__ == '__main__':
    main()
