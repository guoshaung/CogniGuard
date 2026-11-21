"""Public task/schema adapter fixed before opening development outcomes."""
MODULES=['BBB','DDD','FFF'];CUTOFFS=[42,98,154]
FIELDS={
 'older_score':('mastery',.45,'prior_results','Mean of all available TMA scores except the latest'),
 'latest_score':('mastery',.45,'recent_results','Latest available TMA score'),
 'score_delta':('learning_state',.45,'recent_results','Latest score minus mean older scores'),
 'completion_rate':('learning_state',.35,'assessment_process','Submitted TMA count divided by due TMA count at lagged cutoff'),
 'overdue_count':('learning_state',.35,'assessment_process','Due but unsubmitted TMA count at lagged cutoff'),
 'clicks_recent':('behavior_aggregate',.30,'practice_volume','VLE clicks in the last14 days'),
 'clicks_earlier':('behavior_aggregate',.30,'practice_volume','VLE clicks in the preceding14 days'),
 'active_days':('behavior_aggregate',.30,'participation','Distinct active VLE days in the last14 days'),
 'inactive_days':('behavior_aggregate',.30,'participation','Days since last positive VLE click, capped60'),
 'forum_share':('behavior_aggregate',.40,'social','Last14-day forum clicks / all clicks'),
 'content_share':('access_context',.30,'resource','Last14-day content clicks / all clicks'),
 'previous_attempts':('educational_context',.50,'context','Recorded previous module attempts'),
 'studied_credits':('educational_context',.30,'context','Recorded study load credits')}
ROLE_ALIASES={
 'prior_results':['older_score','past attainment','previous results','performance history'],
 'recent_results':['latest_score','score_delta','recent progress','latest work','learning trajectory'],
 'assessment_process':['completion_rate','overdue_count','work keeping pace','assessment preparation','submission progress'],
 'practice_volume':['clicks_recent','clicks_earlier','study activity','practice effort'],
 'participation':['active_days','inactive_days','participation','lost momentum'],
 'social':['forum_share','forum participation','peer discussion'],
 'resource':['content_share','learning resources','content use'],
 'context':['previous_attempts','studied_credits','previous attempts','study load']}
INTENTS={
 'trajectory':{'required':['older_score','latest_score','score_delta'],'explicit':'Estimate the next TMA score using older_score, latest_score and score_delta.','ambiguous':"Review the learner's recent progress and estimate their next assessment outcome using the learning trajectory."},
 'engagement':{'required':['clicks_recent','active_days','inactive_days'],'explicit':'Estimate the next TMA score using clicks_recent, active_days and inactive_days.','ambiguous':"Has the learner lost momentum? Estimate their next assessment outcome using participation and study activity."},
 'readiness':{'required':['completion_rate','overdue_count','latest_score'],'explicit':'Estimate the next TMA score using completion_rate, overdue_count and latest_score.','ambiguous':"Help prepare the next intervention: is work keeping pace with assessment preparation? Estimate the next assessment outcome."}}
METHODS=['Original','TaskSlot','SafeTaskTopK','TrainMI','Repaired-Full','Repaired-no-projection','Repaired-no-attention','Repaired-no-bottleneck','Repaired-no-taskslot','StageRoleRule']
CFG={'projection_weight':.25,'temperature':.25,'privacy_lambda':.25,'slot_bonus':.08,'redundancy_penalty':.15,'token_cap':64}
def question(intent,wording,cutoff):return INTENTS[intent][wording]+f' Snapshot stage{cutoff}.'
