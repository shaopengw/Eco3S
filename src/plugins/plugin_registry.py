"""插件注册表 (PluginRegistry)

实现插件的注册、发现、加载和查询功能。

约定（极简模式）：
- 插件只从仓库根目录 `plugins/*/plugin.yaml` 发现与注册。
"""

import os
import sys
import yaml
import importlib
import inspect
from typing import Dict, List, Type, Optional, Any, Set
from pathlib import Path
import logging

from .base_plugin import BasePlugin
from .plugin_context import PluginContext


class PluginMetadata:
    """
    插件元数据类
    
    存储插件的详细信息，包括类引用、元数据和加载状态。
    """
    
    def __init__(
        self,
        name: str,
        plugin_class: Type[BasePlugin],
        metadata: Dict[str, Any],
        source: str = "unknown"
    ):
        """
        初始化插件元数据
        
        Args:
            name: 插件名称
            plugin_class: 插件类
            metadata: 插件元数据字典
            source: 插件来源（config/scan/manual）
        """
        self.name = name
        self.plugin_class = plugin_class
        self.metadata = metadata
        self.source = source
        self.instance: Optional[BasePlugin] = None
        self.loaded = False
    
    def __repr__(self) -> str:
        return f"PluginMetadata(name={self.name}, version={self.metadata.get('version', 'unknown')}, loaded={self.loaded})"


