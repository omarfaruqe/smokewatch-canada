"""Command-line entry point: `smokewatch <source> ...`."""

from __future__ import annotations

import argparse
import logging
from datetime import date

from smokewatch.extractors import cwfis_hotspots, eccc_aqhi, eccc_climate
from smokewatch.storage import get_store


def _add_dates(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sink", choices=["local", "s3"], default="s3")
    p.add_argument("--date", type=date.fromisoformat, help="single UTC day")
    p.add_argument("--start", type=date.fromisoformat, help="range start (inclusive)")
    p.add_argument("--end", type=date.fromisoformat, help="range end (inclusive)")
    p.add_argument("--force", action="store_true", help="re-extract days already in bronze")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="smokewatch")
    sub = parser.add_subparsers(dest="command", required=True)

    _add_dates(sub.add_parser("hotspots", help="CWFIS fire hotspots -> bronze"))
    aq = sub.add_parser("aqhi", help="ECCC AQHI observations or forecasts -> bronze")
    aq.add_argument("kind", choices=["observations", "forecasts"])
    _add_dates(aq)
    _add_dates(sub.add_parser("weather", help="ECCC hourly climate observations -> bronze"))

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if bool(args.start) != bool(args.end):
        parser.error("--start and --end must be used together")
    store = get_store(args.sink)

    if args.command == "hotspots":
        if args.start:
            rs = cwfis_hotspots.backfill(store, args.start, args.end, skip_existing=not args.force)
            print(f"backfill done: {len(rs)} day(s), {sum(r.feature_count for r in rs)} hotspots")
        else:
            r = cwfis_hotspots.extract(store, args.date)
            print(f"{r.layer} {r.day}: {r.feature_count} hotspots -> {r.data_key}")

    elif args.command == "aqhi":
        if args.kind == "forecasts":
            rs = eccc_aqhi.forecasts(store)
            for r in rs:
                print(f"{r.feature_count} forecast features -> {r.data_key}")
        elif args.start:
            rs = eccc_aqhi.observations_range(
                store, args.start, args.end, skip_existing=not args.force
            )
            print(f"done: {len(rs)} day(s), {sum(r.feature_count for r in rs)} observations")
        else:
            r = eccc_aqhi.observations(store, args.date)
            print(f"{r.feature_count} observations -> {r.data_key}")

    elif args.command == "weather":
        if args.start:
            rs = eccc_climate.hourly_range(
                store, args.start, args.end, skip_existing=not args.force
            )
            print(f"done: {len(rs)} day(s), {sum(r.feature_count for r in rs)} hourly records")
        else:
            r = eccc_climate.hourly(store, args.date)
            print(f"{r.feature_count} hourly records -> {r.data_key}")


if __name__ == "__main__":
    main()
