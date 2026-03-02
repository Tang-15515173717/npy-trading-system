"""
同步回测结果到策略表
将已完成的回测任务结果同步到策略的backtest_result字段
"""
import sqlite3
import json

DB_PATH = "/Users/mac/IdeaProjects/vnpy/database/stock_quant.db"

print("=" * 80)
print("🔄 同步回测结果到策略表")
print("=" * 80)
print()

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 查询所有已完成的回测任务
cursor.execute("""
    SELECT strategy_id, result, completed_at
    FROM backtest_tasks
    WHERE status = 'completed'
    AND result IS NOT NULL
    ORDER BY strategy_id, completed_at DESC
""")

tasks = cursor.fetchall()
print(f"📊 找到 {len(tasks)} 条已完成的回测任务")
print()

# 按策略ID分组，取每个策略最新的回测结果
strategy_results = {}
for strategy_id, result, completed_at in tasks:
    if strategy_id not in strategy_results:
        strategy_results[strategy_id] = {
            'result': result,
            'completed_at': completed_at
        }

print(f"📊 涉及 {len(strategy_results)} 个策略")
print()

# 更新策略表
updated = 0
for strategy_id, data in strategy_results.items():
    result_json = data['result']
    
    try:
        # 解析result以验证是否是有效的JSON
        result_dict = json.loads(result_json)
        
        # 提取关键统计数据用于显示
        stats = result_dict.get('statistics', {})
        
        # 更新策略表
        cursor.execute("""
            UPDATE strategies
            SET backtest_result = ?
            WHERE id = ?
        """, (result_json, strategy_id))
        
        conn.commit()
        
        # 获取策略名称
        cursor.execute("SELECT name FROM strategies WHERE id = ?", (strategy_id,))
        strategy_name = cursor.fetchone()[0]
        
        print(f"✅ 策略ID {strategy_id} ({strategy_name})")
        print(f"   总收益: {stats.get('total_return', 0):.2f}%")
        print(f"   年化收益: {stats.get('annual_return', 0):.2f}%")
        print(f"   最大回撤: {stats.get('max_drawdown', 0):.2f}%")
        print(f"   夏普比率: {stats.get('sharpe_ratio', 0):.2f}")
        print()
        
        updated += 1
    except json.JSONDecodeError:
        print(f"❌ 策略ID {strategy_id} - 回测结果格式错误")
        print()
    except Exception as e:
        print(f"❌ 策略ID {strategy_id} - 更新失败: {str(e)}")
        print()

conn.close()

print("=" * 80)
print("📊 同步完成统计")
print("=" * 80)
print(f"✅ 成功更新: {updated} 个策略")
print(f"📊 总计任务: {len(tasks)} 条")
print("=" * 80)
print()
print("✅ 现在刷新前端页面，应该能看到回测结果了！")
print()
