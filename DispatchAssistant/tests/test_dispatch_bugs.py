import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unified_prototype"))

from app.parser import extract_owner_group, is_workzone_request

class TestDispatchBugs(unittest.TestCase):
    def test_workzone_typos_detected(self):
        # Berbagai variasi typo workzone di lapangan yang harus terdeteksi sebagai workzone
        samples = [
            "Salah_Dispatch_Witel_ke_Witel INC53954491 INC53949905 moban bantuan pindah wokzone dari KRL ke KRW",
            "mohon bantu ubah work-zone ke SUE",
            "pindah workzon ke BTA",
            "Salah_Dispatch_Regional_ke_Regional INC53898947 moban ubah work zone ke PDE",
            "tolong di bantu ubah workzone ke SUE (ODP-SUE-FAG/05)",
        ]
        for s in samples:
            self.assertTrue(is_workzone_request(s), f"Gagal deteksi workzone pada: '{s}'")

    def test_non_dispatch_technical_fields_not_parsed_as_og(self):
        # Permintaan ubah field teknis (Information District, STO, dll) bukan merupakan Owner Group
        note_district = "<p>Salah_Dispatch_Witel_ke_Witel INC53959773 mohon bantu ubah Information District ke TANGERANG</p>"
        og = extract_owner_group(note_district)
        self.assertIsNone(og, f"Information District tidak boleh dianggap sebagai OG, tapi menghasilkan: {og}")

    def test_owner_group_kosong_not_extracted_as_target_og(self):
        # Kata 'OWNER GROUP KOSONG' adalah deskripsi kondisi tiket, bukan target OG tujuan
        samples = [
            (
                "Memunculkan_Ownergroup_Kosong Mohon bantu OWNER GROUP KOSONG untuk didispatch ke ownergroup TIF TIF SPM DATIN",
                "TIF TIF SPM DATIN",
            ),
            (
                "Memunculkan_Ownergroup_Kosong INC54489633 Mohon bantu OWNER GROUP KOSONG untuk didispatch ke ownergroup TIF TIF SPM DATIN",
                "TIF TIF SPM DATIN",
            ),
            (
                "Mohon bantu og kosong untuk didispatch ke TIF TIF SPM DATIN",
                "TIF TIF SPM DATIN",
            ),
            (
                "didispatch ke ownergroup TIF TIF SPM DATIN",
                "TIF TIF SPM DATIN",
            ),
            (
                "Mohon bantu OWNER GROUP KOSONG tolong bantu cek",
                None,
            ),
        ]
        for note, expected in samples:
            og = extract_owner_group(note)
            self.assertEqual(og, expected, f"Gagal parse OG pada note '{note}': dapat '{og}', ekspektasi '{expected}'")

if __name__ == "__main__":
    unittest.main()
