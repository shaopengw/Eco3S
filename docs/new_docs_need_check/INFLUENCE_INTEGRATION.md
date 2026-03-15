# 影响函数系统集成指南

本文档提供了如何将影响函数系统集成到现有模拟器中的详细指导。

## 快速开始

### 1. 在配置文件中定义影响函数

在你的模拟器配置文件中添加 `influences` 部分（或创建单独的 influences 配置文件）:

```yaml
# config/your_simulation/influences_config.yaml
influences:
  - type: linear_multiplier
    source: climate
    target: population
    name: temperature_death_rate
    description: 高温导致死亡率上升
    params:
      multiplier: 0.01
      source_key: temperature
  
  - type: threshold
    source: economy
    target: towns
    name: unemployment_crisis
    description: 高失业率导致城镇危机
    params:
      threshold: 0.1
      compare_op: gt
      impact_value: -0.2
      source_key: unemployment_rate
```

### 2. 在主入口文件中加载影响函数

```python
# entrypoints/main_your_simulation.py
import yaml
from src.influences import InfluenceRegistry

def main():
    # ... 其他初始化代码 ...
    
    # 加载影响函数配置
    influences_config_path = os.path.join(
        project_root, 
        'config', 
        'your_simulation', 
        'influences_config.yaml'
    )
    
    influence_registry = InfluenceRegistry()
    
    if os.path.exists(influences_config_path):
        with open(influences_config_path, 'r', encoding='utf-8') as f:
            influences_config = yaml.safe_load(f)
        influence_registry.load_from_config(influences_config)
        print(f"已加载 {len(influence_registry.get_all_influences())} 个影响函数")
    
    # 将影响函数注册中心传递给模拟器
    simulator = YourSimulator(
        # ... 其他参数 ...
        influence_registry=influence_registry
    )
    
    # ... 运行模拟 ...
```

### 3. 修改 Simulator 类以支持影响函数

```python
# src/simulation/your_simulator.py
from src.influences import InfluenceRegistry

class YourSimulator:
    def __init__(
        self, 
        # ... 其他参数 ...
        influence_registry: InfluenceRegistry = None
    ):
        # ... 其他初始化 ...
        
        # 保存影响函数注册中心
        self.influence_registry = influence_registry or InfluenceRegistry()
        
        # 可选：打印影响函数统计信息
        if self.influence_registry:
            stats = self.influence_registry.get_statistics()
            print(f"模拟器配置了 {stats['total_influences']} 个影响函数")
            print(f"影响目标模块: {list(stats['targets'].keys())}")
    
    def step(self):
        """执行一步模拟"""
        # 1. 准备上下文 - 包含所有模块的引用
        context = self._build_context()
        
        # 2. 各模块执行自己的逻辑
        self.time.step()
        self.climate.step()
        self.economy.step()
        # ... 其他模块的 step ...
        
        # 3. 应用影响函数 - 在模块之间传播影响
        self._apply_influences(context)
        
        # 4. 更新统计和可视化
        self._update_statistics()
    
    def _build_context(self) -> dict:
        """
        构建影响函数所需的上下文字典
        
        Returns:
            包含所有模块引用的字典
        """
        context = {
            'time': self.time,
            'climate': self.climate,
            'economy': self.economy,
            'population': self.population,
            'transport': self.transport,
            'towns': self.towns,
            'social_network': self.social_network,
            # ... 添加你的所有模块 ...
            
            # 可选：添加额外的上下文信息
            'current_step': self.current_step,
            'config': self.config,
        }
        return context
    
    def _apply_influences(self, context: dict):
        """
        应用所有注册的影响函数
        
        Args:
            context: 包含所有模块的上下文字典
        """
        # 按目标模块分组应用影响
        for target_name in self.influence_registry.get_all_targets():
            # 获取目标模块对象
            target_module = context.get(target_name)
            if target_module is None:
                continue
            
            # 获取所有影响该目标的影响函数
            influences = self.influence_registry.get_influences(target_name)
            
            # 应用每个影响函数
            for influence in influences:
                try:
                    impact = influence.apply(target_module, context)
                    
                    if impact is not None:
                        # 处理影响结果
                        self._handle_influence_impact(
                            target_name, 
                            target_module, 
                            influence, 
                            impact
                        )
                
                except Exception as e:
                    # 处理影响函数执行错误
                    print(f"应用影响函数失败: {influence.source}->{influence.target}:{influence.name}")
                    print(f"错误: {str(e)}")
    
    def _handle_influence_impact(
        self, 
        target_name: str, 
        target_module, 
        influence, 
        impact
    ):
        """
        处理影响函数的结果
        
        Args:
            target_name: 目标模块名称
            target_module: 目标模块对象
            influence: 影响函数对象
            impact: 影响函数返回的结果
        """
        # 方法 1: 简单记录影响
        if not hasattr(self, 'influence_logs'):
            self.influence_logs = []
        
        self.influence_logs.append({
            'step': self.current_step,
            'source': influence.source,
            'target': target_name,
            'name': influence.name,
            'impact': impact
        })
        
        # 方法 2: 根据影响类型采取不同行动
        if influence.name == 'temperature_death_rate':
            # 直接修改模块属性
            target_module.death_rate += impact
        
        elif influence.name == 'unemployment_crisis':
            # 触发事件
            target_module.trigger_crisis('unemployment', severity=abs(impact))
        
        elif influence.name == 'extreme_heat_disaster':
            # 触发灾害响应
            target_module.handle_disaster('extreme_heat')
        
        # 方法 3: 使用统一的影响处理接口
        # 假设所有模块都实现了 handle_influence 方法
        if hasattr(target_module, 'handle_influence'):
            target_module.handle_influence(
                source=influence.source,
                name=influence.name,
                impact=impact
            )
```

