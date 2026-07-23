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


    # Normalisasi text

    text = re.sub(
        r"\s+",
        " ",
        note
    ).strip()



    # lowercase untuk proses

    result = text.lower()



    # =================================================
    # Ambil owner group setelah KE LOKER
    # =================================================

    match = re.search(
        r"ke\s+loker\s+(.+)",
        result,
        re.IGNORECASE
    )


    if match:

        result = match.group(1).strip()



    else:

        # fallback jika format hanya "KE xxxx"

        match = re.search(
            r"ke\s+(.+)",
            result,
            re.IGNORECASE
        )


        if match:

            result = match.group(1).strip()



    # =================================================
    # Hapus suffix
    # =================================================

    for suffix in REMOVE_SUFFIX:

        if suffix in result:

            result = result.split(
                suffix
            )[0].strip()

    # Hapus juga via regex untuk variasi
    result = re.sub(
        r'\s*(terimakasih|terima\s*kasih|trimakasih|trima\s*kasih|thanks|thank\s*you)\s*$',
        '',
        result,
        flags=re.IGNORECASE
    ).strip()



    # =================================================
    # Bersihkan karakter
    # =================================================

    result = result.rstrip(
        ".,;:"
    )



    if not result:

        return None



    # Biscuit membutuhkan uppercase

    return result.upper()



# =====================================================
# Compatibility
# =====================================================

def extract_owner_group(note: str):

    return parse_owner_group(note)