"""
交易服务 - StockQuant Pro
模拟交易会话管理、持仓查询、交易记录查询。v2.1 支持回测交易记录及双驱动筛选。
"""
from typing import Dict, Optional, List
from datetime import datetime
from models.simulation import SimulationSession, SimulationPosition, SimulationTrade
from models.backtest import BacktestTrade
from models.stock import Stock
from models.strategy import Strategy
from utils.database import db
import random


class TradeService:
    """交易服务类（简化版）"""

    def start_simulation(self, strategy_id: int, initial_capital: float = 1000000) -> Dict:
        """
        启动模拟交易会话。

        Args:
            strategy_id: 策略ID
            initial_capital: 初始资金

        Returns:
            会话信息字典
        """
        # 查询策略
        strategy = Strategy.query.get(strategy_id)
        if strategy is None:
            raise ValueError(f"策略 {strategy_id} 不存在")

        # 检查是否已有运行中的会话
        existing = SimulationSession.query.filter_by(
            strategy_id=strategy_id, status="running"
        ).first()
        if existing:
            raise ValueError(f"策略 {strategy_id} 已有运行中的模拟交易会话：{existing.session_id}")

        # 生成会话ID
        session_id = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{strategy_id:03d}"

        # 创建会话
        session = SimulationSession(
            session_id=session_id,
            strategy_id=strategy_id,
            strategy_name=strategy.name,
            initial_capital=initial_capital,
            current_capital=initial_capital,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.session.add(session)
        db.session.commit()

        # 模拟创建初始持仓（简化版：随机生成一些持仓）
        self._create_mock_positions(session_id, initial_capital)

        return session.to_dict()

    def stop_simulation(self, session_id: str) -> Dict:
        """
        停止模拟交易会话。

        Args:
            session_id: 会话ID

        Returns:
            会话信息字典
        """
        session = SimulationSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.status != "running":
            raise ValueError(f"会话 {session_id} 已停止")

        # 更新状态
        session.status = "stopped"
        session.stopped_at = datetime.utcnow()
        db.session.commit()

        return session.to_dict()

    def get_simulation_status(self, session_id: Optional[str] = None) -> Dict:
        """
        获取模拟交易状态。

        Args:
            session_id: 会话ID（可选，不传则返回最新运行中的会话）

        Returns:
            会话状态字典
        """
        if session_id:
            session = SimulationSession.query.filter_by(session_id=session_id).first()
        else:
            # 返回最新的运行中会话
            session = (
                SimulationSession.query.filter_by(status="running")
                .order_by(SimulationSession.started_at.desc())
                .first()
            )

        if session is None:
            return {"status": "no_session", "message": "无运行中的模拟交易会话"}

        # 查询持仓和资金
        positions = SimulationPosition.query.filter_by(session_id=session.session_id).all()
        total_market_value = sum(
            float(p.market_value) if p.market_value else 0 for p in positions
        )
        total_pnl = sum(float(p.pnl) if p.pnl else 0 for p in positions)

        result = session.to_dict()
        result["positions_count"] = len(positions)
        result["total_market_value"] = round(total_market_value, 2)
        result["total_pnl"] = round(total_pnl, 2)
        result["total_assets"] = round(
            float(session.current_capital or 0) + total_market_value, 2
        )

        return result

    def get_positions(self, session_id: str) -> List[Dict]:
        """
        获取持仓列表。

        Args:
            session_id: 会话ID

        Returns:
            持仓列表
        """
        session = SimulationSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")

        positions = SimulationPosition.query.filter_by(session_id=session_id).all()
        return [p.to_dict() for p in positions]

    def get_trades(
        self,
        session_id: str,
        ts_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        """
        获取交易记录。

        Args:
            session_id: 会话ID
            ts_code: 股票代码（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            分页结果
        """
        session = SimulationSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")

        query = SimulationTrade.query.filter_by(session_id=session_id)

        if ts_code:
            query = query.filter(SimulationTrade.ts_code == ts_code)

        total = query.count()
        offset = (page - 1) * page_size
        trades = (
            query.order_by(SimulationTrade.datetime.desc()).offset(offset).limit(page_size).all()
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [t.to_dict() for t in trades],
        }

    def get_backtest_trade_records(
        self,
        ts_code: Optional[str] = None,
        direction: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        factor_combo_id: Optional[int] = None,
        strategy_id: Optional[int] = None,
        signal_reason: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        """获取回测交易记录，支持 v2.1 双驱动字段筛选。"""
        query = BacktestTrade.query
        if ts_code:
            query = query.filter(BacktestTrade.ts_code == ts_code)
        if direction:
            query = query.filter(BacktestTrade.direction == direction)
        if start_date:
            query = query.filter(BacktestTrade.trade_date >= start_date)
        if end_date:
            query = query.filter(BacktestTrade.trade_date <= end_date)
        if factor_combo_id is not None:
            query = query.filter(BacktestTrade.factor_combo_id == factor_combo_id)
        if strategy_id is not None:
            query = query.filter(BacktestTrade.strategy_id == strategy_id)
        if signal_reason:
            query = query.filter(BacktestTrade.signal_reason == signal_reason)

        total = query.count()
        offset = (page - 1) * page_size
        trades = (
            query.order_by(BacktestTrade.trade_date.desc(), BacktestTrade.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        items = [t.to_dict() for t in trades]
        stock_map = {}
        if items:
            codes = list({t["ts_code"] for t in items})
            stocks = Stock.query.filter(Stock.ts_code.in_(codes)).all()
            stock_map = {s.ts_code: s.name for s in stocks}
        for it in items:
            it["name"] = stock_map.get(it["ts_code"], it["ts_code"])
            it["datetime"] = f"{it.get('trade_date', '')} 00:00:00"
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    def _create_mock_positions(self, session_id: str, initial_capital: float):
        """创建模拟持仓（简化版）"""
        stocks = ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH"]
        used_capital = 0

        for stock in stocks[:3]:  # 随机持仓 3 只股票
            cost_price = round(random.uniform(10, 50), 2)
            volume = random.randint(1000, 10000) // 100 * 100
            cost = cost_price * volume
            used_capital += cost

            if used_capital > initial_capital * 0.7:  # 最多使用 70% 资金
                break

            current_price = cost_price * random.uniform(0.95, 1.10)
            market_value = current_price * volume
            pnl = market_value - cost
            pnl_pct = (pnl / cost) * 100

            position = SimulationPosition(
                session_id=session_id,
                ts_code=stock,
                volume=volume,
                available=volume,
                cost_price=cost_price,
                current_price=round(current_price, 2),
                market_value=round(market_value, 2),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
            )
            db.session.add(position)

            # 添加交易记录
            trade = SimulationTrade(
                session_id=session_id,
                datetime=datetime.utcnow(),
                ts_code=stock,
                direction="buy",
                price=cost_price,
                volume=volume,
                amount=cost,
                commission=round(cost * 0.0003, 2),
            )
            db.session.add(trade)

        db.session.commit()
