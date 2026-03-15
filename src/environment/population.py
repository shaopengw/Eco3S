from src.interfaces import IPopulation
from typing import Optional, Any, Dict

class Population(IPopulation):
    def __init__(self, initial_population, birth_rate=0.01, influence_registry: Optional[Any] = None):
        """
        初始化人口类
        :param initial_population: 初始人口数量
        :param birth_rate: 出生率
        :param influence_registry: 影响函数注册表（可选）
        """
        self._population = initial_population
        self._birth_rate = birth_rate
        self._influence_registry = influence_registry
    
    # 实现 IPopulation 接口的 property
    @property
    def population(self) -> int:
        """当前人口数量"""
        return self._population
    
    @population.setter
    def population(self, value: int):
        """设置人口数量"""
        self._population = value
    
    @property
    def birth_rate(self) -> float:
        """出生率"""
        return self._birth_rate
    
    @birth_rate.setter
    def birth_rate(self, value: float):
        """设置出生率"""
        self._birth_rate = value

    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        :param target_name: 目标名称（如'birth_rate'）
        :param context: 上下文数据字典
        """
        if self._influence_registry is None:
            return
        
        influences = self._influence_registry.get_influences(target_name)
        if not influences:
            return
        
        for influence in influences:
            try:
                influence.apply(self, context)
            except Exception as e:
                print(f"[Population] Error applying influence to {target_name}: {e}")

    def update_birth_rate(self, satisfaction):
        """
        根据居民平均满意度更新出生率
        :param satisfaction: 居民平均满意度（0-100）
        """
        # 构建上下文
        context = {
            'population': self,
            'satisfaction': satisfaction,
            'current_birth_rate': self.birth_rate,
            'population_size': self.population
        }
        
        # 尝试使用影响函数
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('birth_rate')
            if influences:
                self.apply_influences('birth_rate', context)
                return
        
        # 回退到默认公式（向后兼容）
        base_rate = self.birth_rate
        
        if satisfaction >= 80:
            # 满意度高于80时，出生率上升
            # 每超过80一点，出生率增加0.2%
            increase = (satisfaction - 80) * 0.002
            self.birth_rate = min(0.5, base_rate + increase)
        elif satisfaction <= 50:
            # 满意度低于50时，出生率下降
            # 每低于50一点，出生率降低0.001
            decrease = (50 - satisfaction) * 0.001
            self.birth_rate = max(0.01, base_rate - decrease)
        else:
            # 满意度在50-80之间，保持基础出生率
            self.birth_rate = base_rate

    def birth(self,num):
        """
        人口出生
        """
        self.population += num
        return self.population

    def death(self):
        """
        人口死亡
        """
        if self.population > 0:
            self.population -= 1
        else:
            print("警告：人口已为0，无法继续减少")

    def get_population(self):
        """
        获取当前人口数量
        :return: 当前人口数量
        """
        return self.population

    def print_population_status(self):
        """
        打印人口状态（用于调试）
        """
        print(f"Current Population: {self.population}")
        print(f"Birth Rate: {self.birth_rate * 100}%")