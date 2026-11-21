"""Original finite teaching instances. Not an inference-time language parser."""
from fractions import Fraction as F
import itertools

SPECS = [
 dict(id='S01', split='development', subject='physics', family='spring-ratio',
      title='弹簧静态标定：两个输入求刚度（简单二选一对照）',
      page='college-physics-2e__16-1-hookes-law-stress-and-strain-revisited.html', phrase='Hooke',
      variables={'force':[2,4], 'extension':[1,2]}, nominal=[4,2], target=['stiffness'],
      equations='stiffness = force / extension; static linear elastic range, no preload',
      observations={'F':'force','x':'extension'}, units={'F':'N','x':'m'},
      queries=[('报告标定拉力', [['F']]),('报告弹性伸长量', [['x']])]),
 dict(id='S02', split='development', subject='physics', family='work-balance',
      title='同一包裹的两种功法与后续测量',
      page='college-physics-2e__7-2-kinetic-energy-and-the-work-energy-theorem.html', phrase='net work',
      variables={'applied_work':[94,96,100], 'friction_loss':[2,4,8], 'distance':['2/5','4/5','8/5']},
      nominal=[96,4,'4/5'], target=['force','friction','distance'],
      equations='F=applied_work/d; f=friction_loss/d; N=F-f; W=applied_work-friction_loss; constant collinear forces, horizontal motion',
      observations={'N':'net_force','d':'distance','WA':'applied_work','L':'friction_loss','W':'net_work'},
      units={'N':'N','d':'m','WA':'J','L':'J','W':'J'},
      queries=[('用净力法或各力功相加法计算净功，报告相应两个中间量', [['N','d','W'],['WA','L','W']]),
               ('报告净力', [['N']]),('报告推力做功', [['WA']]),('报告推动位移', [['d']])]),
 dict(id='S03', split='development', subject='physics', family='gas-state-shortcuts',
      title='同一气样状态量与两条计算捷径',
      page='college-physics-2e__13-3-the-ideal-gas-law.html', phrase='ideal gas',
      variables={'pressure':[1,2], 'volume':[2,4], 'temperature':[1,2]}, nominal=[2,4,2], target=['nR'],
      equations='nR=P*V/T; R is public; P,T and V are positive normalized quantities; equilibrium ideal gas',
      observations={'P':'pressure','V':'volume','T':'temperature','PV':'PV','PT':'PT'},
      units={'P':'P0','V':'V0','T':'T0','PV':'P0*V0','PT':'P0/T0'},
      queries=[('报告气压', [['P']]),('报告体积', [['V']]),('报告绝对温度', [['T']]),
               ('任选一个合法计算检查：PV或P/T', [['PV'],['PT']])]),
 dict(id='S04', split='validation', subject='chemistry', family='dilution-sum-ratio',
      title='同一溶液的配制与加水稀释',
      page='chemistry-2e__3-3-molarity.html', phrase='dilution',
      variables={'amount':[1,2], 'initial_volume':[1,2], 'added_volume':[1,2]},
      nominal=[2,2,1], target=['final_concentration'],
      equations='C0=n/V0; Vf=V0+Vadd; Cf=n/Vf; no reaction, conserved solute and additive volumes are explicit synthetic assumptions',
      observations={'n':'amount','V0':'initial_volume','Va':'added_volume','C0':'initial_concentration','Vf':'final_volume'},
      units={'n':'mol','V0':'L','Va':'L','C0':'mol/L','Vf':'L'},
      queries=[('报告溶质量', [['n']]),('报告初始体积', [['V0']]),('报告加入水体积', [['Va']]),
               ('报告最终总体积', [['Vf']]),('报告初始浓度', [['C0']])]),
 dict(id='S05', split='validation', subject='mathematics', family='quadratic-symmetric-invariants',
      title='同一首一二次式的根与对称量',
      page='college-algebra-2e__2-5-quadratic-equations.html', phrase='quadratic',
      variables={'negative_root':[-3,-2,-1], 'positive_root':[1,2,3]}, nominal=[-2,3], target=['b','c'],
      equations='(z-r)(z-s)=z^2+b*z+c; b=-(r+s),c=r*s; discriminant=(r-s)^2',
      observations={'r':'negative_root','s':'positive_root','sum':'root_sum','product':'root_product','D':'discriminant'},
      units={'r':'1','s':'1','sum':'1','product':'1','D':'1'},
      queries=[('报告负根', [['r']]),('报告正根', [['s']]),
               ('完成一个根的对称量检查：任选根和或根积并注明名称', [['sum'],['product']]),
               ('报告判别式', [['D']])]),
 dict(id='S06', split='validation', subject='biology-model', family='synthetic-assay-logic',
      title='简化酶实验记录：条件合取和两条预检查',
      page='biology-2e__6-5-enzymes.html', phrase='inhibitor',
      variables={'enzyme':[0,1], 'substrate':[0,1], 'inhibitor':[0,1]}, nominal=[1,1,0], target=['reaction_on'],
      equations='ON=E and S and not I; ES=E and S; SI=S and not I. AUTHOR TOY MODEL, not a biological law or general causal inference claim',
      observations={'E':'enzyme','S':'substrate','I':'inhibitor','ES':'ES','SI':'SI'},
      units={k:'boolean' for k in ['E','S','I','ES','SI']},
      queries=[('报告酶是否加入', [['E']]),('报告底物是否加入', [['S']]),('报告抑制剂是否加入', [['I']]),
               ('任选一项预检查：酶与底物均有，或底物存在且无抑制剂', [['ES'],['SI']])])
]

def evaluate(spec, vals):
    w={k:F(str(v)) for k,v in zip(spec['variables'],vals)};i=spec['id']
    if i=='S01':w['stiffness']=w['force']/w['extension']
    elif i=='S02':
        w['force']=w['applied_work']/w['distance'];w['friction']=w['friction_loss']/w['distance']
        w['net_force']=w['force']-w['friction'];w['net_work']=w['applied_work']-w['friction_loss']
    elif i=='S03':
        w['PV']=w['pressure']*w['volume'];w['PT']=w['pressure']/w['temperature'];w['nR']=w['PV']/w['temperature']
    elif i=='S04':
        w['initial_concentration']=w['amount']/w['initial_volume'];w['final_volume']=w['initial_volume']+w['added_volume']
        w['final_concentration']=w['amount']/w['final_volume']
    elif i=='S05':
        w['root_sum']=w['negative_root']+w['positive_root'];w['root_product']=w['negative_root']*w['positive_root']
        w['discriminant']=(w['negative_root']-w['positive_root'])**2;w['b']=-w['root_sum'];w['c']=w['root_product']
    else:
        w['ES']=F(bool(w['enzyme'] and w['substrate']));w['SI']=F(bool(w['substrate'] and not w['inhibitor']))
        w['reaction_on']=F(bool(w['enzyme'] and w['substrate'] and not w['inhibitor']))
    return {k:str(v) for k,v in w.items()}

def worlds(spec):return [evaluate(spec,v) for v in itertools.product(*spec['variables'].values())]
