from __future__ import annotations

import argparse
import json

from src.pipeline.discovery_v11 import DiscoveryPipelineV11, save_discovery_v11_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run discovery pipeline v1.1")
    parser.add_argument("--target-count", type=int, default=100)
    parser.add_argument("--per-query-limit", type=int, default=10)
    parser.add_argument("--per-feed-limit", type=int, default=40)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--baseline-report", default="data/discovery_report_v1.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    pipeline = DiscoveryPipelineV11()
    result = pipeline.run(
        target_count=args.target_count,
        per_query_limit=args.per_query_limit,
        per_feed_limit=args.per_feed_limit,
    )
    paths = save_discovery_v11_outputs(
        result=result,
        output_dir=args.output_dir,
        baseline_report_path=args.baseline_report,
    )
    print(
        json.dumps(
            {
                "metrics": result.metrics(),
                "output_paths": paths,
                "baseline_report": args.baseline_report,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
