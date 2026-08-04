import re
import time

from app.parser import extract_owner_group, extract_inc_number, is_bulk_og_change, extract_bulk_og_target, extract_bulk_inc_list
from config.settings import USER_ID, USER_NAME

LOOP_INTERVAL = 600


class SygapService:

    def __init__(self, browser_manager=None):
        self.processed_ids = set()
        self.browser_manager = browser_manager

    def get_dashboard_page(self):
        page = self.browser_manager.get_dashboard_page()
        if page is None:
            raise Exception("Dashboard SYGAP tidak ditemukan. Buka /req_fulfillment dulu.")
        return page

    def navigate_to_dashboard(self):
        page = self.get_dashboard_page()
        self.browser_manager.activate_page(page)
        current = page.url.lower()
        if "/req_fulfillment" in current and "/form/" not in current:
            return page
        page.goto("https://sygap.telkom.co.id/req_fulfillment")
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)
        return page

    def filter_assigned(self, page, group_label="MO-INSERA", group_id=None):
        try:
            sel = page.locator("#searchSelect")
            sel.select_option(label="ASSIGNED")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            if group_id:
                js_set = f"""
                (function() {{
                    var el = document.getElementById('solverGroupSearch');
                    if (el && window.jQuery) {{
                        var $el = jQuery(el);
                        $el.empty();
                        $el.append(new Option('{group_label}', '{group_id}', true, true));
                        $el.val('{group_id}').trigger('change');
                    }}
                }})();
                """
                page.evaluate(js_set)
                page.wait_for_timeout(1500)
            else:
                sg_container = page.locator("#select2-solverGroupSearch-container")
                sg_container.click()
                page.wait_for_timeout(500)

                sg_search = page.locator(".select2-search__field:visible")
                sg_search.fill(group_label)
                page.wait_for_timeout(3000)

                result_opt = page.locator(".select2-results__option:visible").first
                result_opt.click()
                page.wait_for_timeout(1500)

            selected = page.locator("#select2-solverGroupSearch-container").inner_text()
            print(f"SolverGroup: '{selected}'")
            if group_label not in selected:
                print(f"SolverGroup not set, retry...")
                sg_container = page.locator("#select2-solverGroupSearch-container")
                sg_container.click()
                page.wait_for_timeout(500)
                sg_search = page.locator(".select2-search__field:visible")
                sg_search.fill(group_label)
                page.wait_for_timeout(3000)
                result_opt = page.locator(".select2-results__option:visible").first
                result_opt.click()
                page.wait_for_timeout(1500)

                selected2 = page.locator("#select2-solverGroupSearch-container").inner_text()
                print(f"SolverGroup retry: '{selected2}'")
                if group_label not in selected2:
                    print(f"FAILED to set SolverGroup, skipping")
                    return

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter applied ({group_label}): {count} row(s) found")
        except Exception as e:
            print(f"Filter error: {e}")

    def get_ticket_rows(self, page):
        rows = page.locator("#requestFulfillmentTable tbody tr")
        count = rows.count()
        result = []
        for i in range(count):
            row = rows.nth(i)
            try:
                link = row.locator("td a").first
                if link.count() == 0:
                    continue
                request_code = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                status_cell = row.locator("td").nth(6)
                raw_status = status_cell.inner_text().strip()
                status = raw_status.split()[-1] if raw_status.split() else raw_status
                result.append({
                    "row": row,
                    "link": link,
                    "request_code": request_code,
                    "href": href,
                    "status": status,
                })
            except Exception:
                continue
        return result

    def click_ticket(self, page, row_info, skip_close=False):
        if not skip_close:
            self._close_extra_tabs(page)
        link = row_info["link"]
        old_count = len(page.context.pages)
        link.click()
        page.wait_for_timeout(3000)
        new_count = len(page.context.pages)
        if new_count > old_count:
            return page.context.pages[-1]
        for p in page.context.pages:
            if p != page and "/form/" in p.url:
                return p
        return None

    def _close_extra_tabs(self, dashboard_page, log_callback=None):
        log = log_callback or (lambda msg: None)
        for p in dashboard_page.context.pages:
            if p == dashboard_page:
                continue
            try:
                if not p.is_closed():
                    try:
                        url = p.evaluate("window.location.href").lower()
                    except Exception:
                        url = p.url.lower()
                    if "biscuit-dashboard" in url:
                        log(f"  [close_tab] SKIP biscuit-dashboard: {url[:60]}")
                        continue
                    if "biscuit" in url and "tools" in url:
                        log(f"  [close_tab] SKIP biscuit-tools: {url[:60]}")
                        continue
                    if "oss-incident" in url or "insera" in url:
                        log(f"  [close_tab] SKIP INSERA: {url[:60]}")
                        continue
                    log(f"  [close_tab] CLOSING: {url[:60]}")
                    p.close()
            except Exception:
                pass

    def read_ticket_status(self, ticket_page):
        """Quick status check from form field - tanpa tunggu full load"""
        selectors = [
            "select[name*='status'] option[selected]",
            "select[name*='status']",
            "#status",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.inner_text().strip().upper()
                    if not val:
                        val = loc.first.input_value().strip().upper()
                    if "COMPLETED" in val or "COMPLETE" in val:
                        return "COMPLETED"
                    if val:
                        return val
            except Exception:
                continue
        try:
            body = ticket_page.locator("body").inner_text(timeout=3000)
            if "Request Status:" in body and "COMPLETED" in body.upper():
                return "COMPLETED"
        except Exception:
            pass
        return None

    def read_ticket_note(self, ticket_page):
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(3000)
        except Exception:
            pass
        note = ""
        selectors = ["textarea#note", "#note", ".note-editor textarea"]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    note = loc.first.input_value().strip()
                    if note:
                        return note
            except Exception:
                continue
        try:
            editors = ticket_page.locator(".ck-editor__editable")
            for i in range(editors.count()):
                text = editors.nth(i).inner_text().strip()
                if text:
                    note = text
                    break
        except Exception:
            note = ""
        return note

    def read_ticket_id(self, ticket_page):
        selectors = [
            "input[name$='_ticket_id']",
            "input[name*='ticket_id']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    return loc.first.input_value().strip()
            except Exception:
                continue
        return None

    def read_ticket_inc(self, ticket_page):
        """Read INC number from ticket page (header, input, or text content)"""

        selectors = [
            "input[name$='_ticket_no']",
            "input[name*='ticket_no']",
            "input[name$='_request_no']",
            "input[name*='request_no']",
            "input[name$='_no_ticket']",
            "input[name='ticket_id']",
            "input[name$='ticket_id']",
            "#ticket_no",
            "#request_no",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            body_text = ticket_page.locator("body").inner_text(timeout=5000)
            m = re.search(r'INC\d+', body_text)
            if m:
                return m.group(0).upper()
        except Exception:
            pass

        return None

    def read_wo_from_field(self, ticket_page):
        """Read WO number from form field below note (e.g. 'BIMA - WO Number')"""

        selectors = [
            "input[name$='_wo_number']",
            "input[name*='wo_number']",
            "input[name$='_work_order']",
            "input[name*='work_order']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'WO\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            wo_labels = ticket_page.locator("label:has-text('WO Number'), label:has-text('WO')")
            for idx in range(wo_labels.count()):
                label = wo_labels.nth(idx)
                container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group')][1]")
                inp = container.locator("input[type='text'], input:not([type])")
                if inp.count() > 0:
                    val = inp.first.input_value().strip()
                    if val:
                        m = re.search(r'WO\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
        except Exception:
            pass

        try:
            body_text = ticket_page.locator("body").inner_text(timeout=5000)
            m = re.search(r'WO\d+', body_text)
            if m:
                return m.group(0).upper()
        except Exception:
            pass

        return None

    def read_ticket_id_from_field(self, ticket_page):
        """Read Ticket ID/INC from form field below note (e.g. 'INSERA - Ticket ID')"""

        selectors = [
            "input[name$='_ticket_id']",
            "input[name*='ticket_id']",
            "input[name$='_ticket_no']",
            "input[name*='ticket_no']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            id_labels = ticket_page.locator("label:has-text('Ticket ID'), label:has-text('Ticket No'), label:has-text('Request No')")
            for idx in range(id_labels.count()):
                label = id_labels.nth(idx)
                container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group')][1]")
                inp = container.locator("input[type='text'], input:not([type])")
                if inp.count() > 0:
                    val = inp.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
        except Exception:
            pass

        try:
            body_text = ticket_page.locator("body").inner_text(timeout=5000)
            m = re.search(r'INC\d+', body_text)
            if m:
                return m.group(0).upper()
        except Exception:
            pass

        return None

    def extract_parent_gamas_from_note(self, note):
        """Extract parent GAMAS INC from note.
        
        Looks for pattern: Induk gamas : INC... (colon optional)
        Returns INC number or None.
        """
        if not note:
            return None

        match = re.search(r'Induk\s+gamas\s*:?\s*(INC\d+)', note, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def extract_child_incs_excluding_parent(self, note):
        """Extract child INCs from note, excluding the parent GAMAS."""
        if not note:
            return []

        parent = self.extract_parent_gamas_from_note(note)
        all_incs = re.findall(r'INC\d+', note, re.IGNORECASE)
        all_incs = [m.upper() for m in all_incs]

        if parent and parent in all_incs:
            all_incs.remove(parent)

        return all_incs

    def read_child_incs_from_field(self, ticket_page):
        """Read child INC numbers from 'INSERA - Ticket ID' field.
        
        Two-step approach:
        1. First check note for comma-separated INC numbers (multiple children)
        2. Then scan 'INSERA - Ticket ID And User ID' > 'Ticket ID' field (single child)
        """

        try:
            sections = ticket_page.locator("div:has-text('INSERA - Ticket ID And User ID')")
            for idx in range(sections.count()):
                section = sections.nth(idx)
                ticket_id_labels = section.locator("label:has-text('Ticket ID')")
                for lbl_idx in range(ticket_id_labels.count()):
                    label = ticket_id_labels.nth(lbl_idx)
                    container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group') or contains(@class,'row')][1]")
                    inp = container.locator("input[type='text'], input:not([type])")
                    if inp.count() > 0:
                        val = inp.first.input_value().strip()
                        if val:
                            matches = re.findall(r'INC\d+', val, re.IGNORECASE)
                            if matches:
                                return [m.upper() for m in matches]
        except Exception:
            pass

        try:
            all_labels = ticket_page.locator("label:has-text('Ticket ID')")
            for idx in range(all_labels.count()):
                label = all_labels.nth(idx)
                text = label.inner_text().strip()
                if text == "Ticket ID":
                    container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group') or contains(@class,'row')][1]")
                    inp = container.locator("input[type='text'], input:not([type])")
                    if inp.count() > 0:
                        val = inp.first.input_value().strip()
                        if val:
                            matches = re.findall(r'INC\d+', val, re.IGNORECASE)
                            if matches:
                                return [m.upper() for m in matches]
        except Exception:
            pass

        return []

    def take_ownership(self, ticket_page):
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(2000)
        except Exception:
            pass

        try:
            ticket_page.wait_for_selector("#id_coordinator", timeout=10000)
            ticket_page.wait_for_selector("#btn_next_stage, #btn_submit_request", timeout=10000)
            ticket_page.wait_for_timeout(1500)
        except Exception:
            pass

        js_code = f"""
        (async function() {{
            function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

            for (var w = 0; w < 10; w++) {{
                if (window.jQuery && jQuery.fn.select2) break;
                await sleep(500);
            }}
            if (!window.jQuery) return 'NO_JQUERY';

            // Only set Request Coordinator (solver) to user
            var ic = document.getElementById('id_coordinator');
            if (!ic) return 'NO_IC';
            var $ic = jQuery(ic);
            if ($ic.find('option[value="{USER_ID}"]').length === 0) {{
                $ic.append(new Option('{USER_NAME}', '{USER_ID}', false, false));
            }}
            $ic.val('{USER_ID}').trigger('change');
            await sleep(1500);

            var icVal = $ic.val();
            if (icVal !== '{USER_ID}') {{
                return 'VERIFY_FAIL:ic=' + icVal;
            }}

            var nextBtn = document.getElementById('btn_next_stage');
            if (nextBtn && nextBtn.offsetParent !== null) {{
                nextBtn.click(); return 'NEXT_STAGE';
            }}
            var saveBtn = document.getElementById('btn_submit_request');
            if (saveBtn && saveBtn.offsetParent !== null) {{
                saveBtn.click(); return 'SAVE';
            }}
            return 'NO_BUTTON';
        }})();
        """

        try:
            result = ticket_page.evaluate(js_code)
            ticket_page.wait_for_timeout(2000)
            return result
        except Exception as e:
            print(f"take_ownership JS error: {e}")
            return None

    def is_my_ticket(self, ticket_page):
        try:
            val = ticket_page.evaluate("""
                (function() {
                    var el = document.getElementById('id_coordinator');
                    if (!el) return '';
                    return el.value || '';
                })();
            """)
            return str(val).strip() == str(USER_ID).strip()
        except Exception:
            return False

    def change_coordinator_to_me(self, ticket_page):
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(2000)
        except Exception:
            pass

        js_code = f"""
        (async function() {{
            function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

            for (var w = 0; w < 10; w++) {{
                if (window.jQuery && jQuery.fn.select2) break;
                await sleep(500);
            }}
            if (!window.jQuery) return 'NO_JQUERY';

            var ic = document.getElementById('id_coordinator');
            if (!ic) return 'NO_IC';
            var $ic = jQuery(ic);
            if ($ic.find('option[value="{USER_ID}"]').length === 0) {{
                $ic.append(new Option('{USER_NAME}', '{USER_ID}', false, false));
            }}
            $ic.val('{USER_ID}').trigger('change');
            await sleep(1500);

            var icVal = $ic.val();
            if (icVal !== '{USER_ID}') {{
                return 'VERIFY_FAIL:ic=' + icVal;
            }}

            var saveBtn = document.getElementById('btn_submit_request');
            if (saveBtn && saveBtn.offsetParent !== null) {{
                saveBtn.click(); return 'SAVE';
            }}
            return 'NO_BUTTON';
        }})();
        """

        try:
            result = ticket_page.evaluate(js_code)
            ticket_page.wait_for_timeout(3000)
            return result
        except Exception as e:
            print(f"change_coordinator JS error: {e}")
            return None

    def wait_for_in_progress(self, ticket_page, timeout=45):
        start = time.time()
        while time.time() - start < timeout:
            try:
                status_el = ticket_page.locator("#status")
                if status_el.count() > 0:
                    raw = status_el.input_value().strip()
                    if raw == "IN_PROGRESS":
                        return True
                try:
                    ticket_page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
            except Exception:
                pass
            ticket_page.wait_for_timeout(2000)
        return False

    def wait_for_completed(self, ticket_page, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            try:
                status_el = ticket_page.locator("#status")
                if status_el.count() > 0:
                    raw = status_el.input_value().strip()
                    if raw == "COMPLETED":
                        return True
                try:
                    ticket_page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
            except Exception:
                pass
            ticket_page.wait_for_timeout(2000)
        return False

    def complete_ticket(self, ticket_page, note=""):
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=10000)
            ticket_page.wait_for_timeout(2000)

            btn = ticket_page.locator("button:has-text('Complete')")
            if btn.count() == 0:
                btn = ticket_page.locator("a:has-text('Complete')")
            if btn.count() == 0:
                btn = ticket_page.locator("button:has-text('COMPLETED')")
            if btn.count() == 0:
                btn = ticket_page.locator("button:has-text('completed')")
            if btn.count() == 0:
                btn = ticket_page.locator("button:has-text('Completed')")
            if btn.count() > 0:
                print(f"    [COMPLETE] Clicking Complete button...")
                btn.first.scroll_into_view_if_needed()
                ticket_page.wait_for_timeout(500)
                btn.first.click()
                ticket_page.wait_for_timeout(4000)

                if note:
                    print(f"    [COMPLETE] Looking for textbox in dialog...")
                    note_box = None

                    selectors = [
                        ".modal.show .ck-editor__editable",
                        ".modal.show [contenteditable='true']",
                        ".modal.show textarea",
                        ".modal .ck-editor__editable:visible",
                        ".modal [contenteditable='true']:visible",
                        ".modal textarea:visible",
                        "[role='dialog'] .ck-editor__editable:visible",
                        "[role='dialog'] [contenteditable='true']:visible",
                        "[role='dialog'] textarea:visible",
                        ".ck-editor__editable:visible",
                        "[contenteditable='true']:visible",
                        "textarea:visible",
                    ]

                    for sel in selectors:
                        try:
                            loc = ticket_page.locator(sel)
                            if loc.count() > 0:
                                note_box = loc.last
                                print(f"    [COMPLETE] Found with: {sel}")
                                break
                        except Exception:
                            continue

                    if note_box:
                        note_box.click()
                        ticket_page.wait_for_timeout(500)
                        ticket_page.keyboard.press("Control+a")
                        ticket_page.keyboard.press("Backspace")
                        ticket_page.wait_for_timeout(300)
                        ticket_page.keyboard.type(note, delay=30)
                        ticket_page.wait_for_timeout(500)
                        print(f"    [COMPLETE] Typed: {note}")
                    else:
                        print(f"    [COMPLETE] Textbox NOT found!")
                        return False

                submit_btn = ticket_page.locator("#btn_submit_complete")
                print(f"    [COMPLETE] Submit button found: {submit_btn.count()}")
                if submit_btn.count() > 0:
                    submit_btn.scroll_into_view_if_needed()
                    ticket_page.wait_for_timeout(500)
                    if submit_btn.is_visible():
                        submit_btn.click()
                        print(f"    [COMPLETE] Submit clicked")
                        ticket_page.wait_for_timeout(3000)
                        return True
                print(f"    [COMPLETE] Submit not found/visible, trying fallback...")
                confirm = ticket_page.locator("button:has-text('Yes'), button:has-text('OK'), button:has-text('Confirm'), button:has-text('Submit')")
                print(f"    [COMPLETE] Fallback buttons found: {confirm.count()}")
                if confirm.count() > 0:
                    confirm.first.click()
                    ticket_page.wait_for_timeout(3000)
                    return True
            else:
                print(f"    [COMPLETE] Complete button NOT found!")
        except Exception as e:
            print(f"    [COMPLETE] Error: {e}")
        return False

    def find_and_process_tickets(self, log_callback=None, group_label="MO-INSERA", group_id=None):
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_assigned(page, group_label, group_id)
        log(f"Filtered: ASSIGNED + {group_label}")

        page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        page.wait_for_timeout(2000)

        total_scanned = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status in ("COMPLETED", "COMPLETE", "IN_PROGRESS"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_scanned += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code} (ASSIGNED)...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    ticket_id = self.read_ticket_id(ticket_page)
                    note_short = note[:80] + "..." if len(note) > 80 else note
                    log(f"    Note: {note_short}")

                    log(f"    Taking ownership...")
                    btn_action = self.take_ownership(ticket_page)
                    log(f"    Button clicked: {btn_action}")

                    log(f"    Waiting for status IN_PROGRESS...")
                    confirmed = self.wait_for_in_progress(ticket_page)
                    if confirmed:
                        log(f"    TO CONFIRMED: {code} -> {group_label} / IN_PROGRESS")
                        self.processed_ids.add(code)
                        results.append({
                            "request_code": code,
                            "ticket_id": ticket_id,
                            "note": note,
                            "owner_group": extract_owner_group(note),
                        })
                    else:
                        log(f"    TO FAILED: {code} -> status not changed")

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            self.filter_assigned(page, group_label, group_id)
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
            page.wait_for_timeout(2000)

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            processed_this_round = sum(1 for r in results if r.get("request_code") in [row["request_code"] for row in rows])
            if processed_this_round == 0:
                log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results

    def extract_wo_number(self, note):
        match = re.search(r'WO\d+', note)
        if match:
            return match.group(0)
        return None

    def filter_canclwork(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("CANCLWORK")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "CANCLWORK" not in verify_val:
                print("FAILED to set Notes filter!")
                return

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            notes_val_after = notes_input.input_value().strip()
            print(f"Notes after Apply: '{notes_val_after}'")

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter CANCLWORK: {count} row(s) found")
        except Exception as e:
            print(f"Filter CANCLWORK error: {e}")

    def filter_cancelwork(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("CANCELWORK")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "CANCELWORK" not in verify_val:
                print("FAILED to set Notes filter!")
                return

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            notes_val_after = notes_input.input_value().strip()
            print(f"Notes after Apply: '{notes_val_after}'")

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter CANCELWORK: {count} row(s) found")
        except Exception as e:
            print(f"Filter CANCELWORK error: {e}")

    def process_canclwork_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        filters = ["CANCLWORK", "CANCELWORK"]
        filter_idx = 0
        current_filter = filters[filter_idx]

        def apply_filter(filter_name):
            if filter_name == "CANCLWORK":
                self.filter_canclwork(page)
            else:
                self.filter_cancelwork(page)
            try:
                page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
                page.wait_for_timeout(2000)
                return True
            except Exception:
                log(f"No rows found for {filter_name}")
                return False

        if not apply_filter(current_filter):
            log(f"No tickets for {current_filter}. Switching...")
            filter_idx += 1
            if filter_idx < len(filters):
                current_filter = filters[filter_idx]
                if not apply_filter(current_filter):
                    log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results
            else:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results
        log(f"Filtered: OPEN + {current_filter}")

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {current_filter} | {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

            processed_this_round = 0

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_processed += 1
                processed_this_round += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    note_upper = note.upper()
                    if current_filter == "CANCLWORK" and "CANCLWORK" not in note_upper:
                        log(f"    SAFETY: No CANCLWORK in note, SKIP")
                        continue
                    if current_filter == "CANCELWORK" and "CANCELWORK" not in note_upper:
                        log(f"    SAFETY: No CANCELWORK in note, SKIP")
                        continue

                    current_solver = ticket_page.locator("#id_coordinator")
                    solver_val = ""
                    if current_solver.count() > 0:
                        solver_val = current_solver.input_value().strip()
                    log(f"    Solver: {solver_val} | My ID: {USER_ID}")

                    if solver_val != USER_ID:
                        log(f"    Solver bukan saya -> TO dulu...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")

                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")
                    else:
                        log(f"    Solver sudah saya, skip TO")

                    has_osm = any(kw in note_upper for kw in ["OSM", "SOM", "TOM"])
                    if not has_osm:
                        warn = "untuk permintaan CANCLWORK pastikan status OSM sudah CANCEL COMPLETE atau ABORTED"
                        log(f"    SAFETY: No OSM/SOM/TOM in note")
                        log(f"    Complete ticket dengan note: {warn}")
                        self.complete_ticket(ticket_page, note=warn)
                        page.bring_to_front()
                        continue

                    wo_number = self.extract_wo_number(note)
                    if not wo_number:
                        wo_number = self.read_wo_from_field(ticket_page)
                        if wo_number:
                            log(f"    WO from field: {wo_number}")
                    if not wo_number:
                        log(f"    WO number not found anywhere, SKIP")
                        continue
                    log(f"    WO found: {wo_number}")

                    biscuit = BiscuitService(browser_manager=self.browser_manager)
                    if not biscuit.open():
                        log(f"    BISCUIT tab not found!")
                        continue

                    if not biscuit.focus_command():
                        log(f"    BISCUIT command box not found!")
                        continue

                    command = f"/pushmasscanclwork {wo_number}"
                    log(f"    Sending: {command}")

                    max_retries = 2
                    response = None
                    for attempt in range(1, max_retries + 1):
                        biscuit.send(command)
                        log(f"    Command sent (attempt {attempt})")

                        from app.services.response_service import ResponseService
                        response = ResponseService(
                            biscuit.get_page(),
                            biscuit.get_response_count_before()
                        ).read()
                        log(f"    BISCUIT response: {response.status} - {response.message}")

                        if response.status != "UNKNOWN":
                            break

                        if attempt < max_retries:
                            log(f"    BISCUIT timeout, retrying...")
                            biscuit.focus_command()
                            biscuit.wait_for_ready()

                    if response.status == "SUCCESS":
                        complete_note = "Cek Kembali"
                        log(f"    BISCUIT SUKSES! Complete ticket...")
                    else:
                        complete_note = response.message[:200]
                        log(f"    BISCUIT GAGAL! Complete dengan alasan error...")

                    page.bring_to_front()
                    page.wait_for_timeout(1000)
                    if not ticket_page.is_closed():
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)
                        completed = self.complete_ticket(ticket_page, note=complete_note)
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED ({response.status})")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                        else:
                            log(f"    Gagal complete ticket {code}")

                    results.append({
                        "request_code": code,
                        "wo_number": wo_number,
                        "note": note,
                        "biscuit_status": response.status,
                    })
                    self.processed_ids.add(code)

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            if not apply_filter(current_filter):
                log(f"No rows after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

            if processed_this_round == 0:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No actionable {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

        return results

    def filter_dispatch(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("dispatch")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "dispatch" not in verify_val.lower():
                print("FAILED to set Notes filter!")
                return

            # Set Solver Group ke MO-INSERA
            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            og_selected = page.locator("#select2-solverGroupSearch-container").inner_text()
            print(f"SolverGroup: '{og_selected}'")

            search_btn = page.locator("#btn_apply")
            if search_btn.count() == 0:
                search_btn = page.locator("button.btn-primary .fa-search")
                if search_btn.count() > 0:
                    search_btn = search_btn.locator("xpath=ancestor::button")
            if search_btn.count() > 0:
                search_btn.first.click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter DISPATCH: {count} row(s) found")
        except Exception as e:
            print(f"Filter DISPATCH error: {e}")

    def filter_gamas_relations(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("gamas")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter GAMAS RELATIONS: {count} row(s) found")
        except Exception as e:
            print(f"Filter GAMAS RELATIONS error: {e}")

    def process_gamas_relations_tickets(self, log_callback=None):
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        log("Menunggu user login ke INSERA...")
        log("Buka tab INSERA di Chrome GAMAS, lalu login.")
        logged_in = False
        for wait in range(120):
            pages = page.context.pages
            if wait % 10 == 0:
                log(f"  Tabs detected: {len(pages)}")
                for idx, p in enumerate(pages):
                    try:
                        real_url = p.evaluate("window.location.href")
                        log(f"    Tab {idx+1}: {real_url[:80]}")
                    except Exception:
                        try:
                            log(f"    Tab {idx+1}: {p.url[:80]}")
                        except Exception:
                            log(f"    Tab {idx+1}: (error)")
            for p in pages:
                try:
                    real_url = p.evaluate("window.location.href").lower()
                    if "oss-incident" in real_url and "login" not in real_url:
                        logged_in = True
                        break
                except Exception:
                    try:
                        url = p.url.lower()
                        if "oss-incident" in url:
                            logged_in = True
                            break
                    except Exception:
                        continue
            if logged_in:
                log("INSERA tab terdeteksi (sudah login)! Mulai scan...")
                break
            if wait % 10 == 0:
                log(f"  Menunggu INSERA login... ({wait}s)")
            time.sleep(1)

        if not logged_in:
            log("INSERA belum login setelah 120 detik. Scan tetap dimulai...")

        self.filter_gamas_relations(page)
        log("Filtered: OPEN + gamas + MO-INSERA")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_processed += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info, skip_close=True)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    log(f"    Taking ownership...")
                    btn_action = self.take_ownership(ticket_page)
                    log(f"    Button clicked: {btn_action}")

                    confirmed = self.wait_for_in_progress(ticket_page)
                    if not confirmed:
                        log(f"    TO FAILED: {code}")
                        continue
                    log(f"    TO CONFIRMED: {code}")

                    note = self.read_ticket_note(ticket_page)
                    parent_inc = self.extract_parent_gamas_from_note(note)
                    if parent_inc:
                        log(f"    Parent INC from note: {parent_inc}")
                    else:
                        log(f"    'Induk gamas' tidak ada di note. SKIP (hindari relasi salah).")
                        continue

                    child_incs = self.extract_child_incs_excluding_parent(note)
                    if not child_incs:
                        child_incs = self.read_child_incs_from_field(ticket_page)
                    if not child_incs:
                        log(f"    No child INCs found, SKIP")
                        continue
                    log(f"    Child INCs ({len(child_incs)}): {','.join(child_incs[:5])}...")

                    child_str = ",".join(child_incs)

                    from app.services.insera_gamas_service import InseraGamasService
                    insera = InseraGamasService(browser_manager=self.browser_manager, log_callback=log)
                    if not insera.open():
                        log(f"    INSERA tab not found! Buka tab INSERA lalu login.")
                        continue

                    max_nav_retries = 3
                    nav_ok = False
                    for nav_attempt in range(1, max_nav_retries + 1):
                        if not insera.navigate_to_relations():
                            log(f"    Failed navigate to Gamas Relations (attempt {nav_attempt})")
                            if nav_attempt < max_nav_retries:
                                insera.get_page().wait_for_timeout(5000)
                            continue

                        page_url = insera.get_page().url.lower()
                        page_content = ""
                        try:
                            page_content = insera.get_page().content().lower()
                        except Exception:
                            pass

                        if "login" in page_url:
                            log(f"    INSERA belum login! Login manual dulu.")
                            break

                        is_error = "system error" in page_content or (
                            "unintended error" in page_content
                        )
                        if is_error:
                            log(f"    Joget error at: {page_url[:60]}")
                            if nav_attempt < max_nav_retries:
                                log(f"    Retrying in 10s... (attempt {nav_attempt}/{max_nav_retries})")
                                insera.get_page().wait_for_timeout(10000)
                                insera.navigate_to_relations()
                            continue

                        if "gamasrelations" in page_url:
                            nav_ok = True
                            break

                    if not nav_ok:
                        log(f"    INSERA GAMAS not accessible, SKIP")
                        continue

                    log(f"    Waiting for INSERA fields to load...")
                    if not insera.wait_for_fields(timeout=30):
                        log(f"    INSERA fields not visible, SKIP")
                        continue

                    if not insera.fill_parent(parent_inc):
                        log(f"    Failed fill parent field")
                        continue

                    if not insera.fill_child(child_str):
                        log(f"    Failed fill child field")
                        continue

                    log(f"    Parent: {parent_inc}")
                    log(f"    Child: {child_str[:100]}...")

                    if not insera.click_save():
                        log(f"    Failed save on INSERA")
                        continue

                    log(f"    INSERA save OK, completing ticket...")

                    page.bring_to_front()
                    page.wait_for_timeout(1000)
                    self.browser_manager.activate_page(ticket_page)
                    try:
                        ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    ticket_page.wait_for_timeout(3000)

                    completed = self.complete_ticket(ticket_page, note="Cek Kembali")
                    if completed:
                        log(f"    Waiting COMPLETED status...")
                        is_completed = self.wait_for_completed(ticket_page)
                        if is_completed:
                            log(f"    Ticket {code} -> COMPLETED")
                        else:
                            log(f"    Ticket {code} status belum COMPLETED")
                    else:
                        log(f"    Gagal complete ticket {code}")

                    results.append({
                        "request_code": code,
                        "parent_inc": parent_inc,
                        "child_incs": child_incs,
                    })
                    self.processed_ids.add(code)

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            self.filter_gamas_relations(page)
            page.wait_for_timeout(3000)

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            if total_processed == 0:
                log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results

    def process_dispatch_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_dispatch(page)
        log("Filtered: dispatch")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_processed += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "dispatch" not in note.lower():
                        log(f"    SAFETY: No 'dispatch' in note, SKIP")
                        continue

                    if "workzone" in note.lower() or "work zone" in note.lower():
                        log(f"    SAFETY: 'workzone'/'work zone' found in note, SKIP")
                        continue

                    note_upper = note.upper()

                    owner_group = extract_owner_group(note)
                    inc_number = extract_inc_number(note)
                    print(f"    [DEBUG] OG={owner_group} | INC={inc_number} | C4={'C4' in note_upper}")

                    if is_bulk_og_change(note):
                        bulk_og = extract_bulk_og_target(note)
                        bulk_incs = extract_bulk_inc_list(note)
                        log(f"    BULK OG CHANGE: target={bulk_og} | INCs={len(bulk_incs)}")

                        if not bulk_og:
                            log(f"    Cannot parse bulk OG target, SKIP")
                            continue

                        if "C4" in bulk_og.upper():
                            log(f"    BULK OG is C4 ({bulk_og}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)

                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "C4_COMPLETE",
                                    "note": note,
                                })
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue

                        if not bulk_incs:
                            inc_from_page = self.read_ticket_inc(ticket_page)
                            if not inc_from_page:
                                inc_from_page = self.read_ticket_id_from_field(ticket_page)
                            if inc_from_page:
                                bulk_incs = [inc_from_page]
                                log(f"    INC from page: {inc_from_page}")
                            else:
                                log(f"    No INCs found in note or page, SKIP")
                                continue

                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            log(f"    Status: {status} -> TO ke saya dulu...")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue
                        if not biscuit.focus_command():
                            log(f"    BISCUIT command box not found!")
                            continue

                        all_success = True
                        failed_incs = []
                        for idx, inc in enumerate(bulk_incs):
                            command = f"/dispatchticket {inc} {bulk_og}"
                            log(f"    [{idx+1}/{len(bulk_incs)}] Sending: {command}")

                            max_retries = 2
                            response = None
                            for attempt in range(1, max_retries + 1):
                                biscuit.send(command)
                                log(f"    Command sent (attempt {attempt})")

                                from app.services.response_service import ResponseService
                                response = ResponseService(
                                    biscuit.get_page(),
                                    biscuit.get_response_count_before()
                                ).read()
                                log(f"    BISCUIT response: {response.status} - {response.message}")

                                if response.status != "UNKNOWN":
                                    break

                                if attempt < max_retries:
                                    log(f"    BISCUIT timeout, retrying...")
                                    biscuit.focus_command()
                                    biscuit.wait_for_ready()

                            if response.status == "SUCCESS":
                                log(f"    {inc} -> OK")
                            else:
                                log(f"    {inc} -> FAILED: {response.message}")
                                all_success = False
                                failed_incs.append(f"{inc}: {response.message}")

                            if idx < len(bulk_incs) - 1:
                                biscuit.focus_command()
                                biscuit.wait_for_ready()

                        if all_success:
                            log(f"    All INCs dispatched successfully")
                        else:
                            log(f"    Some INCs failed: {len(failed_incs)}")

                        complete_note = "Cek Kembali"

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "BULK_OG_CHANGE",
                                    "bulk_og": bulk_og,
                                    "total_incs": len(bulk_incs),
                                    "failed_incs": len(failed_incs),
                                })
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code}")
                        continue

                    if owner_group:
                        log(f"    OG: {owner_group} | INC from note: {inc_number or 'N/A'}")

                        if "TIF SPM DATIN" in owner_group:
                            log(f"    SKIP: OG '{owner_group}' -> TIF SPM DATIN")
                            continue

                        if "C4" in owner_group.upper():
                            log(f"    OG is C4 ({owner_group}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)

                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "C4_COMPLETE",
                                    "note": note,
                                })
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue

                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            log(f"    Status: {status} -> TO ke saya dulu...")

                            log(f"    Taking ownership...")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                        if not inc_number:
                            log(f"    INC not in note, reading from ticket page...")
                            inc_number = self.read_ticket_inc(ticket_page)
                            if not inc_number:
                                inc_number = self.read_ticket_id_from_field(ticket_page)
                                if inc_number:
                                    log(f"    INC from field: {inc_number}")
                            log(f"    INC from page: {inc_number or 'NOT FOUND'}")

                        if not inc_number:
                            log(f"    INC number not found anywhere, SKIP")
                            continue

                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue
                        if not biscuit.focus_command():
                            log(f"    BISCUIT command box not found!")
                            continue

                        command = f"/dispatchticket {inc_number} {owner_group}"
                        log(f"    Sending: {command}")

                        max_retries = 2
                        response = None
                        for attempt in range(1, max_retries + 1):
                            biscuit.send(command)
                            log(f"    Command sent (attempt {attempt})")

                            from app.services.response_service import ResponseService
                            response = ResponseService(
                                biscuit.get_page(),
                                biscuit.get_response_count_before()
                            ).read()
                            log(f"    BISCUIT response: {response.status} - {response.message}")

                            if response.status != "UNKNOWN":
                                break

                            if attempt < max_retries:
                                log(f"    BISCUIT timeout, retrying...")
                                biscuit.focus_command()
                                biscuit.wait_for_ready()

                        if response.status == "SUCCESS":
                            log(f"    BISCUIT SUKSES! Complete ticket...")
                            complete_note = "Cek Kembali"
                        else:
                            log(f"    BISCUIT GAGAL! Complete dengan alasan error...")
                            complete_note = response.message[:200]

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED ({response.status})")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                            else:
                                log(f"    Gagal complete ticket {code}")

                        total_processed += 1
                        results.append({
                            "request_code": code,
                            "owner_group": owner_group,
                            "note": note,
                            "biscuit_status": response.status,
                        })
                        self.processed_ids.add(code)

                    elif "C4" in note_upper:
                        log(f"    No OG but C4 found -> TO dulu...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")

                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)

                        completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED (C4)")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                            results.append({
                                "request_code": code,
                                "type": "C4_COMPLETE",
                                "note": note,
                            })
                            self.processed_ids.add(code)
                        else:
                            log(f"    Gagal complete ticket {code} (C4)")

                    else:
                        log(f"    No OG and no C4, SKIP")
                        continue

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            self.filter_dispatch(page)
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
            page.wait_for_timeout(2000)

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            processed_this_round = sum(1 for r in results if r.get("request_code") in [row["request_code"] for row in rows])
            if processed_this_round == 0:
                log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results