class PluginRegistry:
    """
    插件注册表
    
    提供插件的管理功能：
    - 注册插件类和元数据
    - 从 plugins/*/plugin.yaml 发现插件
    - 加载插件实例
    - 按接口类型查询插件
    
    Example:
        ```python
        registry = PluginRegistry(logger=LogManager.get_logger('registry'))
        
        # 发现插件
        registry.discover(['plugins/custom', 'plugins/community'])
        
        # 加载插件
        context = PluginContext(config={}, logger=logger)
        plugin = registry.load_plugin('my_plugin', context, width=100, height=100)
        
        # 查询插件
        all_plugins = registry.get_all()
        map_plugins = registry.get_plugins_by_interface('IMapPlugin')
        ```
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化插件注册表
        
        Args:
            logger: 日志记录器
        """
        self._plugins: Dict[str, PluginMetadata] = {}  # 已注册的插件
        self._logger = logger
        self._discovered_paths: Set[str] = set()  # 已扫描的路径
        # modules_config.yaml 中的 selected_modules: {module_name: plugin_name}
        # 允许主引擎通过模块名查询插件实例：registry.get_plugin('map')
        self._module_bindings: Dict[str, str] = {}

    def bind_modules(self, selected_modules: Dict[str, str]) -> None:
        """绑定模块名到插件名。

        Args:
            selected_modules: 形如 {"map": "map", "time": "time"}
        """
        if not isinstance(selected_modules, dict):
            return
        bindings: Dict[str, str] = {}
        for module_name, plugin_name in selected_modules.items():
            if not isinstance(module_name, str) or not module_name.strip():
                continue
            if not isinstance(plugin_name, str) or not plugin_name.strip():
                continue
            bindings[module_name.strip()] = plugin_name.strip()
        self._module_bindings = bindings
    
    # ========================================
    # 核心注册方法
    # ========================================
    
    def register(
        self,
        plugin_class: Type[BasePlugin],
        metadata: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        source: str = "manual"
    ) -> str:
        """
        注册插件类
        
        Args:
            plugin_class: 插件类（必须继承 BasePlugin）
            metadata: 插件元数据（如果为 None，将尝试从类中获取）
            name: 插件名称（如果为 None，使用类名）
            source: 插件来源标识
            
        Returns:
            str: 插件名称
            
        Raises:
            ValueError: 如果插件类无效或名称冲突
            
        Example:
            ```python
            registry.register(CustomMapPlugin, {
                "name": "CustomMap",
                "version": "1.0.0",
                "description": "Custom map plugin"
            })
            ```
        """
        # 验证插件类
        if not inspect.isclass(plugin_class):
            raise ValueError(f"Expected a class, got {type(plugin_class)}")
        
        if not issubclass(plugin_class, BasePlugin):
            raise ValueError(
                f"Plugin class {plugin_class.__name__} must inherit from BasePlugin"
            )
        
        # 确定插件名称
        if name is None:
            name = plugin_class.__name__
        
        # 检查名称冲突
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' is already registered")
        
        # 获取元数据
        if metadata is None:
            # 仅当构造函数可无参调用时，才尝试实例化提取 metadata。
            # 发现/注册阶段通常没有 DI 容器或其他依赖可用；强行实例化会导致缺参告警。
            def _can_instantiate_without_args(cls: Type[Any]) -> bool:
                try:
                    sig = inspect.signature(cls.__init__)
                except Exception:
                    return False

                params = list(sig.parameters.values())
                # 跳过 self
                if params and params[0].name == 'self':
                    params = params[1:]
                for p in params:
                    if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                        continue
                    if p.default is inspect._empty:
                        return False
                return True

            if _can_instantiate_without_args(plugin_class):
                try:
                    temp_instance = plugin_class()
                    temp_instance.init(PluginContext())
                    metadata = temp_instance.get_metadata()
                except Exception as e:
                    self._log_warning(
                        f"Failed to auto-extract metadata from {plugin_class.__name__}: {e}"
                    )

            if metadata is None:
                # 无法自动提取：使用最小元数据占位，避免在注册阶段产生噪音告警。
                self._log_debug(
                    f"Skip auto-extract metadata for {plugin_class.__name__}: constructor requires arguments"
                )
                metadata = {
                    "name": name,
                    "version": "unknown",
                    "description": f"Auto-registered plugin {name}",
                    "author": "unknown",
                    "dependencies": []
                }
        
        # 创建元数据对象
        plugin_metadata = PluginMetadata(
            name=name,
            plugin_class=plugin_class,
            metadata=metadata,
            source=source
        )
        
        # 注册
        self._plugins[name] = plugin_metadata
        self._log_info(f"Registered plugin: {name} (source: {source})")
        
        return name
    
    # ========================================
    # 插件发现方法
    # ========================================
    
    def discover(self, paths: Optional[List[str]] = None) -> int:
        """
        发现插件（仅目录扫描 plugin.yaml）
        
        Args:
            paths: 要扫描的目录路径列表（如果为 None，使用默认路径）
            
        Returns:
            int: 发现的插件数量
            
        Note:
            - 仅扫描指定目录下的子目录 plugin.yaml
            - 默认扫描路径: ['plugins/']
            
        Example:
            ```python
            # 使用默认路径
            count = registry.discover()
            
            # 指定自定义路径
            count = registry.discover(['plugins/custom', 'plugins/community'])
            ```
        """
        discovered_count = 0

        # 从目录扫描发现
        if paths is None:
            paths = ['plugins/']
        
        for path in paths:
            scan_count = self._discover_from_directory(path)
            discovered_count += scan_count
        
        self._log_info(f"Discovery completed: {discovered_count} plugins found")
        return discovered_count
    
    def _discover_from_directory(self, directory: str) -> int:
        """
        从目录扫描发现插件
        
        发现方式：
        - plugin.yaml：查找子目录中的 plugin.yaml 元数据文件
        
        Args:
            directory: 要扫描的目录路径
            
        Returns:
            int: 发现的插件数量
            
        目录结构示例:
            ```
            plugins/
            ├── map/
            │   ├── plugin.yaml            # 插件元数据（方式1）
            │   ├── map_plugin.py          # 插件实现
            │   └── __init__.py
            ├── custom_plugin/
            │   └── plugin.py              # 直接扫描（方式2）
            ```
        """
        if not os.path.exists(directory):
            self._log_debug(f"Directory not found: {directory}")
            return 0
        
        # 避免重复扫描
        abs_path = os.path.abspath(directory)
        if abs_path in self._discovered_paths:
            return 0
        self._discovered_paths.add(abs_path)
        
        count = 0
        path_obj = Path(directory)
        
        # 将目录添加到 sys.path
        parent_path = str(path_obj.parent.absolute())
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        
        try:
            for subdir in path_obj.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    yaml_file = subdir / 'plugin.yaml'
                    if yaml_file.exists():
                        yaml_count = self._discover_from_plugin_yaml(yaml_file, subdir)
                        count += yaml_count

            self._log_info(f"Discovered {count} plugins from directory: {directory}")
            return count

        except Exception as e:
            self._log_error(f"Failed to scan directory {directory}: {e}")
            return 0
    
    def _discover_from_plugin_yaml(self, yaml_file: Path, plugin_dir: Path) -> int:
        """
        从 plugin.yaml 文件发现插件
        
        Args:
            yaml_file: plugin.yaml 文件路径
            plugin_dir: 插件目录路径
            
        Returns:
            int: 发现的插件数量（0 或 1）
        """
        try:
            # 读取 YAML 文件
            with open(yaml_file, 'r', encoding='utf-8') as f:
                plugin_config = yaml.safe_load(f)
            
            # 检查是否启用
            if not plugin_config.get('enabled', True):
                self._log_debug(f"Plugin disabled in {yaml_file}")
                return 0
            
            # 获取插件信息
            plugin_name = plugin_config.get('name')
            plugin_class_name = plugin_config.get('plugin_class')
            module_name = plugin_config.get('module')
            
            if not plugin_name or not plugin_class_name:
                self._log_warning(f"Invalid plugin.yaml: {yaml_file}")
                return 0
            
            # 检查是否已注册
            if plugin_name in self._plugins:
                self._log_debug(f"Plugin already registered: {plugin_name}")
                return 0
            
            # 构建完整模块路径
            plugin_package = plugin_dir.name
            if module_name:
                # 使用指定的模块名
                full_module_path = f"{plugin_dir.parent.name}.{plugin_package}.{module_name}"
            else:
                # 尝试从 __init__.py 导入
                full_module_path = f"{plugin_dir.parent.name}.{plugin_package}"
            
            # 导入模块并获取插件类
            try:
                module = importlib.import_module(full_module_path)
                plugin_class = getattr(module, plugin_class_name)
                
                if not issubclass(plugin_class, BasePlugin):
                    self._log_warning(f"Class {plugin_class_name} is not a BasePlugin subclass")
                    return 0
                
            except (ImportError, AttributeError) as e:
                self._log_error(f"Failed to import plugin from {yaml_file}: {e}")
                return 0
            
            # 准备元数据
            metadata = {
                'name': plugin_name,
                'version': plugin_config.get('version', '1.0.0'),
                'description': plugin_config.get('description', ''),
                'author': plugin_config.get('author', 'Unknown'),
                'dependencies': plugin_config.get('dependencies', []),
                'interfaces': plugin_config.get('interfaces', []),
                'init_params': plugin_config.get('init_params', {}),
                'config': plugin_config.get('config', {})
            }
            
            # 注册插件
            self.register(
                plugin_class=plugin_class,
                name=plugin_name,
                metadata=metadata,
                source=f"yaml:{yaml_file}"
            )
            
            self._log_info(f"✓ Discovered plugin '{plugin_name}' from {yaml_file}")
            return 1
            
        except Exception as e:
            self._log_error(f"Failed to process {yaml_file}: {e}")
            return 0
    
    # ========================================
    # 插件加载方法
    # ========================================
    
    def load_plugin(
        self,
        name: str,
        context: PluginContext,
        container: Optional[Any] = None,
        **init_kwargs
    ) -> BasePlugin:
        """
        加载插件实例
        
        Args:
            name: 插件名称
            context: 插件上下文
            **init_kwargs: 传递给插件构造函数的参数
            
        Returns:
            BasePlugin: 插件实例
            
        Raises:
            KeyError: 如果插件未注册
            RuntimeError: 如果插件加载失败
            
        Note:
            - 如果插件已加载，返回现有实例
            - 否则创建新实例并初始化
            
        Example:
            ```python
            plugin = registry.load_plugin(
                'custom_map',
                context,
                width=100,
                height=100,
                data_file='towns.json'
            )
            ```
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not registered")
        
        metadata = self._plugins[name]
        
        # 如果已加载，返回现有实例
        if metadata.loaded and metadata.instance:
            return metadata.instance
        
        try:
            # 创建实例：先用配置文件里的 init_params，再用调用方参数覆盖
            init_params = {}
            try:
                init_params = dict(metadata.metadata.get('init_params', {}) or {})
            except Exception:
                init_params = {}
            init_params.update(init_kwargs)

            # 优先使用 DI 容器创建实例（支持自动注入依赖），否则直接构造
            if container is not None and hasattr(container, 'create'):
                plugin = container.create(metadata.plugin_class, **init_params)
            else:
                plugin = metadata.plugin_class(**init_params)
            
            # 初始化
            plugin.init(context)
            
            # 调用加载钩子
            plugin.on_load()
            plugin._mark_loaded()
            
            # 保存实例
            metadata.instance = plugin
            metadata.loaded = True
            
            self._log_info(f"Loaded plugin: {name}")
            return plugin
            
        except Exception as e:
            self._log_error(f"Failed to load plugin '{name}': {e}")
            raise RuntimeError(f"Plugin '{name}' load failed: {e}") from e
    
    def unload_plugin(self, name: str) -> None:
        """
        卸载插件实例
        
        Args:
            name: 插件名称
            
        Raises:
            KeyError: 如果插件未注册
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not registered")
        
        metadata = self._plugins[name]
        
        if not metadata.loaded or not metadata.instance:
            return
        
        try:
            # 调用卸载钩子
            metadata.instance.on_unload()
            metadata.instance._mark_unloaded()
            
            # 清除实例
            metadata.instance = None
            metadata.loaded = False
            
            self._log_info(f"Unloaded plugin: {name}")
            
        except Exception as e:
            self._log_error(f"Failed to unload plugin '{name}': {e}")
            raise
    
    # ========================================
    # 查询方法
    # ========================================
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        获取已加载的插件实例
        
        Args:
            name: 插件名称
            
        Returns:
            Optional[BasePlugin]: 插件实例，如果未加载返回 None
        """
        # 允许通过模块名查询
        if name in self._module_bindings:
            name = self._module_bindings[name]

        if name not in self._plugins:
            return None
        
        metadata = self._plugins[name]
        return metadata.instance if metadata.loaded else None
    
    def get_plugin_metadata(self, name: str) -> Optional[PluginMetadata]:
        """
        获取插件元数据
        
        Args:
            name: 插件名称
            
        Returns:
            Optional[PluginMetadata]: 插件元数据，如果不存在返回 None
        """
        return self._plugins.get(name)
    
    def get_plugins_by_interface(self, interface_name: str) -> List[str]:
        """
        按接口类型获取插件名称列表
        
        Args:
            interface_name: 接口名称（如 "IMapPlugin"）
            
        Returns:
            List[str]: 匹配的插件名称列表
            
        Example:
            ```python
            # 获取所有地图插件
            map_plugins = registry.get_plugins_by_interface('IMapPlugin')
            ```
        """
        result = []
        
        for name, metadata in self._plugins.items():
            # 检查类的基类
            for base in inspect.getmro(metadata.plugin_class):
                if base.__name__ == interface_name:
                    result.append(name)
                    break
        
        return result
    
    def has_plugin(self, name: str) -> bool:
        """
        检查插件是否已注册
        
        Args:
            name: 插件名称
            
        Returns:
            bool: 如果已注册返回 True，否则返回 False
        """
        return name in self._plugins
    
    def is_loaded(self, name: str) -> bool:
        """
        检查插件是否已加载
        
        Args:
            name: 插件名称
            
        Returns:
            bool: 如果已加载返回 True，否则返回 False
        """
        if name not in self._plugins:
            return False
        return self._plugins[name].loaded
    
    def get_all(self) -> Dict[str, PluginMetadata]:
        """
        获取所有已注册的插件
        
        Returns:
            Dict[str, PluginMetadata]: 插件名称到元数据的映射
        """
        return self._plugins.copy()
    
    def get_all_loaded(self) -> Dict[str, BasePlugin]:
        """
        获取所有已加载的插件实例
        
        Returns:
            Dict[str, BasePlugin]: 插件名称到实例的映射
        """
        return {
            name: metadata.instance
            for name, metadata in self._plugins.items()
            if metadata.loaded and metadata.instance
        }
    
    def get_plugin_list(self) -> List[Dict[str, Any]]:
        """
        获取插件列表（包含详细信息）
        
        Returns:
            List[Dict]: 插件信息列表
            
        Example:
            ```python
            plugins = registry.get_plugin_list()
            for plugin in plugins:
                print(f"{plugin['name']} v{plugin['version']} - {plugin['loaded']}")
            ```
        """
        result = []
        
        for name, metadata in self._plugins.items():
            result.append({
                'name': name,
                'version': metadata.metadata.get('version', 'unknown'),
                'description': metadata.metadata.get('description', ''),
                'author': metadata.metadata.get('author', 'unknown'),
                'loaded': metadata.loaded,
                'source': metadata.source,
                'class': metadata.plugin_class.__name__,
                'dependencies': metadata.metadata.get('dependencies', [])
            })
        
        return result
    
    def clear(self) -> None:
        """
        清空注册表（卸载所有插件）
        
        Warning:
            此操作会卸载所有已加载的插件
        """
        # 卸载所有插件
        for name in list(self._plugins.keys()):
            if self.is_loaded(name):
                try:
                    self.unload_plugin(name)
                except Exception as e:
                    self._log_error(f"Error unloading plugin '{name}' during clear: {e}")
        
        # 清空注册表
        self._plugins.clear()
        self._discovered_paths.clear()
        self._log_info("Plugin registry cleared")
    
    # ========================================
    # 日志辅助方法
    # ========================================
    
    def _log_info(self, message: str) -> None:
        """记录 INFO 日志"""
        if self._logger:
            self._logger.info(message)
    
    def _log_warning(self, message: str) -> None:
        """记录 WARNING 日志"""
        if self._logger:
            self._logger.warning(message)
    
    def _log_error(self, message: str) -> None:
        """记录 ERROR 日志"""
        if self._logger:
            self._logger.error(message)
    
    def _log_debug(self, message: str) -> None:
        """记录 DEBUG 日志"""
        if self._logger:
            self._logger.debug(message)
    
    # ========================================
    # 特殊方法
    # ========================================
    
    def __len__(self) -> int:
        """返回已注册的插件数量"""
        return len(self._plugins)
    
    def __contains__(self, name: str) -> bool:
        """支持 'name in registry' 语法"""
        return name in self._plugins
    
    def __repr__(self) -> str:
        loaded = sum(1 for m in self._plugins.values() if m.loaded)
        return f"PluginRegistry(total={len(self._plugins)}, loaded={loaded})"