## 高级用法

### 1. 在模块类中添加影响处理方法

```python
# src/environment/population.py
class Population:
    def __init__(self):
        # ... 初始化 ...
        self.influence_modifiers = {}  # 存储影响带来的修正值
    
    def handle_influence(self, source: str, name: str, impact):
        """
        统一的影响处理接口
        
        Args:
            source: 影响来源模块
            name: 影响名称
            impact: 影响值
        """
        # 根据影响名称采取不同行动
        if name == 'temperature_death_rate':
            # 累加到死亡率修正
            self.influence_modifiers['death_rate'] = \
                self.influence_modifiers.get('death_rate', 0) + impact
        
        elif name == 'extreme_heat_disaster':
            # 触发灾害
            self.trigger_disaster('extreme_heat')
        
        # ... 其他影响处理 ...
    
    def calculate_death_rate(self) -> float:
        """计算实际死亡率（考虑所有影响）"""
        base_rate = self.base_death_rate
        
        # 应用影响修正
        modifier = self.influence_modifiers.get('death_rate', 0)
        
        return max(0, base_rate + modifier)
    
    def reset_influences(self):
        """在每步结束时重置影响修正"""
        self.influence_modifiers.clear()
```

### 2. 条件性应用影响

有时你可能只想在特定条件下应用某些影响：

```python
def _apply_influences(self, context: dict):
    """应用影响函数（带条件控制）"""
    # 获取当前模拟阶段
    phase = self._get_simulation_phase()
    
    for target_name in self.influence_registry.get_all_targets():
        target_module = context.get(target_name)
        if target_module is None:
            continue
        
        influences = self.influence_registry.get_influences(target_name)
        
        for influence in influences:
            # 根据模拟阶段决定是否应用
            if self._should_apply_influence(influence, phase):
                impact = influence.apply(target_module, context)
                if impact is not None:
                    self._handle_influence_impact(
                        target_name, target_module, influence, impact
                    )

def _should_apply_influence(self, influence, phase: str) -> bool:
    """
    判断是否应该应用该影响函数
    
    Args:
        influence: 影响函数对象
        phase: 当前模拟阶段 ('early', 'middle', 'late')
    
    Returns:
        是否应该应用
    """
    # 例如：某些影响只在模拟中后期生效
    late_phase_influences = [
        'resource_depletion',
        'infrastructure_decay'
    ]
    
    if phase == 'early' and influence.name in late_phase_influences:
        return False
    
    return True
```

### 3. 记录和分析影响

```python
class YourSimulator:
    def __init__(self, ...):
        # ... 其他初始化 ...
        
        # 影响统计
        self.influence_stats = {
            'total_applications': 0,
            'by_source': {},
            'by_target': {},
            'by_influence': {}
        }
    
    def _handle_influence_impact(self, target_name, target_module, influence, impact):
        """处理影响并记录统计"""
        # 更新统计
        self.influence_stats['total_applications'] += 1
        
        source = influence.source
        self.influence_stats['by_source'][source] = \
            self.influence_stats['by_source'].get(source, 0) + 1
        
        self.influence_stats['by_target'][target_name] = \
            self.influence_stats['by_target'].get(target_name, 0) + 1
        
        influence_key = f"{source}->{target_name}:{influence.name}"
        if influence_key not in self.influence_stats['by_influence']:
            self.influence_stats['by_influence'][influence_key] = {
                'count': 0,
                'total_impact': 0,
                'impacts': []
            }
        
        self.influence_stats['by_influence'][influence_key]['count'] += 1
        self.influence_stats['by_influence'][influence_key]['impacts'].append({
            'step': self.current_step,
            'value': impact
        })
        
        # 处理影响...
    
    def print_influence_statistics(self):
        """打印影响函数统计信息"""
        print("\n=== 影响函数统计 ===")
        print(f"总应用次数: {self.influence_stats['total_applications']}")
        
        print("\n按源模块统计:")
        for source, count in self.influence_stats['by_source'].items():
            print(f"  {source}: {count} 次")
        
        print("\n按目标模块统计:")
        for target, count in self.influence_stats['by_target'].items():
            print(f"  {target}: {count} 次")
        
        print("\n最活跃的影响函数:")
        sorted_influences = sorted(
            self.influence_stats['by_influence'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        for influence_key, data in sorted_influences[:5]:
            print(f"  {influence_key}: {data['count']} 次")
```

