"""
全面修复回测任务数据中的所有字段错误
"""
import sqlite3
import os
import json

def fix_all_backtest_data():
    print("=" * 60)
    print("全面修复回测任务数据")
    print("=" * 60)

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'stock_quant.db')
    print(f"数据库路径: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 获取所有记录
        print("\n1️⃣ 读取所有记录...")
        cursor.execute("SELECT id, task_id, stocks, initial_capital, commission, slippage, benchmark, status, progress, result, error_msg, started_at, completed_at, created_at FROM backtest_tasks")
        all_records = cursor.fetchall()
        print(f"总共 {len(all_records)} 条记录")

        # 分析并修复每条记录
        print("\n2️⃣ 分析并修复记录...")
        fixed_count = 0

        for row in all_records:
            id = row[0]

            # 检查字段是否混乱
            stocks = row[2]
            initial_capital = row[3]
            commission = row[4]
            slippage = row[5]
            benchmark = row[6]
            status = row[7]
            progress = row[8]
            result = row[9]
            error_msg = row[10]
            started_at = row[11]
            completed_at = row[12]
            created_at = row[13]

            # 检查是否需要修复
            needs_fix = False
            if progress and isinstance(progress, str) and progress.startswith('{'):
                needs_fix = True  # progress 是 JSON，说明字段错位了

            if not needs_fix:
                continue

            # 尝试推断正确的字段值
            # 假设混乱的插入顺序，我们需要根据特征来识别字段

            # 识别 JSON 字段
            new_result = None
            new_stocks = stocks
            new_status = status
            new_progress = progress

            # 如果 progress 是 JSON，它可能是 result
            try:
                if progress and isinstance(progress, str) and progress.strip().startswith('{'):
                    json.loads(progress)  # 验证是否为有效 JSON
                    new_result = progress
                    new_progress = 100 if 'completed' in str(status) else 0
            except:
                pass

            # 如果 result 不是 JSON，可能是其他字段
            if not new_result and result and isinstance(result, str) and result.strip().startswith('{'):
                try:
                    json.loads(result)
                    new_result = result
                except:
                    pass

            # 识别状态字段
            if status and isinstance(status, str) and status in ['running', 'completed', 'failed', 'pending']:
                new_status = status
            elif status and isinstance(status, int):
                new_progress = status
                new_status = 'completed' if status == 100 else 'running'

            # 识别 stocks 字段
            if stocks and isinstance(stocks, str):
                try:
                    if stocks.strip().startswith('['):
                        json.loads(stocks)  # 验证是否为 JSON 数组
                        new_stocks = stocks
                except:
                    new_stocks = '[]'

            # 识别金额和比率字段
            new_initial_capital = 1000000
            new_commission = 0.0003
            new_slippage = 0.001
            new_benchmark = '000001.SH'

            for field in [initial_capital, commission, slippage]:
                try:
                    val = float(field)
                    if val > 1000:
                        new_initial_capital = val
                    elif val < 0.1:
                        if new_commission == 0.0003:
                            new_commission = val
                        else:
                            new_slippage = val
                except:
                    pass

            # 识别基准指数和状态
            for field in [benchmark, status]:
                if field and isinstance(field, str):
                    if '.' in field and any(c.isdigit() for c in field):
                        new_benchmark = field
                    elif field in ['running', 'completed', 'failed', 'pending']:
                        new_status = field

            # 执行更新
            try:
                cursor.execute("""
                    UPDATE backtest_tasks
                    SET stocks = ?,
                        initial_capital = ?,
                        commission = ?,
                        slippage = ?,
                        benchmark = ?,
                        status = ?,
                        progress = ?,
                        result = ?,
                        error_msg = ?
                    WHERE id = ?
                """, (
                    new_stocks,
                    new_initial_capital,
                    new_commission,
                    new_slippage,
                    new_benchmark,
                    new_status,
                    new_progress,
                    new_result,
                    error_msg,
                    id
                ))
                fixed_count += 1
                if fixed_count <= 3:
                    print(f"  ✅ 修复记录 ID={id}")
            except Exception as e:
                print(f"  ❌ 修复记录 ID={id} 失败: {e}")

        conn.commit()
        print(f"\n✅ 成功修复 {fixed_count} 条记录")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_all_backtest_data()
