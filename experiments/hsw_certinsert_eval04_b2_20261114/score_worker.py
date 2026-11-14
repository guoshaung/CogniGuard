"""Run the unmodified CUDA scorer without loading Python numerical runtimes."""
import json
import sys
from pathlib import Path


def main():
    root, runtime, model = sys.argv[1:]
    sys.path.insert(0, str(Path(root) / "experiments/hsw_insertion_feasibility_20261109_01"))
    from run05_gpu_scorer import GPUScorer

    scorer = GPUScorer(runtime, model)
    try:
        print(json.dumps({"ready": True, "prefix_tokens": len(scorer.prefix_ids)}), flush=True)
        for line in sys.stdin:
            request = json.loads(line)
            if request["operation"] == "stop":
                break
            texts = request["texts"]
            try:
                result = ([len(scorer.tokenize(text)) for text in texts]
                          if request["operation"] == "tokenize" else scorer.score_many(texts))
                print(json.dumps({"result": result}), flush=True)
            except Exception as error:
                print(json.dumps({"error": type(error).__name__}), flush=True)
    finally:
        scorer.close()


if __name__ == "__main__":
    main()
