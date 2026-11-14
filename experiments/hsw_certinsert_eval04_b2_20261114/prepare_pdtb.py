"""Export the same PDTB Appendix A inventory used by the context diagnostic."""
import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "experiments/hsw_certinsert_eval04_20261113/context_nli_diagnostic_20261114"
    sys.path.insert(0, str(source))
    from report import connective_pages

    words = list(connective_pages())
    out = root / "var/results/hsw-st/certinsert_eval04_b2_20261114/pdtb100.json"
    with out.open("x", encoding="utf-8") as stream:
        json.dump(words, stream, indent=2)


if __name__ == "__main__":
    main()
