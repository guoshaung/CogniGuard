"""Stronger chronological process interface; retain originals and require equality."""
from collections import defaultdict
import json
import subprocess
import sys
from experiments.c2rag_imperfect_forecast_20261027_01.common import *


def main():
    deadline();groups=defaultdict(list)
    for item in read('public/forecast_inputs.json'):groups[(item['stream_id'],item['condition'])].append(item)
    receipts=[]
    for (sid,c),items in groups.items():
        deadline();proc=subprocess.Popen([sys.executable,'-B','-m','experiments.c2rag_imperfect_forecast_20261027_01.forecast_online_worker'],
                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
        output=[]
        for item in items:
            # No later request prefix is sent until this answer is returned.
            proc.stdin.write(json.dumps(item,ensure_ascii=False)+'\n');proc.stdin.flush()
            line=proc.stdout.readline()
            if not line:raise RuntimeError(proc.stderr.read())
            output.append(json.loads(line))
        proc.stdin.close();stderr=proc.stderr.read();code=proc.wait()
        assert code==0 and 'isolation verified' in stderr
        original=read(f'forecasts/{sid}__{c}.json');assert output==original
        name=f'forecasts_causal_recheck/{sid}__{c}.json';write(name,output)
        receipts.append({'stream_id':sid,'condition':c,'identical_all_packet_fields':True,
                         'scenario_hashes':[x['scenario_hash'] for x in output],
                         'worker_exit':code,'selftest':stderr.strip()})
    write('repairs/forecast_information_boundary.json',{'issue':'initial batch worker read a file containing later prefix rows; pure packet function used only current row',
       'repair':'one fresh process per stream/condition; dispatcher sends next prefix only after current forecast returns; all evidence file reads blocked',
       'configuration_and_forecasts_changed':False,'affected_scope':'all320 files,2560 packets causally regenerated',
       'method_rerun_required':False,'reason':'every packet field and scenario hash identical, original files and traces retained',
       'workers':receipts})
    print('Causal recheck complete:',len(receipts),'isolated chronological workers, all forecasts identical')


if __name__=='__main__':main()
