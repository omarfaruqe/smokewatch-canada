"""Command-line entry point: `smokewatch hotspots ...`."""

from __future__ import annotations

import argparse
import logging
from datetime import date

from smokewatch.extractors import cwfis_hotspots
from smokewatch.storage import get_store


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="smokewatch")
    sub = parser.add_subparsers(dest="command", required=True)

    hs = sub.add_parser("hotspots", help="extract CWFIS fire hotspots to bronze")
    hs.add_argument("--sink", choices=["local", "s3"], default="s3")
    hs.add_argument("--date", type=date.fromisoformat, help="single day (backfill layer)")
    hs.add_argument("--start", type=date.fromisoformat, help="backfill start date")
    hs.add_argument("--end", type=date.fromisoformat, help="backfill end date")
    hs.add_argument("--force", action="store_true", help="re-extract days already in bronze")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = get_store(args.sink)

    if args.command == "hotspots":
        if args.start or args.end:
            if not (args.start and args.end):
                parser.error("--start and --end must be used together")
            results = cwfis_hotspots.backfill(
                store, args.start, args.end, skip_existing=not args.force
            )
            total = sum(r.feature_count for r in results)
            print(f"backfill done: {len(results)} day(s), {total} hotspots")
        else:
            r = cwfis_hotspots.extract(store, args.date)
            print(f"{r.layer} {r.day}: {r.feature_count} hotspots -> {r.data_key}")


if __name__ == "__main__":
    main()
