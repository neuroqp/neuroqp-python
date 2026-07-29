#!/usr/bin/env python3
"""Report available NeuroQP package and skill updates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        from neuroqp._skill import update_notifications

        notifications = update_notifications(Path(__file__).parents[1])
    except Exception:
        notifications = ()

    if args.as_json:
        print(json.dumps({"notifications": notifications}))
    else:
        for notification in notifications:
            print(notification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
