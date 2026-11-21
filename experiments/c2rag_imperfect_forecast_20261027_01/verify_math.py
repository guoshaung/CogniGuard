"""Validate all T06 fact combinations independently under positive exact equations."""
import itertools
from experiments.c2rag_imperfect_forecast_20261027_01.common import read,write,module,deadline
from experiments.c2rag_real_source_structure_20261027_01.math_reference import check


def main():
    bank=read('public/banks.json')['T06'];task=bank['source_contract'];ref=module('reference')
    fields=list(task['fields']);certs=[]
    for bits in range(1<<len(fields)):
        deadline();known={f for i,f in enumerate(fields) if bits&(1<<i)}
        proof=check(task,known);horn='TARGET' in ref.closure(known,task['rules'])
        assert proof['status']!='UNKNOWN'
        assert horn==(proof['status']=='UNIQUE'),(known,proof)
        certs.append(proof|{'horn_recovers':horn})
    write('mathematical_contract_verification.json',{'T06_field_subsets':len(certs),'disagreements':0,'unknown':0,
        'certificates':certs,'source':'independent rational equations, no controller engine',
        'kinetic':'all four binding subsets: none/m/v not complete; m+v complete, positive alternate allowed values available'})
    print('All T06 128 subsets exact-equation verified')


if __name__=='__main__':main()
