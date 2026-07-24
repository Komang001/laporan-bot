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

    text = re.sub(r"\s+", " ", note).strip()
    result = text.lower()

    # Ambil owner group setelah "LE LOKER" / "KE LOKER" / "KE"
    match = re.search(r"(?:le|ke)\s+loker\s+(.+)", result, re.IGNORECASE)
    if match:
        result = match.group(1).strip()
    else:
        match = re.search(r"ke\s+(.+)", result, re.IGNORECASE)
        if match:
            result = match.group(1).strip()

    # Hapus suffix
    for suffix in REMOVE_SUFFIX:
        if suffix in result:
            result = result.split(suffix)[0].strip()

    result = re.sub(
        r'\s*(terimakasih|terima\s*kasih|trimakasih|trima\s*kasih|thanks|thank\s*you)\s*$',
        '',
        result,
        flags=re.IGNORECASE
    ).strip()

    # Bersihkan karakter
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