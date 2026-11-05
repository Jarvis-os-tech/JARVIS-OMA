"""One bounded parsing request per process, outside the real-time audio loop."""
import contextlib
from datetime import datetime
import json
import sys

from jarvis_control.command_values import MAX_TEXT, parse_values


def main():
    request = json.loads(sys.stdin.read(MAX_TEXT * 8 + 1))
    anchor = request.pop('anchor', None)
    if anchor:
        anchor = datetime.fromisoformat(anchor)
    with contextlib.redirect_stdout(sys.stderr):
        result = parse_values(**request, anchor=anchor)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
