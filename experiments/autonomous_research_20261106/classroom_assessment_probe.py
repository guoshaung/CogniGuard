import ast, json, os, socket, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
def deny(*args,**kwargs): raise RuntimeError('network prohibited')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
from cogniguard.agents.learning_assessment_agent import LearningAssessmentAgent
source=root/'cogniguard/applications/education/classroom.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
names={'_compute_mastery_after','_clamp01','get_mastery_label'}
module=ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names],type_ignores=[])
ns={'Any':object};exec(compile(module,str(source),'exec'),ns)
agent=LearningAssessmentAgent(llm_client=None)
responses=[('correct_short','x=2',2),('wrong_short','x=7',7),('wrong_echo','equation algebra subtract three divide two isolate answer equals two. My answer is x=7.',7)]
out=[]
for name,text,x in responses:
 payload={'teaching_answer':'equation algebra subtract three divide two isolate answer equals two',
          'student_response':text,'knowledge_point':'equation algebra','profile_encoding':{}}
 assessment=agent.generate(payload)
 mastery=ns['_compute_mastery_after'](mastery_before=.63,assessment_score=assessment['mastery_score'],dialogue_mode='human_student',profile={},round_number=1,assessment=assessment)
 out.append({'case':name,'equation_correct':2*x+3==7,'score':assessment['mastery_score'],
             'assessment_label':assessment['assessment_result'],'next_mastery':mastery,
             'next_mastery_label':ns['get_mastery_label'](mastery),
             'direct_profile_update_requested':assessment['profile_update_evidence']['direct_profile_update_requested'],
             'model_call':False})
print(json.dumps({'cases':out,'classroom_graph_run':False,'fixed_hash_seed':os.environ.get('PYTHONHASHSEED')},indent=2))
