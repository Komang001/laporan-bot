#!/usr/bin/env python3
"""
Export history sebulan kebelakang dari logs/history_all.csv ke Excel
Usage:
  python scripts/export_monthly_history.py              # 30 hari terakhir
  python scripts/export_monthly_history.py --days 30
  python scripts/export_monthly_history.py --start 2026-07-27 --end 2026-08-27
  python scripts/export_monthly_history.py --output logs/History_Bulanan.xlsx
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HISTORY_ALL = BASE / "logs" / "history_all.csv"
HISTORY_DIR = BASE / "logs"

def parse_args():
    p = argparse.ArgumentParser(description="Export history bulanan ke Excel")
    p.add_argument("--days", type=int, default=30, help="Jumlah hari kebelakang (default 30)")
    p.add_argument("--start", type=str, default=None, help="Tanggal mulai YYYY-MM-DD")
    p.add_argument("--end", type=str, default=None, help="Tanggal akhir YYYY-MM-DD (default hari ini)")
    p.add_argument("--output", type=str, default=None, help="Path output Excel")
    return p.parse_args()

def load_history():
    if not HISTORY_ALL.exists():
        print(f"[WARN] {HISTORY_ALL} belum ada — bot belum pernah log sejak aktivasi 27 Agu. Hanya ada history_2026-07-15_to_2026-07-21.csv (12 tiket).")
        # Fallback ke history_2026-07-15 file
        fallback = BASE / "logs" / "history_2026-07-15_to_2026-07-21.csv"
        if fallback.exists():
            print(f"[INFO] Fallback baca {fallback}")
            return fallback
        return None
    return HISTORY_ALL

def main():
    args = parse_args()
    src = load_history()
    if src is None or not Path(src).exists():
        print("Tidak ada file history. Jalankan bot dulu agar logs/history_YYYY-MM-DD.csv terisi.")
        sys.exit(1)

    # Tentukan range tanggal
    end_dt = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_dt = end_dt - timedelta(days=args.days)

    print(f"Range: {start_dt.strftime('%Y-%m-%d')} s/d {end_dt.strftime('%Y-%m-%d')} ({args.days} hari)")

    # Baca CSV
    rows = []
    header = None
    with open(src, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for r in reader:
            # Cari kolom tanggal: "Waktu Proses" atau "Waktu" atau "Tanggal Selesai Dikerjakan"
            tgl_str = r.get("Waktu Proses") or r.get("Waktu") or r.get("Tanggal Selesai Dikerjakan") or ""
            # Fallback ke tgl_selesai
            if not tgl_str:
                tgl_str = r.get("Tanggal Selesai") or ""
            # Parse tanggal
            try:
                # Ambil YYYY-MM-DD saja
                dt = datetime.strptime(tgl_str[:10], "%Y-%m-%d")
            except Exception:
                # Jika format Request Number based? skip
                continue
            if start_dt.date() <= dt.date() <= end_dt.date():
                rows.append(r)

    print(f"Ditemukan {len(rows)} tiket dalam range dari total file {src.name}")

    # Output Excel
    if args.output:
        out = Path(args.output)
    else:
        out = HISTORY_DIR / f"History_{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}.xlsx"
        # Jika src adalah fallback lama, beri nama bulanan
        if "2026-07-15" in src.name:
            out = HISTORY_DIR / f"History_Bulanan_{start_dt.strftime('%Y-%m')}.xlsx"

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.formatting.rule import CellIsRule
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError:
        # Fallback ke CSV filtered
        out_csv = out.with_suffix(".csv")
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        print(f"openpyxl tidak ada, export ke CSV: {out_csv}")
        print(f"File: {out_csv} ({out_csv.stat().st_size} bytes)")
        return

    # --- Build per-fitur sheets ---
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in rows:
        fitur = (r.get("Fitur") or "UNKNOWN").strip().upper()
        if fitur not in ["CANCLWORK","DISPATCH","DISPATCH_INCIDENT","GAMAS","CHANGE_SERVICE_ID","REPORT"]:
            fitur = "LAINNYA"
        grouped[fitur].append(r)

    def _make_sheet(wb, title, rows_sub, header, start_dt, end_dt, is_summary=False, src_name=""):
        ws = wb.create_sheet(title=title) if not is_summary else wb.active
        if is_summary:
            ws.title = title
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.merge_cells("A1:M1")
        t = ws["A1"]
        t.value = f"{'RINGKASAN' if is_summary else title} — {start_dt.strftime('%d %b %Y')} s/d {end_dt.strftime('%d %b %Y')} ({len(rows_sub)} tiket)" if not is_summary else f"HISTORY TIKET SYGAP → INSERA — {start_dt.strftime('%d %b %Y')} s/d {end_dt.strftime('%d %b %Y')} ({len(rows)} tiket) | Per sheet = per fitur"
        t.font = Font(size=12 if is_summary else 11, bold=True, color="1F4E78")
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 20
        ws.merge_cells("A2:M2")
        s = ws["A2"]
        s.value = f"Sumber: {src_name} — {start_dt.strftime('%Y-%m-%d')} s/d {end_dt.strftime('%Y-%m-%d')} | Sheet per fitur, jangan campur" if is_summary else f"Fitur: {title} — {len(rows_sub)} tiket"
        s.font = Font(size=8, italic=True, color="5B7FA6")
        s.alignment = Alignment(horizontal="center")
        ws.row_dimensions[2].height = 14
        header_row = 4
        header_font = Font(bold=True, color="FFFFFF", size=9)
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        thin_border = Border(left=Side(style="thin", color="B4C6E7"), right=Side(style="thin", color="B4C6E7"), top=Side(style="thin", color="B4C6E7"), bottom=Side(style="thin", color="B4C6E7"))
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
        if not header:
            header = ["Waktu Proses","Fitur","Tiket SYGAP (REQ)","No Tiket INSERA (INC)","Isi Note (500 char)","Tanggal Masuk SYGAP","Tanggal Selesai Dikerjakan","Owner Group/Inc/ServiceType","Reply SYGAP","BISCUIT Status","BISCUIT Message","Status","Solver ID"]
        for col, h in enumerate(header, start=1):
            c = ws.cell(row=header_row, column=col, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center
            c.border = thin_border
        ws.row_dimensions[header_row].height = 34
        widths = [19,13,20,20,38,19,19,22,22,14,32,12,12]
        for i,w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A5"
        ws.auto_filter.ref = f"A{header_row}:M{header_row}"
        if not rows_sub:
            ws.merge_cells("A5:M5")
            c = ws["A5"]
            c.value = "Tidak ada tiket untuk fitur ini di rentang tanggal tersebut."
            c.font = Font(size=9, italic=True, color="7F7F7F")
            c.alignment = center
            ws.row_dimensions[5].height = 22
        else:
            for r_idx, r in enumerate(rows_sub, start=5):
                for c_idx, h in enumerate(header, start=1):
                    val = r.get(h, "")
                    c = ws.cell(row=r_idx, column=c_idx, value=val)
                    c.font = Font(size=9)
                    c.border = thin_border
                    c.alignment = left_wrap if c_idx in (5,11) else center
                    if c_idx in (1,6,7):
                        c.number_format = "yyyy-mm-dd hh:mm:ss"
                ws.row_dimensions[r_idx].height = 18
                if r_idx % 2 == 0:
                    for c_idx in range(1, len(header)+1):
                        ws.cell(row=r_idx, column=c_idx).fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"SUCCESS"'], fill=green_fill, font=Font(color="006100")))
            ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"FAILED"'], fill=red_fill, font=Font(color="9C0006")))
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1
        ws.print_title_rows = f"{header_row}:{header_row}"
        return ws

    wb = openpyxl.Workbook()
    _make_sheet(wb, "RINGKASAN", rows, header, start_dt, end_dt, is_summary=True, src_name=src.name)
    order = ["DISPATCH","DISPATCH_INCIDENT","CANCLWORK","GAMAS","CHANGE_SERVICE_ID","REPORT","LAINNYA"]
    for fitur in order:
        if fitur in grouped or fitur in ["DISPATCH","GAMAS","CANCLWORK"]:
            _make_sheet(wb, fitur, grouped.get(fitur, []), header, start_dt, end_dt, is_summary=False, src_name=src.name)

    wb.save(out)
    print(f"Excel per-fitur tersimpan: {out} ({out.stat().st_size} bytes) - {len(rows)} tiket, {len(grouped)} fitur — sheets: RINGKASAN + {', '.join([k for k in order if k in grouped])}")
    print(f"Buka di Excel: {out}")

if __name__ == "__main__":
    main()
