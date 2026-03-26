"""测试 PluginRegistry 在注册阶段的 metadata 提取策略。

目标：
- 构造函数可无参调用的插件：允许沿用旧逻辑自动提取 get_metadata。
- 构造函数存在必填参数（依赖 DI）的插件：注册阶段不应强行无参实例化，需安全回退。
"""

import os
import sys

# 添加项目路径（与仓库现有测试保持一致）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins import BasePlugin, PluginContext, PluginRegistry


class NoArgPlugin(BasePlugin):
    def init(self, context: PluginContext) -> None:
        self._context = context

    def on_load(self) -> None:
        self._mark_loaded()

    def on_unload(self) -> None:
        self._mark_unloaded()

    def get_metadata(self):
        return {
            "name": "NoArg",
            "version": "9.9.9",
            "description": "no-arg plugin",
            "author": "test",
            "dependencies": [],
        }


class RequiredArgPlugin(BasePlugin):
    def __init__(self, required_dep):
        super().__init__()
        self.required_dep = required_dep

    def init(self, context: PluginContext) -> None:
        self._context = context

    def on_load(self) -> None:
        self._mark_loaded()

    def on_unload(self) -> None:
        self._mark_unloaded()

    def get_metadata(self):
        return {
            "name": "RequiredArg",
            "version": "1.2.3",
            "description": "requires dependency in __init__",
            "author": "test",
            "dependencies": ["dep"],
        }


def test_register_auto_extract_metadata_when_noarg_ctor():
    registry = PluginRegistry(logger=None)
    registry.register(NoArgPlugin, name="noarg")
    meta = registry.get_plugin_metadata("noarg")
    assert meta is not None
    assert meta.metadata.get("version") == "9.9.9"


def test_register_skips_auto_extract_when_ctor_requires_args():
    registry = PluginRegistry(logger=None)

    # metadata=None 时，register 不能因 __init__ 缺参而抛异常
    registry.register(RequiredArgPlugin, name="required")
    meta = registry.get_plugin_metadata("required")
    assert meta is not None

    # 因为无法无参实例化提取 get_metadata，这里应回退为 unknown
    assert meta.metadata.get("version") == "unknown"
