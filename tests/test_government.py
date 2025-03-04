import unittest
from src.environment.map import Map
from src.environment.job_market import JobMarket
from src.agents.government import Government
from src.environment.time import Time

class TestGovernment(unittest.TestCase):
    def setUp(self):
        self.map = Map(size=10)
        self.job_market = JobMarket()
        self.time = Time(start_year=1650, end_year=1700)
        self.government = Government(map=self.map, job_market=self.job_market, initial_budget=10000, time=self.time)

    def test_provide_jobs(self):
        self.government.provide_jobs()
        self.assertIn("Canal Maintenance", self.job_market.get_available_jobs())  # 检查是否提供工作机会
        self.assertEqual(self.government.get_budget(), 9000)  # 检查预算是否正确减少

    def test_maintain_canal(self):
        self.map.initialize_river()
        self.government.maintain_canal()
        self.assertEqual(self.government.get_budget(), 9500)  # 检查预算是否正确减少
        self.assertLess(self.map.river_grid[0, 5], 1)  # 检查运河损坏程度是否更新

    def test_suppress_rebellion(self):
        self.assertTrue(self.government.suppress_rebellion(rebellion_strength=50))  # 检查是否成功镇压叛乱
        self.assertEqual(self.government.get_military_strength(), 95)  # 检查军事力量是否正确减少

if __name__ == "__main__":
    unittest.main()