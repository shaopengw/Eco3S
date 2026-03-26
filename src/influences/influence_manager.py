"""src.influences.influence_manager

InfluenceManager 是“影响函数编排器”，只做两件事：
1) 把 simulator_state 透传成 context（最小补齐常用字段）；
2) 按 influences.yaml 中的 execution_order 顺序触发各模块的 apply_influences。

重要：不在这里硬编码任何相互影响公式/依赖顺序。
新增模块或新增影响时，优先改 influences.yaml。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging


ExecutionStep = Tuple[str, str]  # (module_name, target_name)


class InfluenceManager:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.execution_order: List[ExecutionStep] = []

    def build_global_context(self, simulator_state: Dict[str, Any]) -> Dict[str, Any]:
        """构建影响函数 context。

        尽量保持通用与简洁：
        - 默认把 simulator_state 直接作为 context；
        - 仅补齐 `result`（用于把影响函数的中间结果写回）。
        """

        context: Dict[str, Any] = dict(simulator_state or {})
        context.setdefault("result", {})

        time_obj = context.get("time")
        if time_obj is not None:
            # 常用字段：很多影响函数需要年份，但放在这里补齐不会绑定具体业务逻辑
            context.setdefault("current_year", getattr(time_obj, "current_time", None))
            context.setdefault("start_year", getattr(time_obj, "start_time", None))

        return context

    def apply_all_influences(
        self,
        simulator_state: Dict[str, Any],
        execution_order: Optional[Iterable[ExecutionStep]] = None,
    ) -> Dict[str, Any]:
        context = self.build_global_context(simulator_state)

        order = list(execution_order) if execution_order is not None else self._resolve_execution_order(simulator_state)
        if not order:
            return context

        for module_name, target_name in order:
            self._apply_module_influence(module_name, target_name, context, simulator_state)

        return context

    def _resolve_execution_order(self, simulator_state: Dict[str, Any]) -> List[ExecutionStep]:
        if self.execution_order:
            return list(self.execution_order)

        for obj in (simulator_state or {}).values():
            registry = getattr(obj, "_influence_registry", None)
            if registry is None:
                continue
            order = getattr(registry, "execution_order", None)
            if order:
                return list(order)

        return []

    def _apply_module_influence(
        self,
        module_name: str,
        target_name: str,
        context: Dict[str, Any],
        simulator_state: Dict[str, Any],
    ) -> None:
        module = (simulator_state or {}).get(module_name)
        if module is None:
            return

        # 支持“集合模块”（dict/list/tuple/set）：对其中每个元素逐个触发 apply_influences。
        if isinstance(module, dict):
            items = list(module.values())
        elif isinstance(module, (list, tuple, set)):
            items = list(module)
        else:
            items = [module]

        for item in items:
            apply_fn = getattr(item, "apply_influences", None)
            if apply_fn is None:
                continue

            registry = getattr(item, "_influence_registry", None)
            if registry is None:
                continue

            try:
                apply_fn(target_name, context)
            except Exception as e:
                self.logger.error(
                    f"应用影响函数失败: {module_name}.{target_name}: {e}",
                    exc_info=True,
                )
    
    def set_execution_order(self, order: List[tuple]) -> None:
        """
        设置模块影响函数的执行顺序
        
        Args:
            order: 执行顺序列表，每个元素为 (module_name, target_name) 元组
        
        Example:
            manager.set_execution_order([
                ('climate', 'climate_impact'),
                ('map', 'canal_condition'),
                ('population', 'birth_rate'),
            ])
        """
        self.execution_order = order
        self.logger.info(f"影响函数执行顺序已更新: {len(order)} 个步骤")
