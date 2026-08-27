import os
import sys
import re
import json
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

from modules.base import BaseHospitalModule
from common.env import get_user_credentials

FEMH_BASE_URL = "https://www.femh.org.tw"
FEMH_PROGRESS_URL = "https://www.femh.org.tw/visit/visit.aspx?Action=9"
FEMH_SCHEDULE_BASE = "https://www.femh.org.tw/webregs/RegSec1.aspx?ID="
FEMH_QUERY_REG_URL = "https://www.femh.org.tw/webreg_net/default.aspx"

DEPT_MAP = {
    "M痘疫苗門診": "0213F", "一般外科": "0281", "一般醫學內科": "0214", "人工植牙科": "0270J",
    "口腔顎面外科": "0271", "大腸直腸外科": "0286", "小兒外科": "0289", "小兒部": "0230",
    "兒科": "0230", "小兒科": "0230", "心臟血管內科": "0401", "心臟內科": "0401",
    "心臟血管外科": "0406", "心臟外科": "0406", "牙周病科": "0270B", "牙科部": "0270",
    "牙科": "0270", "皮膚科": "0240", "耳鼻喉部": "0250", "耳鼻喉科": "0250",
    "形體美容醫學中心": "0296", "肝膽胃腸科": "0204", "胃腸肝膽科": "0204", "腸胃科": "0204",
    "乳房門診": "0281B", "兒童牙科": "0270D", "兒童發展篩檢門診": "0230F", "放射腫瘤科": "0380",
    "泌尿科": "0285", "家庭牙科": "0270I", "家庭醫學科自費健檢": "0292G", "家庭醫學部": "0292",
    "家庭醫學科": "0292", "家醫科": "0292", "國際旅遊門診": "0292", "特殊需求者牙科": "0270F",
    "疼痛門診": "0330A", "神經外科": "0282", "神經醫學部": "0206", "神經內科": "0206",
    "胸腔內科": "0207", "胸腔外科": "0284", "骨科部": "0287", "骨科": "0287",
    "高壓氧中心": "0299", "假牙贋復科": "0270C", "婦科": "0221", "婦產部": "0221",
    "婦產科": "0221", "眼科部": "0260", "眼科": "0260", "脫垂尿失禁門診": "0221C",
    "創傷科": "0288", "復健科": "0450", "腎臟內科": "0205", "傳統醫學科": "0370",
    "中醫": "0370", "傷造口護理諮詢": "0283E", "感染科": "0213", "新陳代謝科": "0203",
    "內分泌新陳代謝科": "0203", "腫瘤科暨血液科": "0208", "血液腫瘤科": "0208", "過敏免疫風溼科": "0210",
    "風濕免疫科": "0210", "精神暨心身醫學部": "0293", "精神科": "0293", "身心科": "0293",
    "影像醫學科": "0340", "齒顎矯正科": "0272", "整形外科": "0283", "營養科": "0430"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

def resolve_dept_code(keyword: str) -> str:
    kw = (keyword or "").strip()
    if not kw:
        return ""
    if kw in DEPT_MAP.values():
        return kw
    if kw in DEPT_MAP:
        return DEPT_MAP[kw]
    for name, code in DEPT_MAP.items():
        if kw in name or name in kw:
            return code
    return kw

class FemhModule(BaseHospitalModule):
    def dept(self, keyword: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        kw = (keyword or "").strip().lower()
        matched = []
        seen = set()

        target_code = resolve_dept_code(kw) if kw else ""

        for name, code in DEPT_MAP.items():
            if kw:
                if kw in name.lower() or kw in code.lower() or (target_code and code == target_code):
                    if name not in seen:
                        seen.add(name)
                        matched.append({"department_name": name, "department_code": code})
            else:
                if code not in seen:
                    seen.add(code)
                    matched.append({"department_name": name, "department_code": code})

        return {
            "success": True,
            "hospital": "FEMH (亞東紀念醫院)",
            "count": len(matched),
            "keyword": keyword,
            "departments": matched
        }

    def schedule(self, dept: str, doctor: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        dept_code = resolve_dept_code(dept)
        if not dept_code:
            return {"success": False, "error": f"無法識別的科別名稱或代碼：「{dept}」"}

        url = f"{FEMH_SCHEDULE_BASE}{dept_code}"
        try:
            r = requests.get(url, headers=HEADERS, verify=False, timeout=15)
            r.raise_for_status()
        except Exception as e:
            return {"success": False, "error": f"連線至門診時刻表失敗：{e}"}

        soup = BeautifulSoup(r.text, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return {"success": False, "error": "門診時刻表頁面中未找到排班表格。"}

        headers_list = []
        schedule_data = []
        table = tables[0]
        header_tr = table.find("tr")
        if header_tr:
            headers_list = [th.get_text(strip=True) for th in header_tr.find_all(["th", "td"])]

        rows = table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all(["td", "th"])
            if not tds:
                continue
            session_name = tds[0].get_text(strip=True)
            days_data = {}
            for idx, td in enumerate(tds[1:], start=1):
                day_title = headers_list[idx] if idx < len(headers_list) else f"第{idx}天"
                a_tags = td.find_all("a")
                doc_list = []
                if a_tags:
                    for a in a_tags:
                        txt = a.get_text(strip=True)
                        clean_name = re.sub(r"(網|現|網現|額滿|現場)", "", txt).strip()
                        if not clean_name:
                            continue
                        href = str(a.get("href", "") or "")
                        available = "RegData.aspx" in href
                        if doctor and doctor not in clean_name:
                            continue
                        doc_list.append({
                            "name": clean_name,
                            "available": available,
                            "status": "可掛號" if available else "額滿"
                        })

                if doc_list:
                    days_data[day_title] = doc_list

            schedule_data.append({
                "session": session_name,
                "days": days_data
            })

        return {
            "success": True,
            "hospital": "FEMH (亞東紀念醫院)",
            "department": dept,
            "dept_code": dept_code,
            "doctor_filter": doctor,
            "headers": headers_list,
            "schedule": schedule_data
        }

    def progress(self, dept: str, doctor: str = "", session: str = "", room: str = "", number: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        dept_code = resolve_dept_code(dept) if dept else ""
        sess = requests.Session()
        try:
            r = sess.get(FEMH_PROGRESS_URL, headers=HEADERS, verify=False, timeout=15)
            r.raise_for_status()
        except Exception as e:
            return {"success": False, "error": f"連線至亞東醫院看診進度系統失敗：{e}"}

        soup = BeautifulSoup(r.text, "html.parser")
        records = []
        rows = soup.find_all("tr")
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            txts = [td.get_text(strip=True) for td in tds]
            if "診間" in txts[0] or "醫師" in txts[1]:
                d_name = txts[0]
                doc_name = txts[1]
                c_num = txts[2]
                if doctor and doctor not in doc_name:
                    continue
                records.append({
                    "department": d_name,
                    "doctor": doc_name,
                    "current_number": c_num
                })

        return {
            "success": True,
            "hospital": "FEMH (亞東紀念醫院)",
            "department": dept,
            "records": records
        }

    def records(self, id_number: str = "", birthday: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        creds = get_user_credentials()
        actual_id = id_number or creds.get("id_number")
        actual_bday = birthday or creds.get("birthday_roc") or creds.get("birthday_ad")

        if not actual_id:
            return {"success": False, "error": "缺少身分證字號。請設定 USER_ID_NUMBER 或帶入參數。"}

        return {
            "success": True,
            "hospital": "FEMH (亞東紀念醫院)",
            "id_number": actual_id,
            "birthday": actual_bday,
            "records": []
        }
