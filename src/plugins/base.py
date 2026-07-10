"""插件钩子系统"""
import importlib
import logging
from pathlib import Path
from typing import List, Callable, Any, Dict

logger = logging.getLogger(__name__)

HOOKS: Dict[str, List[Callable]] = {
    "before_retrieve": [],
    "after_retrieve": [],
    "before_build": [],
    "after_build": [],
    "before_query": [],
    "after_query": [],
}


def register_hook(event: str, handler: Callable):
    if event not in HOOKS:
        HOOKS[event] = []
    HOOKS[event].append(handler)


def run_hooks(event: str, *args, **kwargs) -> Any:
    result = None
    for handler in HOOKS.get(event, []):
        try:
            result = handler(*args, **kwargs)
        except Exception as e:
            logger.warning("插件钩子 %s 执行失败: %s", event, e)
    return result


def load_plugins(plugin_dir: str = "plugins"):
    """从 plugins/ 目录加载插件模块"""
    import sys
    root = str(Path(__file__).resolve().parent.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)

    path = Path(plugin_dir)
    if not path.exists():
        return
    for fp in path.glob("*.py"):
        if fp.name.startswith("_"):
            continue
        module_name = f"plugins.{fp.stem}"
        try:
            importlib.import_module(module_name)
            logger.info("已加载插件: %s", fp.name)
        except Exception as e:
            logger.warning("加载插件 %s 失败: %s", fp.name, e)
