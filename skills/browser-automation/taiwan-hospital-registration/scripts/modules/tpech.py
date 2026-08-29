import os
import sys
import re
import json
import time
import subprocess
from typing import Dict, Any
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import urllib3
from PIL import Image
from playwright.sync_api import sync_playwright

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
    "0900": "耳鼻喉科", "1000": "眼科", "1100": "皮腹科", "1200": "神經內科",
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

        dept_code = dept.upper()
        if dept_code not in DEPT_OFFICIAL_H:
            # check alias
            dept_code = ALIAS_MAP_H.get(dept, "AA00")

        dept_name = DEPT_OFFICIAL_H.get(dept_code, "消化內科")
        url = f"https://webreg.tpech.gov.tw/RegOnline1_2.aspx?ZCode={branch_code}&DeptCode={dept_code}&deptname={quote(dept_name)}"

        try:
            r = requests.get(url, verify=False, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            schedules = []
            seen_schedule = set()
            current_dates = []
            
            for t in soup.find_all('table'):
                rows = t.find_all('tr')
                for row in rows:
                    cells = [c.text.strip().replace('\r', '').replace('\n', '') for c in row.find_all(['td', 'th'])]
                    if any(re.search(r'\d{3}/\d{1,2}/\d{1,2}', ct) for ct in cells):
                        current_dates = [c for c in cells if c]
                    elif cells and cells[0] in ['上午', '下午', '夜間']:
                        session_name = cells[0]
                        tds = row.find_all('td')[1:]
                        for col_idx, td in enumerate(tds):
                            raw_date = current_dates[col_idx] if col_idx < len(current_dates) else ''
                            date_match = re.search(r'\d{3}/\d{1,2}/\d{1,2}\s*\([^)]+\)', raw_date)
                            clean_date = date_match.group(0) if date_match else raw_date.strip()
                            clean_date = re.sub(r'\s+', ' ', clean_date)
                            
                            links = td.find_all('a', href=True)
                            for a in links:
                                if 'RegOnline1_3.aspx' in a['href']:
                                    doc_name = a.text.strip()
                                    if doctor and doctor.strip() not in doc_name:
                                        continue
                                    href = a['href']
                                    key = (clean_date, session_name, doc_name, href)
                                    if key not in seen_schedule:
                                        seen_schedule.add(key)
                                        schedules.append({
                                            "date": clean_date,
                                            "session": session_name,
                                            "doctor": doc_name,
                                            "link": href
                                        })
                                    
            return {
                "success": True,
                "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
                "branch_code": branch_code,
                "branch_name": branch_name,
                "department": dept_name,
                "doctor_filter": doctor,
                "count": len(schedules),
                "schedule": schedules
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"抓取門診表失敗: {str(e)}"
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

    def book(self, id_number: str = "", birthday: str = "", branch: str = "H", dept: str = "", doctor: str = "", index: str = "21", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")

        creds = get_user_credentials()
        actual_id = id_number or creds.get("id_number")
        actual_bday = birthday or creds.get("birthday_roc") or creds.get("birthday_ad")

        if not actual_id:
            return {"success": False, "error": "缺少身分證字號。請設定 USER_ID_NUMBER 或帶入參數。"}

        b_str = str(actual_bday)
        if len(b_str) == 6:
            y, m, d = b_str[:2], b_str[2:4], b_str[4:6]
        elif len(b_str) == 7:
            y, m, d = b_str[:3], b_str[3:5], b_str[5:7]
        else:
            y, m, d = "72", "10", "20"

        def get_captcha_ocr(img_path):
            cmd = ['tesseract', img_path, 'stdout', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789']
            res = subprocess.run(cmd, capture_output=True, text=True)
            d = ''.join(c for c in res.stdout if c.isdigit())
            if len(d) == 4:
                return d
            img = Image.open(img_path).convert('L')
            img = img.resize((img.width * 3, img.height * 3), Image.Resampling.LANCZOS)
            img_bin = img.point(lambda p: 255 if p > 140 else 0)
            proc_path = '/tmp/tpech_proc.png'
            img_bin.save(proc_path)
            res2 = subprocess.run(['tesseract', proc_path, 'stdout', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789'], capture_output=True, text=True)
            return ''.join(c for c in res2.stdout if c.isdigit())

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                alerts = []
                def on_dialog(dialog_obj):
                    alerts.append(dialog_obj.message)
                    dialog_obj.accept()
                page.on('dialog', on_dialog)

                page.goto("https://webreg.tpech.gov.tw/RegOnline1_1.aspx?ZCode=" + branch_code)
                page.click('a:has-text("消化內科")')
                page.wait_for_load_state("networkidle")
                
                page.click(f'a[href*="index={index}"]')
                page.wait_for_load_state("networkidle")
                
                page.check("input#rbPAT_ID")
                page.fill("input#no", actual_id)
                page.select_option("select#yeartype", value="")
                page.select_option("select#y1", value=y)
                page.select_option("select#m1", value=m)
                page.select_option("select#d1", value=d)
                page.check("input#rbAgreeNot")
                
                for attempt in range(1, 6):
                    alerts.clear()
                    captcha_img = page.query_selector('img[src*="ValidateCode"]')
                    if captcha_img:
                        captcha_path = "/tmp/tpech_captcha.png"
                        captcha_img.screenshot(path=captcha_path)
                        ocr = get_captcha_ocr(captcha_path)
                        if ocr and len(ocr) == 4:
                            page.fill("input#TextBox1", ocr)
                            page.click("input#Button1")
                            page.wait_for_load_state("networkidle")
                            time.sleep(2)
                            
                            is_err = any("驗證碼錯誤" in a for a in alerts)
                            if is_err:
                                page.goto(f"https://webreg.tpech.gov.tw/RegOnline1_3.aspx?ChaId=A105&tab=1&index={index}")
                                page.wait_for_load_state("networkidle")
                                continue
                            else:
                                browser.close()
                                return {
                                    "success": True,
                                    "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
                                    "alerts": alerts,
                                    "message": "預約門診掛號成功"
                                }
                browser.close()
                return {"success": False, "error": "掛號失敗或驗證碼多次輸入錯誤"}
        except Exception as e:
            return {"success": False, "error": f"預約掛號失敗: {str(e)}"}

    def cancel(self, id_number: str = "", birthday: str = "", branch: str = "H", **kwargs) -> Dict[str, Any]:
        branch_code = resolve_branch_code(branch)
        branch_name = BRANCH_MAP.get(branch_code, "和平院區")

        creds = get_user_credentials()
        actual_id = id_number or creds.get("id_number")
        actual_bday = birthday or creds.get("birthday_roc") or creds.get("birthday_ad")

        if not actual_id:
            return {"success": False, "error": "缺少身分證字號。請設定 USER_ID_NUMBER 或帶入參數。"}

        # Convert birthday ROC into year, month, day
        b_str = str(actual_bday)
        if len(b_str) == 6:
            y, m, d = b_str[:2], b_str[2:4], b_str[4:6]
        elif len(b_str) == 7:
            y, m, d = b_str[:3], b_str[3:5], b_str[5:7]
        else:
            y, m, d = "72", "10", "20"

        def get_captcha_ocr(img_path):
            cmd = ['tesseract', img_path, 'stdout', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789']
            res = subprocess.run(cmd, capture_output=True, text=True)
            d = ''.join(c for c in res.stdout if c.isdigit())
            if len(d) == 4:
                return d
            img = Image.open(img_path).convert('L')
            img = img.resize((img.width * 3, img.height * 3), Image.Resampling.LANCZOS)
            img_bin = img.point(lambda p: 255 if p > 140 else 0)
            proc_path = '/tmp/tpech_proc.png'
            img_bin.save(proc_path)
            res2 = subprocess.run(['tesseract', proc_path, 'stdout', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789'], capture_output=True, text=True)
            return ''.join(c for c in res2.stdout if c.isdigit())

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                alerts = []
                def on_dialog(d):
                    alerts.append(d.message)
                    d.accept()
                page.on('dialog', on_dialog)
                
                page.goto('https://webreg.tpech.gov.tw/RegOnline3_1.aspx')
                page.wait_for_load_state('networkidle')
                
                page.check('input#rbPAT_ID')
                page.fill('input#no', actual_id)
                page.select_option('select#yeartype', value='')
                page.select_option('select#y1', value=y)
                page.select_option('select#m1', value=m)
                page.select_option('select#d1', value=d)
                
                captcha_img = page.query_selector('img[src*="ValidateCode"]')
                if captcha_img:
                    captcha_path = '/tmp/tpech_cancel_captcha.png'
                    captcha_img.screenshot(path=captcha_path)
                    ocr = get_captcha_ocr(captcha_path)
                    page.fill('input#TextBox1', ocr)
                    
                page.click('input#Button1')
                page.wait_for_load_state('networkidle')
                
                chk = page.query_selector('input#dgA_del_0')
                if chk:
                    chk.check()
                    page.click('input#Cancel')
                    page.wait_for_load_state('networkidle')
                    time.sleep(2)
                    
                    browser.close()
                    return {
                        "success": True,
                        "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
                        "alerts": alerts,
                        "message": "掛號已成功取消"
                    }
                else:
                    browser.close()
                    return {
                        "success": True,
                        "hospital": f"TPECH 臺北市立聯合醫院 ({branch_name})",
                        "message": "查無可取消的預約掛號紀錄"
                    }
        except Exception as e:
            return {"success": False, "error": f"取消掛號失敗: {str(e)}"}
