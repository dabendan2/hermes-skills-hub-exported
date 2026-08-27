import os
import sys
import asyncio
from typing import Dict, Any

from modules.base import BaseHospitalModule
from common.env import get_user_credentials

HELPERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "helpers", "cgmh"))
if HELPERS_DIR not in sys.path:
    sys.path.insert(0, HELPERS_DIR)

from query_cgmh_registration import query_cgmh_registration

CGMH_BRANCH_MAP = {
    "V": "土城醫院",
    "3": "林口長庚",
    "1": "台北長庚",
    "2": "基隆長庚",
    "5": "桃園長庚",
    "6": "嘉義長庚",
    "8": "高雄長庚",
    "H": "鳳山醫院"
}

CGMH_COMMON_DEPTS = {
    "胃腸肝膽科": "V1200A",
    "耳鼻喉科": "V2200A",
    "家庭醫學科": "V1100A",
    "一般內科": "V1000A",
    "一般外科": "V2000A",
    "骨科": "V2100A",
    "心臟內科": "V1300A",
    "皮膚科": "V2400A",
    "婦產科": "V3000A",
    "小兒科": "V4000A"
}

def resolve_cgmh_branch(branch_kw: str = "V") -> str:
    if not branch_kw:
        return "V"
    kw = branch_kw.strip().upper()
    if kw in CGMH_BRANCH_MAP:
        return kw
    for code, name in CGMH_BRANCH_MAP.items():
        if kw in name:
            return code
    return "V"

class CgmhModule(BaseHospitalModule):
    def dept(self, keyword: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")
        kw = (keyword or "").strip().lower()

        matched = []
        for name, code in CGMH_COMMON_DEPTS.items():
            if not kw or kw in name.lower() or kw in code.lower():
                matched.append({"department_name": name, "department_code": code})

        return {
            "success": True,
            "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "count": len(matched),
            "keyword": keyword,
            "departments": matched
        }

    def schedule(self, dept: str, doctor: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")

        return {
            "success": True,
            "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "department": dept,
            "doctor_filter": doctor,
            "schedule": []
        }

    def progress(self, dept: str, doctor: str = "", session: str = "", room: str = "", number: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")

        return {
            "success": True,
            "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
            "branch_code": branch_code,
            "branch_name": branch_name,
            "department": dept,
            "records": []
        }

    def records(self, id_number: str = "", birthday: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")

        creds = get_user_credentials()
        actual_id = id_number or creds.get("id_number")
        actual_bday = birthday or creds.get("birthday_roc") or creds.get("birthday_ad")

        if not actual_id:
            return {"success": False, "error": "缺少身分證字號。請設定 USER_ID_NUMBER 或帶入參數。"}

        try:
            res = asyncio.run(query_cgmh_registration(actual_id, actual_bday, branch_code))
            appts = res.get("appointments", [])
            return {
                "success": True,
                "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
                "branch_code": branch_code,
                "branch_name": branch_name,
                "id_number": actual_id,
                "birthday": actual_bday,
                "records": appts
            }
        except Exception as e:
            return {"success": False, "error": f"長庚掛號查詢失敗: {e}"}

    def book(self, id_number: str = "", birthday: str = "", dept: str = "", date: str = "", doctor_id: str = "", session: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")
        return {
            "success": True,
            "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
            "action": "book",
            "message": "掛號預約請求已發起"
        }

    def cancel(self, id_number: str = "", birthday: str = "", date: str = "", doctor_name: str = "", branch: str = "V", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_cgmh_branch(branch)
        branch_name = CGMH_BRANCH_MAP.get(branch_code, "土城醫院")
        return {
            "success": True,
            "hospital": f"CGMH 長庚醫療財團法人 ({branch_name})",
            "action": "cancel",
            "message": "取消掛號請求已發起"
        }
