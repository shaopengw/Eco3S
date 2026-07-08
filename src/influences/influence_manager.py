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
    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        influence_registry: Optional[Any] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.execution_order: List[ExecutionStep] = []
        self.influence_registry = influence_registry

        # 影响函数执行轨迹（默认关闭，仅在预检/隔离测试时开启）。
        # 记录每条影响函数“真的被应用 / 因模块缺失被静默跳过 / 抛异常”等事件，
        # 供 InfluenceTestRunner 之类的工具判断 influence 机制是否健康。
        self._trace_enabled: bool = False
        self.last_run_trace: List[Dict[str, Any]] = []

    def enable_trace(self, enabled: bool = True) -> None:
        """开启/关闭执行轨迹记录。开启后每次 apply_all_influences 会刷新 last_run_trace。"""
        self._trace_enabled = bool(enabled)

    def _record(self, event: str, **fields: Any) -> None:
        """仅在轨迹开启时记录一条事件，正常运行路径零开销。"""
        if self._trace_enabled:
            self.last_run_trace.append({"event": event, **fields})

    def set_registry(self, influence_registry: Optional[Any]) -> None:
        """（可选）绑定全局 InfluenceRegistry。

        绑定后，若某个模块没有自己的 `_influence_registry` / `apply_influences`，
        InfluenceManager 会回退到全局 registry 中查找 target_name 对应的影响函数。
        """
        self.influence_registry = influence_registry

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
        simulator_state: Optional[Dict[str, Any]] = None,
        plugin_registry: Optional[Any] = None,
        extra_state: Optional[Dict[str, Any]] = None,
        execution_order: Optional[Iterable[ExecutionStep]] = None,
        target_root: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """应用所有影响函数。

        支持两种调用方式（向后兼容）：
        1. 直接传 `simulator_state`（旧方式）
        2. 传 `plugin_registry` + `extra_state`，内部自动构建 simulator_state（推荐）

        Args:
            simulator_state: 完整的模拟器状态字典（旧方式）。
            plugin_registry: 插件注册表；若提供则自动从 selected_modules 构建 simulator_state。
            extra_state: 需要额外补充到 simulator_state 的字段（如 residents、gdp 等）。
            execution_order: 显式指定的执行顺序；若 None 则从 registry 中解析。
            target_root: 影响函数写回目标属性的“根对象”。
                当 target_name 不是 simulator_state 中的模块键时，影响函数会写回到该对象。
                通常传入 simulator 实例自身，使 influences.yaml 中的属性型 target
                （如 consumer_confidence、GDP）直接映射到 simulator 属性。

        Returns:
            构建/更新后的全局 context。
        """
        if simulator_state is None and plugin_registry is not None:
            # 自动从 plugin_registry 构建 simulator_state（推荐新方式）
            from src.simulation.plugin_access import build_simulator_state_from_registry
            simulator_state = build_simulator_state_from_registry(
                plugin_registry, extra_state=extra_state
            )

        if simulator_state is None:
            simulator_state = {}
            if extra_state:
                simulator_state.update(extra_state)

        context = self.build_global_context(simulator_state)

        if self._trace_enabled:
            self.last_run_trace = []

        order = list(execution_order) if execution_order is not None else self._resolve_execution_order(simulator_state)
        if not order:
            return context

        for module_name, target_name in order:
            self._apply_module_influence(
                module_name, target_name, context, simulator_state, target_root=target_root
            )

        return context

    def _resolve_execution_order(self, simulator_state: Dict[str, Any]) -> List[ExecutionStep]:
        if self.execution_order:
            return list(self.execution_order)

        # 优先使用全局 InfluenceRegistry 的执行顺序
        registry = self.influence_registry
        if registry is not None:
            order = getattr(registry, "execution_order", None)
            if order:
                return list(order)

        # 向后兼容：从 simulator_state 中各模块自己的 _influence_registry 读取
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
        target_root: Optional[Any] = None,
    ) -> None:
        # 保留模块名：直接在 simulator/aggregate 层应用全局 registry，避免被 per-agent apply_influences 截走
        if module_name == "__simulator__":
            self._apply_registry_influences(
                target_name=target_name,
                context=context,
                simulator_state=simulator_state,
                target_root=target_root,
            )
            return

        module = (simulator_state or {}).get(module_name)
        if module is None:
            # 模块名不在 simulator_state 中 —— 整条影响函数被静默跳过（头号失败模式）。
            self._record("module_missing", module=module_name, target=target_name)
            return

        # 支持“集合模块”（dict/list/tuple/set）：对其中每个元素逐个触发 apply_influences。
        if isinstance(module, dict):
            items = list(module.values())
        elif isinstance(module, (list, tuple, set)):
            items = list(module)
        else:
            items = [module]

        module_has_own_influences = False
        for item in items:
            apply_fn = getattr(item, "apply_influences", None)
            registry = getattr(item, "_influence_registry", None)
            if apply_fn is None or registry is None:
                continue

            module_has_own_influences = True
            try:
                apply_fn(target_name, context)
            except Exception as e:
                self.logger.error(
                    f"应用影响函数失败: {module_name}.{target_name}: {e}",
                    exc_info=True,
                )

        # 若模块自己没有影响函数实现，则回退到全局 InfluenceRegistry。
        if not module_has_own_influences and self.influence_registry is not None:
            self._apply_registry_influences(
                target_name=target_name,
                context=context,
                simulator_state=simulator_state,
                target_root=target_root,
            )

    def _apply_registry_influences(
        self,
        target_name: str,
        context: Dict[str, Any],
        simulator_state: Dict[str, Any],
        target_root: Optional[Any] = None,
    ) -> None:
        """从全局 InfluenceRegistry 中查找 target_name 对应的影响函数并执行。

        target 对象的解析优先级：
        1. simulator_state 中以 target_name 为键的模块（如 towns、residents）
        2. target_root（通常传入 simulator 实例，用于 consumer_confidence/GDP 等属性型 target）
        3. simulator_state 字典本身（兜底）

        新增：
        - 如果 target 是 dict/list/tuple/set，则对其中每个元素分别应用影响函数，
          从而支持 `target: residents` 类针对集合内每个对象的影响。
        - 如果 target_root 上不存在 target_name 属性，但 residents 字典中的对象存在该属性，
          则回退到对每个居民应用影响函数（兼容 AI 生成的 per-resident 影响）。
        """
        registry = self.influence_registry
        if registry is None:
            return

        influences = registry.get_influences(target_name)
        if not influences:
            self._record("no_influences_for_target", target=target_name)
            return

        target_obj = simulator_state.get(target_name)
        # 如果 simulator_state 中该键对应的是标量（如 float 初始值），
        # 则不应把它当作目标对象，而是回退到 target_root 或 simulator_state 字典。
        if target_obj is None or isinstance(target_obj, (int, float, str, bool)):
            target_obj = target_root
        if target_obj is None:
            target_obj = simulator_state

        # 展开集合型 target，实现 per-element 影响
        if isinstance(target_obj, dict):
            target_items = list(target_obj.values())
        elif isinstance(target_obj, (list, tuple, set)):
            target_items = list(target_obj)
        else:
            target_items = [target_obj]

        # 兜底：target_root 缺少目标属性，但 residents 可能拥有该 per-resident 属性
        if (
            len(target_items) == 1
            and target_items[0] is target_root
            and not hasattr(target_root, target_name)
        ):
            residents = simulator_state.get("residents")
            if isinstance(residents, dict) and residents:
                sample = next(iter(residents.values()))
                if hasattr(sample, target_name):
                    target_items = list(residents.values())

        for influence in influences:
            if getattr(influence, "placeholder", False):
                self._record("placeholder_skip", name=influence.name, target=target_name)
                continue
            for item in target_items:
                try:
                    # 记录应用前的 target 属性值（仅对根对象）
                    pre_value = None
                    if item is target_root and target_name and hasattr(item, target_name):
                        pre_value = getattr(item, target_name)

                    result = influence.apply(item, context)

                    # 记录应用后的值并计算变化
                    post_value = None
                    if item is target_root and target_name and hasattr(item, target_name):
                        post_value = getattr(item, target_name)
                        context[target_name] = post_value

                    self._record(
                        "applied",
                        name=influence.name,
                        target=target_name,
                        pre=pre_value,
                        post=post_value,
                    )
                    self._log_influence_apply(
                        influence, target_name, pre_value, post_value, result
                    )
                except Exception as e:
                    self._record(
                        "apply_error",
                        name=influence.name,
                        target=target_name,
                        error=str(e),
                    )
                    self.logger.error(
                        f"应用全局影响函数失败: {target_name} ({influence.name}): {e}",
                        exc_info=True,
                    )

    def _log_influence_apply(
        self,
        influence: Any,
        target_name: str,
        pre_value: Any,
        post_value: Any,
        result: Any,
    ) -> None:
        """记录单条影响函数的执行结果与变化率。"""
        delta = None
        delta_ratio = None
        anomaly = False

        if isinstance(pre_value, (int, float)) and isinstance(post_value, (int, float)):
            delta = post_value - pre_value
            if pre_value != 0:
                delta_ratio = delta / pre_value
            elif post_value != 0:
                delta_ratio = float("inf") if post_value > 0 else float("-inf")

            if (
                (delta_ratio is not None and abs(delta_ratio) > 10)
                or (delta is not None and abs(delta) > 1_000_000)
            ):
                anomaly = True

        msg = (
            f"INFLUENCE_APPLY name={influence.name} "
            f"source={influence.source} target={target_name} "
            f"pre={pre_value} post={post_value}"
        )
        if result is not None:
            msg += f" result={result:.6g}" if isinstance(result, (int, float)) else f" result={result}"
        if delta is not None:
            msg += f" delta={delta:.6g}"
        if delta_ratio is not None and abs(delta_ratio) != float("inf"):
            msg += f" delta_ratio={delta_ratio:.6g}"
        elif delta_ratio is not None:
            msg += " delta_ratio=inf"
        if anomaly:
            msg += " [ANOMALY]"

        if anomaly:
            self.logger.warning(msg)
        else:
            self.logger.debug(msg)

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
