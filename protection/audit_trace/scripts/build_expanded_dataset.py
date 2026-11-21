from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from expanded_data_builder import main


if __name__ == "__main__":
    main()
