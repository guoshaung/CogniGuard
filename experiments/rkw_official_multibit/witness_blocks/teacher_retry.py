import json
from pathlib import Path
from teacher import generate
p=Path("var/icml-multibit/witness_teacher_retry.jsonl")
fixes=[
 ("rectangle",1,"The area of this rectangle is 36 square meters because its length times its width is 9 meters times 4 meters."),
 ("speed",2,"Knowing a cyclist's total distance and elapsed time determines average speed only. It cannot, by itself, determine the speed at any particular instant."),
]
with p.open("x",encoding="utf8") as f:
 for topic,pos,fact in fixes:
  prompt=f"Write a short standalone paragraph teaching exactly these facts: {fact} Use three complete sentences, describe the specified rectangle or cyclist without inventing a room or extra numerical example, and preserve the numerical values, units, and conditions. Return the paragraph only."
  f.write(json.dumps(dict(topic=topic,position=pos,fact=fact,prompt=prompt,**generate("qwen2.5:7b-instruct",prompt,61129)))+"\n")
  f.flush()

