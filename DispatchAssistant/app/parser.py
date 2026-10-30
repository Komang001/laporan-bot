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

INVALID_OG_NAMES = {
    "KOSONG",
    "NULL",
    "NONE",
    "BLANK",
    "TIDAK ADA",
    "TIDAK",
    "ADA",
}


# =====================================================
# Workzone Request Detection
# =====================================================

def is_workzone_request(note: str) -> bool:
    """True jika note meminta perubahan workzone (toleran typo, misal wokzone/work zone/wz)."""
    if not note:
        return False
    text = re.sub(r"<[^>]+>", " ", note)
    return bool(re.search(r"\b(?:wo?r?k[_\s-]*zone?s?|wz)\b", text, re.IGNORECASE))


# =====================================================
# Parse Owner Group
# =====================================================

def parse_owner_group(note: str):

    if not note:
        return None

    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()

    # Try patterns in order of priority
    # Pola 1: loker/og/owner group/disini yang BUKAN diikuti status 'kosong/null/blank'
    patterns = [
        r"(?:\bloker\b|\bog\b|owner\s*gr(?:o)?up|\bdisini\b)\s*[:.]?\s+(?!(?:kosong|null|blank|none|tidak\s*ada)\b)(.+)",
        r"(?:\bke\b|\bto\b)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        # Jika pola 'ke/to', pastikan bukan diarahkan dari field teknis non-OG (mis. Information District ke X)
        if pattern.startswith(r"(?:\bke\b"):
            preceding = text[:match.start()].strip()
            if re.search(r"\b(?:information\s+district|status|sto|rk|datek|wo?r?k[_\s-]*zone?s?|service\s+(?:id|type|no))\s*$", preceding, re.IGNORECASE):
                continue

        candidate = match.group(1).strip()

        # Strip label prefixes: "Owner Group", "Ownergroup", "Owner Grup", "LOKER", "OWNER GROUP", "DISINI", "OG"
        candidate = re.sub(r"(?i)\bowner\s*gr(?:o)?up\b", "", candidate)
        candidate = re.sub(r"(?i)\bloker\b", "", candidate)
        candidate = re.sub(r"(?i)\bog\b", "", candidate)
        candidate = re.sub(r"(?i)\bdisini\b", "", candidate)
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

        if result and result.upper() not in INVALID_OG_NAMES:
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
# TTR Request Detection (INCIDENT)
# =====================================================

def is_ttr_request(note: str):
    """True jika note meminta TTR (request TTR).

    Contoh cocok:
      - 'request TTR INC...', 'req TTR', 'mohon TTR', 'minta TTR'
      - 'TTR corrective', 'ttrcorrective'
      - 'Memunculkan_Ownergroup_Kosong TTR End to End tidak sesuai (TTR Freeze)'
      - fallback: kata TTR standalone (filter SYGAP notes=TTR)
    Tidak cocok:
      - note dispatch biasa tanpa kata TTR
      - tag 'TTR_Freeze' saja (underscore = bukan word boundary,
        mis. '<p>TTR_Freeze #ANOMALI_RESOLVE ... Salah_Dispatch...'
        yang harus tetap ditangani alur DISPATCH, bukan TTR).
    """
    if not note:
        return False
    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"(request|req|mohon|minta|tolong)\s+ttr\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bttr\s*corrective\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bttrcorrective\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bttr\s+end\s+to\s+end\b", text, re.IGNORECASE):
        return True
    return bool(re.search(r"\bTTR\b", text, re.IGNORECASE))


def extract_ttr_inc_number(note: str):
    """Ambil INC target untuk /ttrcorrective dari note.

    Prioritas: INC pertama di note, sama seperti dispatch.
    Return INC uppercase atau None.
    """
    return extract_inc_number(note)


# =====================================================
# Impacted Service Request (INSERA terdampak gangguan)
# =====================================================

def is_impacted_service_request(note: str):
    """True jika note meminta pemunculan service type karena data INSERA
    terdampak gangguan aplikasi lain (dieksekusi via /loaddatek).

    Trigger: 'tiket_impacted_service_tidak_ada' (case-insensitive,
    pemisah boleh underscore/spasi/strip), mis.:
      - 'tiket_impacted_service_tidak_ada INC53396753 ... mohon bantu ubah Service Type : Null menjadi INTERNET ...'
      - 'tiket_impacted_service_tidak_ada INC53397107 mohon bantu ubah service type kosong ...'
    """
    if not note:
        return False
    text = re.sub(r"<[^>]+>", " ", note)
    text = re.sub(r"\s+", " ", text).strip()
    return bool(re.search(
        r"tiket[_\s-]*impacted[_\s-]*service[_\s-]*tidak[_\s-]*ada",
        text,
        re.IGNORECASE,
    ))


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

    # Strip label prefixes: "Owner Group", "Ownergroup", "LOKER", "OWNER GROUP", "OG"
    raw = re.sub(r"(?i)\bowner\s*gr(?:o)?up\b", "", raw)
    raw = re.sub(r"(?i)\bloker\b", "", raw)
    raw = re.sub(r"(?i)\bog\b", "", raw)
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
        elif (
            len(w) > 1
            and w[0].isupper()
            and w[1:].islower()
            and w.replace("-", "").replace("_", "").isalnum()
        ):
            og_words.append(w)
        else:
            break
    result = " ".join(og_words).strip()
    if result and result.upper() not in INVALID_OG_NAMES:
        return result.upper()
    return None


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

    # Pattern 1: Explicit "Service ID" label - but validate format looks like service ID
    # COBA SEMUA kemunculan label, ambil kandidat valid pertama.
    # (fix: dulu berhenti di label pertama walau kandidatnya sampah,
    #  mis. "...pelurusan service id ke Service ID : 1-L6JHRQ0_..." yang
    #  menangkap kata "Service" lalu menyerah sebelum label yang benar.)
    pattern_explicit = r"(?i)\b(?:service\s*id|service_id|serviceid)\s*(?:menjadi|jadi|ke|adalah|:|:|=|\->|->)?\s*([A-Za-z0-9_\-\.]+)"
    for match in re.finditer(pattern_explicit, clean):
        candidate = match.group(1).strip().rstrip(".,;:!")
        if not candidate or candidate.lower() in ("menjadi", "jadi", "ke", "adalah", "null", "none", "tidak", "ada"):
            continue
        # Validate: service ID should contain underscore and digits (format: DIGITS_DIGITS_WORD)
        if re.search(r"\d+_\d+", candidate):
            return candidate

    # Pattern 2: Fallback - Service ID format is typically DIGITS_DIGITS_WORD
    # e.g. 20780_0224233814_VOICE, 5480832_0214711635_VOICE.
    # Izinkan prefix segmen strip (mis. 1-L6JHRQ0_131437114624_INTERNET).
    pattern_format = r"\b([A-Za-z0-9][A-Za-z0-9_\-\.]*\d+_\d+_[A-Za-z][A-Za-z0-9]*)\b"
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

