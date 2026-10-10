# 执行身份：Codex
"""虚构章节的作者视图；不发送请求。"""
import copy

import pytest

from pipeline_author25 import build_views


def fixture(mode, count=3):
    material = {'book_id': 'fictional133', 'chapter': '01', 'paragraphs': [
        {'paragraph_id': f'p{i:03}', 'full_id': f'fictional133:ch01:p{i:03}',
         'text': f'霁棠把第{i}盏灯交给闻澜。'} for i in range(1, count + 1)]}
    part = {'A_status': 'complete', 'B_status': 'complete', 'J2_status': 'complete',
            'C_status': 'complete', 'C': {'C_mode': mode, 'paragraphs': [
                {'p': p['paragraph_id'], 'viewpoint': '全知'} for p in material['paragraphs']],
                'scenes': []}, 'C_pending': []}
    return material, part


@pytest.mark.parametrize('mode', ['text_v110', 'viewpoint_evidence_v123'])
@pytest.mark.parametrize('case', ['one_missing', 'many_reasons', 'pending_only', 'complete',
                                  'mismatched', 'empty', 'yellow_row', 'duplicate', 'full_id', 'scene_field', 'malformed_pending'])
def test_c_view_completeness(mode, case):
    material, part = fixture(mode, 0 if case == 'empty' else 3)
    if case in ('one_missing', 'many_reasons', 'duplicate', 'full_id'):
        part['C']['paragraphs'] = part['C']['paragraphs'][:1 if case == 'many_reasons' else 2]
        part['C_pending'] = [{'paragraph_id': 'p003', 'reason': '正文段缺标注'}]
    if case == 'many_reasons':
        part['C_pending'] = [{'paragraph_id': 'p002', 'reason': '回包解析失败'},
                             {'paragraph_id': 'p003', 'reason': '预算用尽未投'}]
    if case == 'pending_only':
        part['C_pending'] = [{'paragraph_id': 'p002', 'reason': '上游未答'}]
    if case == 'mismatched':
        part['C_pending'] = [{'paragraph_id': 'p999', 'reason': '上游未答'}]
    if case == 'yellow_row':
        part['C']['paragraphs'][1].update(viewpoint_status='待核', viewpoint_pending_reason='依据不足')
    if case == 'duplicate':
        part['C_pending'] *= 2
    if case == 'full_id':
        part['C_pending'][0]['paragraph_id'] = 'fictional133:ch01:p003'
    if case == 'scene_field':
        part['C_pending'] = [{'level': 'field', 'row': '窗边', 'reason': '字段格式不符'}]
    if case == 'malformed_pending':
        part['C_pending'] = [{'level': 'paragraph', 'row': '坏格式', 'reason': '回包解析失败'}]
    before = copy.deepcopy(part)
    store = build_views([material], {'01': part})
    assert part == before
    status = store['view_status']['写法视角表']
    chapter = status['chapter_status']['01']
    if case != 'empty':
        assert store['view_status']['场景在场表']['status'] == '完整'
        assert store['view_status']['用餐在场表']['status'] == '完整'
    if case in ('complete', 'scene_field'):
        assert status['status'] == '完整'
        assert status['pending_count'] == status['missing_count'] == 0
    elif case == 'empty':
        assert status['status'] == '未完成'  # 空章沿用旧显示。
        assert status['pending_count'] == status['missing_count'] == 0
    else:
        assert status['status'] != '完整'
        assert status['pending_count'] == (2 if case == 'many_reasons' else 1)
        assert status['missing_count'] == (2 if case == 'many_reasons' else 1 if case in ('one_missing', 'duplicate', 'full_id') else 0)
        assert '不完整' in status['label']
        if case in ('mismatched', 'malformed_pending'):
            assert ('p999' if case == 'mismatched' else '未提供段号') in status['label']
            assert '原因未知' in status['label']
            assert chapter['unmatched_pending_count'] == 1
        elif case == 'many_reasons':
            assert chapter['reason_groups'] == [
                {'reason': '回包解析失败', 'count': 1, 'paragraph_ids': ['p002']},
                {'reason': '预算用尽未投', 'count': 1, 'paragraph_ids': ['p003']}]
        else:
            assert ('p002' if case in ('pending_only', 'yellow_row') else 'p003') in status['label']
