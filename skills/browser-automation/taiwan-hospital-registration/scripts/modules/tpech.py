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

TPECH_DEPT_URL = "https://webreg.tpech.gov.tw/RegOnline1_1.aspx"

BRANCH_MAP = {
    "H": "和平院區", "J": "婦幼院區", "F": "仁愛院區", "G": "中興院區",
    "Q": "忠孝院區", "M": "陽明院區", "X": "林森院區", "K": "松德院區",
    "S": "中醫中心", "W": "昆明院區"
}

DEPT_OFFICIAL_H = {
    "0100": "家庭醫學科", "0200": "一般內科", "0300": "一般外科", "0400": "小兒科",
    "0500": "婦產科", "0600": "骨科", "0700": "神經外科", "0800": "泌尿科",
    "0900": "耳鼻喉科", "1000": "眼科", "1100": "皮膚科", "1200": "神經內科",
    "1300": "精神科", "1400": "復健科", "1500": "整形外科", "4000": "牙科",
    "6000": "中醫科", "6001": "中醫內科", "6002": "中醫針灸科", "6003": "中醫傷科",
    "AA00": "消化內科", "AB00": "心臟血管內科", "AC00": "胸腔內科", "AD00": "腎臟內科",
    "AE00": "過敏免疫風濕科", "AF00": "血液腫瘤科", "AG00": "內分泌及新陳代謝科"
}

ALIAS_MAP_H = {
    "家醫": "0100", "家醫科": "0100", "家庭醫學科": "0100",
    "內科": "0200", "一般內科": "0200", "外科": "0300", "一般外科": "0300",
    "兒科": "0400", "小兒科": "0400", "婦科": "0500", "婦產科": "0500",
    "骨科": "0600", "胃腸科": "AA00", "肝膽科": "AA00", "胃腸肝膽科": "AA00",
    "心臟科": "AB00", "心臟內科": "AB00", "心臟血管內科": "AB00"
}

def resolve_branch_code(branch_kw: str = "H") -> str:
    if not branch_kw:
        return "H"
    kw = branch_kw.strip().upper()
    if kw in BRANCH_MAP:
        return kw
    for code, name in BRANCH_MAP.items():
        if kw in name:
            return code
    return "H"

class TpechModule(BaseHospitalModule):
    def dept(self, keyword: str = "", branch: str = "H", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")
        kw = (keyword or "").strip().lower()

        dept_dict = {}
        for code, name in DEPT_OFFICIAL_H.items():
            dept_dict[name] = code
        for alias, code in ALIAS_MAP_H.items():
            official_name = DEPT_OFFICIAL_H.get(code, alias)
            dept_dict[official_name] = code

        matched = []
        seen = set()

        for name, code in dept_dict.items():
            if kw:
                aliases = [a for a, c in ALIAS_MAP_H.items() if c == code]
                if kw in name.lower() or kw in code.lower() or any(kw in a.lower() for a in aliases):
                    if (name, code) not in seen:
                        seen.add((name, code))
                        matched.append({"department_name": name, "department_code": code})
            else:
                if (name, code) not in seen:
                    seen.add((name, code))
                    matched.append({"department_name": name, "department_code": code})

        return {
            "success": True,
            "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "count": len(matched),
            "keyword": keyword,
            "departments": matched
        }

    def schedule(self, dept: str, doctor: str = "", branch: str = "H", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")

        # Try schedule query
        return {
            "success": True,
            "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "department": dept,
            "doctor_filter": doctor,
            "schedule": []
        }

    def progress(self, dept: str, doctor: str = "", session: str = "", room: str = "", number: str = "", branch: str = "H", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")

        return {
            "success": True,
            "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "department": dept,
            "records": []
        }

    def records(self, id_number: str = "", birthday: str = "", branch: str = "H", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")

        creds = get_user_credentials()
        actual_id = id_number or creds.get("id_number")
        actual_bday = birthday or creds.get("birthday_roc") or creds.get("birthday_ad")

        if not actual_id:
            return {"success": False, "error": "缺少身分證字號。請設定 USER_ID_NUMBER 或帶入參數。"}

        return {
            "success": True,
            "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "id_number": actual_id,
            "birthday": actual_bday,
            "records": []
        }
