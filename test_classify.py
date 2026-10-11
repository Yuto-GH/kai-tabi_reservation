
import unittest
from monitor import classify


class TestAvailabilityClassification(unittest.TestCase):
    
    def test_possible_available(self):
        text = """
        検索結果1/1件
        洋室（3名定員）
        残り2室
        1〜3名
        43㎡
        トリプル
        1泊1室合計 38,300 円
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

    def test_remaining_rooms_means_possible_available(self):
        text = """
        検索結果1/1件
        洋室（3名定員）
        残り2室
        部屋の仕様を見る
        1〜3名
        43㎡
        トリプル
        1名初日 19,150 円
        1泊1室合計 38,300 円
        界タビ20s 料金・空室カレンダー
        ● 空きあり
        ▲ 残りわずか
        × 満室
        """
        status, reason = classify(text)
        self.assertEqual(status, "POSSIBLE_AVAILABLE")

if __name__ == "__main__":
    unittest.main()
