"""src.utils.entrypoint_runner

放置 entrypoints 的固定运行骨架：
- 可选：从 influences.yaml 加载 InfluenceRegistry
- 可选：从缓存恢复 Simulator
- 构建新 Simulator（由调用方提供 build_new_simulator）
- 运行 + 可选保存缓存

目标：让 main*.py 尽量只保留"仿真特有编排"，减少重复样板代码。
"""

from __future__ import annotations

import inspect
import argparse
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Protocol, Sequence, Set, Tuple

import yaml

from src.influences import InfluenceRegistry
from src.simulation.plugin_access import require_module
from src.utils.simulation_cache import SimulationCache
from src.visualization.auto_plotter import auto_plot_results


class CacheBackend(Protocol):
    """可替换的缓存后端接口。

    入口层/运行骨架只依赖这些方法，便于后续换成插件式实现。
    默认后端为 `SimulationCache`。
    """

    @staticmethod
    def generate_cache_filename(*, population: Any, total_years: Any, cache_dir: str, with_timestamp: bool) -> str: ...

    @staticmethod
    def find_latest_cache(*, population: Any, target_years: Any, cache_dir: str): ...

    @staticmethod
    def load_cache(*, file_path: str, simulator_class: type, simulator_years: int, config: dict): ...

    @staticmethod
    def save_cache(simulator: Any, file_path: str) -> bool: ...


@dataclass(frozen=True)
class CacheOptions:
    cache_dir: str
    resume_from_cache: bool
    save_cache: bool
def _boolish(value: Any) -> bool:
    """把常见的 0/1、true/false、"0"/"1" 等配置值转成 bool。

    说明：YAML 中 0/1 很常见；而字符串 "0" 在 Python 中 truthy，
    因此需要显式解析。
    """

    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off", ""}:
            return False
        # 未识别字符串：按 Python 习惯兜底
        return True

    return bool(value)


def get_cache_options(config: dict, cache_dir: str) -> CacheOptions:
    """从配置中提取缓存选项。

    约定：只从 config['simulation'] 读取。
    如果字段缺失，则默认关闭（False）。
    """

    sim_cfg = (config or {}).get("simulation", {}) or {}

    resume = sim_cfg.get("resume_from_cache", False)
    save = sim_cfg.get("save_cache", False)

    return CacheOptions(
        cache_dir=cache_dir,
        resume_from_cache=_boolish(resume),
        save_cache=_boolish(save),
    )


def load_influence_registry_from_dir(config_dir: str, logger: Optional[logging.Logger] = None) -> InfluenceRegistry:
    """从配置目录加载 influences.yaml，失败则返回空 registry（不抛错）。"""

    influence_logger = logger or logging.getLogger("influences")
    influence_registry = InfluenceRegistry(logger=influence_logger)

    influences_config_path = os.path.join(config_dir, "influences.yaml")
    if not os.path.exists(influences_config_path):
        return influence_registry

    try:
        with open(influences_config_path, "r", encoding="utf-8") as f:
            influences_config = yaml.safe_load(f)
        influence_registry.load_from_config(influences_config)
    except Exception as e:
        influence_logger.warning(f"加载 influences.yaml 失败，将使用默认行为: {e}")

    return influence_registry


