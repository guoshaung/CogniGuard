from common_adjusted import *
O.mkdir(exist_ok=False)
assert sha(PREV/'EVAL_FREEZE.json')=='a50f08df466c35a1c07177e14f05305389299bea3288158fb62c31ed0180c001'
put(E/'FREEZE.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),task_sha256=sha(E/'TASK_AUTHORITY.md'),protocol_sha256=sha(E/'PROTOCOL.md'),method_freeze_sha256=sha(PREV/'EVAL_FREEZE.json'),seed=2026111205,bootstrap_seed=2026111206,bootstrap_replicates=2000,N=[10,50,200],m=[4,8],threshold=.01,method_changes=False,paid_API=0,prior_attempts_preserved=str(BASE/'batch02'),GPU_seconds_remaining=172800-220.563-read(BASE/'batch02/GPU_USAGE.json')['seconds']))
put(O/'STATE.json',dict(stage='PROTOCOL_FROZEN_BEFORE_MATERIALS',next='Commit then select P1/P2/P3/P6 inputs',new_generation=0))
