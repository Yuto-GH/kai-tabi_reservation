import unittest

from monitor import classify


class TestClassify(unittest.TestCase):
    def test_one_of_one_with_rooms_is_possible_available(self):
        status, _ = classify("検索結果1/1件 客室A 残り2室")
        self.assertEqual(status, "POSSIBLE_AVAILABLE")

    def test_one_of_two_with_rooms_is_possible_available(self):
        status, reason = classify("検索結果1/2件 客室A 残り2室")
        self.assertEqual(status, "POSSIBLE_AVAILABLE")
        self.assertIn("remaining rooms", reason)

    def test_two_of_three_with_one_room_is_possible_available(self):
        status, _ = classify("検索結果2/3件 客室A 残り1室")
        self.assertEqual(status, "POSSIBLE_AVAILABLE")

    def test_zero_of_two_without_remaining_rooms_is_not_available(self):
        status, _ = classify("検索結果0/2件 客室A")
        self.assertEqual(status, "UNKNOWN")

    def test_positive_result_without_remaining_room_signal_is_unknown(self):
        status, _ = classify("検索結果1/2件 客室A")
        self.assertEqual(status, "UNKNOWN")

    def test_zero_remaining_rooms_is_not_available(self):
        status, _ = classify("検索結果1/2件 客室A 残り0室")
        self.assertEqual(status, "UNKNOWN")

    def test_sold_out_wording_is_unavailable(self):
        status, _ = classify("誠に恐れ入りますが、満室となっております")
        self.assertEqual(status, "UNAVAILABLE")

    def test_calendar_legend_alone_is_unknown(self):
        status, _ = classify("● 空きあり ▲ 残りわずか × 満室 ー 休館")
        self.assertEqual(status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
