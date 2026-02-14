from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from firecrawl import Firecrawl

from app.config import FIRECRAWL_API_URL, FIRECRAWL_API_KEY


@dataclass(frozen=True)
class FirecrawlSettings:
    api_url: str
    api_key: str


class FirecrawlClient:
    """
    FirecrawlClient: 对 firecrawl python SDK 的封装 + 单例访问点。

    - 提供 scrape / crawl 等常用方法，方便其他模块调用
    - 线程安全单例（适合 Web 服务 / worker 多线程场景）
    """

    _instance: Optional["FirecrawlClient"] = None
    _lock = threading.Lock()

    def __init__(self, config: FirecrawlSettings):
        self._settings: FirecrawlSettings = config
        self._app: Firecrawl = self._create_app(config)

    @staticmethod
    def _create_app(config: FirecrawlSettings) -> Firecrawl:
        return Firecrawl(api_url=config.api_url, api_key=config.api_key)

    @classmethod
    def get_instance(cls) -> "FirecrawlClient":
        """
        线程安全的单例获取。
        - 首次调用可传 settings
        - 之后重复调用可不传
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            config = FirecrawlSettings(
                api_url=FIRECRAWL_API_URL,
                api_key=FIRECRAWL_API_KEY,
            )

            cls._instance = cls(config)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """测试用：重置单例。"""
        with cls._lock:
            cls._instance = None

    def scrape_url(
            self,
            url: str,
            formats: Optional[List[str]] = None,
            only_main_content: bool = True,
            timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        timeout: milliseconds
        """
        try:
            return self._app.scrape(url, formats=formats, only_main_content=only_main_content,
                                    timeout=timeout).model_dump(
                exclude_none=True)
        except Exception as e:
            raise RuntimeError(f"Firecrawl scrape_url failed: url={url}") from e
