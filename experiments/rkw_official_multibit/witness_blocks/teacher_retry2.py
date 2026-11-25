import json
from pathlib import Path
from teacher import generate
fact="A cyclist covered 120 meters in 20 seconds. These totals give an average speed of 6 meters per second, but do not determine the instantaneous speed. Additional position-versus-time information is needed."
prompt="Explain this exact example in at least three complete sentences. Use these same numbers only. Do not add any other example. "+fact
row=dict(topic="speed",position=2,fact=fact,prompt=prompt,**generate("qwen2.5:7b-instruct",prompt,61129))
Path("var/icml-multibit/witness_teacher_retry2.jsonl").open("x",encoding="utf8").write(json.dumps(row)+"\n")
