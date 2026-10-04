# 执行身份：Codex
"""只修输出形状，不补故事内容；错误位置用于最多一次格式重写。"""
import copy
import json
import re

BC_FIELDS = ('B', 'C', 'fact_chapters', 'source_chapters', 'review_flags')
A_FIELDS = ('A', 'old_plan_rows', 'plan_history', 'open_plan_keys', 'review_flags')
TAGS = ('叙述带过', '动作展开', '对话', '心理', '场景')
STATUSES = ('未执行', '执行中', '兑现', '落空', '放弃')

BC_SCHEMA = '''只输出以下五个顶层数组：{"B":[],"C":[],"fact_chapters":[],"source_chapters":[],"review_flags":[]}。
C 必须是数组，每项是本书本章对象；即使只有一个对象也写成 [{...}]。
B每行：change_id,book_id,chapter,operation(替换/新增),old_record_keys[],local_key,text,reason,evidence[{paragraph_id,quote}]。新增local_key用输入给定前缀；替换沿用原旧键。所有证据是完整段号与连续逐字短引。
C每项：book_id,chapter,paragraphs[],scenes[]。paragraphs每项：paragraph_id(短号),main_tag,secondary_tag,viewpoint,quote,review_status,note。
main_tag只能取叙述带过、动作展开、对话、心理、场景；secondary_tag为null或另一种不同标签。不能填B、C、发言、心声、人物判断等其他类别。viewpoint为感知者人物名、全知、切换或null，不能按说话人自动选。review_status为已标注或限审。
scenes每项：scene_id,paragraph_ids(短号数组),location[],light_weather[],objects_visuals[],sounds_smells[],atmosphere[]；五格每项{text,evidence:[{paragraph_id(完整号),quote}]}。
fact_chapters每项：book_id,chapter,kept_old_keys[],revised_old_keys[],excluded_nonstory_keys[],flagged_old_keys[]。
source_chapters每项：book_id,chapter,paragraphs:[{paragraph_id,fact_record_keys[],disposition,note}]。
review_flags每项：flag_id,book_id,chapter,category,fact_keys[],plan_keys[],paragraph_ids[],reason,conservative_text,original_gap_keys[]。
不能输出A和计划历史；不能把本章对象直接当成C值。即使某类没有内容也保留空数组。'''

A_SCHEMA = '''只输出以下五个顶层数组：{"A":[],"old_plan_rows":[],"plan_history":[],"open_plan_keys":[],"review_flags":[]}。
A每行：change_id,book_id,as_of_chapter,old_ledger_keys[],decision(沿用/修订/新增/撤回计划分类),subject_text,plan,candidate_refs,reason,evidence[{paragraph_id,quote}]。evidence每项是对象，不能把事实编号字符串直接塞入证据数组。
plan为null或{content,scope:"in_book_character",status,source_fact_ref:null,fulfilled_fact_ref:null,deadline:null或{text,story_time:null},condition:null或原话,condition_fact_ref:null}；status只能取未执行、执行中、兑现、落空、放弃。candidate_refs为null或{source_record_key,fulfilled_record_key,condition_record_key}。
old_plan_rows每项：old_key,meaning,plan_keys[],retained_native_field,note。
plan_history每项：plan_key,book_id,old_ledger_keys[],A_change_ids[],introduced_chapter,states[]；states每项chapter,status,source_record_key,fulfilled_record_key,condition_record_key,change_basis_record_keys[],note。仅列本章状态，早章由程序保留。
open_plan_keys仅含本书本章仍未执行或执行中的稳定计划键。
review_flags每项：flag_id,book_id,chapter,category,fact_keys[],plan_keys[],paragraph_ids[],reason,conservative_text,original_gap_keys[]。
不能输出B或C；事实引用须指向输入给出的有效事实键，缺失要标黄。即使没有计划也输出完整五数组。'''


def decode(response, fields):
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('结束状态不是stop，输出未完整；不拼接截断正文')
    text = choice.get('message', {}).get('content') or ''
    if not text.strip():
        raise ValueError('正文为空，不能用推理正文当候选')
    text = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', text)
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError('顶层必须是对象')
    obj = copy.deepcopy(obj)
    conversions = []
    if 'C' in fields and isinstance(obj.get('C'), dict):
        c = obj['C']
        if set(('book_id', 'chapter', 'paragraphs', 'scenes')).issubset(c) and isinstance(c['paragraphs'], list) and isinstance(c['scenes'], list):
            obj['C'] = [c]
            conversions.append('C的单章对象包为单元素数组，内部内容不变')
    for field in fields:
        if not isinstance(obj.get(field), list):
            raise ValueError('字段' + field + '必须是数组，实际为' + type(obj.get(field)).__name__)
    for field, required in (('B', ('local_key', 'text', 'old_record_keys')), ('A', ('change_id',)),
                            ('plan_history', ('plan_key', 'states', 'A_change_ids'))):
        if field not in fields:
            continue
        for index, row in enumerate(obj[field]):
            if not isinstance(row, dict):
                raise ValueError(field + '[' + str(index) + ']必须是对象')
            for key in required:
                if key not in row:
                    raise ValueError(field + '[' + str(index) + ']缺少字段' + key)
            if field in ('A', 'B') and any(not isinstance(e, dict) for e in row.get('evidence', [])):
                raise ValueError(field + '[' + str(index) + ']证据数组每项必须是含paragraph_id、quote的对象')
    if 'C' in fields:
        for ci, chapter in enumerate(obj['C']):
            if not isinstance(chapter, dict) or not isinstance(chapter.get('paragraphs'), list):
                raise ValueError('C[' + str(ci) + ']必须是含paragraphs数组的本章对象')
            for pi, paragraph in enumerate(chapter['paragraphs']):
                main, secondary = paragraph.get('main_tag'), paragraph.get('secondary_tag')
                if main not in TAGS or secondary is not None and (secondary not in TAGS or secondary == main):
                    raise ValueError('C[' + str(ci) + '].paragraphs[' + str(pi) + ']标签越界；主标签须从' +
                                     '/'.join(TAGS) + '选择，副标签为空或另一个不同标签')
    if 'A' in fields:
        for index, row in enumerate(obj['A']):
            if row.get('plan') and row['plan'].get('status') not in STATUSES:
                raise ValueError('A[' + str(index) + ']计划状态越界，只能取' + '/'.join(STATUSES))
    return obj, conversions
