"""验证在线数据飞轮的模拟脚本。"""
import asyncio
import json

from app.core.failure_case import write_online_failure_case
from app.core.trace_collector import TraceCollector


async def main():
    # 模拟在线查询失败场景：SQL 执行报错
    tc = TraceCollector()
    tc.start_query(
        request_id="online_test_001",
        query="统计2025年第一季度每个大区销售额最高的商品品类及其销售额",
        user_scope={},
        source="online",
    )
    fake_sql = (
        "SELECT region_name, category, total_sales FROM "
        "(SELECT dr.region_name, dp.category, SUM(fo.order_amount) AS total_sales, "
        "ROW_NUMBER() OVER(PARTITION BY dr.region_name ORDER BY total_sales DESC) AS rn "
        "FROM fact_order fo JOIN dim_region dr ON fo.region_id = dr.region_id "
        "JOIN dim_product dp ON fo.product_id = dp.product_id "
        "WHERE fo.date_id BETWEEN 20250101 AND 20250331 "
        "GROUP BY dr.region_name, dp.category) t WHERE t.rn = 1"
    )
    fake_error = '(asyncmy.errors.OperationalError) (1054, "Unknown column \'total_sales\' in \'window order by\'")'
    tc.set_sql_validation(sql=fake_sql, valid=False, error=fake_error)
    tc.finish_query(error=fake_error)
    tc.save_to_file()

    path = write_online_failure_case(tc, tc.error)
    if path:
        print(f"失败样例已写入: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"source:       {data['source']}")
        print(f"error_type:   {data['error_type']}")
        print(f"question:     {data['question']}")
        print(f"has gold_sql: {'gold_sql' in data}")
        print(f"generated_sql: {data['generated_sql'][:80]}...")
        print(f"trace_file:   {data['trace_file']}")
    else:
        print("未生成失败样例（查询成功）")

    # 模拟 AST 安全校验失败
    print("\n--- 场景2: AST 安全校验拦截 ---")
    tc2 = TraceCollector()
    tc2.start_query(
        request_id="online_test_002",
        query="删除所有订单数据",
        user_scope={},
        source="online",
    )
    tc2.set_sql_validation(sql="DELETE FROM fact_order", valid=False, error="[AST_SECURITY] 禁止执行非查询语句")
    tc2.finish_query(error="[AST_SECURITY] 禁止执行非查询语句")
    tc2.save_to_file()

    path2 = write_online_failure_case(tc2, tc2.error)
    if path2:
        print(f"失败样例已写入: {path2}")
        data2 = json.loads(path2.read_text(encoding="utf-8"))
        print(f"source:       {data2['source']}")
        print(f"error_type:   {data2['error_type']}")
        print(f"question:     {data2['question']}")
        print(f"has gold_sql: {'gold_sql' in data2}")
    else:
        print("未生成失败样例")

    # 模拟查询成功（不应生成失败样例）
    print("\n--- 场景3: 查询成功（不应生成失败样例）---")
    tc3 = TraceCollector()
    tc3.start_query(request_id="online_test_003", query="查询所有商品品类", user_scope={}, source="online")
    tc3.set_sql_validation(sql="SELECT category FROM dim_product", valid=True)
    tc3.set_execution_result([{"category": "手机数码"}, {"category": "家用电器"}])
    tc3.finish_query(error=None)
    tc3.save_to_file()

    path3 = write_online_failure_case(tc3, None)
    if path3:
        print(f"不应该生成失败样例！但生成了: {path3}")
    else:
        print("正确：查询成功，未生成失败样例")


asyncio.run(main())
