# 执行身份：Codex
"""计划候选的原文位置保留立项章，当前状态与跨章承接由历史承担。"""
from pr_pipeline_r02 import assemble as legacy_assemble


def preserve_origin(document):
    changes=[]
    for h in document['review_audit']['plan_history']:
        origin=h.get('introduced_chapter')
        if not origin:continue
        for row in document['A']:
            if row.get('change_id') not in h.get('A_change_ids',[]) or not row.get('plan'):continue
            if row.get('as_of_chapter')!=origin:
                changes.append(dict(plan_key=h['plan_key'],change_id=row['change_id'],before=row.get('as_of_chapter'),after=origin,field='as_of_chapter'))
                row['as_of_chapter']=origin
    return changes


def assemble(result,chapter_result):
    legacy_assemble(result,chapter_result)
    preserve_origin(result)
    return result