async def run_with_cache(
    *,
    config: dict,
    config_path: str,
    cache_dir: str,
    simulator_class: type,
    build_new_simulator: Callable[[dict, str], Awaitable[Any]],
    post_resume: Optional[Callable[[Any], None]] = None,
    after_run: Optional[Callable[[Any], None]] = None,
    cache_backend: Optional[CacheBackend] = None,
    auto_plot_results: bool = True,
) -> Any:
    """固定运行骨架：先尝试从缓存恢复，否则调用 build_new_simulator 构建。"""

    backend: CacheBackend = cache_backend or SimulationCache

    cache_opts = get_cache_options(config, cache_dir)

    population = (config or {}).get("simulation", {}).get("initial_population")
    total_years = (config or {}).get("simulation", {}).get("total_years")

    cache_file = None
    if cache_opts.save_cache:
        cache_file = backend.generate_cache_filename(
            population=population,
            total_years=total_years,
            cache_dir=cache_opts.cache_dir,
            with_timestamp=True,
        )

    simulator = None

    if cache_opts.resume_from_cache:
        result = backend.find_latest_cache(
            population=population,
            target_years=total_years,
            cache_dir=cache_opts.cache_dir,
        )
        found_cache_file = result[0] if result else None
        found_year = result[1] if result else None

        if found_cache_file and os.path.exists(found_cache_file):
            if found_year == total_years:
                response = input(
                    f"发现已有的模拟文件 {found_cache_file}，是否需要重新模拟？(Y/N): "
                )
                if response.upper() != "Y":
                    return None

            elif found_year is not None and found_year < total_years:
                try:
                    simulator_years = total_years - found_year
                    simulator = backend.load_cache(
                        file_path=found_cache_file,
                        simulator_class=simulator_class,
                        simulator_years=simulator_years,
                        config=config,
                    )
                    if simulator is not None and post_resume is not None:
                        post_resume(simulator)
                except Exception:
                    simulator = None

    if simulator is None:
        simulator = await build_new_simulator(config, config_path)

    try:
        await simulator.run()

        # 如果没有自定义 after_run，自动保存结果
        if after_run is None:
            if hasattr(simulator, 'save_results') and callable(simulator.save_results):
                simulator.save_results()
        else:
            after_run(simulator)

        # 自动绘图
        if auto_plot_results:
            plot_config = (config or {}).get('visualization')
            _try_auto_plot(simulator, plot_config=plot_config)
    finally:
        if simulator is not None and cache_opts.save_cache and cache_file:
            try:
                backend.save_cache(simulator, cache_file)
            except Exception:
                pass

    return simulator


def _try_auto_plot(simulator: Any, plot_config: Optional[Dict] = None) -> None:
    """尝试自动根据 simulator.results 或数据目录中的结果文件生成图表。"""
    try:
        # 优先从 simulator.results 直接绘图
        if hasattr(simulator, 'results') and isinstance(simulator.results, dict):
            auto_plot_results(simulator.results, plot_config=plot_config)
            return

        # 否则扫描数据目录
        from src.utils.simulation_context import SimulationContext
        data_dir = SimulationContext.get_data_dir()
        if os.path.exists(data_dir):
            files = [f for f in os.listdir(data_dir) if f.startswith('running_data')]
            csv_files = [f for f in files if f.endswith('.csv')]
            json_files = [f for f in files if f.endswith('.json')]

            if csv_files:
                csv_files.sort(key=lambda f: os.path.getctime(os.path.join(data_dir, f)), reverse=True)
                auto_plot_results(os.path.join(data_dir, csv_files[0]), plot_config=plot_config)
                return

            if json_files:
                json_files.sort(key=lambda f: os.path.getctime(os.path.join(data_dir, f)), reverse=True)
                auto_plot_results(os.path.join(data_dir, json_files[0]), plot_config=plot_config)
    except Exception as e:
        print(f"自动绘图失败: {e}")


# ====================
# 运行期初始化编排（entrypoints 共享）
# ====================


class RuntimeInitError(RuntimeError):
    """运行期初始化编排异常。"""


@dataclass(frozen=True)
class RuntimeInitStep:
    name: str
    requires: Set[str]
    provides: Set[str]
    run: Callable[[MutableMapping[str, Any]], Any]


@dataclass(frozen=True)
class BasicRuntimeInitResult:
    residents: Dict[int, Any]
    towns: Any
    social_network: Any


