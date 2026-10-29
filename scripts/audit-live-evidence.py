import argparse
import json
from pathlib import Path
import sys

from rimprobe.errors import ProbeError
from rimprobe.evidence import audit_evidence


def main():
    parser = argparse.ArgumentParser(description="Read-only audit of a completed RimProbe MCP regression. Does not launch games.")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--agent-root", type=Path, required=True, help="Explicit build to compare; historical evidence needs its matching build, not today's replacement.")
    parser.add_argument("--game", type=Path, help="Also verify the currently installed owned Agent, without modifying it.")
    arguments = parser.parse_args()
    try:
        result = audit_evidence(arguments.evidence, arguments.agent_root, arguments.game)
    except ProbeError as error:
        print(json.dumps(error.as_dict(), ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
