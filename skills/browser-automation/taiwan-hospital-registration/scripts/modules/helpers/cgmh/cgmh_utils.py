import pytesseract
from PIL import Image

# Shared utilities for Chang Gung Memorial Hospital (CGMH) automation scripts.

def clean_ocr_text(txt):
    """
    Strips non-alphanumeric characters from OCR recognized strings.
    """
    return "".join(c for c in txt if c.isalnum())

def solve_captcha(img_path):
    """
    Solves the CGMH 4-character alphanumeric CAPTCHA using multiple image-processing strategies.
    Returns a 4-character string if successful, otherwise a fallback recognized string.
    """
    img = Image.open(img_path)
    
    strategies = [
        # Strategy 1: Nearest Neighbor 6x, PSM 7 (highly reliable for clean alphanumeric strings)
        (lambda i: i.resize((i.width * 6, i.height * 6), Image.Resampling.NEAREST), "--psm 7"),
        # Strategy 2: Nearest Neighbor 6x, PSM 8 (treat as single word)
        (lambda i: i.resize((i.width * 6, i.height * 6), Image.Resampling.NEAREST), "--psm 8"),
        # Strategy 3: Grayscale, Lanczos 6x, Threshold 127, PSM 7
        (lambda i: i.convert('L').resize((i.width * 6, i.height * 6), Image.Resampling.LANCZOS).point(lambda p: 255 if p > 127 else 0), "--psm 7"),
        # Strategy 4: Grayscale, Lanczos 6x, Threshold 150, PSM 7
        (lambda i: i.convert('L').resize((i.width * 6, i.height * 6), Image.Resampling.LANCZOS).point(lambda p: 255 if p > 150 else 0), "--psm 7"),
        # Strategy 5: Grayscale, Lanczos 6x, Threshold 100, PSM 7
        (lambda i: i.convert('L').resize((i.width * 6, i.height * 6), Image.Resampling.LANCZOS).point(lambda p: 255 if p > 100 else 0), "--psm 7"),
        # Strategy 6: Nearest Neighbor 6x, PSM 6 (uniform block of text)
        (lambda i: i.resize((i.width * 6, i.height * 6), Image.Resampling.NEAREST), "--psm 6"),
    ]
    
    for idx, (process_fn, psm) in enumerate(strategies, 1):
        try:
            processed_img = process_fn(img)
            config = f"{psm} -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            txt = pytesseract.image_to_string(processed_img, config=config).strip()
            cleaned = clean_ocr_text(txt)
            if len(cleaned) == 4:
                return cleaned
        except Exception:
            pass
            
    # Fallback default recognition if no strategy yielded exactly 4 characters
    try:
        img_large = img.resize((img.width * 6, img.height * 6), Image.Resampling.NEAREST)
        txt = pytesseract.image_to_string(img_large, config="--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").strip()
        return clean_ocr_text(txt)
    except Exception:
        return "AAAA"
