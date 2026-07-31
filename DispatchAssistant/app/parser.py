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

    # Cari setelah "LOKER" / "OG" / "OWNER GROUP"
    match = re.search(
        r"(?:loker|og|owner\s+group)\s+(.+)",
        text,
        re.IGNORECASE
    )
    if match:
        result = match.group(1).strip()
    else:
        match = re.search(r"ke\s+(.+)", text, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
        else:
            return None

    # Ambil hanya kata UPPERCASE (OG selalu UPPERCASE)
    words = result.split()
    og_words = []
    for w in words:
        # Berhenti jika bukan UPPERCASE atau angka INC
        if w.startswith("INC") or w.startswith("Req") or w.startswith("REQ"):
            break
        # Skip angka standalone di awal (bukan bagian OG)
        if w.isdigit():
            if og_words:
                og_words.append(w)
            else:
                break
        # Uppercase dengan huruf, angka, atau tanda hubung (misal MO-INSERA, TIF ASR FBB AREA 2)
        elif w.replace("-", "").replace("_", "").isalpha() and w == w.upper() and len(w) > 0:
            og_words.append(w)
        elif w.replace("-", "").replace("_", "").isalnum() and w == w.upper() and len(w) > 0:
            og_words.append(w)
        else:
            break

    result = " ".join(og_words).strip()

    # Hapus suffix
    for suffix in REMOVE_SUFFIX:
        if suffix in result.lower():
            result = result.split(suffix)[0].strip()

    result = result.rstrip(".,;:")

    if not result:
        return None

    return result.upper()


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


def extract_wo_number(text: str):
    if not text:
        return None
    match = re.search(r'WO\d+', text, re.IGNORECASE)
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
    return "Salah_Dispatch_Regional_ke_Regional" in note


def extract_bulk_og_target(note: str):
    if not note:
        return None

    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()

    # Pattern1: "ke {OG} tiket :"
    match = re.search(r"ke\s+(.+?)\s+tiket\s*:", text, re.IGNORECASE)
    if match:
        return _clean_og_target(match.group(1))

    # Pattern2: "ke {OG}" (sampai akhir atau sebelum kata kunci lain)
    match = re.search(r"ke\s+(.+?)(?:\s+(?:Nama|Request|Mohon|moban|mohon|Inc|Ticket|User|TSEL))", text, re.IGNORECASE)
    if match:
        return _clean_og_target(match.group(1))

    # Pattern3: "ke {OG}" sampai akhir string
    match = re.search(r"ke\s+(.+)", text, re.IGNORECASE)
    if match:
        return _clean_og_target(match.group(1))

    return None


def _clean_og_target(raw: str):
    raw = raw.strip().rstrip(".,;:")
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