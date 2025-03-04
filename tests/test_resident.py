import unittest
from unittest.mock import MagicMock, patch
import asyncio
from src.agents.resident import Resident

class TestResident(unittest.TestCase):
    def setUp(self):
        """
        在每个测试之前初始化一个 Resident 实例。
        """
        # 创建一个模拟的就业市场对象
        self.mock_job_market = MagicMock()
        self.resident = Resident(
            resident_id="12345",
            location=(0, 0),
            job_market=self.mock_job_market,
            model_type="gpt-3.5-turbo"
        )

    def test_initial_state(self):
        """
        测试初始化状态
        """
        self.assertEqual(self.resident.resident_id, "12345")
        self.assertEqual(self.resident.location, (0, 0))
        self.assertFalse(self.resident.employed)
        self.assertIsNone(self.resident.job)
        self.assertEqual(self.resident.income, 0)
        self.assertEqual(self.resident.satisfaction, 100)
        self.assertEqual(self.resident.rebellion_risk, 0)

    def test_employ(self):
        """
        测试居民就业功能
        """
        self.resident.employ("船员")
        self.assertTrue(self.resident.employed)
        self.assertEqual(self.resident.job, "船员")
        self.assertEqual(self.resident.income, 100)
        self.assertEqual(self.resident.satisfaction, 110)  # 满意度增加10

    def test_unemploy(self):
        """
        测试居民失业功能
        """
        self.resident.employ("船员")  # 首先就业
        self.resident.unemploy()
        self.assertFalse(self.resident.employed)
        self.assertIsNone(self.resident.job)
        self.assertEqual(self.resident.income, 0)
        self.assertEqual(self.resident.satisfaction, 90)  # 满意度减少20

    def test_migrate(self):
        """
        测试居民迁徙功能
        """
        self.resident.migrate((10, 10))
        self.assertEqual(self.resident.location, (10, 10))

    def test_evaluate_rebellion_risk_no_risk(self):
        """
        测试评估叛乱风险（无风险）
        """
        self.resident.satisfaction = 80  # 满意度较高
        self.resident.income = 80  # 收入较高
        self.resident.employed = True  # 就业
        self.resident.evaluate_rebellion_risk()
        self.assertEqual(self.resident.rebellion_risk, 0)

    def test_evaluate_rebellion_risk_high_risk(self):
        """
        测试评估叛乱风险（高风险）
        """
        self.resident.satisfaction = 30  # 满意度低
        self.resident.income = 30  # 收入低
        self.resident.employed = False  # 失业
        self.resident.evaluate_rebellion_risk()
        self.assertGreater(self.resident.rebellion_risk, 0)  # 叛乱风险应该增加

    def test_decide_rebellion_no_rebellion(self):
        """
        测试决定是否参与叛乱（不参与）
        """
        self.resident.satisfaction = 80  # 满意度较高
        self.resident.income = 80  # 收入较高
        self.resident.employed = True  # 就业
        self.assertFalse(self.resident.decide_rebellion())

    def test_decide_rebellion_yes_rebellion(self):
        """
        测试决定是否参与叛乱（参与）
        """
        self.resident.satisfaction = 30  # 满意度低
        self.resident.income = 30  # 收入低
        self.resident.employed = False  # 失业
        self.assertTrue(self.resident.decide_rebellion())

    # def test_receive_information(self):
    #     """
    #     测试接收信息
    #     """
    #     self.resident.receive_information("新的政策公告")
    #     self.assertEqual(self.resident.satisfaction, 105)  # 满意度增加5
    #     # 确保 CAMEL 框架的记忆记录被调用
    #     self.assertGreater(len(self.resident.memory.records), 0)
    def test_receive_information(self):
        """
        测试接收信息
        """
        self.resident.receive_information("新的政策公告")
        self.assertEqual(self.resident.satisfaction, 105)  # 满意度增加5
        # 确保 CAMEL 框架的记忆记录被调用
        self.resident.memory.write_record.assert_called()  # 验证 `write_record` 是否被调用

    async def test_process_information(self):
        """
        测试处理接收到的信息
        """
        # 使用模拟模型后端
        self.resident.model_backend.run = MagicMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="好的，感谢政策公告！"))]))
        
        # 先接收一条信息
        self.resident.receive_information("新的政策公告")
        
        # 处理信息
        await self.resident.process_information()
        
        # 确保模型生成了回应
        self.resident.model_backend.run.assert_called()
        # 确保记忆记录中包含居民的回应
        self.assertGreater(len(self.resident.memory.records), 1)

    @patch('builtins.print')
    # def test_print_resident_status(self, mock_print):
    #     """
    #     测试打印居民状态
    #     """
    #     self.resident.print_resident_status()
    #     # 验证 print 函数被调用
    #     mock_print.assert_called()
    def test_print_resident_status(self):
        """
        测试打印居民状态
        """
        with patch("builtins.print") as mock_print:
            self.resident.print_resident_status()  # 调用方法
            mock_print.assert_called() 
if __name__ == "__main__":
    unittest.main()
