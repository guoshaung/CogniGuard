"""Decode actual delivered teaching text by role/unit; no controller labels/gold."""
from fractions import Fraction as F
import re


def decode(text,task_id):
    if not text:return {}
    s=text.replace('−','-')
    number=r'(-?\d+(?:\.\d+)?(?:/\d+)?)'
    def grab(pattern):
        m=re.search(pattern,s)
        if not m:raise ValueError('UNSUPPORTED_REPLY: '+text)
        return F(m.group(1))
    if s.startswith('1 J='):
        return {}  # Unit identity is not a package mass or measured energy.
    if s.startswith('净力法：'):
        return {'F_net':grab('净力'+number+r'\s*N'),'d_push':grab('位移'+number+r'\s*m'),
                'W_net':grab('净功'+number+r'\s*J')}
    if s.startswith('分力功法：'):
        return {'W_push':grab('推力功'+number+r'\s*J'),'loss_push':-grab('摩擦功'+number+r'\s*J'),
                'W_net':grab('净功'+number+r'\s*J')}
    if s.startswith('质量'):return {'m':grab('质量'+number+r'\s*kg')}
    if s.startswith('初始速率'):return {'u0_sq':grab('初始速率'+number+r'\s*m/s')**2}
    if s.startswith('初始动能'):return {'K_initial':grab('初始动能'+number+r'\s*J')}
    if s.startswith('水平净力'):return {'F_net':grab('净力'+number+r'\s*N')}
    if s.startswith('推力功'):return {'W_push':grab('推力功'+number+r'\s*J')}
    if s.startswith('位移') and task_id=='T06':return {'d_push':grab('位移'+number+r'\s*m')}
    if s.startswith('净功'):return {'W_net':grab('净功'+number+r'\s*J')}
    if s.startswith(('末态动能','停止前动能')):return {'K_final':grab('动能'+number+r'\s*J')}
    if s.startswith('摩擦力'):return {'f':grab('摩擦力'+number+r'\s*N')}
    if s.startswith('末速平方'):return {'v1_sq':grab('末速平方'+number+r'\s*m²/s²')}
    raise ValueError('UNKNOWN_REPLY: '+text)
