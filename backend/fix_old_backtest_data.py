"""
修复旧的回测任务数据中的字段错误
旧数据字段顺序搞混了，需要交换字段值
"""
import sqlite3
import os

def fix_backtest_data():
    print("=" * 60)
    print("修复旧的回测任务数据")
    print("=" * 60)

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'stock_quant.db')
    print(f"数据库路径: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查有问题的记录
        print("\n1️⃣ 检查有问题的记录...")
        cursor.execute("""
            SELECT id, task_id, initial_capital, commission, slippage, benchmark, status
            FROM backtest_tasks
            WHERE typeof(slippage) = 'text'
        """)
        problematic_rows = cursor.fetchall()

        if not problematic_rows:
            print("✅ 没有发现需要修复的记录")
            return

        print(f"发现 {len(problematic_rows)} 条需要修复的记录")
        for row in problematic_rows[:3]:
            print(f"  ID {row[0]}: initial_capital={row[2]}, commission={row[3]}, slippage={row[4]}, benchmark={row[5]}, status={row[6]}")

        # 修复数据
        print("\n2️⃣ 开始修复数据...")
        fixed_count = 0

        for row in problematic_rows:
            id, task_id, initial_capital, commission, slippage, benchmark, status = row

            # 字段映射（根据错误的插入顺序推断）
            # 旧: initial_capital=commission值, commission=slippage值, slippage=benchmark值, benchmark=status值
            # 实际正确的值应该是：
            new_initial_capital = 1000000.0  # 默认值
            new_commission = float(initial_capital) if initial_capital else 0.0003
            new_slippage = float(commission) if commission else 0.001
            new_benchmark = slippage if slippage and '.' in slippage else '000001.SH'
            new_status = benchmark if benchmark in ['running', 'completed', 'failed', 'pending'] else 'completed'

            try:
                cursor.execute("""
                    UPDATE backtest_tasks
                    SET initial_capital = ?,
                        commission = ?,
                        slippage = ?,
                        benchmark = ?,
                        status = ?
                    WHERE id = ?
                """, (new_initial_capital, new_commission, new_slippage, new_benchmark, new_status, id))
                fixed_count += 1
                print(f"  ✅ 修复记录 ID={id}")
            except Exception as e:
                print(f"  ❌ 修复记录 ID={id} 失败: {e}")

        conn.commit()
        print(f"\n✅ 成功修复 {fixed_count} 条记录")

        # 验证修复结果
        print("\n3️⃣ 验证修复结果...")
        cursor.execute("""
            SELECT id, task_id, initial_capital, commission, slippage, benchmark, status
            FROM backtest_tasks
            WHERE typeof(slippage) = 'text'
        """)
        still_bad = cursor.fetchall()

        if still_bad:
            print(f"⚠️  还有 {len(still_bad)} 条记录未修复")
        else:
            print("✅ 所有记录已正确修复")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_backtest_data()
