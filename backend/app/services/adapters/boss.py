"""Boss 直聘仅生成官方搜索跳转，不请求其内部接口。"""

from app.services.adapters.nowcoder import boss_search_url, is_boss_public_url

__all__ = ["boss_search_url", "is_boss_public_url"]
