import unittest
from src.environment.time import Time

class TestTime(unittest.TestCase):
    def setUp(self):
        self.time = Time(start_year=1650, end_year=1700)

    def test_step(self):
        self.time.step()
        self.assertEqual(self.time.get_current_quarter(), 2)  # 检查时间步长是否正确推进
        for _ in range(4):
            self.time.step()
        self.assertEqual(self.time.get_current_year(), 1651)  # 检查年份是否正确推进

    def test_is_end(self):
        for _ in range(50 * 4):  # 模拟50年
            self.time.step()
        self.assertTrue(self.time.is_end())  # 检查是否到达结束时间

    def test_get_current_time(self):
        self.assertEqual(self.time.get_current_time(), "1650 Q1")  # 检查当前时间是否正确

if __name__ == "__main__":
    unittest.main()