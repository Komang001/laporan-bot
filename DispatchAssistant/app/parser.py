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

    # Cari setelah "KE OWNER GROUP" / "KE OG" / "KE LOKER" / "LE LOKER" / "KE"
    match = re.search(
        r"(?:ke\s+(?:owner\s+group|og|loker)|le\s+loker)\s+(.+)",
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
        if w.isupper() and w.isalpha():
            og_words.append(w)
        elif w.upper() == w and len(w) > 1 and w.isalpha():
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


# =====================================================
# Compatibility
# =====================================================

def extract_owner_group(note: str):
    return parse_owner_group(note)