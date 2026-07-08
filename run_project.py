"""run_project.py

统一项目启动器。

用法:
    python run_project.py --project cross_border_production_simulation
    python run_project.py --project TEOG  # 兼容旧项目 fallback
    python run_project.py --project cross_border_production_simulation \
                          --config_path projects/cross_border_production_simulation/config/simulation_config.yaml

说明:
- 如果 projects/<name>/ 存在，按新项目结构加载 projects/<name>/simulator.py。
- 否则回退到旧结构：config/<name>/ + src/simulation/simulator_<name>.py。
- 项目可选的 projects/<name>/main.py 中的 hook（build_new_simulator / post_resume / after_run）会被加载。
- 实验输出（history / cache）自动隔离到项目目录下。
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


def _setup_sys_path(repo_root: str, project_name: str, project_dir: Optional[str] = None) -> None:
    """确保仓库根目录、projects/ 以及项目目录在 sys.path 中。"""
    paths_to_add = [repo_root, os.path.join(repo_root, "projects")]
    if project_dir:
        paths_to_add.append(project_dir)
    for path in paths_to_add:
        abs_path = os.path.abspath(path)
        if abs_path not in sys.path:
            sys.path.insert(0, abs_path)


def _load_module_from_path(module_path: str, module_name: str) -> Any:
    """通过文件路径动态加载模块，避免不同项目间的模块名冲突。"""
    module_path = os.path.abspath(module_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从 {module_path} 创建模块 spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_simulator_class(module: Any) -> type:
    """在模块中查找 Simulator 类（优先类名以 Simulator 结尾且非 BaseSimulator）。"""
    candidates = [
        cls
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if cls.__module__ == module.__name__
        and cls.__name__.endswith("Simulator")
        and cls.__name__ != "BaseSimulator"
    ]
    if candidates:
        return candidates[0]

    all_classes = [
        cls
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if cls.__module__ == module.__name__
    ]
    if all_classes:
        return all_classes[0]

    raise ValueError(f"在 {getattr(module, '__file__', module)} 中未找到 Simulator 类")


def _load_optional_main_py(project_dir: str, project_name: str) -> Optional[Any]:
    """加载项目可选的 main.py（用于自定义 hook），不存在则返回 None。"""
    main_path = os.path.join(project_dir, "main.py")
    if not os.path.exists(main_path):
        return None
    module_name = f"project_main_{project_name}"
    return _load_module_from_path(main_path, module_name)


def _pick_hook(module: Optional[Any], name: str) -> Optional[Callable[..., Any]]:
    """从 main.py 模块中提取指定 hook。"""
    if module is None:
        return None
    fn = getattr(module, name, None)
    return fn if callable(fn) else None


def _read_modules_config(config_dir: str) -> dict:
    """读取 modules_config.yaml，失败返回空字典。"""
    path = os.path.join(config_dir, "modules_config.yaml")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logging.getLogger("run_project").warning(f"读取 modules_config.yaml 失败: {exc}")
        return {}


def _infer_enable_flags(modules_config: dict, is_legacy: bool) -> tuple[bool, bool]:
    """根据 selected_modules 推断是否启用 government / rebellion。

    新项目：严格按 selected_modules 推断。
    旧项目 fallback：若未找到 modules_config.yaml，保持旧行为（双开），
    以兼容 default/TEOG/info_propagation 等老入口。
    """
    selected = modules_config.get("selected_modules")
    if isinstance(selected, list):
        names = {str(n).strip() for n in selected if isinstance(n, str)}
        return "government" in names, "rebellion" in names
    if is_legacy:
        return True, True
    return False, False


def _resolve_project_paths(args: argparse.Namespace, repo_root: str) -> dict:
    """根据命令行参数和仓库结构解析项目路径。"""
    project_name = args.project
    project_dir = os.path.join(repo_root, "projects", project_name)

    is_new_project = os.path.isdir(project_dir)

    if is_new_project:
        config_dir = os.path.join(project_dir, "config")
        simulator_path = os.path.join(project_dir, "simulator.py")
        config_path = args.config_path or os.path.join(config_dir, "simulation_config.yaml")
        cache_dir = os.path.join(project_dir, "backups")
        history_dir = os.path.join(project_dir, "history")
    else:
        # 旧项目 fallback
        config_dir = os.path.join(repo_root, "config", project_name)
        simulator_path = os.path.join(repo_root, "src", "simulation", f"simulator_{project_name}.py")
        config_path = args.config_path or os.path.join(config_dir, "simulation_config.yaml")
        cache_dir = os.path.join(repo_root, "backups")
        history_dir = None

    return {
        "project_name": project_name,
        "project_dir": project_dir if is_new_project else None,
        "config_dir": config_dir,
        "simulator_path": simulator_path,
        "config_path": config_path,
        "cache_dir": cache_dir,
        "history_dir": history_dir,
        "is_new_project": is_new_project,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Eco3S 统一项目启动器")
    parser.add_argument("--project", type=str, required=True, help="项目名称")
    parser.add_argument("--config_path", type=str, default=None, help="手动指定 simulation_config.yaml 路径")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    paths = _resolve_project_paths(args, repo_root)

    project_name = paths["project_name"]
    project_dir = paths["project_dir"]
    config_dir = paths["config_dir"]
    simulator_path = paths["simulator_path"]
    config_path = paths["config_path"]
    cache_dir = paths["cache_dir"]
    history_dir = paths["history_dir"]
    is_new_project = paths["is_new_project"]

    if not os.path.exists(simulator_path):
        raise FileNotFoundError(f"未找到 simulator 文件: {simulator_path}")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"未找到配置文件: {config_path}")

    # 调整 sys.path，让 src/、projects/、项目目录均可被导入
    _setup_sys_path(repo_root, project_name, project_dir)

    # 加载 simulation_config.yaml
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 动态加载 simulator 模块
    if is_new_project:
        # 新项目使用绝对导入，直接用 'simulator' 作为模块名，
        # 便于同目录下的 main.py 通过 `import simulator` 复用同一模块对象。
        simulator_module_name = "simulator"
    else:
        # 旧项目 simulator 使用相对导入，需要伪装成 src.simulation 包下的模块
        simulator_module_name = f"src.simulation.runner_simulator_{project_name}"
    simulator_module = _load_module_from_path(simulator_path, simulator_module_name)
    simulator_class = _find_simulator_class(simulator_module)

    # 加载可选的 main.py hook
    main_module = _load_optional_main_py(project_dir, project_name) if is_new_project else None
    build_new_simulator_hook = _pick_hook(main_module, "build_new_simulator")
    post_resume_hook = _pick_hook(main_module, "post_resume")
    after_run_hook = _pick_hook(main_module, "after_run")

    # 设置 SimulationContext
    from src.utils.simulation_context import SimulationContext

    SimulationContext.set_simulation_type(project_name)
    sim_cfg = config.get("simulation", {}) or {}
    SimulationContext.set_simulation_name(
        sim_cfg.get("simulation_name"),
        population=sim_cfg.get("initial_population"),
        total_years=sim_cfg.get("total_years"),
    )
    if history_dir:
        os.makedirs(history_dir, exist_ok=True)
        SimulationContext.set_base_history_dir(history_dir)

    # 推断 enable_government / enable_rebellion
    modules_config = _read_modules_config(config_dir)
    enable_government, enable_rebellion = _infer_enable_flags(modules_config, not is_new_project)

    from src.utils.entrypoint_runner import build_simulator_via_di, run_with_cache

    # 默认 build_new_simulator
    async def _build_new_simulator(cfg: dict, cfg_path: str) -> Any:
        residents_kwargs = {
            "initial_population": (cfg.get("simulation") or {}).get("initial_population", 1000),
            "resident_info_path": ((cfg.get("data") or {}).get("resident_info_path", "")),
            "resident_prompt_path": ((cfg.get("data") or {}).get("resident_prompt_path", "")),
            "resident_actions_path": ((cfg.get("data") or {}).get("resident_actions_path", "")),
            "window_size": 10,
        }
        return await build_simulator_via_di(
            config=cfg,
            config_path=cfg_path,
            simulator_class=simulator_class,
            residents_kwargs=residents_kwargs,
            enable_government=enable_government,
            enable_rebellion=enable_rebellion,
            logger=logging.getLogger("entrypoint_runner"),
        )

    # 如果 main.py 提供了 build_new_simulator，优先使用它
    build_new_simulator: Callable[[dict, str], Any] = _build_new_simulator
    if build_new_simulator_hook is not None:
        sig = inspect.signature(build_new_simulator_hook)
        if "simulator_class" in sig.parameters:
            build_new_simulator = lambda cfg, cfg_path: build_new_simulator_hook(  # type: ignore[assignment]
                cfg, cfg_path, simulator_class=simulator_class
            )
        else:
            build_new_simulator = build_new_simulator_hook  # type: ignore[assignment]

    print(f"开始运行模拟: {project_name}")
    print(f"  config_path: {config_path}")
    print(f"  simulator:   {simulator_path}")
    print(f"  cache_dir:   {cache_dir}")
    if history_dir:
        print(f"  history_dir: {history_dir}")

    os.makedirs(cache_dir, exist_ok=True)

    await run_with_cache(
        config=config,
        config_path=config_path,
        cache_dir=cache_dir,
        simulator_class=simulator_class,
        build_new_simulator=build_new_simulator,
        post_resume=post_resume_hook,
        after_run=after_run_hook,
    )


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    asyncio.run(main())
