#!/usr/bin/env python3
import os
import re
import sys
import argparse
import requests
from PIL import Image
import pytesseract

def download_image(url, output_path):
    """Downloads an image from a URL to a local path."""
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return False

def run_localized_ocr(img_path, public_ratio=0.35, output_dir=None):
    """Crops localized regions of a pre-sales blueprint, runs OCR, and extracts metrics."""
    if not os.path.exists(img_path):
        print(f"File not found: {img_path}", file=sys.stderr)
        return None
    
    try:
        img = Image.open(img_path)
    except Exception as e:
        print(f"Error opening image {img_path}: {e}", file=sys.stderr)
        return None
    
    w, h = img.size
    
    # Define standard crop coordinates for layout blueprint labels (corners and edges)
    crops = {
        "top_left": (0, 0, int(w * 0.5), int(h * 0.25)),
        "top_right": (int(w * 0.5), 0, w, int(h * 0.25)),
        "bottom_left": (0, int(h * 0.5), int(w * 0.5), h),
        "bottom_right": (int(w * 0.5), int(h * 0.75), w, h),
    }
    
    all_text = ""
    results = {
        "file": img_path,
        "width": w,
        "height": h,
        "crops": {}
    }
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    for name, box in crops.items():
        crop_img = img.crop(box)
        if output_dir:
            crop_img.save(os.path.join(output_dir, f"crop_{name}_{os.path.basename(img_path)}"))
            
        # Preprocessing to improve OCR accuracy
        gray = crop_img.convert('L')
        large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        
        try:
            txt = pytesseract.image_to_string(large, lang='chi_tra+eng').strip()
        except Exception as e:
            print(f"Tesseract error on {name}: {e}", file=sys.stderr)
            txt = ""
            
        results["crops"][name] = txt
        all_text += "\n" + txt

    # Parsing Layout Code (e.g., A1, A2, B3, C6, D6, E2, F6)
    # Commonly written like "A2(同E2)戶", "D6戶", "C2戶"
    layout_codes = set()
    # Match pattern for layout labels like A2, D6, C1, B5, etc.
    code_matches = re.findall(r'\b([A-F]\d)\b', all_text)
    for code in code_matches:
        layout_codes.add(code)
    
    # Check for Chinese representations of layout codes
    zh_code_matches = re.findall(r'([A-F]\d)\s*戶', all_text)
    for code in zh_code_matches:
        layout_codes.add(code)
        
    # Parsing Exclusive Area in Square Meters (e.g. 55.11平方公尺, 67.39平方公尺)
    sqm_area = None
    sqm_matches = re.findall(r'(\d+\.\d+)\s*(?:平方公尺|sqm|m\^2|F\s*FER|BER|F\s*FAR|F\s*F2R)', all_text, re.IGNORECASE)
    if sqm_matches:
        sqm_area = float(sqm_matches[0])
    else:
        # Generic decimal search near area-related keywords
        area_keywords = ["專有", "部分", "面積", "主建物", "陽台"]
        for line in all_text.split('\n'):
            if any(kw in line for kw in area_keywords):
                decimal_matches = re.findall(r'(\d+\.\d+)', line)
                if decimal_matches:
                    sqm_area = float(decimal_matches[0])
                    break

    # Calculate calculations
    results["layout_codes"] = sorted(list(layout_codes))
    results["exclusive_sqm"] = sqm_area
    
    if sqm_area:
        exclusive_pyeong = sqm_area * 0.3025
        sales_pyeong = exclusive_pyeong / (1.0 - public_ratio)
        results["exclusive_pyeong"] = round(exclusive_pyeong, 2)
        results["sales_pyeong"] = round(sales_pyeong, 2)
    else:
        results["exclusive_pyeong"] = None
        results["sales_pyeong"] = None
        
    return results

def main():
    parser = argparse.ArgumentParser(description="Taiwan Real Estate Layout localized crop-OCR tool.")
    parser.add_argument("source", help="Image URL or local file path")
    parser.add_argument("-p", "--public-ratio", type=float, default=0.35, help="Assumed public ratio (default: 0.35)")
    parser.add_argument("-o", "--output-dir", help="Directory to save crop files for debugging")
    args = parser.parse_args()
    
    source = args.source
    is_url = source.startswith("http://") or source.startswith("https://")
    
    local_path = source
    if is_url:
        os.makedirs("rian_park_temp", exist_ok=True)
        local_path = os.path.join("rian_park_temp", "downloaded_layout.jpg")
        print(f"Downloading remote image: {source} -> {local_path} ...")
        if not download_image(source, local_path):
            sys.exit(1)
            
    print(f"Running localized OCR on {local_path} ...")
    report = run_localized_ocr(local_path, public_ratio=args.public_ratio, output_dir=args.output_dir)
    
    if report:
        print("\n" + "="*40)
        print("🏠 TAIWAN REAL ESTATE LAYOUT OCR REPORT")
        print("="*40)
        print(f"File/Source: {source}")
        print(f"Image Resolution: {report['width']} x {report['height']}")
        print(f"Detected Layout Codes: {', '.join(report['layout_codes']) if report['layout_codes'] else 'Not Found'}")
        
        if report['exclusive_sqm']:
            print(f"Exclusive Area (專有部分面積): {report['exclusive_sqm']} m²")
            print(f"Exclusive Pyeong (約專有坪數): {report['exclusive_pyeong']} 坪")
            print(f"Assumed Public Ratio (公設比): {args.public_ratio * 100:.1f}%")
            print(f"Calculated Sales Pyeong (約登記銷售坪數): {report['sales_pyeong']} 坪")
        else:
            print("Area metrics (專有部分面積) could not be reliably extracted.")
        print("="*40 + "\n")
    else:
        print("Failed to analyze image.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
