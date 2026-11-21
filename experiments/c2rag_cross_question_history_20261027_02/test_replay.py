"""Meaningful regressions for stage binding, signed work and history persistence."""
from fractions import Fraction as F
from experiments.c2rag_cross_question_history_20261027_02.observer import decode


def test_phase_binding_and_unit_only_text():
    assert decode('初始动能3.75 J。','T05')=={'K_initial':F(15,4)}
    assert decode('停止前动能95.75 J。','T08')=={'K_final':F(383,4)}
    assert decode('位移0.800 m。','T06')=={'d_push':F(4,5)}
    assert decode('1 J=1 kg·m²/s²。','T05')=={}
    assert decode('','T08')=={}


def test_signed_work_and_exact_speed_square():
    a=decode('分力功法：推力功96 J，摩擦功−4 J，重力和支持力功0，净功92 J。','T06')
    assert a=={'W_push':F(96),'loss_push':F(4),'W_net':F(92)}
    assert decode('末速平方383/60 m²/s²，速率约2.53 m/s。','T08')=={'v1_sq':F(383,60)}


def test_same_person_mass_and_later_energy_derive_terminal_speed():
    first=decode('质量30 kg。','T05');later=decode('停止前动能95.75 J。','T08')
    assert 2*later['K_final']/first['m']==F(383,60)
    assert 'K_final' not in first and 'm' not in later
