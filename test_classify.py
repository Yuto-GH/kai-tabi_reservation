
import unittest
from monitor import classify


class TestAvailabilityClassification(unittest.TestCase):

    def test_possible_available(self):
        # 空室があり、予約ボタンが表示されている想定
        text = """
        界タビ20s
        検索結果1/1件
        空室あり
        このプランを予約
        """
        status, reason = classify(text)
        self.assertEqual(status, "POSSIBLE_AVAILABLE")

    def test_unavailable(self):
        # 今回取得した満室ページを簡略化した想定
        text = """
        界タビ20s
        検索結果0/1件
        別館：露天風呂付き和洋室
        満室
        """
        status, reason = classify(text)
        self.assertEqual(status, "UNAVAILABLE")

    def test_unknown(self):
        # 空室・満室を判断できない想定
        text = """
        界タビ20s
        予約ページを表示しています
        """
        status, reason = classify(text)
        self.assertEqual(status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
