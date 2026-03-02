"""
打分驱动回测引擎 - 版本管理
============================
每个引擎版本是独立的类文件，互不干扰。
新增版本只需：
  1. 在 scoring_engines/ 下新建 vN_xxx.py，继承 BaseEngine
  2. 在本文件的 ENGINES 注册表中添加一行
  3. 前端自动出现新版本选项
"""

from services.scoring_engines.registry import ENGINES, get_engine, list_engines

__all__ = ["ENGINES", "get_engine", "list_engines"]
