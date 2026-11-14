"""Use the existing CPU bridge in a process without other OpenMP runtimes."""
import json
import sys

from shared import BRIDGE, MODEL
from run05_scorer import Scorer


def main():
    model = Scorer(BRIDGE, MODEL)
    print('{"ready":true}', flush=True)
    try:
        for line in sys.stdin:
            data = json.loads(line)
            if data.get("stop"):
                break
            text = data["text"]
            length = len(model.tokenize(model.prefix+text))
            result = model.score(text) if length <= 1024 else {"overlength": length}
            print(json.dumps(result), flush=True)
    finally:
        model.close()


if __name__ == "__main__":
    main()
