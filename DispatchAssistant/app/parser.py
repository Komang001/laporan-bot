import re


# =====================================================
# Owner Group Keywords
# =====================================================

REMOVE_SUFFIX = [
    "terimakasih",
    "terima kasih",
    "trimakasih",
    "trima kasih",
    "thanks",
    "thank you",
]


# =====================================================
# Parse Owner Group
# =====================================================

def parse_owner_group(note: str):

    if not note:
        return None

    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()

    # Try patterns in order of priority
    patterns = [
        r"(?:\bloker\b|\bog\b|owner\s+gr(?:o)?up)\s*[:.]?\s+(.+)",
        r"ke\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        candidate = match.group(1).strip()

        # Strip label prefixes: "Owner Group", "Owner Grup", "LOKER", "OWNER GROUP"
        candidate = re.sub(r"(?i)\bowner\s+gr(?:o)?up\b", "", candidate)
        candidate = re.sub(r"(?i)\bloker\b", "", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()

        # Ambil hanya kata UPPERCASE atau Title-Case (OG kadang ditulis campur,
        # misal "TIF Surveillance Area 1")
        words = candidate.split()
        og_words = []
        for w in words:
            # Berhenti jika bukan UPPERCASE atau angka INC
            if w.startswith("INC") or w.startswith("Req") or w.startswith("REQ"):
                break
            # Bersihkan tanda baca trailing (koma, titik, pagar) sebelum cek
            w_clean = w.strip(".,;:#")
            if not w_clean:
                break
            # Skip angka standalone di awal (bukan bagian OG)
            if w_clean.isdigit():
                if og_words:
                    og_words.append(w_clean)
                else:
                    break
            # Uppercase dengan huruf, angka, atau tanda hubung (misal MO-INSERA, TIF ASR FBB AREA 2)
            elif w_clean.replace("-", "").replace("_", "").isalpha() and w_clean == w_clean.upper() and len(w_clean) > 0:
                og_words.append(w_clean)
            elif w_clean.replace("-", "").replace("_", "").isalnum() and w_clean == w_clean.upper() and len(w_clean) > 0:
                og_words.append(w_clean)
            # Title-Case (huruf besar di awal, sisanya kecil) - bagian OG campur
            elif (
                len(w_clean) > 1
                and w_clean[0].isupper()
                and w_clean[1:].islower()
                and w_clean.replace("-", "").replace("_", "").isalnum()
            ):
                og_words.append(w_clean)
            else:
                break

        result = " ".join(og_words).strip()

        # Hapus suffix (case-insensitive)
        for suffix in REMOVE_SUFFIX:
            if suffix in result.lower():
                result = re.split(re.escape(suffix), result, flags=re.IGNORECASE)[0].strip()

        result = result.rstrip(".,;:#")

        if result:
            return result.upper()

    return None


# =====================================================
# Extract INC Number
# =====================================================

def extract_inc_number(text: str):
    if not text:
        return None
    match = re.search(r'INC\d+', text, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None


# =====================================================
# Compatibility
# =====================================================

def extract_owner_group(note: str):
    return parse_owner_group(note)


# =====================================================
# Bulk OG Change Detection
# =====================================================

def is_bulk_og_change(note: str):
    if not note:
        return False
    if "Salah_Dispatch_Regional_ke_Regional" not in note:
        return False
    return len(extract_bulk_inc_list(note)) > 1


def extract_bulk_og_target(note: str):
    if not note:
        return None

    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()

    # Try "ke" and "menjadi" patterns with priorities
    prefixes = [r"ke", r"menjadi"]

    for prefix in prefixes:
        # Pattern1: "{prefix} {OG} tiket :"
        match = re.search(rf"{prefix}\s+(.+?)\s+tiket\s*:", text, re.IGNORECASE)
        if match:
            return _clean_og_target(match.group(1))

        # Pattern2: "{prefix} {OG}" (before keywords like Nama, Request, Mohon, etc.)
        match = re.search(rf"{prefix}\s+(.+?)(?:\s+(?:Nama|Request|Mohon|moban|mohon|Inc|Ticket|User|TSEL))", text, re.IGNORECASE)
        if match:
            return _clean_og_target(match.group(1))

        # Pattern3: "{prefix} {OG}" sampai akhir string
        match = re.search(rf"{prefix}\s+(.+)", text, re.IGNORECASE)
        if match:
            return _clean_og_target(match.group(1))

    return None


def _clean_og_target(raw: str):
    raw = raw.strip().rstrip(".,;:")

    # Strip label prefixes: "Owner Group", "LOKER", "OWNER GROUP"
    raw = re.sub(r"(?i)\bowner\s+group\b", "", raw)
    raw = re.sub(r"(?i)\bloker\b", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    words = raw.split()
    og_words = []
    for w in words:
        if w.startswith("INC") or w.startswith("Req") or w.startswith("REQ"):
            break
        if w.isdigit():
            if og_words:
                og_words.append(w)
            else:
                break
        elif w.replace("-", "").replace("_", "").isalpha() and w == w.upper() and len(w) > 0:
            og_words.append(w)
        elif w.replace("-", "").replace("_", "").isalnum() and w == w.upper() and len(w) > 0:
            og_words.append(w)
        else:
            break
    result = " ".join(og_words).strip()
    return result.upper() if result else None


def extract_bulk_inc_list(note: str):
    if not note:
        return []
    matches = re.findall(r'INC\d+', note, re.IGNORECASE)
    return [m.upper() for m in matches]


# =====================================================
# Extract Service ID
# =====================================================

def extract_service_id(text: str):
    """Extract Service ID from ticket note.
    
    Examples:
      - 'Service ID menjadi 5480832_0214711635_VOICE' -> '5480832_0214711635_VOICE'
      - 'Service ID : 5480832_0214711635_VOICE' -> '5480832_0214711635_VOICE'
      - 'Service ID: 5480832_0214711635_VOICE' -> '5480832_0214711635_VOICE'
      - 'service_id = 5480832_0214711635_VOICE' -> '5480832_0214711635_VOICE'
      - 'service id ke 5480832_0214711635_VOICE' -> '5480832_0214711635_VOICE'
      - 'SERVICE NO MENJADI 0224233814 20780_0224233814_VOICE Sesuai' -> '20780_0224233814_VOICE'
    """
    if not text:
        return None

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Pattern 1: Explicit "Service ID" label
    pattern_explicit = r"(?i)\b(?:service\s*id|service_id|serviceid)\s*(?:menjadi|jadi|ke|adalah|:|:|=|\->|->)?\s*([A-Za-z0-9_\-\.]+)"
    match = re.search(pattern_explicit, clean)
    if match:
        candidate = match.group(1).strip().rstrip(".,;:!")
        if candidate and candidate.lower() not in ("menjadi", "jadi", "ke", "adalah", "null", "none", "tidak", "ada"):
            return candidate

    # Pattern 2: Fallback - Service ID format is typically DIGITS_DIGITS_WORD
    # e.g. 20780_0224233814_VOICE, 5480832_0214711635_VOICE
    pattern_format = r"\b(\d+_\d+_[A-Za-z][A-Za-z0-9]*)\b"
    match = re.search(pattern_format, clean)
    if match:
        return match.group(1)

    return None


# =====================================================
# Extract Service Type
# =====================================================

def extract_service_type(text: str):
    """Extract Service Type from ticket note.
    
    Examples:
      - 'moban ubah service type ke WMS LITE' -> 'WMS LITE'
      - 'Service Type menjadi VOICE' -> 'VOICE'
      - 'Service Type : VOICE' -> 'VOICE'
      - 'service type: WMS LITE' -> 'WMS LITE'
      - 'service_type = INTERNET' -> 'INTERNET'
      - 'mohon ganti service type ke ASTINET terima kasih' -> 'ASTINET'
    """
    if not text:
        return None

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()

    stop_keywords = [
        r"\bservice\s*id\b",
        r"\bservice_id\b",
        r"\bservice\s*no\b",
        r"\bservice_no\b",
        r"\bsesuai\b",
        r"\breference\b",
        r"\bref\b",
        r"\bmohon\b",
        r"\bmoban\b",
        r"\btolong\b",
        r"\bbantu\b",
        r"\bterima\s*kasih\b",
        r"\btrimakasih\b",
        r"\bmakasih\b",
        r"\bthanks\b",
        r"\blapor\b",
        r"\binet\b",
        r"\bcabut\b",
        r"\bsymptom\b",
        r"\bsymtomp\b",
        r"\bdiinsera\b",
        r"\bdi\s*insera\b",
        r"\binsera\b",
        r"\bINC\d+\b",
        r"#\w+",
        r"\bya\b",
        r"\bsaja\b",
        r"\bdll\b",
        r"\bdst\b",
        r"\boke?\b",
        r"\bsip\b",
        r"\btq\b",
        r"\boho\b",
    ]
    stop_pattern = "|".join(stop_keywords)

    pattern = (
        r"\b(?:service\s*type|service_type|servicetype)\s*"
        r"(?:menjadi|jadi|ke|adalah|diubah\s*ke|dirubah\s*ke|:|=|\->|->)?\s*"
        r"([A-Za-z0-9\s\-_]+?)"
        r"(?=\s*(?:" + stop_pattern + r")|[.,;!?:|]|$)"
    )

    match = re.search(pattern, clean, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"^(?:menjadi|ke|adalah|=|:)\s*", "", candidate, flags=re.IGNORECASE).strip()
        if candidate and candidate.lower() not in ("null", "none", "tidak", "ada", "-", ""):
            return candidate.upper()

    return None
