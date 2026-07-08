"""
MallPilot 工具统一注册模块。

这个模块负责把 guide、order、after_sales 三类工具集中注册到 MCPToolManager。
"""
from core.commerce_store import CommerceStore
from mcp.tool_manager import MCPToolManager
from tools.after_sales_tools import register_after_sales_tools
from tools.guide_tools import register_guide_tools
from tools.order_tools import register_order_tools


# 做什么：统一注册所有电商角色工具。
# 为什么：让生命周期入口只保留一行注册调用，避免工具清单继续膨胀在 api/main.py 中。
def register_commerce_tools(tool_manager: MCPToolManager, commerce_store: CommerceStore) -> None:
    register_guide_tools(tool_manager, commerce_store)
    register_order_tools(tool_manager, commerce_store)
    register_after_sales_tools(tool_manager, commerce_store)
