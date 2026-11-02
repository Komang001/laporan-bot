"""Filter scheduler 1-pintu (prototype, standalone).

File ini SENGAJA tidak mengedit `app/services/sygap_service.py`.
Semua logika anti-rebut tinggal di sini agar program lama 100% utuh.

Aturan SYGAP (tidak bisa digabung, harus bergantian):
  FASE TO     : status = ASSIGNED saja (assignee = All).
                BOLEH di-TO hanya jika solver masih kosong.
  FASE EXECUTE: status = OPEN + assignee = Assigned to Me.
                Hanya kerjakan yang solver-nya saya.

  TOLAK saat TO jika solver = Rizky / saya sendiri / orang lain.
"""

import re


def _in_skip_list(solver_text, skip_ids=None):
    skip_ids = skip_ids or ["55652", "Rizky Senja Budiman", "CRS2018192"]
    t = (solver_text or "").strip()
    if not t:
        return False
    tl = t.lower()
    tokens = set(re.split(r"[^a-z0-9]+", tl))
    for item in skip_ids:
        s = str(item).strip()
        if not s:
            continue
        if s.isdigit():
            if s == tl or s in tokens:
                return True
        elif s.lower() in tl:
            return True
    return False


def _solver_is_me(solver_text, my_id="55654", my_name="I Nyoman Windu"):
    sol_low = (solver_text or "").strip().lower()
    if not sol_low:
        return False
    my_id_s = str(my_id).strip().lower()
    my_name_s = str(my_name).strip().lower()
    for me in (my_id_s, my_name_s, "40010176", "crs2019332", "windu"):
        if not me:
            continue
        if me.isdigit():
            if me == sol_low or me in set(re.split(r"[^a-z0-9]+", sol_low)):
                return True
        elif me in sol_low:
            return True
    return False


def is_mine(row_info, my_id="55654", my_name="I Nyoman Windu"):
    """True jika solver = saya, status apa pun (untuk FASE EXECUTE OPEN+ME)."""
    return _solver_is_me(row_info.get("solver") or "", my_id, my_name)


def _check_for_to(row_info, required_status, my_id="55654",
                  my_name="I Nyoman Windu", skip_ids=None):
    """Inti cek TO: status harus required_status + solver kosong."""
    status = (row_info.get("status") or "").strip().upper()
    solver = (row_info.get("solver") or "").strip()

    if status != required_status:
        return False, f"status {status or '?'} bukan {required_status}"

    if _in_skip_list(solver, skip_ids):
        return False, "solver Rizky di tabel"

    empty_marks = ("", "-", "--", "\u2013", "none", "null",
                   "unassigned", "unassign", "open", "auto", ":")
    sol_low = solver.strip().lower()
    if sol_low in empty_marks:
        return True, f"{required_status} + solver kosong"
    # Solver masih nama GROUP (MO-INSERA / MO-BIMA) = belum di-TO orang.
    # Ini yang tampil di baris saat filter ASSIGNED.
    group_marks = ("mo-insera", "mo-bima")
    if sol_low in group_marks or any(sol_low.startswith(g + " ") or
                                     sol_low.startswith(g + "\n")
                                     for g in group_marks):
        return True, f"{required_status} + solver masih group (kosong)"

    if _solver_is_me(solver, my_id, my_name):
        return False, "sudah milik saya (tunggu EXECUTE)"

    return False, f"sudah di-TO orang lain ({solver[:40]})"


def check_open_for_to(row_info, my_id="55654", my_name="I Nyoman Windu",
                      skip_ids=None):
    """Cek 1 baris tabel boleh di-TO atau tidak (status OPEN).

    row_info: dict {"request_code","status","solver"}
    Returns: (allowed: bool, reason: str)
    """
    return _check_for_to(row_info, "OPEN", my_id, my_name, skip_ids)


