"""
LLM 大模型服务 - StockQuant Pro
使用 DeepSeek API 对回测数据进行智能分析总结
支持 OpenAI 兼容 API 格式，可轻松切换其他大模型
"""
import json
import logging
import requests
from typing import Dict, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)


class LLMService:
    """大模型调用服务"""

    # 回测分析的系统提示词
    BACKTEST_SYSTEM_PROMPT = """你是一个专业的量化交易策略分析师，擅长根据回测数据进行深度复盘分析。

你的任务是根据提供的回测指标和交易数据，给出：
1. **策略总评**（2-3句话概括策略表现）
2. **核心问题诊断**（列出最关键的1-3个问题，用数据说话）
3. **具体优化建议**（针对每个问题给出可落地的改进方案，包含参数建议）
4. **风险提示**（实盘前需要注意的事项）

要求：
- 语言简洁专业，不要废话
- 每个观点都必须基于具体数据
- 优化建议要具体可执行，不要笼统的建议
- 如果策略表现好，也要指出潜在风险
- 用markdown格式输出，使用二级标题分段"""

    def __init__(self) -> None:
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""

    def _load_config(self) -> None:
        """从 Flask app config 加载配置"""
        self._api_key = current_app.config.get("DEEPSEEK_API_KEY", "")
        self._base_url = current_app.config.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self._model = current_app.config.get("DEEPSEEK_MODEL", "deepseek-chat")

    def is_available(self) -> bool:
        """检查 LLM 服务是否可用（是否配置了 API Key）"""
        self._load_config()
        return bool(self._api_key)

    def chat(self, user_prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """
        调用大模型进行对话

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数，控制创造性
            max_tokens: 最大输出 token 数

        Returns:
            模型回复文本，失败返回 None
        """
        self._load_config()

        if not self._api_key:
            logger.warning("DeepSeek API Key 未配置，跳过 LLM 调用")
            return None

        url = f"{self._base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            logger.info(f"调用 DeepSeek API, model={self._model}, prompt长度={len(user_prompt)}")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"DeepSeek 响应成功, 输出长度={len(content)}")
            return content

        except requests.exceptions.Timeout:
            logger.error("DeepSeek API 调用超时")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"DeepSeek API HTTP错误: {e}, 响应: {e.response.text if e.response else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"DeepSeek API 调用异常: {e}")
            return None

    def analyze_backtest(self, analysis_data: Dict[str, Any]) -> Optional[str]:
        """
        用大模型分析回测结果

        Args:
            analysis_data: 完整的回测分析数据（包含 task_info, problems, suggestions 等）

        Returns:
            AI 生成的分析总结文本（markdown 格式）
        """
        # 构造精简的数据摘要，避免 token 过多
        task_info = analysis_data.get("task_info", {})
        problems = analysis_data.get("problems", [])
        pnl = analysis_data.get("pnl_analysis", {})
        trade_freq = analysis_data.get("trade_frequency", {})
        holding = analysis_data.get("holding_period", {})
        cost = analysis_data.get("cost_analysis", {})
        stock_perf = analysis_data.get("stock_performance", {})

        # 构建数据摘要
        data_summary = f"""## 回测数据概览

### 基础信息
- 策略名称：{task_info.get('strategy_name', '未知')}
- 回测区间：{task_info.get('date_range', '未知')}
- 初始资金：{task_info.get('initial_capital', 0):,.0f} 元

### 核心指标
- 总收益率：{task_info.get('total_return', 0):.2f}%
- 年化收益：{task_info.get('annual_return', 0):.2f}%
- 最大回撤：{task_info.get('max_drawdown', 0):.2f}%
- 夏普比率：{task_info.get('sharpe_ratio', 0):.2f}
- 胜率：{task_info.get('win_rate', 0):.2f}%

### 交易统计
- 总交易次数：{trade_freq.get('total_trades', 0)} 笔
- 买入次数：{trade_freq.get('buy_trades', 0)}
- 卖出次数：{trade_freq.get('sell_trades', 0)}
- 日均交易：{trade_freq.get('avg_trades_per_day', 0):.2f} 笔
- 交易日数：{trade_freq.get('trading_days', 0)} 天

### 盈亏分析
- 完整交易数：{pnl.get('completed_trades', 0)}
- 盈利交易：{pnl.get('winning_trades', 0)}
- 亏损交易：{pnl.get('losing_trades', 0)}
- 净盈亏：{pnl.get('net_pnl', 0):,.2f} 元
- 总盈利：{pnl.get('total_profit', 0):,.2f} 元
- 总亏损：{pnl.get('total_loss', 0):,.2f} 元
- 平均盈利：{pnl.get('avg_win', 0):,.2f} 元
- 平均亏损：{pnl.get('avg_loss', 0):,.2f} 元
- 盈亏比：{pnl.get('profit_factor', 0):.2f}"""

        # 添加持仓信息
        if holding and not holding.get("warning"):
            data_summary += f"""

### 持仓周期
- 平均持仓：{holding.get('avg_holding_days', 0):.1f} 天
- 最长持仓：{holding.get('max_holding_days', 0)} 天
- 最短持仓：{holding.get('min_holding_days', 0)} 天
- 短线（≤5天）：{holding.get('short_term_count', 0)} 笔
- 中线（6-20天）：{holding.get('medium_term_count', 0)} 笔
- 长线（>20天）：{holding.get('long_term_count', 0)} 笔"""

        # 添加成本信息
        if cost:
            data_summary += f"""

### 交易成本
- 总手续费：{cost.get('total_commission', 0):,.2f} 元
- 手续费/资金比：{cost.get('commission_to_capital_ratio', 0):.2f}%"""

        # 添加个股表现
        if stock_perf:
            best = stock_perf.get("best_performing_stocks", [])[:3]
            worst = stock_perf.get("worst_performing_stocks", [])[:3]
            if best:
                data_summary += "\n\n### 表现最好的个股\n"
                for s in best:
                    data_summary += f"- {s['ts_code']}: 净盈亏 {s.get('net_amount', 0):,.0f} 元，交易 {s.get('trade_count', 0)} 次\n"
            if worst:
                data_summary += "\n### 表现最差的个股\n"
                for s in worst:
                    data_summary += f"- {s['ts_code']}: 净盈亏 {s.get('net_amount', 0):,.0f} 元，交易 {s.get('trade_count', 0)} 次\n"

        # 添加已识别的问题
        if problems:
            data_summary += "\n\n### 系统已识别的问题\n"
            for p in problems:
                data_summary += f"- [{p.get('severity', '')}] {p.get('description', '')}\n"

        user_prompt = f"""请基于以下回测数据，对这个量化交易策略进行全面的复盘分析。

{data_summary}

请从策略总评、核心问题诊断、优化建议、风险提示四个维度给出分析。优化建议务必结合具体数据，给出可落地的参数调整方向。"""

        return self.chat(
            user_prompt=user_prompt,
            system_prompt=self.BACKTEST_SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=2000
        )


# 全局单例
llm_service = LLMService()
