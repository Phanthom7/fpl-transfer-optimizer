"""Print scorecards; exit 1 if any requested gate is BLOCKED."""
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def main(argv):
    files = [RESULTS / f"phase{p}.json" for p in argv] if argv else sorted(RESULTS.glob("phase*.json"))
    blocked = False
    for f in files:
        if not f.exists():
            print(f"{f.name}: not run"); blocked = True; continue
        d = json.loads(f.read_text())
        print(f"Phase {d['phase']}: gate {d['gate']}")
        blocked |= d["gate"] == "BLOCKED"
    sys.exit(1 if blocked else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