@dataclass(frozen=True)
class RuntimeModulesState:
        """通用运行期初始化输出。

        说明：
        - 尽量只包含"系统态"与初始化产物，不绑定特定 Simulator。
        - `modules` 中保存所有已加载插件（key 为插件名）。
        - `initialized` 表示已完成"运行期初始化"的模块名集合。
        - 模块对象默认都是 plugin 实例（而非 service），以便调用初始化方法/触发事件；
            业务侧若需要 service，可用 `module.service`。
        """

        plugin_registry: Any
        config: dict

        modules: Dict[str, Any] = field(default_factory=dict)
        initialized: Set[str] = field(default_factory=set)

        map: Any = None
        time: Any = None
        population: Any = None
        towns: Any = None
        social_network: Any = None
        climate: Any = None
        transport_economy: Any = None
        job_market: Any = None
        government: Any = None
        rebellion: Any = None
        residents_plugin: Any = None

        residents: Optional[Dict[int, Any]] = None


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def run_steps(
    *,
    steps: Sequence[RuntimeInitStep],
    initial_state: Optional[MutableMapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    """对 steps 做拓扑排序并执行。"""

    state: MutableMapping[str, Any] = initial_state or {}
    remaining: List[RuntimeInitStep] = list(steps)

    made_progress = True
    while remaining and made_progress:
        made_progress = False
        for idx, step in list(enumerate(remaining)):
            if not step.requires.issubset(state.keys()):
                continue

            result = await _maybe_await(step.run(state))
            if isinstance(result, Mapping):
                state.update(dict(result))

            remaining.pop(idx)
            made_progress = True
            break

    if remaining:
        missing = {req for step in remaining for req in step.requires if req not in state}
        names = ", ".join(step.name for step in remaining)
        raise RuntimeInitError(f"运行期初始化编排失败，剩余步骤无法满足依赖: {names}; 缺失: {sorted(missing)}")

    return state


def _get_cfg(config: dict, path: str, default: Any = None) -> Any:
    cur: Any = config
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _collect_loaded_plugins(plugin_registry: Any) -> Dict[str, Any]:
    """尽量通用地枚举已加载插件。"""

    if plugin_registry is None:
        return {}

    get_all_loaded = getattr(plugin_registry, "get_all_loaded", None)
    if callable(get_all_loaded):
        try:
            loaded = get_all_loaded()
            return dict(loaded) if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    return {}


def _get_module_dependencies(
    *,
    module_name: str,
    plugin_registry: Any,
) -> List[str]:
    """获取模块依赖：优先使用 PluginRegistry 的依赖图，否则回退到单插件 metadata。"""

    # 优先从统一依赖图读取（与加载期约束一致）
    graph_getter = getattr(plugin_registry, "get_dependency_graph", None)
    if callable(graph_getter):
        try:
            graph = graph_getter()
            deps = graph.get(module_name, [])
            return [d for d in deps if isinstance(d, str) and d.strip()]
        except Exception:
            pass

    # 回退：直接读取单个插件的 metadata
    md_getter = getattr(plugin_registry, "get_plugin_metadata", None)
    if callable(md_getter):
        try:
            md = md_getter(module_name)
            deps = (md.metadata or {}).get("dependencies", []) if md is not None else []
            if isinstance(deps, list):
                return [d for d in deps if isinstance(d, str) and d.strip()]
        except Exception:
            pass
    return []


def _iter_auto_init_methods(plugin: Any) -> List[Tuple[str, Callable[..., Any]]]:
    """枚举插件的"可自动初始化"的方法。

    约定：
    - 方法名为 initialize 或 initialize_* 会被认为是运行期初始化步骤。
    - 只收集在插件类**本身**定义的方法，排除从业务基类（如 Map/Towns/ClimateSystem）
      继承来的方法，避免运行期重复/错误调用。
    - residents 插件的 ensure_initialized 由 orchestrator 统一特殊处理。
    """

    methods: List[Tuple[str, Callable[..., Any]]] = []
    plugin_cls = plugin.__class__
    for method_name, member in inspect.getmembers(plugin, predicate=callable):
        if method_name == "initialize" or method_name.startswith("initialize_"):
            if method_name not in plugin_cls.__dict__:
                continue
            # 排除从基类继承并重写的方法（如 Map/Towns/SocialNetwork 的 initialize_*）
            if any(
                method_name in base.__dict__
                for base in plugin_cls.__mro__[1:]
                if base is not object
            ):
                continue
            methods.append((method_name, member))
    return methods


async def orchestrate_basic_runtime_init(
    *,
    plugin_registry: Any,
    config: dict,
    residents_kwargs: Optional[Dict[str, Any]] = None,
) -> BasicRuntimeInitResult:
    """默认模拟/多数 entrypoint 共享的运行期初始化编排。"""

    residents_kwargs = dict(residents_kwargs or {})

    runtime_state = await orchestrate_runtime_modules_init(
        plugin_registry=plugin_registry,
        config=config,
        residents_kwargs=residents_kwargs,
    )

    return BasicRuntimeInitResult(
        residents=runtime_state.residents or {},
        towns=runtime_state.towns,
        social_network=runtime_state.social_network,
    )


async def orchestrate_runtime_modules_init(
    *,
    plugin_registry: Any,
    config: dict,
    residents_kwargs: Optional[Dict[str, Any]] = None,
) -> RuntimeModulesState:
    """通用运行期初始化编排：依赖驱动 + 方法签名驱动。

    目标：减少 entrypoint_runner 对"具体模块名/固定顺序"的硬编码。

    自动规则：
    - 自动枚举 plugin_registry 中已加载插件。
    - 每个插件：
      - 依赖来自插件自身 metadata.dependencies（由 plugins/*/plugin.yaml 提供）。
      - 自动执行其 `initialize` / `initialize_*` 方法（按依赖与参数签名排序）。
      - residents 插件：若存在 `ensure_initialized`，则用 config+residents_kwargs 拼装参数并执行，产出 `residents`。

    依赖与排序：
    - 编排器将每个模块的"就绪"标记为 `initialized:<module>`。
    - 若某个模块依赖另一个模块（dependencies 中声明），则其初始化会等待依赖模块 `initialized`。
    - 若某个 initialize_* 的签名参数与其他模块同名（如 map/towns/social_network），也会等待该模块 initialized。

    扩展方式（新增模块示例）：
    - 在 plugins/<插件>/plugin.yaml 的 dependencies 中声明依赖（例如 ["map"]）。
    - 在插件类里提供 `initialize_xxx(map, ...)` 或 `initialize_xxx(map_service, ...)`（后者会自动传入依赖模块的 service）。
    """

    residents_kwargs = dict(residents_kwargs or {})

    modules = _collect_loaded_plugins(plugin_registry)
    loaded_names: Set[str] = set(modules.keys())

    # 初始状态：包含 plugin_registry/config，以及每个模块实例。
    initial_state: MutableMapping[str, Any] = {
        "plugin_registry": plugin_registry,
        "config": config,
    }
    for name, plugin in modules.items():
        if name == "residents":
            initial_state["residents_plugin"] = plugin
        else:
            initial_state[name] = plugin

    steps: List[RuntimeInitStep] = []

    init_done_tokens_by_module: Dict[str, List[str]] = {}

    # --- 1) residents.ensure_initialized（若存在）---
    if "residents" in modules:
        residents_plugin = initial_state.get("residents_plugin")
        ensure_fn = getattr(residents_plugin, "ensure_initialized", None)
        if callable(ensure_fn):
            deps = _get_module_dependencies(
                module_name="residents",
                plugin_registry=plugin_registry,
            )

            done_token = "init_done:residents.ensure_initialized"
            init_done_tokens_by_module.setdefault("residents", []).append(done_token)

            async def _run_residents_init(
                state: MutableMapping[str, Any],
                _ensure_fn: Callable[..., Any] = ensure_fn,
                _residents_kwargs: Dict[str, Any] = residents_kwargs,
                _done_token: str = done_token,
            ) -> Dict[str, Any]:
                # 保持旧行为：从 config 读取 resident_* 路径与 initial_population。
                if state.get("map") is None:
                    raise RuntimeInitError("residents 模块存在，但 map 模块缺失，无法初始化 residents")

                sim_cfg = _get_cfg(state["config"], "simulation", {}) or {}
                data_cfg = _get_cfg(state["config"], "data", {}) or {}

                kwargs = {
                    "initial_population": sim_cfg.get("initial_population"),
                    "resident_info_path": data_cfg.get("resident_info_path"),
                    "config_dir": os.path.dirname(data_cfg.get("agent_profile_path") or ""),
                    "agent_profile_path": data_cfg.get("agent_profile_path"),
                }
                kwargs.update({k: v for k, v in (_residents_kwargs or {}).items() if v is not None})

                residents_value = await _maybe_await(_ensure_fn(**kwargs))
                return {
                    "residents": residents_value,
                    _done_token: True,
                }

            requires: Set[str] = {"config"}
            requires.update({f"initialized:{d}" for d in deps if isinstance(d, str) and d.strip()})
            # 若 residents 依赖 map，通常希望 map 先完成 initialize_map（而非仅实例存在）
            if "map" in loaded_names:
                requires.add("initialized:map")

            steps.append(
                RuntimeInitStep(
                    name="auto_init:residents.ensure_initialized",
                    requires=requires,
                    provides={"residents", done_token},
                    run=_run_residents_init,
                )
            )

    # --- 2) 通用 initialize / initialize_* 自动初始化 ---
    for module_name, plugin in modules.items():
        if module_name == "residents":
            # residents 的初始化由 ensure_initialized 驱动；这里避免重复。
            continue

        deps = _get_module_dependencies(
            module_name=module_name,
            plugin_registry=plugin_registry,
        )

        for method_name, method in _iter_auto_init_methods(plugin):
            try:
                sig = inspect.signature(method)
            except Exception:
                continue

            param_names: List[str] = []
            for p in sig.parameters.values():
                if p.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    param_names.append(p.name)

            done_token = f"init_done:{module_name}.{method_name}"
            init_done_tokens_by_module.setdefault(module_name, []).append(done_token)

            requires: Set[str] = set()
            requires.update({f"initialized:{d}" for d in deps if isinstance(d, str) and d.strip()})

            # 若签名里出现模块名参数，则默认按 "initialized:<name>" 约束排序。
            for p in param_names:
                if p in {"config", "plugin_registry"}:
                    requires.add(p)
                    continue

                # 若参数名与已加载模块同名：认为它依赖对方模块已 initialized
                if p in loaded_names:
                    requires.add(f"initialized:{p}")
                else:
                    requires.add(p)

            async def _run_auto_init_method(
                state: MutableMapping[str, Any],
                _method: Callable[..., Any] = method,
                _param_names: Tuple[str, ...] = tuple(param_names),
                _done_token: str = done_token,
            ) -> Dict[str, Any]:
                kwargs: Dict[str, Any] = {}
                for p in _param_names:
                    if p == "config":
                        kwargs[p] = state.get("config")
                        continue
                    if p == "plugin_registry":
                        kwargs[p] = state.get("plugin_registry")
                        continue

                    if p in state:
                        kwargs[p] = state[p]
                        continue

                    # 支持 <module>_service 取依赖模块的 service
                    if p.endswith("_service"):
                        base = p[: -len("_service")]
                        base_obj = state.get(base)
                        if base_obj is not None and getattr(base_obj, "service", None) is not None:
                            kwargs[p] = getattr(base_obj, "service")
                            continue

                    raise RuntimeInitError(f"自动初始化参数无法满足: {_method.__qualname__} 缺少参数 '{p}'")

                await _maybe_await(_method(**kwargs))
                return {_done_token: True}

            steps.append(
                RuntimeInitStep(
                    name=f"auto_init:{module_name}.{method_name}",
                    requires=requires,
                    provides={done_token},
                    run=_run_auto_init_method,
                )
            )

    # --- 3) 每个模块的 initialized 标记（依赖驱动）---
    for module_name in modules.keys():
        deps = _get_module_dependencies(
            module_name=module_name,
            plugin_registry=plugin_registry,
        )

        requires: Set[str] = set()
        requires.update({f"initialized:{d}" for d in deps if isinstance(d, str) and d.strip()})
        requires.update(set(init_done_tokens_by_module.get(module_name, []) or []))

        init_token = f"initialized:{module_name}"

        def _mark_initialized(state: MutableMapping[str, Any], _k: str = init_token) -> Dict[str, Any]:
            return {_k: True}

        steps.append(
            RuntimeInitStep(
                name=f"mark_initialized:{module_name}",
                requires=requires,
                provides={init_token},
                run=_mark_initialized,
            )
        )

    # --- 4) 系统级轻量 wiring（保持旧行为，且不强依赖）---
    # 将 towns 的 resident_group 绑定 social_network（若两者都存在）
    if "towns" in modules and "social_network" in modules:
        def _wire_groups_social_network(state: MutableMapping[str, Any]) -> Dict[str, Any]:
            towns_obj = state.get("towns")
            social_network_obj = state.get("social_network")
            if towns_obj is None or social_network_obj is None:
                return {}

            towns_dict = getattr(towns_obj, "towns", None)
            if isinstance(towns_dict, dict):
                for _, town_data in towns_dict.items():
                    try:
                        resident_group = town_data.get("resident_group") if isinstance(town_data, dict) else None
                        if resident_group:
                            resident_group.set_social_network(social_network_obj)
                    except Exception:
                        continue

            return {"wired:towns.social_network": True}

        steps.append(
            RuntimeInitStep(
                name="wire:towns.social_network",
                requires={"initialized:towns", "initialized:social_network"},
                provides={"wired:towns.social_network"},
                run=_wire_groups_social_network,
            )
        )

    state = await run_steps(
        steps=steps,
        initial_state=initial_state,
    )

    initialized_modules: Set[str] = set()
    for name in modules.keys():
        if state.get(f"initialized:{name}"):
            initialized_modules.add(name)

    return RuntimeModulesState(
        plugin_registry=plugin_registry,
        config=config,
        modules=dict(modules),
        initialized=initialized_modules,
        map=modules.get("map"),
        time=modules.get("time"),
        population=modules.get("population"),
        towns=modules.get("towns"),
        social_network=modules.get("social_network"),
        climate=modules.get("climate"),
        transport_economy=modules.get("transport_economy"),
        job_market=modules.get("job_market"),
        government=modules.get("government"),
        rebellion=modules.get("rebellion"),
        residents_plugin=modules.get("residents"),
        residents=state.get("residents"),
    )


# ==================== 通用 DI 构建器（动态模块初始化） ====================

async def build_simulator_via_di(
    *,
    config: dict,
    config_path: str,
    simulator_class: type,
    residents_kwargs: Optional[Dict[str, Any]] = None,
    enable_government: bool = False,
    enable_rebellion: bool = False,
    logger: Optional[logging.Logger] = None,
) -> Any:
    """通用模拟器 DI 构建器（动态模块初始化）。
    根据 modules_config.yaml 的 selected_modules 自动初始化，便于后续扩展。
    """
    from src.influences import InfluenceManager
    from src.plugins.bootstrap import initialize_plugin_system
    from src.utils.di_helpers import setup_container_for_simulation

    runner_logger = logger or logging.getLogger("entrypoint_runner")

    config_dir = os.path.dirname(config_path)
    modules_config_path = os.path.join(config_dir, "modules_config.yaml")

    runner_logger.info("正在初始化影响函数系统...")
    influence_registry = load_influence_registry_from_dir(config_dir, logger=logging.getLogger("influences"))
    container = setup_container_for_simulation(influence_registry=influence_registry)

    runner_logger.info("正在初始化插件系统...")
    plugin_registry = initialize_plugin_system(
        config=config,
        modules_config_path=modules_config_path,
        container=container,
        logger=logging.getLogger("plugin_system"),
    )

    runner_logger.info("正在编排运行期模块初始化...")
    runtime_state = await orchestrate_runtime_modules_init(
        plugin_registry=plugin_registry,
        config=config,
        residents_kwargs=residents_kwargs,
    )

    # 采集通用初始化结果
    simulator_kwargs = {
        "plugin_registry": plugin_registry,
        "residents": runtime_state.residents or {},
        "config": config,
    }

    # 社交网络可视化（如存在）
    social_network = runtime_state.social_network
    if social_network:
        try:
            social_network.visualize()
        except Exception as e:
            runner_logger.warning(f"社交网络可视化失败：{e}")
        try:
            social_network.plot_degree_distribution()
        except Exception as e:
            runner_logger.warning(f"社交网络节点度分布可视化失败：{e}")

    # 动态初始化 government 模块（如启用且已加载）
    if enable_government and "government" in runtime_state.modules:
        runner_logger.info("正在初始化 government 模块...")
        from src.agents.agent_group import AgentGroup
        import src.agents.government as government_agents

        government_plugin = require_module(runtime_state.plugin_registry, "government")
        government_obj = getattr(government_plugin, "service", None) or government_plugin

        government_info_path = (config.get("data") or {}).get("government_info_path")
        government_officials, _, _ = await AgentGroup.generate_agents_from_info_json(
            government_info_path,
            group_obj=government_obj,
            rank_factories={
                "普通官员": lambda agent_id, gov, pool: government_agents.OrdinaryGovernmentAgent(
                    agent_id=agent_id, government=gov, shared_pool=pool
                ),
                "高级官员": lambda agent_id, gov, pool: government_agents.HighRankingGovernmentAgent(
                    agent_id=agent_id, government=gov, shared_pool=pool
                ),
            },
            shared_pool_factory=government_agents.government_SharedInformationPool,
            init_agent=lambda official, data: (
                setattr(official, "personality", data["personality"]),
                setattr(official, "function", data["function"]) if data.get("rank") == "普通官员" else None,
                setattr(official, "faction", data["faction"]) if data.get("rank") == "普通官员" else None,
            ),
            add_info_officer=lambda agent_id, gov, pool: government_agents.InformationOfficer(
                agent_id=agent_id, government=gov, shared_pool=pool
            ),
            validate_types=(
                government_agents.OrdinaryGovernmentAgent,
                government_agents.HighRankingGovernmentAgent,
                government_agents.InformationOfficer,
            ),
        )
        simulator_kwargs["government_officials"] = government_officials

    # 动态初始化 rebellion 模块（如启用且已加载）
    if enable_rebellion and "rebellion" in runtime_state.modules:
        runner_logger.info("正在初始化 rebellion 模块...")
        from src.agents.agent_group import AgentGroup
        import src.agents.rebels as rebels_agents_module

        rebellion_plugin = require_module(runtime_state.plugin_registry, "rebellion")
        rebellion_obj = getattr(rebellion_plugin, "service", None) or rebellion_plugin

        rebellion_info_path = (config.get("data") or {}).get("rebellion_info_path")
        rebels_agents, _, _ = await AgentGroup.generate_agents_from_info_json(
            rebellion_info_path,
            group_obj=rebellion_obj,
            rank_factories={
                "普通叛军": lambda agent_id, reb, pool: rebels_agents_module.OrdinaryRebel(
                    agent_id=agent_id, rebellion=reb, shared_pool=pool
                ),
                "叛军头子": lambda agent_id, reb, pool: rebels_agents_module.RebelLeader(
                    agent_id=agent_id, rebellion=reb, shared_pool=pool
                ),
            },
            shared_pool_factory=rebels_agents_module.RebelsSharedInformationPool,
            init_agent=lambda rebel, data: (
                setattr(rebel, "personality", data["personality"]),
                setattr(rebel, "role", data["role"]) if data.get("rank") == "普通叛军" else None,
            ),
            add_info_officer=lambda agent_id, reb, pool: rebels_agents_module.InformationOfficer(
                agent_id=agent_id, rebellion=reb, shared_pool=pool
            ),
            validate_types=(
                rebels_agents_module.OrdinaryRebel,
                rebels_agents_module.RebelLeader,
                rebels_agents_module.InformationOfficer,
            ),
        )
        simulator_kwargs["rebels_agents"] = rebels_agents

    # 创建影响管理器
    influence_manager = InfluenceManager(logger=logging.getLogger("influences"))
    simulator_kwargs["influence_manager"] = influence_manager

    runner_logger.info(f"正在构建 {simulator_class.__name__} 实例...")
    simulator = simulator_class(**simulator_kwargs)

    return simulator


# ==================== 向后兼容包装函数（保留以支持旧入口） ====================

async def build_default_simulator_via_di(
    *,
    config: dict,
    config_path: str,
    simulator_class: type,
    residents_kwargs: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> Any:
    """默认(default)模拟的"全接管"构建器。

    目标：让 entrypoints 只保留 run_with_cache + after_run。
    - InfluenceRegistry/DIContainer/PluginSystem 初始化
    - 运行期模块编排（map/residents/towns/social_network）
    - government/rebellion 动态初始值 + agent 生成
    - InfluenceManager + Simulator 构建
    """

    return await build_simulator_via_di(
        config=config,
        config_path=config_path,
        simulator_class=simulator_class,
        residents_kwargs=residents_kwargs,
        enable_government=True,
        enable_rebellion=True,
        logger=logger,
    )


async def build_teog_simulator_via_di(
    *,
    config: dict,
    config_path: str,
    simulator_class: type,
    residents_kwargs: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> Any:
    """TEOG 入口包装函数：调用通用构建器，启用政府官员生成。"""

    return await build_simulator_via_di(
        config=config,
        config_path=config_path,
        simulator_class=simulator_class,
        residents_kwargs=residents_kwargs,
        enable_government=True,
        enable_rebellion=False,
        logger=logger,
    )


async def build_info_propagation_simulator_via_di(
    *,
    config: dict,
    config_path: str,
    simulator_class: type,
    residents_kwargs: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> Any:
    """信息传播入口包装函数：调用通用构建器，仅初始化 residents。"""

    return await build_simulator_via_di(
        config=config,
        config_path=config_path,
        simulator_class=simulator_class,
        residents_kwargs=residents_kwargs,
        enable_government=False,
        enable_rebellion=False,
        logger=logger,
    )
