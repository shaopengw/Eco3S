import unittest
from src.environment.map import Map

# class TestMap(unittest.TestCase):
#     def setUp(self):
#         self.map = Map(size=10)

#     def test_initialize_river(self):
#         self.map.initialize_river()
#         self.assertEqual(self.map.river_grid[0, 5], 1)  # 检查沿河区域是否正确初始化
#         self.assertEqual(self.map.river_grid[9, 5], 1)

#     def test_initialize_market_towns(self):
#         self.map.initialize_market_towns()
#         self.assertIn((0, 5), self.map.market_towns)  # 检查市场城镇是否正确初始化
#         self.assertIn((5, 5), self.map.market_towns)

#     def test_update_river_condition(self):
#         self.map.initialize_river()
#         self.map.update_river_condition(year=1850)
#         self.assertLess(self.map.river_grid[0, 5], 1)  # 检查运河损坏程度是否更新

#     def test_is_river_nearby(self):
#         self.map.initialize_river()
#         self.assertTrue(self.map.is_river_nearby((0, 5)))  # 检查是否靠近运河
#         self.assertFalse(self.map.is_river_nearby((0, 0)))

# if __name__ == "__main__":
#     unittest.main()
if __name__ == "__main__":
    # 初始化地图
    map = Map(size=100)
    map.initialize_river()
    map.initialize_market_towns()

    # 打印地图信息
    map.print_map()

    # 可视化地图
    map.visualize_map()

    # 更新运河状态并重新可视化
    map.update_river_condition(year=1850)
    map.visualize_map()