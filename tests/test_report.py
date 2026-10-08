import unittest
from core.common import (
    clean_daka_summary,
    clean_gift_summary,
    clean_welfare_summary,
    build_report_text,
    make_progress_bar
)

class TestReportLogic(unittest.TestCase):
    def test_clean_gift_summary_sent_tiger_food(self):
        # 即使送礼后库存为 0，也必须显示送出的情况（如已送 10 个），不能显示为“无余粮跳过”
        detail = "成功送出 10 个虎粮（库存 10 → 0）"
        res = clean_gift_summary(detail, success=True, count=10)
        self.assertEqual(res, "已送 10 个")

    def test_clean_gift_summary_regex_fallback(self):
        # 即使未显式传 count，也应从 detail 优先提取送出数量
        detail = "成功送出 10 个虎粮（库存 10 → 0）"
        res = clean_gift_summary(detail, success=True)
        self.assertEqual(res, "已送 10 个")

    def test_clean_gift_summary_no_food(self):
        # 原本就没有虎粮时，应正确显示无余粮跳过
        detail = "包裹中暂无虎粮"
        res = clean_gift_summary(detail, success=True, count=0)
        self.assertEqual(res, "无余粮跳过")

    def test_clean_daka_summary(self):
        # 今日已打卡或新打卡成功
        self.assertEqual(clean_daka_summary("今日已经完成粉丝团打卡，无需重复领取", success=True, intimacy=5), "打卡成功 (+5)")
        self.assertEqual(clean_daka_summary("打卡成功（亲密度+5，状态复查已确认）", success=True, intimacy=5), "打卡成功 (+5)")

    def test_build_report_text_full_flow(self):
        # 模拟打卡+领福利+送出10虎粮的完整流程
        summary = {
            "version": "v2",
            "nick": "狂鸟丶楚河-90327",
            "room_id": "998",
            "account": "18579071857",
            "all_success": True,
            "fans_level": "Lv.22",
            "badge_name": "楚河",
            "current_score": 167817,
            "next_score": 175000,
            "need_intimacy": "7183",
            "daka_success": True,
            "daka_detail": "今日已经完成粉丝团打卡，无需重复领取",
            "daka_intimacy": 5,
            "welfare_success": True,
            "welfare_detail": "今日已领取过 10 虎粮福利",
            "gift_success": True,
            "gift_detail": "成功送出 10 个虎粮（库存 10 → 0）",
            "gift_count": 10,
            "left_count": 0,
            # 今日亲密度 = 打卡亲密度 (5) + 送虎粮个数 (10) = 15
            "today_score": str(5 + 10),
            "today_quota": "4000",
        }

        report = build_report_text(summary)
        print("\n--- 测试渲染报告（送出 10 个虎粮）---")
        print(report)
        print("--------------------------------------")

        self.assertIn("🔥 今日：15 / 4000", report)
        self.assertIn("├ 送礼：已送 10 个", report)
        self.assertIn("└ 余量：0 个", report)
        self.assertIn("├ 签到：打卡成功 (+5)", report)
        self.assertIn("├ 福利：已领 10 虎粮", report)

    def test_build_report_text_no_gift(self):
        # 模拟打卡成功但包裹无余粮的流程
        summary = {
            "version": "v2",
            "nick": "狂鸟丶楚河-90327",
            "room_id": "998",
            "account": "18579071857",
            "all_success": True,
            "fans_level": "Lv.22",
            "badge_name": "楚河",
            "current_score": 167817,
            "next_score": 175000,
            "need_intimacy": "7183",
            "daka_success": True,
            "daka_detail": "今日已经完成粉丝团打卡，无需重复领取",
            "daka_intimacy": 5,
            "welfare_success": True,
            "welfare_detail": "今日已领取过 10 虎粮福利",
            "gift_success": True,
            "gift_detail": "包裹中暂无虎粮",
            "gift_count": 0,
            "left_count": 0,
            # 今日亲密度 = 打卡亲密度 (5) + 送虎粮个数 (0) = 5
            "today_score": str(5 + 0),
            "today_quota": "4000",
        }

        report = build_report_text(summary)
        print("\n--- 测试渲染报告（暂无余粮）---")
        print(report)
        print("-------------------------------")

        self.assertIn("🔥 今日：5 / 4000", report)
        self.assertIn("├ 送礼：无余粮跳过", report)
        self.assertIn("└ 余量：0 个", report)

    def test_mobile_bot_execute_calculation(self):
        from unittest.mock import MagicMock
        from core.mobile_bot import HuyaMobileBotV2

        bot = HuyaMobileBotV2({"COOKIE": "yyuid=123; udb_uid=123", "ACCOUNT": "18579071857"})
        bot.ensure_logged_in = MagicMock(return_value=True)
        bot.mobile_punch_card = MagicMock(return_value={
            "success": True, "status": "打卡成功", "detail": "打卡成功（亲密度+5）", "intimacy": 5
        })
        bot.claim_mobile_welfare = MagicMock(return_value={
            "success": True, "status": "领取成功", "detail": "成功领取移动端专属福利", "item_count": 10
        })
        bot.send_tiger_food = MagicMock(return_value={
            "success": True, "status": "赠送成功", "detail": "成功送出 10 个虎粮（库存 10 → 0）",
            "count": 10, "left_count": 0
        })
        bot.query_badge_wup = MagicMock(return_value={
            "fans_level": "Lv.22", "badge_name": "楚河", "need_intimacy": "7183",
            "intimacy_progress": "167817/175000", "quota_score": 4000,
            "raw": {"current_score": 167817, "next_score": 175000}
        })
        bot.wechat_push = False

        summary = bot.execute()
        self.assertEqual(summary["gift_count"], 10)
        self.assertEqual(summary["today_score"], "15")  # 5 打卡 + 10 送粮 = 15

        report = build_report_text(summary)
        self.assertIn("🔥 今日：15 / 4000", report)
        self.assertIn("├ 送礼：已送 10 个", report)
        self.assertIn("└ 余量：0 个", report)

    def test_web_bot_execute_calculation(self):
        from unittest.mock import MagicMock
        from core.web_bot import HuyaWebBotV1

        bot = HuyaWebBotV1({"COOKIE": "yyuid=123", "ACCOUNT": "18579071857"})
        bot.ensure_logged_in = MagicMock(return_value=True)
        bot.web_punch_card = MagicMock(return_value={
            "success": True, "status": "打卡成功", "detail": "网页端打卡成功（亲密度+5）", "intimacy": 5,
            "fans_level": "22级", "badge_name": "楚河", "need_intimacy": "7183"
        })
        bot.web_send_tiger_food = MagicMock(return_value={
            "success": True, "status": "赠送成功", "detail": "成功送出 5 个免费虎粮",
            "count": 5, "left_count": 15
        })
        bot._close_browser = MagicMock()
        bot.wechat_push = False

        summary = bot.execute()
        self.assertEqual(summary["gift_count"], 5)
        self.assertEqual(summary["today_score"], "10")  # 5 打卡 + 5 送粮 = 10

        report = build_report_text(summary)
        self.assertIn("🔥 今日：10 / 4000", report)
        self.assertIn("├ 送礼：已送 5 个", report)
        self.assertIn("└ 余量：15 个", report)

    def test_wup_signal_code_compatibility(self):
        from core.wup import HuyaWupClient
        from core.mobile_bot import PackageGiftClient

        # 当网关未下发 SIGNAL_SERVICE_RET 时，应安全返回 "0"
        self.assertEqual(HuyaWupClient._signal_code({10: {}}), "0")
        self.assertEqual(PackageGiftClient._signal_code({10: {}}), "0")
        # 当网关显式下发非 0 状态码时，应准确识别为错误码
        self.assertEqual(HuyaWupClient._signal_code({10: {"SIGNAL_SERVICE_RET": "1001"}}), "1001")
        self.assertEqual(PackageGiftClient._signal_code({10: {"SIGNAL_SERVICE_RET": "1001"}}), "1001")

if __name__ == "__main__":
    unittest.main()