def check_assigned_for_to(row_info, my_id="55654", my_name="I Nyoman Windu",
                          skip_ids=None):
    """Cek 1 baris tabel boleh di-TO atau tidak (status ASSIGNED, assignee All).

    Dipakai FASE TO scheduler: filter dashboard = ASSIGNED saja.
    Returns: (allowed: bool, reason: str)
    """
    return _check_for_to(row_info, "ASSIGNED", my_id, my_name, skip_ids)


def is_open_for_to(row_info, **kw):
    allowed, _ = check_open_for_to(row_info, **kw)
    return allowed


def is_assigned_to_me(row_info, my_id="55654", my_name="I Nyoman Windu"):
    """True jika tiket ASSIGNED/IN_PROGRESS ke saya (kompatibel lama)."""
    status = (row_info.get("status") or "").strip().upper()
    if status not in ("ASSIGNED", "IN_PROGRESS", "WIP", "WORK_IN_PROGRESS"):
        return False
    solver = (row_info.get("solver") or "").strip()
    if not solver:
        return False
    return _solver_is_me(solver, my_id, my_name)


def filter_rows_assigned_for_to(rows, log_callback=None, **kw):
    """Saring list rows -> hanya yang boleh di-TO (ASSIGNED + solver kosong)."""
    log = log_callback or (lambda msg: None)
    kept = []
    for r in rows:
        allowed, reason = check_assigned_for_to(r, **kw)
        if allowed:
            kept.append(r)
        else:
            log(f"  [TO-FILTER] {r.get('request_code', '?')} - SKIP ({reason})")
    log(f"[TO-FILTER] {len(kept)}/{len(rows)} tiket ASSIGNED siap TO")
    return kept


def filter_rows_open_for_to(rows, log_callback=None, **kw):
    """Saring list rows -> hanya yang boleh di-TO. Tidak menyentuh browser."""
    log = log_callback or (lambda msg: None)
    kept = []
    for r in rows:
        allowed, reason = check_open_for_to(r, **kw)
        if allowed:
            kept.append(r)
        else:
            log(f"  [TO-FILTER] {r.get('request_code', '?')} - SKIP ({reason})")
    log(f"[TO-FILTER] {len(kept)}/{len(rows)} tiket OPEN siap TO")
    return kept


if __name__ == "__main__":
    # Self-test tanpa browser (kasus TO = ASSIGNED + solver kosong)
    cases = [
        ({"request_code": "REQ1", "status": "ASSIGNED", "solver": ""}, True),
        ({"request_code": "REQ2", "status": "ASSIGNED", "solver": "-"}, True),
        ({"request_code": "REQ3", "status": "ASSIGNED",
          "solver": "I Nyoman Windu"}, False),
        ({"request_code": "REQ4", "status": "ASSIGNED",
          "solver": "Dika Prananda"}, False),
        ({"request_code": "REQ5", "status": "ASSIGNED",
          "solver": "Rizky Senja Budiman"}, False),
        ({"request_code": "REQ6", "status": "COMPLETED", "solver": ""}, False),
        ({"request_code": "REQ7", "status": "ASSIGNED", "solver": "55654"}, False),
        ({"request_code": "REQ8", "status": "OPEN", "solver": ""}, False),
        ({"request_code": "REQ9", "status": "ASSIGNED", "solver": "MO-INSERA"}, True),
        ({"request_code": "REQ10", "status": "ASSIGNED", "solver": "mo-bima"}, True),
    ]
    ok = True
    for row, exp in cases:
        got, reason = check_assigned_for_to(row)
        status = "OK" if got == exp else "FAIL"
        if got != exp:
            ok = False
        print(f"{row['request_code']} -> {got} ({reason}) exp={exp} [{status}]")
    print("is_mine REQ3:",
          is_mine({"request_code": "REQ3",
                   "status": "OPEN",
                   "solver": "I Nyoman Windu"}))
    print("SEMUA OK" if ok else "ADA FAIL")
