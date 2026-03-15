from src.interfaces import ITransportEconomy
from typing import Optional, Any, Dict

class TransportEconomy(ITransportEconomy):
    def __init__(self, transport_cost: float, transport_task: float, maintenance_cost_base: float = 100,
                 influence_registry: Optional[Any] = None):
        """
        初始化运输经济系统
        :param transport_cost: 基础运输成本
        :param transport_task: 年度运输任务量（吨）
        :param maintenance_cost_base: 基础维护成本
        :param influence_registry: 影响函数注册表（可选）
        """
        self._transport_cost = transport_cost  # 基础运输成本
        self._transport_task = transport_task  # 年度运输任务量
        self._maintenance_cost_base = maintenance_cost_base  # 基础维护成本
        self._river_price = transport_cost
        self._sea_price = round((self._transport_cost / 5),2)  # 初始化海运价格
        self._influence_registry = influence_registry
    
    # 实现 ITransportEconomy 接口的 property
    @property
    def transport_cost(self) -> float:
        """基础运输成本"""
        return self._transport_cost
    
    @property
    def transport_task(self) -> float:
        """年度运输任务量（吨）"""
        return self._transport_task
    
    @property
    def maintenance_cost_base(self) -> float:
        """基础维护成本"""
        return self._maintenance_cost_base
    
    @property
    def river_price(self) -> float:
        """当前河运价格"""
        return self._river_price
    
    @river_price.setter
    def river_price(self, value: float):
        """设置河运价格"""
        self._river_price = value
    
    @property
    def sea_price(self) -> float:
        """海运价格"""
        return self._sea_price

    def apply_influences(self, target_name: str, context: Dict[str, Any]) -> None:
        """
        应用影响函数到指定目标
        :param target_name: 目标名称（如'river_price', 'maintenance_cost', 'total_cost'）
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
                print(f"[TransportEconomy] Error applying influence to {target_name}: {e}")

    def calculate_river_price(self, navigability):
        """
        计算河运价格
        :param navigability: 通航能力（0-1）
        :return: 河运价格
        """
        # 构建上下文
        context = {
            'transport_economy': self,
            'navigability': navigability,
            'transport_cost': self.transport_cost,
            'current_river_price': self.river_price
        }
        
        # 尝试使用影响函数
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('river_price')
            if influences:
                self.apply_influences('river_price', context)
                return self.river_price
        
        # 回退到默认公式（向后兼容）
        river_price = round(self.transport_cost * (2 - navigability),2)
        self.river_price = max(river_price, self.transport_cost)
        return self.river_price

    def calculate_maintenance_cost(self, navigability, exponent=3):
        """
        计算河运维护成本
        :param navigability: 当前通航能力（0-1）
        :param exponent: 指数
        :return: 维护成本
        """
        # 构建上下文
        result = {'maintenance_cost': 0.0}
        context = {
            'transport_economy': self,
            'navigability': navigability,
            'exponent': exponent,
            'maintenance_cost_base': self.maintenance_cost_base,
            'result': result
        }
        
        # 尝试使用影响函数
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('maintenance_cost')
            if influences:
                self.apply_influences('maintenance_cost', context)
                return round(result['maintenance_cost'], 2)
        
        # 回退到默认公式（向后兼容）
        return round(self.maintenance_cost_base * ((2 - navigability) ** exponent), 2)


    def calculate_total_transport_cost(self, river_ratio):
        """
        计算总运输成本
        :param river_ratio: 河运比例（0-1）
        :return: 总运输成本
        """
        # 构建上下文
        result = {'total_cost': 0.0}
        context = {
            'transport_economy': self,
            'river_ratio': river_ratio,
            'river_price': self.river_price,
            'sea_price': self.sea_price,
            'transport_task': self.transport_task,
            'result': result
        }
        
        # 尝试使用影响函数
        if self._influence_registry is not None:
            influences = self._influence_registry.get_influences('total_transport_cost')
            if influences:
                self.apply_influences('total_transport_cost', context)
                return result['total_cost']
        
        # 回退到默认公式（向后兼容）
        river_cost = self.river_price * river_ratio * self.transport_task
        sea_cost = self.sea_price * (1 - river_ratio) * self.transport_task
        return river_cost + sea_cost
