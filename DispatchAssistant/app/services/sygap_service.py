import re
import time

from app.browser import browser_manager
from app.parser import extract_owner_group
from config.settings import USER_ID, USER_NAME, INSERA_GROUP_ID


class SygapService:

    def __init__(self):
        self.processed_ids = set()

    def get_dashboard_page(self):
        page = browser_manager.get_dashboard_page()
        if page is None:
            raise Exception("Dashboard SYGAP tidak ditemukan. Buka /req_fulfillment dulu.")
        return page

    def navigate_to_dashboard(self):
        page = self.get_dashboard_page()
        browser_manager.activate_page(page)
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

    def click_ticket(self, page, row_info):
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

    def _close_extra_tabs(self, dashboard_page):
        for p in dashboard_page.context.pages:
            if p == dashboard_page:
                continue
            try:
                if not p.is_closed():
                    url = p.url.lower()
                    if "biscuit-dashboard" in url:
                        continue
                    if "biscuit" in url and "tools" in url:
                        continue
                    p.close()
            except Exception:
                pass

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

    def is_dispatch_ticket(self, note):
        if not note:
            return False
        lower = note.lower()
        keywords = ["dispatch", "pindah og", "pindah loket", "pindah loker",
                     "salah dispatch", "owner group"]
        for kw in keywords:
            if kw in lower:
                return True
        return False

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
            btn = ticket_page.locator("button:has-text('Complete')")
            if btn.count() == 0:
                btn = ticket_page.locator("a:has-text('Complete')")
            if btn.count() == 0:
                btn = ticket_page.locator("button:has-text('COMPLETED')")
            if btn.count() == 0:
                btn = ticket_page.locator("button:has-text('completed')")
            if btn.count() > 0:
                print(f"    [COMPLETE] Clicking Complete button...")
                btn.first.click()
                ticket_page.wait_for_timeout(3000)

                if note:
                    print(f"    [COMPLETE] Looking for CKEditor in dialog...")
                    note_box = ticket_page.locator(".ck-editor__editable:visible")
                    if note_box.count() == 0:
                        note_box = ticket_page.locator("[contenteditable='true']:visible")
                    print(f"    [COMPLETE] CKEditor found: {note_box.count()}")
                    if note_box.count() > 0:
                        note_box.first.click()
                        ticket_page.wait_for_timeout(500)
                        ticket_page.keyboard.press("Control+a")
                        ticket_page.keyboard.press("Backspace")
                        ticket_page.wait_for_timeout(300)
                        ticket_page.keyboard.type(note, delay=30)
                        ticket_page.wait_for_timeout(500)
                        print(f"    [COMPLETE] Typed: {note}")

                submit_btn = ticket_page.locator("#btn_submit_complete")
                print(f"    [COMPLETE] Submit button found: {submit_btn.count()}")
                if submit_btn.count() > 0 and submit_btn.is_visible():
                    submit_btn.click()
                    print(f"    [COMPLETE] Submit clicked")
                    ticket_page.wait_for_timeout(3000)
                    return True
                else:
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
                return True
        except Exception:
            pass
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

        page_num = 1
        total_scanned = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- Page {page_num}: {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s) on this page")

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status != "ASSIGNED":
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_scanned += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code} (ASSIGNED)...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open ticket {code}")
                    continue

                try:
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
                    self.processed_ids.add(code)
                    self._close_extra_tabs(page)
                    page.wait_for_timeout(1500)

            next_btn = page.locator("#requestFulfillmentTable_next")
            is_disabled = next_btn.get_attribute("class") or ""
            if "disabled" in is_disabled:
                log(f"No more pages. Total ASSIGNED scanned: {total_scanned}")
                break

            log(f"Going to next page...")
            next_btn.click()
            page.wait_for_timeout(3000)
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
            page.wait_for_timeout(1000)
            page_num += 1

        return results

    def extract_wo_number(self, note):
        match = re.search(r'WO\d+', note)
        if match:
            return match.group(0)
        return None

    def filter_canclwork(self, page):
        try:
            page.locator("#searchSelect").select_option(label="ASSIGNED")
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

    def process_canclwork_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_canclwork(page)
        log("Filtered: ASSIGNED + CANCLWORK")

        page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        page.wait_for_timeout(2000)

        page_num = 1
        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- Page {page_num}: {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s) on this page")

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status != "ASSIGNED":
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
                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "CANCLWORK" not in note.upper():
                        log(f"    SAFETY: No CANCLWORK in note, SKIP")
                        continue

                    wo_number = self.extract_wo_number(note)
                    if not wo_number:
                        log(f"    WO number not found in note, SKIP")
                        continue

                    log(f"    WO found: {wo_number}")

                    log(f"    Taking ownership...")
                    btn_action = self.take_ownership(ticket_page)
                    log(f"    Button clicked: {btn_action}")

                    confirmed = self.wait_for_in_progress(ticket_page)
                    if not confirmed:
                        log(f"    TO FAILED: {code}")
                        continue

                    log(f"    TO CONFIRMED: {code}")

                    biscuit = BiscuitService()
                    if not biscuit.open():
                        log(f"    BISCUIT tab not found!")
                        continue

                    if not biscuit.focus_command():
                        log(f"    BISCUIT command box not found!")
                        continue

                    command = f"/pushmasscanclwork {wo_number}"
                    log(f"    Sending: {command}")
                    biscuit.send(command)
                    log(f"    Command sent to BISCUIT")

                    from app.services.response_service import ResponseService
                    response = ResponseService(
                        biscuit.get_page(),
                        biscuit.get_response_count_before()
                    ).read()
                    log(f"    BISCUIT response: {response.status} - {response.message}")

                    if response.status == "SUCCESS":
                        log(f"    BISCUIT SUKSES! Kembali ke tiket...")
                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            browser_manager.activate_page(ticket_page)
                            ticket_page.wait_for_timeout(1000)
                            completed = self.complete_ticket(ticket_page, note="Cek Kembali")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED, tapi sudah di-complete")
                            else:
                                log(f"    Gagal complete ticket {code}")
                    else:
                        log(f"    BISCUIT response bukan SUKSES, skip complete")

                    total_processed += 1
                    results.append({
                        "request_code": code,
                        "wo_number": wo_number,
                        "note": note,
                        "biscuit_status": response.status,
                    })

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self.processed_ids.add(code)
                    self._close_extra_tabs(page)
                    page.wait_for_timeout(1500)

            next_btn = page.locator("#requestFulfillmentTable_next")
            is_disabled = next_btn.get_attribute("class") or ""
            if "disabled" in is_disabled:
                log(f"No more pages. Total processed: {total_processed}")
                break

            log(f"Going to next page...")
            next_btn.click()
            page.wait_for_timeout(3000)
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
            page.wait_for_timeout(1000)
            page_num += 1

        return results

    def filter_dispatch(self, page):
        try:
            page.locator("#searchSelect").select_option(label="ASSIGNED")
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

    def process_dispatch_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_dispatch(page)
        log("Filtered: ASSIGNED + dispatch")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        page_num = 1
        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- Page {page_num}: {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s) on this page")

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if status != "ASSIGNED":
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
                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "dispatch" not in note.lower():
                        log(f"    SAFETY: No 'dispatch' in note, SKIP")
                        continue

                    note_upper = note.upper()
                    if "C4_CONSUMER" in note_upper or "C4 CONSUMER" in note_upper:
                        log(f"    SAFETY: C4 CONSUMER found in note, SKIP")
                        continue

                    owner_group = extract_owner_group(note)
                    if not owner_group:
                        log(f"    Owner group not found in note, SKIP")
                        continue
                    log(f"    Owner Group: {owner_group}")

                    log(f"    Taking ownership...")
                    btn_action = self.take_ownership(ticket_page)
                    log(f"    Button clicked: {btn_action}")

                    confirmed = self.wait_for_in_progress(ticket_page)
                    if not confirmed:
                        log(f"    TO FAILED: {code}")
                        continue
                    log(f"    TO CONFIRMED: {code}")

                    biscuit = BiscuitService()
                    if not biscuit.open():
                        log(f"    BISCUIT tab not found!")
                        continue
                    if not biscuit.focus_command():
                        log(f"    BISCUIT command box not found!")
                        continue

                    command = f"/dispatchticket {code} {owner_group}"
                    log(f"    Sending: {command}")
                    biscuit.send(command)
                    log(f"    Command sent to BISCUIT")

                    from app.services.response_service import ResponseService
                    response = ResponseService(
                        biscuit.get_page(),
                        biscuit.get_response_count_before()
                    ).read()
                    log(f"    BISCUIT response: {response.status} - {response.message}")

                    if response.status == "SUCCESS":
                        log(f"    BISCUIT SUKSES! Complete ticket...")
                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            browser_manager.activate_page(ticket_page)
                            ticket_page.wait_for_timeout(1000)
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
                    else:
                        log(f"    BISCUIT response bukan SUKSES, skip complete")

                    total_processed += 1
                    results.append({
                        "request_code": code,
                        "owner_group": owner_group,
                        "note": note,
                        "biscuit_status": response.status,
                    })

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self.processed_ids.add(code)
                    self._close_extra_tabs(page)
                    page.wait_for_timeout(1500)

            next_btn = page.locator("#requestFulfillmentTable_next")
            is_disabled = next_btn.get_attribute("class") or ""
            if "disabled" in is_disabled:
                log(f"No more pages. Total processed: {total_processed}")
                break

            log(f"Going to next page...")
            next_btn.click()
            page.wait_for_timeout(3000)
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
            page.wait_for_timeout(1000)
            page_num += 1

        return results


sygap_service = SygapService()
