"""示例插件：构建后日志"""
import logging
from src.plugins.base import register_hook

logger = logging.getLogger(__name__)


def on_after_build(chunks, **kwargs):
    logger.info("[插件] 知识库构建完成，共 %d 个文本块", len(chunks) if chunks else 0)
    return chunks


register_hook("after_build", on_after_build)
