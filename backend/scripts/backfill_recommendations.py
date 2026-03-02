#!/usr/bin/env python3
"""
补全历史推荐记录
从指定日期开始，为所有活跃策略补全推荐记录
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.daily_observer import DailyObserverStrategy, DailyObserverRecord
from models.daily_recommendation import DailyRecommendation
from services.recommendation_service import record_recommendation
from utils.database import db

app = create_app()


def get_trading_days(start_date: str, end_date: str) -> list:
    """生成交易日列表（排除周末）"""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    
    trading_days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            trading_days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    
    return trading_days


def backfill_strategy(strategy_id: int, start_date: str, end_date: str) -> dict:
    """为单个策略补全推荐记录"""
    result = {
        "strategy_id": strategy_id,
        "total": 0,
        "added": 0,
        "skipped": 0,
        "errors": []
    }
    
    trading_days = get_trading_days(start_date, end_date)
    result["total"] = len(trading_days)
    
    for date in trading_days:
        # 检查是否有该日期的观测记录
        has_record = DailyObserverRecord.query.filter_by(
            strategy_id=strategy_id,
            date=date
        ).first() is not None
        
        if not has_record:
            result["skipped"] += 1
            continue
        
        # 检查是否已有推荐记录
        existing = DailyRecommendation.query.filter_by(
            strategy_id=strategy_id,
            record_date=date
        ).first()
        
        if existing:
            result["skipped"] += 1
            continue
        
        # 记录推荐
        rec_result = record_recommendation(strategy_id, target_date=date)
        if rec_result.get("success"):
            result["added"] += 1
            print(f"  ✅ 策略{strategy_id} - {date}")
        else:
            result["errors"].append(f"{date}: {rec_result.get('message')}")
            print(f"  ❌ 策略{strategy_id} - {date}: {rec_result.get('message')}")
    
    return result


def backfill_all(start_date: str = "20260123", end_date: str = None):
    """为所有活跃策略补全推荐记录"""
    with app.app_context():
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        
        print(f"\n📊 补全推荐记录")
        print(f"   日期范围: {start_date} ~ {end_date}")
        print("=" * 50)
        
        # 获取所有活跃策略
        strategies = DailyObserverStrategy.query.filter_by(status="active").all()
        print(f"   活跃策略: {len(strategies)}个\n")
        
        total_added = 0
        total_skipped = 0
        
        for strategy in strategies:
            print(f"\n🔄 策略 {strategy.id}: {strategy.name}")
            result = backfill_strategy(strategy.id, start_date, end_date)
            total_added += result["added"]
            total_skipped += result["skipped"]
            
            print(f"   新增: {result['added']}, 跳过: {result['skipped']}")
            if result["errors"]:
                print(f"   错误: {len(result['errors'])}个")
        
        print("\n" + "=" * 50)
        print(f"✅ 补全完成！新增: {total_added}, 跳过: {total_skipped}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="补全历史推荐记录")
    parser.add_argument("--start", default="20260123", help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD（默认今天）")
    parser.add_argument("--strategy", type=int, help="指定策略ID（不指定则处理所有活跃策略）")
    
    args = parser.parse_args()
    
    if args.strategy:
        with app.app_context():
            end_date = args.end or datetime.now().strftime("%Y%m%d")
            print(f"\n🔄 补全策略 {args.strategy}")
            result = backfill_strategy(args.strategy, args.start, end_date)
            print(f"\n✅ 完成！新增: {result['added']}, 跳过: {result['skipped']}")
    else:
        backfill_all(args.start, args.end)
