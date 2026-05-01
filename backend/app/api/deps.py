"""
API 依赖注入
"""

from app.ai.graph_builder import get_travel_graph


def get_graph():
    """获取旅行规划图实例"""
    return get_travel_graph()