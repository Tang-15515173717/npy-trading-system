#!/usr/bin/env python3
"""
每日推荐记录脚本
在收盘后运行，记录所有策略的明日操作建议到 Markdown 文件
"""
import os
import sys
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.daily_observer import DailyObserverStrategy, DailyObserverRecord
from models.stock import Stock
from models.bar_data import BarData
from services.scoring_engines.registry import get_engine

app = create_app()

def get_action_plan(strategy_id: int) -> dict:
    """获取策略的操作计划"""
    from models.daily_observer import DailyObserverStrategy, DailyObserverRecord
    
    strategy = DailyObserverStrategy.query.get(strategy_id)
    if not strategy:
        return None
    
    latest_record = DailyObserverRecord.query.filter_by(
        strategy_id=strategy_id
    ).order_by(DailyObserverRecord.date.desc()).first()
    
    if not latest_record:
        return None
    
    # 解析数据
    holdings_dict = json.loads(latest_record.holdings) if latest_record.holdings else {}
    scores_dict = json.loads(latest_record.scores) if latest_record.scores else {}
    selected_stocks = json.loads(latest_record.selected_stocks) if latest_record.selected_stocks else []
    
    # 获取股票名称
    all_ts_codes = list(set(selected_stocks + list(holdings_dict.keys())))
    stocks = Stock.query.filter(Stock.ts_code.in_(all_ts_codes)).all()
    stock_names = {s.ts_code: s.name for s in stocks}
    
    # 获取最新价格
    bars = BarData.query.filter(
        BarData.ts_code.in_(all_ts_codes),
        BarData.trade_date == latest_record.date
    ).all()
    price_dict = {bar.ts_code: float(bar.close) for bar in bars}
    
    # 准备引擎参数
    engine_id = strategy.scoring_engine_id or "daily_observer"
    engine = get_engine(engine_id)
    
    strategy_params = {
        "top_n": strategy.top_n,
        "max_positions": strategy.max_positions,
        "take_profit_ratio": strategy.take_profit_ratio,
        "stop_loss_ratio": strategy.stop_loss_ratio,
        "sell_rank_out": strategy.sell_rank_out,
        "signal_confirm_days": strategy.signal_confirm_days,
        "blacklist_cooldown": strategy.blacklist_cooldown
    }
    
    # 准备持仓数据
    holdings_for_engine = {}
    for ts_code, holding_info in holdings_dict.items():
        holdings_for_engine[ts_code] = {
            "buy_price": float(holding_info.get("buy_price", 0)),
            "buy_date": holding_info.get("buy_date"),
            "volume": holding_info.get("volume", 0),
            "score": holding_info.get("score", 0),
            "rank": holding_info.get("rank", 0)
        }
    
    # 准备得分数据
    stock_scores_for_engine = {}
    for ts_code in all_ts_codes:
        stock_scores_for_engine[ts_code] = {
            "score": scores_dict.get(ts_code, 0),
            "price": price_dict.get(ts_code, 0),
            "rank": 0
        }
    
    # 调用引擎决策
    decisions = engine.decide_daily_trades(
        holdings=holdings_for_engine,
        stock_scores=stock_scores_for_engine,
        strategy_params=strategy_params,
        trade_date=latest_record.date
    )
    
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy.name,
        "data_date": latest_record.date,
        "total_value": float(latest_record.total_value),
        "cash": float(latest_record.cash) if latest_record.cash else 0,
        "holdings": [
            {
                "ts_code": ts_code,
                "name": stock_names.get(ts_code, ts_code),
                "buy_price": float(info.get("buy_price", 0)),
                "current_price": price_dict.get(ts_code, 0),
                "volume": info.get("volume", 0)
            }
            for ts_code, info in holdings_dict.items()
        ],
        "buy_signals": [
            {
                "ts_code": b.get("ts_code"),
                "name": stock_names.get(b.get("ts_code"), b.get("ts_code")),
                "price": b.get("price", 0),
                "reason": b.get("reason", "因子选股")
            }
            for b in decisions.get("buy", [])
        ],
        "sell_signals": [
            {
                "ts_code": s.get("ts_code"),
                "name": stock_names.get(s.get("ts_code"), s.get("ts_code")),
                "price": s.get("price", 0),
                "reason": s.get("reason", "")
            }
            for s in decisions.get("sell", [])
        ]
    }

def record_recommendations():
    """记录所有策略的明日推荐"""
    with app.app_context():
        now = datetime.now()
        today = now.strftime("%Y%m%d")
        
        # 计算明日日期
        from datetime import timedelta
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        next_trade_date = next_day.strftime("%Y%m%d")
        
        # 获取所有活跃策略
        strategies = DailyObserverStrategy.query.filter_by(status="active").all()
        
        # 创建记录目录
        record_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs", "daily_recommendations")
        os.makedirs(record_dir, exist_ok=True)
        
        # 生成记录文件
        filename = f"{record_dir}/{today}_recommendations.md"
        
        lines = []
        lines.append(f"# 📅 {today} 收盘后 - 明日({next_trade_date})操作建议\n")
        lines.append(f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("---\n")
        
        for strategy in strategies:
            plan = get_action_plan(strategy.id)
            if not plan:
                continue
            
            lines.append(f"\n## 策略 {strategy.id}: {strategy.name}\n")
            lines.append(f"- **数据日期**: {plan['data_date']}")
            lines.append(f"- **总资产**: ¥{plan['total_value']:,.2f}")
            lines.append(f"- **现金**: ¥{plan['cash']:,.2f}\n")
            
            # 当前持仓
            lines.append("### 📊 当前持仓\n")
            lines.append("| 代码 | 名称 | 买入价 | 现价 | 数量 |")
            lines.append("|------|------|--------|------|------|")
            for h in plan['holdings']:
                lines.append(f"| {h['ts_code']} | {h['name']} | {h['buy_price']:.2f} | {h['current_price']:.2f} | {h['volume']} |")
            
            # 明日买入
            if plan['buy_signals']:
                lines.append(f"\n### 🟢 明日买入（{next_trade_date}）\n")
                lines.append("| 代码 | 名称 | 参考价 | 原因 |")
                lines.append("|------|------|--------|------|")
                for b in plan['buy_signals']:
                    lines.append(f"| {b['ts_code']} | {b['name']} | {b['price']:.2f} | {b['reason']} |")
            
            # 明日卖出
            if plan['sell_signals']:
                lines.append(f"\n### 🔴 明日卖出（{next_trade_date}）\n")
                lines.append("| 代码 | 名称 | 参考价 | 原因 |")
                lines.append("|------|------|--------|------|")
                for s in plan['sell_signals']:
                    lines.append(f"| {s['ts_code']} | {s['name']} | {s['price']:.2f} | {s['reason']} |")
            
            if not plan['buy_signals'] and not plan['sell_signals']:
                lines.append("\n**无操作建议，继续持有**\n")
            
            lines.append("\n---\n")
        
        # 写入文件
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✅ 已记录到: {filename}")
        return filename

if __name__ == "__main__":
    record_recommendations()
