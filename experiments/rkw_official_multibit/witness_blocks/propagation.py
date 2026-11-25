"""Run a bounded propagation diagnostic on the one eligible encoded block."""
import json
from pathlib import Path
from teacher import generate

folder = Path(__file__).resolve().parent
rows = [json.loads(line) for line in (folder / "official_blocks.jsonl").read_bytes().splitlines()]
marked = next(row for row in rows if row["sample"] == "speed-2")
rectangle = next(row["original"] for row in rows if row["sample"] == "rectangle-0")
operations = {
    "summary": "Summarize the paragraph in two complete sentences. Preserve numerical values, units, and the limitation on instantaneous speed.",
    "rewrite": "Rewrite the paragraph in fresh wording. Preserve its numerical values, units, and the distinction between instantaneous and average speed.",
    "mixed_content": "Combine the two independent examples into a concise lesson. Preserve both examples and their exact numerical values, units, and limitations.",
}
with (folder / "propagation_raw.jsonl").open("x", encoding="utf8", newline="\n") as stream:
    for operation, prompt in operations.items():
        for carrier, text in (("encoded", marked["text"]), ("clean", marked["original"])):
            if operation == "mixed_content":
                text += "\n\n" + rectangle
            output = generate("llama3.1:8b", prompt + "\n\n" + text, 61129)
            stream.write(json.dumps(dict(operation=operation, carrier=carrier, input=text, prompt=prompt, **output)) + "\n")
            stream.flush()