### 4. 动态注册影响函数

除了从配置文件加载，你也可以在运行时动态注册影响函数：

```python
from src.influences import LinearMultiplierInfluence, ThresholdInfluence

def setup_dynamic_influences(simulator):
    """动态设置影响函数"""
    # 注册线性影响
    temp_influence = LinearMultiplierInfluence(
        source='climate',
        target='population',
        name='dynamic_temperature_impact',
        multiplier=0.02,  # 更大的影响系数
        source_key='temperature'
    )
    simulator.influence_registry.register(temp_influence)
    
    # 注册阈值影响
    crisis_influence = ThresholdInfluence(
        source='economy',
        target='population',
        name='economic_crisis',
        threshold=500,  # GDP低于500触发危机
        impact_value='crisis',
        source_key='gdp',
        compare_op='lt'
    )
    simulator.influence_registry.register(crisis_influence)
    
    print(f"动态注册了 2 个影响函数")
```

## 完整示例

以下是一个完整的集成示例：

```python
# entrypoints/main_climate_economy_sim.py
import os
import sys
import yaml

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.simulation.climate_economy_simulator import ClimateEconomySimulator
from src.influences import InfluenceRegistry

def main():
    # 加载基本配置
    config_path = os.path.join(project_root, 'config', 'climate_economy_sim', 'simulation_config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 加载影响函数配置
    influences_config_path = os.path.join(project_root, 'config', 'climate_economy_sim', 'influences_config.yaml')
    influence_registry = InfluenceRegistry()
    
    if os.path.exists(influences_config_path):
        with open(influences_config_path, 'r', encoding='utf-8') as f:
            influences_config = yaml.safe_load(f)
        
        loaded_count = influence_registry.load_from_config(influences_config)
        print(f"✓ 加载了 {loaded_count} 个影响函数")
        
        # 打印统计信息
        stats = influence_registry.get_statistics()
        print(f"  - 影响目标: {', '.join(stats['targets'].keys())}")
        print(f"  - 影响来源: {', '.join(stats['sources'].keys())}")
    
    # 创建模拟器
    simulator = ClimateEconomySimulator(
        config=config,
        influence_registry=influence_registry
    )
    
    # 运行模拟
    print("\n开始模拟...")
    for step in range(config['simulation']['steps']):
        simulator.step()
        
        if step % 10 == 0:
            print(f"步骤 {step}: 气温={simulator.climate.temperature:.1f}°C, GDP={simulator.economy.gdp:.0f}")
    
    # 打印影响统计
    simulator.print_influence_statistics()
    
    print("\n模拟完成！")

if __name__ == "__main__":
    main()
```

## 最佳实践

1. **上下文设计**: 在 `_build_context()` 中包含所有必要的模块引用和元数据。

2. **错误处理**: 在 `_apply_influences()` 中使用 try-except，防止单个影响函数的错误影响整个模拟。

3. **性能优化**: 如果有大量影响函数，考虑：
   - 缓存影响函数查询结果
   - 只在必要时重新计算影响
   - 使用条件判断提前退出

4. **调试支持**: 添加详细的日志记录，帮助理解影响函数的执行：
   ```python
   if self.debug_mode:
       print(f"应用影响: {influence.source}->{target_name}:{influence.name} = {impact}")
   ```

5. **配置验证**: 在加载配置后验证影响函数的完整性：
   ```python
   def validate_influences(self):
       """验证所有影响函数引用的模块都存在"""
       all_modules = set(self._build_context().keys())
       stats = self.influence_registry.get_statistics()
       
       missing_sources = set(stats['sources'].keys()) - all_modules
       missing_targets = set(stats['targets'].keys()) - all_modules
       
       if missing_sources:
           print(f"警告: 以下源模块不存在: {missing_sources}")
       if missing_targets:
           print(f"警告: 以下目标模块不存在: {missing_targets}")
   ```

## 扩展影响函数系统

如果内置的影响函数类型不能满足需求，可以创建自定义类型：

```python
# src/influences/custom_influences.py
from src.influences import IInfluenceFunction

class CustomInfluence(IInfluenceFunction):
    """自定义影响函数"""
    
    def __init__(self, source: str, target: str, name: str, **params):
        super().__init__(source, target, name, "自定义影响")
        # 处理自定义参数
        self.param1 = params.get('param1')
        self.param2 = params.get('param2')
    
    def apply(self, target_obj, context: dict):
        """实现自定义逻辑"""
        # 你的逻辑
        pass

# 注册自定义工厂
def create_custom_influence(config: dict) -> CustomInfluence:
    """从配置创建自定义影响函数"""
    return CustomInfluence(
        source=config['source'],
        target=config['target'],
        name=config['name'],
        **config.get('params', {})
    )

# 在主程序中注册
influence_registry.register_factory('custom', create_custom_influence)
```

然后就可以在配置文件中使用：

```yaml
influences:
  - type: custom
    source: module_a
    target: module_b
    name: custom_effect
    params:
      param1: value1
      param2: value2
```
