#!/usr/bin/env python3
import json
import sys
import os
import re
import subprocess
import argparse

def robust_parse_address(addr):
    # Convert full-width alphanumeric to half-width
    half = []
    for char in addr:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            half.append(chr(code - 0xfee0))
        elif code == 0x3000:
            half.append(chr(0x0020))
        else:
            half.append(char)
    addr = "".join(half)
    
    # Standardize '之' to '-'
    addr = addr.replace("之", "-")
    
    county = ""
    district = ""
    street = ""
    section = ""
    lane = ""
    alley = ""
    door = ""
    floor = ""
    
    # Sequential slice extraction
    m_county = re.search(r"([^市縣]+[市縣])", addr)
    if m_county:
        county = m_county.group(1)
        addr = addr[m_county.end():]
        
    m_dist = re.search(r"([^區鄉鎮市]+[區鄉鎮市])", addr)
    if m_dist:
        district = m_dist.group(1)
        addr = addr[m_dist.end():]
        
    m_street = re.search(r"([^路街]+[路街])", addr)
    if m_street:
        street = m_street.group(1)
        addr = addr[m_street.end():]
        
    m_sec = re.search(r"([0-9一二三四五六七八九十]+段)", addr)
    if m_sec:
        section = m_sec.group(1)
        addr = addr[m_sec.end():]
        
    m_lane = re.search(r"(\d+巷)", addr)
    if m_lane:
        lane = m_lane.group(1)
        addr = addr[m_lane.end():]
        
    m_alley = re.search(r"(\d+弄)", addr)
    if m_alley:
        alley = m_alley.group(1)
        addr = addr[m_alley.end():]
        
    m_door = re.search(r"(\d+(?:-\d+)?)號", addr)
    if m_door:
        door = m_door.group(1)
        addr = addr[m_door.end():]
        
    m_floor = re.search(r"(\d+樓)", addr)
    if m_floor:
        floor = m_floor.group(1)
        
    return {
        "county": county,
        "district": district,
        "street": street,
        "section": section,
        "lane": lane,
        "alley": alley,
        "door": door,
        "floor": floor
    }

