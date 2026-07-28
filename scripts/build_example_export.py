"""Build the deterministic downloadable v2 example export."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "minimal-v2"
TARGET = ROOT / "docs" / "assets" / "downloads" / "neuroqp-example-v2.zip"


def build() -> bytes:
    """Return the example export as deterministic ZIP bytes."""

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in SOURCE.rglob("*") if item.is_file()):
            member = ZipInfo(path.relative_to(SOURCE).as_posix(), (1980, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, path.read_bytes(), compresslevel=9)
    return output.getvalue()


def main() -> int:
    """Write the archive or verify the committed copy."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()

    if args.check:
        if not TARGET.is_file() or TARGET.read_bytes() != expected:
            print(f"out of date: {TARGET.relative_to(ROOT)}")
            return 1
        print(f"up to date: {TARGET.relative_to(ROOT)}")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(expected)
    print(f"wrote: {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
