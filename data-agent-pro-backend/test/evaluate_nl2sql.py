import argparse
import asyncio
from pathlib import Path

from test.evaluator.runner import NL2SQLEvaluator, load_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NL2SQL evaluation cases.")
    parser.add_argument("--cases", type=Path, default=Path("test/eval_cases.json"), help="Path to evaluation cases JSON.")
    parser.add_argument("--report-dir", type=Path, default=Path("test/reports"), help="Directory to write reports.")
    parser.add_argument("--limit", type=int, default=None, help="Only run first N cases.")
    parser.add_argument("--tag", action="append", default=None, help="Only run cases containing this tag. Can be repeated.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases, limit=args.limit, tags=args.tag)
    evaluator = NL2SQLEvaluator(cases=cases, report_dir=args.report_dir)
    summary, _ = await evaluator.run()
    print(f"评测完成：{summary.total} 条样本")
    print(f"语义执行结果准确率：{summary.result_layer['execution_accuracy']:.2%}")
    print(f"严格执行结果准确率：{summary.result_layer['strict_execution_accuracy']:.2%}")
    print(f"报告根目录：{args.report_dir}")


if __name__ == "__main__":
    asyncio.run(main())