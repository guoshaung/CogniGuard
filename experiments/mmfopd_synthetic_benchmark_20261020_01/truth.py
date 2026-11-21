"""Independent executable teaching decisions. Never imports any selector."""
TYPES=['grade_diagnosis','weak_points','learning_path','resource_recommendation','behavior_intervention','exam_preparation','dynamic_progress','agent_collaboration']
class Unknown(Exception):pass
class Unavailable(Exception):pass
INPUTS=[
 [('recent_score','prior_score'),('mastery_a','recent_score','fatigue'),('error_a','attempts'),('mastery_a','mastery_b','mastery_c','recent_score')],
 [('mastery_a','mastery_b','mastery_c'),('error_a','error_b'),('prerequisite','mastery_a','mastery_b'),('error_a','attempts','mastery_a')],
 [('prerequisite','mastery_a','time_budget'),('mastery_a','mastery_b','mastery_c'),('mastery_a','practice_rate','time_budget'),('prerequisite','mastery_b','mastery_c','fatigue')],
 [('preference','mastery_a'),('access_rate','mastery_b'),('error_a','preference','time_budget'),('preference','access_rate','mastery_a','mastery_b')],
 [('inactive_days','activity_recent'),('fatigue','activity_recent','activity_prior'),('practice_rate','error_a'),('inactive_days','confidence_a','time_budget','fatigue')],
 [('mastery_a','time_budget'),('error_a','error_b','deadline'),('recent_score','prior_score','deadline'),('mastery_a','mastery_b','mastery_c','time_budget')],
 [('mastery_a','prior_mastery'),('activity_recent','activity_prior'),('recent_score','prior_score','practice_rate'),('mastery_a','prior_mastery','history_slope','confidence_a')],
 [('agent_a','agent_b'),('agent_a','agent_b','confidence_a','confidence_b'),('agent_a','behavior_flag','time_budget'),('agent_b','prerequisite','confidence_b')]
]
PARAMS=[
 [('threshold',)]*4,[(),('weight',),('threshold',),('threshold',)],
 [('threshold','budget'),(),('threshold','budget'),('threshold',)],
 [('threshold',),('threshold',),('count','budget'),('threshold',)],
 [('days','count'),('threshold','weight'),('threshold','count'),('days','threshold','budget')],
 [('threshold','budget'),('days',),('count','days'),('budget',)],
 [('threshold',)]*4,[('threshold',),('threshold',),('threshold','budget'),('threshold',)]
]
def execute(type_id,variant,values,p):
    seen=[]
    def g(k):
        if k not in seen:seen.append(k)
        if k not in values:raise Unknown(k)
        if values[k] is None:raise Unavailable(k)
        return float(values[k])
    def label(v):return 'support' if v<p['threshold'] else 'advance'
    def weakest():return min(range(3),key=lambda j:g(('mastery_a','mastery_b','mastery_c')[j]))
    def path():
        if g('prerequisite')<p['threshold']:return ['prerequisite','practice']
        return ['topic_a','review'] if g('mastery_a')<p['threshold'] and g('time_budget')>p['budget'] else ['practice']
    programs=[
      [lambda:label((g('recent_score')-g('prior_score'))/100+.5),lambda:label(.5*g('mastery_a')+.5*g('recent_score')/100-.2*g('fatigue')),lambda:label(1-g('error_a')/max(1,g('attempts'))),lambda:label((g('mastery_a')+g('mastery_b')+g('mastery_c')+g('recent_score')/100)/4)],
      [lambda:('weakest',weakest()),lambda:('error_focus','a' if g('error_a')>g('error_b')*p['weight'] else 'b'),lambda:('prerequisite' if g('prerequisite')<p['threshold'] else ('topic_a' if g('mastery_a')<g('mastery_b') else 'topic_b')),lambda:label(g('mastery_a')-g('error_a')/max(1,g('attempts')))],
      [path,lambda:['topic_'+str(weakest()),'practice'],lambda:['scaffold','practice'] if g('mastery_a')<p['threshold'] and g('practice_rate')<p['threshold'] and g('time_budget')>p['budget'] else ['review'],lambda:['prerequisite'] if g('prerequisite')<p['threshold'] else (['rest','topic_b'] if g('fatigue')>p['threshold'] else ['topic_b' if g('mastery_b')<g('mastery_c') else 'topic_c'])],
      [lambda:('worked_visual' if g('preference')>.5 else 'worked_text') if g('mastery_a')<p['threshold'] else 'challenge',lambda:'offline' if g('access_rate')<p['threshold'] else ('intro' if g('mastery_b')<p['threshold'] else 'advanced'),lambda:'short_example' if g('time_budget')<p['budget'] else ('error_diagram' if g('error_a')>p['count'] and g('preference')>.5 else 'worked_text'),lambda:'offline' if g('access_rate')<p['threshold'] else ('diagram' if g('preference')>.5 and g('mastery_a')<g('mastery_b') else 'text')],
      [lambda:'check_in' if g('inactive_days')>p['days'] and g('activity_recent')<p['count'] else 'continue',lambda:'rest' if g('fatigue')>p['threshold'] else ('check_in' if g('activity_recent')<g('activity_prior')*p['weight'] else 'continue'),lambda:'scaffold' if g('practice_rate')<p['threshold'] and g('error_a')>p['count'] else 'continue',lambda:'check_in' if g('inactive_days')>p['days'] and g('confidence_a')<p['threshold'] else ('rest' if g('time_budget')<p['budget'] and g('fatigue')>p['threshold'] else 'continue')],
      [lambda:'focused_review' if g('mastery_a')<p['threshold'] and g('time_budget')<p['budget'] else 'mock_exam',lambda:('urgent_a' if g('error_a')>g('error_b') else 'urgent_b') if g('deadline')<p['days'] else 'spaced_review',lambda:'intensive' if g('recent_score')<g('prior_score')-p['count'] and g('deadline')<p['days'] else 'mock_exam',lambda:('brief_'+str(weakest())) if g('time_budget')<p['budget'] else ('practice_'+str(weakest()))],
      [lambda:label(g('mastery_a')-g('prior_mastery')+.5),lambda:label(g('activity_recent')/max(1,g('activity_prior'))/2),lambda:label((g('recent_score')-g('prior_score'))/100+.5*g('practice_rate')),lambda:label((g('mastery_a')-g('prior_mastery'))*g('confidence_a')+g('history_slope')+.5)],
      [lambda:'resolve' if abs(g('agent_a')-g('agent_b'))>p['threshold']/2 else 'agree',lambda:label((g('agent_a')*g('confidence_a')+g('agent_b')*g('confidence_b'))/max(.01,g('confidence_a')+g('confidence_b'))),lambda:'tutor_then_check' if g('agent_a')<p['threshold'] and g('behavior_flag')>.5 and g('time_budget')>p['budget'] else 'handoff_quiz',lambda:'prerequisite_handoff' if g('prerequisite')<p['threshold'] else ('verify_quiz' if g('agent_b')<p['threshold'] and g('confidence_b')>.5 else 'agree')]
    ]
    try:
        answer=programs[type_id][variant]()
        if isinstance(answer,tuple):answer=list(answer)
        return {'status':'answer','answer':answer,'read_keys':seen}
    except Unavailable as exc:return {'status':'clarify','answer':'need_more:'+str(exc),'read_keys':seen}
    except Unknown:return {'status':'unresolved','answer':None,'read_keys':seen}
