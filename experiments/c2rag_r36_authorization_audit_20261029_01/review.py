"""One-pass, source-frozen audit; no controller or teaching generation is run."""
import csv
import io
import itertools
import json
import re
from collections import Counter

from experiments.c2rag_r36_authorization_audit_20261029_01.common import (
    OUT, PROJECT_ROOT, frozen, qualified, read, write,
)


def text(path):
    assert path in read('freeze.json')['source_sha256'], path
    return (PROJECT_ROOT / path).read_text(encoding='utf8')


def jsonl(path):
    return [json.loads(line) for line in text(path).splitlines() if line.strip()]


def anchor(path, marker, pointer=None):
    lines = text(path).splitlines()
    hits = [i for i, line in enumerate(lines, 1) if marker in line]
    assert hits, (path, marker)
    return {'path': path, 'lines': hits, 'marker': marker, 'pointer': pointer,
            'source_sha256': read('freeze.json')['source_sha256'][path]}


def csvout(name, rows):
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write(name, buf.getvalue())


def team_fields():
    """Read existing inline YAML nodes only. Not an authorization parser."""
    path = 'configs/teacher-teams.yaml'
    teams = {}
    current = None
    for line_no, line in enumerate(text(path).splitlines(), 1):
        match = re.fullmatch(r'  ([a-z_]+):', line)
        if match:
            current = match.group(1)
            teams[current] = []
        if 'view_fields:' in line:
            node = re.search(r'\{id: ([a-z_]+),', line)
            fields = re.search(r'view_fields: \[([^]]+)\]', line)
            assert current and node and fields
            teams[current].append({'id': node[1], 'line': line_no,
                                  'fields': [s.strip() for s in fields[1].split(',')]})
    result = []
    for name, nodes in teams.items():
        target = set().union(*(set(node['fields']) for node in nodes))
        witnesses = []
        minimum = None
        for k in range(1, len(nodes) + 1):
            witnesses = [list(g) for g in itertools.combinations(range(len(nodes)), k)
                         if set().union(*(set(nodes[i]['fields']) for i in g)) == target]
            if witnesses:
                minimum = k
                break
        result.append({'team': name, 'nodes': nodes, 'input_field_union': sorted(target),
                       'minimum_input_field_cover_nodes': minimum,
                       'minimum_cover_witnesses': [[nodes[i]['id'] for i in g] for g in witnesses],
                       'interpretation': 'STATIC_INPUT_FIELD_COVER_ONLY; not recipient/coalition knowledge coverage',
                       'runtime_parent_messages_included': False,
                       'coalition_authorization': 'UNKNOWN'})
    return result


