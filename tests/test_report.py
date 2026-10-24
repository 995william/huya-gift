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
        # 当网关在 STATUS_RESULT_DESC 下发 905 异常时，应准确识别
        gateway_err = {10: {"STATUS_RESULT_DESC": "wup request biz execption:905"}}
        self.assertEqual(HuyaWupClient._signal_code(gateway_err), "905")
        self.assertEqual(PackageGiftClient._signal_code(gateway_err), "905")

    def test_fans_sign_sunday_and_flags(self):
        from core.wup import FansSignStatus

        # position = 0 代表周日，测试未打卡 (sign_flags & 1 == 0) 与已打卡 (sign_flags & 1 == 1)
        status_sunday_uncheck = FansSignStatus("0", 0, "ok", 0, 0, 0)
        self.assertFalse(status_sunday_uncheck.signed_today)
        status_sunday_checked = FansSignStatus("0", 0, "ok", 0, 0, 1)
        self.assertTrue(status_sunday_checked.signed_today)

        # position = 1 代表周一，测试打卡位
        status_monday_checked = FansSignStatus("0", 0, "ok", 1, 0, 1)
        self.assertTrue(status_monday_checked.signed_today)

    def test_package_tiger_food_parsing(self):
        from unittest.mock import MagicMock
        from core.mobile_bot import PackageGiftClient

        client = PackageGiftClient("yyuid=123; guid=test_guid")
        # 模拟 WUP 成功返回：tag 0 为礼物列表，每个 gift 的 tag 0 为 simple_info (tag 1: "虎粮", tag 0: 4)
        mock_root = {10: {"SIGNAL_SERVICE_RET": "0"}}
        mock_response = {
            "tRsp": {
                0: {
                    0: [
                        {
                            0: {0: 4, 1: "虎粮", 3: 1729000000},
                            5: 10,  # 数量
                        }
                    ]
                }
            }
        }
        client._send_wup = MagicMock(return_value=(mock_root, mock_response))
        inv = client.query_tiger_food(123456)
        self.assertEqual(inv.signal_code, "0")
        self.assertEqual(inv.item_name, "虎粮")
        self.assertEqual(inv.item_type, 4)
        self.assertEqual(inv.count, 10)

    def test_daily_tiger_food_client_user_id_encoding(self):
        from core.mobile_bot import DailyTigerFoodClient
        from core.wup import JceInputStream

        # 测试当仅提供标准 Cookie 时，自动提取 guid，无 token 时 token_type 默认为 0
        client = DailyTigerFoodClient("yyuid=123456; guid=my_guid_abc")
        parsed = JceInputStream(client.user_id_bytes).parse_all()
        user_id = parsed.get(0, {})
        self.assertEqual(user_id.get(0), 123456)
        self.assertEqual(user_id.get(1), "my_guid_abc")
        self.assertEqual(user_id.get(2), "")
        self.assertEqual(user_id.get(5), 0)  # 无 token 默认为 0 (Cookie 登录)
        self.assertEqual(client.ua, user_id.get(3))  # 请求头 huya_ua 与包体内 UA 一致


if __name__ == "__main__":
    unittest.main()