def infer_layout_for_address(target_address):
    print(f"Analyzing address: {target_address}")
    parsed = robust_parse_address(target_address)
    if not parsed or not parsed['door']:
        print("Error: Could not parse door number or address components.", file=sys.stderr)
        return False
        
    print(f"Parsed Components: County={parsed['county']}, District={parsed['district']}, Street={parsed['street']}{parsed['section']}, Lane={parsed['lane']}, Alley={parsed['alley']}, Door={parsed['door']}, Floor={parsed['floor']}")
    
    # Construct query string for tw-lvr
    query_parts = []
    if parsed['county']: query_parts.append(parsed['county'])
    if parsed['district']: query_parts.append(parsed['district'])
    if parsed['street']: query_parts.append(parsed['street'])
    if parsed['section']: query_parts.append(parsed['section'])
    if parsed['lane']: query_parts.append(parsed['lane'])
    
    query_str = "".join(query_parts)
    print(f"Constructed tw-lvr query location: {query_str}")
    
    # Run tw-lvr via wrapper script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wrapper_path = os.path.join(script_dir, "tw-lvr-wrapper.sh")
    
    temp_json = "temp_transactions.json"
    cmd = [wrapper_path, "extract", "--where", query_str, "--from", "201201", "--to", "202612", "--out", temp_json]
    
    print("Running actual price registry query in background...")
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        print(f"Error executing tw-lvr: {e}", file=sys.stderr)
        return False
        
    if not os.path.exists(temp_json):
        print("Error: Query did not produce output transactions.", file=sys.stderr)
        return False
        
    try:
        with open(temp_json, 'r', encoding='utf-8') as f:
            transactions = json.load(f)
    except Exception as e:
        print(f"Error parsing transaction results: {e}", file=sys.stderr)
        if os.path.exists(temp_json): os.remove(temp_json)
        return False
        
    # Filter transactions matching the same vertical stack / door
    target_door = parsed['door'] # e.g. "67-2" or "67"
    
    exact_stack_matches = []
    adjacent_matches = []
    
    for tx in transactions:
        # Standardize matching door formats (e.g. 67-2 vs 67之2)
        addr = tx.get("address", "")
        normalized_addr = addr.replace("之", "-")
        tx_door_match = re.search(r"(\d+(?:-\d+)?)號", normalized_addr)
        if tx_door_match:
            tx_door = tx_door_match.group(1)
            if tx_door == target_door:
                exact_stack_matches.append(tx)
            elif tx_door.split("-")[0] == target_door.split("-")[0]:
                adjacent_matches.append(tx)
                
    # Clean up temp file
    if os.path.exists(temp_json):
        os.remove(temp_json)
        
    print("\n" + "="*50)
    print(f"🏠 結構格局推導報告：{target_address}")
    print("="*50)
    
    if exact_stack_matches:
        print(f"\n✅ 成功找到該垂直線路 (門牌: {target_door} 號) 的歷史成交與申報資料 (共 {len(exact_stack_matches)} 筆)：")
        exact_stack_matches.sort(key=lambda x: x.get("txnDate", ""), reverse=True)
        
        # Collect unique layouts and areas
        layouts = set()
        areas = []
        main_areas = []
        public_pcts = []
        
        print("\n| 交易年月 | 樓層 | 總面積 (坪) | 主建物實坪 | 格局 | 建案名稱 |")
        print("|---|---|---|---|---|---|")
        for tx in exact_stack_matches:
            date = tx.get("txnDate", "未知")
            floor = tx.get("floor", "未知")
            area = tx.get("totalAreaPing", 0)
            main_m2 = tx.get("mainAreaM2")
            main_ping = f"{main_m2 * 0.3025:.2f} 坪" if main_m2 else "未登記"
            lay = tx.get("layout") or "無格局登記"
            bldg = tx.get("building") or "華廈/大樓"
            
            layouts.add(lay)
            areas.append(area)
            if main_m2:
                main_areas.append(main_m2 * 0.3025)
                # Public ratio approx (excluding parkings)
                if area > 0:
                    pub_ratio = 1 - (main_m2 * 0.3025 / area)
                    public_pcts.append(pub_ratio * 100)
            
            print(f"| {date} | {floor} | {area:.2f} | {main_ping} | {lay} | {bldg} |")
            
        print("\n### 🔍 結構物理格局推導結論：")
        primary_layout = list(layouts)[0] if len(layouts) == 1 else "、".join(layouts)
        avg_area = sum(areas) / len(areas) if areas else 0
        avg_main = sum(main_areas) / len(main_areas) if main_areas else 0
        avg_pub = sum(public_pcts) / len(public_pcts) if public_pcts else 18.9 # default fallback
        
        print(f"- **主體原始格局**：**{primary_layout}**")
        print(f"- **標準登記總面積**：約 **{avg_area:.2f} 坪**")
        print(f"- **室內主建物實坪**：約 **{avg_main:.2f} 坪**")
        print(f"- **公設比估算**：約 **{avg_pub:.1f}%**")
        print("\n💡 說明：同一垂直線路（即同一個-分號門牌，如67-2號）在結構中具有相同的承重牆、梁柱主體、管道間與外窗位置，除非住戶後續大肆變更，否則格局是絕對一致的。")
        
    elif adjacent_matches:
        print(f"\n⚠️ 未找到該特定線路 ({target_door} 號) 的歷史記錄，但找到同社區鄰近戶別 (門牌首號 {target_door.split('-')[0]} 號) 的資料 (共 {len(adjacent_matches)} 筆)：")
        adjacent_matches.sort(key=lambda x: x.get("txnDate", ""), reverse=True)
        
        print("\n| 門牌 | 交易年月 | 樓層 | 總面積 (坪) | 格局 | 建案名稱 |")
        print("|---|---|---|---|---|---|")
        for tx in adjacent_matches[:10]:
            addr = tx.get("address", "未知")
            date = tx.get("txnDate", "未知")
            floor = tx.get("floor", "未知")
            area = tx.get("totalAreaPing", 0)
            lay = tx.get("layout") or "無格局登記"
            bldg = tx.get("building") or "華廈/大樓"
            print(f"| {addr} | {date} | {floor} | {area:.2f} | {lay} | {bldg} |")
            
        print("\n💡 建議：可依此鄰近同面積級距（坪數相近者）之格局作為該社區相同棟別的鏡射或同款對稱格局參考。")
        
    else:
        print(f"\n❌ 遺憾：在該路段/巷弄資料中，未找到該門牌或同號群組的實價登錄登記歷史。")
        
    print("="*50)
    return True

def main():
    parser = argparse.ArgumentParser(description="Infer Taiwanese building layout using actual price registry vertical stacks.")
    parser.add_argument("address", help="Exact address to infer (e.g. 台北市信義區忠孝東路五段372巷27弄67-2號2樓)")
    args = parser.parse_args()
    
    infer_layout_for_address(args.address)

if __name__ == '__main__':
    main()