def main():
    frozen()
    master = 'data/datasets/education_scenarios/teacher_resources.jsonl'
    layered = 'data/scenario_layers/teacher_resources/teacher_resources_v1.jsonl'
    first = jsonl(master)
    second = jsonl(layered)
    master_info = {
        'path': master, 'records': len(first),
        'digit_normalized_content_templates': len({re.sub(r'\d+', '#', r['content']) for r in first}),
        'content_character_lengths': [len(r['content']) for r in first],
        'copyright_label_counts': dict(Counter(r.get('copyright') for r in first)),
        'root_fields': sorted(set().union(*(set(r) for r in first))),
        'review': '30 short placeholder statements, not 30 substantive authored lesson documents; label is unverified',
    }
    layer_info = {
        'path': layered, 'records': len(second),
        'return_modes': dict(Counter(r['return_mode'] for r in second)),
        'copyright_levels': [r['copyright_level'] for r in second],
        'root_fields': sorted(set().union(*(set(r) for r in second))),
        'review': '10 short instructional prompts; source strings and numeric risk levels lack issuer/recipient bindings',
    }
    manifest = json.loads(text('data/datasets/manifest.json'))
    manifest_checks = [
        {'path': 'data/datasets/manifest.json', 'pointer': '/stats/teacher_resources',
         'declared': manifest['stats']['teacher_resources'], 'observed': len(first), 'status': 'MISMATCH'},
        {'path': 'data/datasets/manifest.json', 'pointer': '/stats/student_profiles',
         'declared': manifest['stats']['student_profiles'],
         'observed': len(jsonl('data/datasets/education_scenarios/student_profiles.jsonl')), 'status': 'MISMATCH'},
    ]
    pilot_paths = [p for p in read('freeze.json')['source_sha256']
                   if '/karc_pilot_20261025_v3/private/' in p and p.endswith('.json')]
    pilot = []
    for p in sorted(pilot_paths):
        obj = json.loads(text(p))
        pilot.append({'path': p, 'asset_id': obj['asset_id'], 'domain': obj['domain'],
                      'source_type': obj['source_type'], 'annotation': obj['annotation'],
                      'fact_policy': obj['copyright_and_permissions']['fact_policy'],
                      'real_issuer_evidence': 'SYNTHETIC_ONLY'})
    html = [r for r in read('file_scan.json') if r['suffix'] == '.html']
    openstax = {'cached_html_files': len(html),
                'license_named_files': sum('license' in r['path'].lower() for r in html),
                'unique_detected_source_urls': len({r['OpenStax_url_detected'] for r in html}),
                'cached_footer_CC_BY_NC_SA_4_0_files': sum(any('/by-nc-sa/4.0/' in s for s in r['license_links']) for r in html),
                'live_revalidation': False,
                'license_scope': 'cached page/footer links only; not an image-by-image clearance or exclusive access grant',
                'pages': [{k: r[k] for k in ['path', 'sha256', 'OpenStax_url_detected', 'license_links']} for r in html]}
    teams = team_fields()
    write('source_facts.json', {'master': master_info, 'layered': layer_info,
                              'manifest_checks': manifest_checks, 'pilot': pilot, 'OpenStax': openstax})
    write('static_input_field_covers.json', teams)

    # Explicit reviewer adjudication. These are not independently annotated truths.
    # A family is an inventory unit, never a count of independent teaching tasks.
    gates = ['real_teaching_origin', 'source_backed_principals', 'issuer_bound_permissions',
             'specific_restricted_target', 'normal_request_and_correct_candidates',
             'source_backed_answer_availability', 'coalition_authorization_semantics',
             'actual_cross_question_instance_binding']
    statuses = {
        'F01': ['NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F02': ['UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F03': ['SYNTHETIC_ONLY'] * 8,
        'F04': ['UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F05': ['UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F06': ['SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F07': ['SYNTHETIC_ONLY'] * 8,
        'F08': ['NOT_SUPPORTED', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F09': ['NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
        'F10': ['UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'NOT_SUPPORTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
    }
    reasons = {
        'F01': '30个数字归一后同模板的占位声明；teacher_original不是可追溯作者或授权签发记录，无实质标准答案。',
        'F02': '10条短题意/教学提示；source标签、copyright_level和return_mode并未给出持久接收者及实际签发权限，也不是经核准的多解答案。',
        'F03': '10个v1 episode与50个程序配对episode、10个synthetic profile及50个兼容profile；上下文流是设计描述，不是实际课堂交付日志；真实授权无证。',
        'F04': '30份raw history及30份processed语义是同组派生记录；存在合成生成脚本和数据最小化规则，真实性未独立验证；没有受限教师目标及对其签发的角色授权。',
        'F05': '8792个GSM8K及3个MATH题解条目；本地题答可见，但冻结副本缺完整许可证/版本链，也无受限实例/角色答案可用性；SUPPORTED仅指题答字段，未重评分8795题。',
        'F06': '35个缓存HTML，教材来源可追溯且含公开解法；公开数值题解不能改称秘密，没有真实教学接收者、限制目标和授权矩阵。',
        'F07': '20个AI辅助原创合成资产，文档明确人物、机构、实验虚构，权限为模拟；不是20份真实教学来源。',
        'F08': '6种实际配置的Agent团队；view_fields约束内部初始输入，不是机构给不同学生的资产授权，提示风格不等于同效用答案候选。',
        'F09': '应用示例实现服务器scope及单subject会话边界；demo可生成默认license/source标签，但标签并非原始授权证明，未绑定真实多接收者任务。',
        'F10': '10条inputs/decision/timestamp测试日志，缺真实课堂出处、授权签发者及独立核验的候选答案/持续知识目标。',
    }
    evidence = {
        'F01': [anchor(master, '"copyright"', '/copyright'), anchor(master, '"content"', '/content'),
                anchor('data/datasets/manifest.json', '"teacher_resources": 5', '/stats/teacher_resources')],
        'F02': [anchor(layered, '"return_mode"', '/return_mode'), anchor(layered, '"source"', '/source')],
        'F03': [anchor('scripts/build_episode_dataset.py', 'def build_generated_episodes'),
                anchor('scripts/build_episode_dataset.py', 'deterministic_stratified_rotation_v2'),
                anchor('data/scenario_layers/manifest.json', 'synthetic_profiles')],
        'F04': [anchor('scripts/generate_synthetic_multimodal_data.py', 'Synthetic'),
                anchor('data/processed/manifest.json', 'privacy_rule', '/privacy_rule')],
        'F05': [anchor('data/datasets/manifest.json', '公开基准')],
        'F06': [anchor('experiments/c2rag_r10_20261020_01/local_sources/college-physics-2e__7-2-kinetic-energy-and-the-work-energy-theorem.html', 'import-auto-id2521056'),
                anchor('experiments/c2rag_r10_20261020_01/local_sources/college-physics-2e__7-2-kinetic-energy-and-the-work-energy-theorem.html', 'import-auto-id1115429'),
                anchor('experiments/c2rag_r10_20261020_01/local_sources/college-physics-2e__7-2-kinetic-energy-and-the-work-energy-theorem.html', 'import-auto-id1997856')],
        'F07': [anchor('data/benchmarks/karc_pilot_20261025_v3/DATASET_CARD.md', '全部研究'),
                anchor('data/benchmarks/karc_pilot_20261025_v3/DATASET_CARD.md', '模拟')],
        'F08': [anchor('configs/teacher-teams.yaml', 'committee:'), anchor('configs/teacher-teams.yaml', 'view_fields:'),
                anchor('configs/teacher-prompts.yaml', '暂不')],
        'F09': [anchor('cogniguard/integrations/education.py', 'education_subject'),
                anchor('cogniguard/integrations/education.py', 'Education sessions belong'),
                anchor('cogniguard/applications/education/case_study.py', 'course_limited_license'),
                anchor('cogniguard/applications/education/classroom.py', 'educational_license')],
        'F10': [],  # All field pointers are in the redacted scan; no test input quotations exported.
    }
    audits = []
    scan = {r['path']: r for r in read('file_scan.json')}
    for family in read('source_selection.json'):
        fid = family['family']
        row = {'family': fid, 'name': family['title'], 'files': len(family['files']),
               'json_top_level_records': sum(scan[f['path']]['records'] for f in family['files']),
               **dict(zip(gates, statuses[fid])), 'reason': reasons[fid], 'evidence': evidence[fid]}
        row['qualified'] = qualified(row)
        audits.append(row)
    write('review_adjudications.json', {'reviewer': 'single research-assistant author review; no independent human labels',
                                       'family_inventory_not_task_denominator': True, 'families': audits})
    csvout('ROLE_AUTH_AUDIT.csv', [{k: v for k, v in row.items() if k != 'evidence'} for row in audits])
    csvout('SOURCE_REGISTER.csv', [{'family': f['family'], **item} for f in read('source_selection.json') for item in f['files']])
    availability = [
        {'source': 'OpenStax work-energy example', 'actual_alternatives': 'net-force work; sum of force-specific works',
         'same_task_evidence': 'source explicitly asks two approaches to the same net-work problem',
         'recipient_role_availability': 'UNKNOWN', 'restriction_origin': 'none in source; prior research simulated it',
         'menu_break': 'NOT_EVALUATED'},
        {'source': 'teacher team prompts/configuration', 'actual_alternatives': 'procedure/socratic/concept/visual roles',
         'same_task_evidence': 'prompt styles have different required outputs; same utility not established',
         'recipient_role_availability': 'internal input field configuration only; actual end-recipient grants UNKNOWN',
         'restriction_origin': 'configuration/demo; no asset-owner grant', 'menu_break': 'NOT_EVALUATED'},
        {'source': 'layered teacher_resources', 'actual_alternatives': 'return_mode labels',
         'same_task_evidence': 'no verified per-role list of correct concrete responses',
         'recipient_role_availability': 'UNKNOWN', 'restriction_origin': 'self-declared source labels',
         'menu_break': 'NOT_EVALUATED'},
        {'source': 'KARC Pilot v3', 'actual_alternatives': 'simulated unit/role contracts',
         'same_task_evidence': 'author-generated, not observed real teaching',
         'recipient_role_availability': 'SYNTHETIC_ONLY', 'restriction_origin': 'explicit simulated policy',
         'menu_break': 'EXCLUDED_FROM_REAL_SOURCE_CLAIM'},
    ]
    csvout('ANSWER_AVAILABILITY.csv', availability)
    write('decision.json', {
        'round': 'R36', 'status': 'EXPLORATORY', 'decision': 'ANALYZE',
        'question': 'source-backed non-covering <=3 coalition and fixed-menu break',
        'frozen_unique_files': len(read('freeze.json')['source_sha256']),
        'source_families': len(audits), 'qualified_real_task_contracts': 0,
        'certified_noncovering_real_tasks': 0, 'certified_menu_breaks': 0,
        'gap': None, 'gap_status': 'NOT_EVALUATED_NO_QUALIFIED_REAL_CONTRACT',
        'unknowns_retained': True, 'algorithms_run': [], 'new_algorithms': 0,
        'model_calls': 0, 'gpu_calls': 0, 'paid_api_calls': 0, 'data_downloads': 0,
        'claims_not_supported': ['no such real tasks exist anywhere', 'fixed menu is universally optimal',
                                 'six Agent nodes imply a noncovering unauthorized coalition',
                                 'source licenses imply exclusive answer permissions'],
        'next_single_step': 'Obtain one existing, owner/issuer-approved teaching-task contract: persistent recipients, asset grants, approved correct reply alternatives and actual delivery history. Do not alter roles to produce a gap.',
        'stop_after_sync': True,
    })
    assert not any(row['qualified'] for row in audits)
    frozen()
    print('Reviewed 10 frozen source families; qualified real-task contracts=0. No defense/OPT experiment run.')


if __name__ == '__main__':
    main()
