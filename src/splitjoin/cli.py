"""Command-line interface for splitjoin."""
from __future__ import annotations

import argparse
from pathlib import Path

from .splitjoin import IntegrityError, join_file, split_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="splitjoin",
        description="Split a file into checksummed chunks and rejoin with verification.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("split", help="Split a file into chunks")
    sp.add_argument("src", help="File to split")
    sp.add_argument("out_dir", help="Directory to write chunks + manifest.json")
    sp.add_argument("--chunk-size", type=int, required=True, help="Bytes per chunk")

    jp = sub.add_parser("join", help="Rejoin chunks from a manifest")
    jp.add_argument("chunk_dir", help="Directory containing manifest.json and chunks")
    jp.add_argument("out_path", help="File to write the reassembled output")
    jp.add_argument("--no-verify", action="store_true",
                    help="Skip checksum verification (not recommended)")

    args = parser.parse_args(argv)

    if args.command == "split":
        if args.chunk_size <= 0:
            parser.error("--chunk-size must be positive")
        m = split_file(args.src, args.out_dir, args.chunk_size)
        print(
            f"Split {m['original_name']} ({m['total_size']} bytes) into "
            f"{len(m['chunks'])} chunk(s); whole sha256={m['whole_sha256'][:16]}…"
        )
        return 0

    # join
    try:
        result = join_file(args.chunk_dir, args.out_path, verify=not args.no_verify)
    except IntegrityError as exc:
        print(f"INTEGRITY FAILURE: {exc}")
        return 2
    state = "verified" if result["verified"] else "UNVERIFIED"
    print(
        f"Rejoined {result['chunks']} chunk(s) -> {Path(args.out_path).name} "
        f"({result['bytes_written']} bytes) [{state}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
