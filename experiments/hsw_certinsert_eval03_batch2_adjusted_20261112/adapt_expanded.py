from common_adjusted import *
s=(E/'prepare_attacks.py').read_text(encoding='utf-8-sig');s=s[:s.index(' # P2 original insertion offsets')]+"\nif __name__=='__main__':main()\n"
s=s.replace("O/'P1'","O/'P1_expanded'").replace("O/'data/PUBLIC_OUTPUTS.json'","O/'data_expanded/PUBLIC_OUTPUTS.json'").replace("O/'data/OBSERVATIONS.json'","O/'data_expanded/OBSERVATIONS.json'").replace("E/'P1_INPUT_FREEZE.json'","E/'P1_EXPANDED_INPUT_FREEZE.json'")
s=s.replace("for x in items:\n     if x['id'] in ids:continue", "for x in sorted(items,key=lambda x:rank('scrub_target',x['source_id']))[:200]:")
s=s.replace('observation_overlap=False',"observation_overlap=x['id'] in ids").replace("stage='N10_ONLY_OTHER_N_PENDING_T5'","stage='EXPANDED_POOL_SEPARATE_FROM_INITIAL_N10'")
(E/'prepare_expanded_attacks.py').write_text(s,encoding='utf8')
s=(E/'score_cpu.py').read_text(encoding='utf-8-sig').replace("O/'P1/TASKS.json'","O/mode/'TASKS.json'").replace("mode=='P1'","mode.startswith('P1')").replace("mode!='P1'","not mode.startswith('P1')")
(E/'score_expanded.py').write_text(s,encoding='utf8')
