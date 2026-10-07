# 执行身份：Codex
"""有界返回协议、正文指针和一次拆分；不发请求。"""
import copy
import json
import math
import re

from pipeline_records25 import SECTIONS, flatten

PROTOCOL = 'bounded_delta_pointer_v28'
REPAIR_MAX_BYTES = 6000
REVIEW_PATCH_MAX_BYTES = 1024
REVIEW_CLAIMS_MAX_BYTES = 1024
REVIEW_CLAIM_MAX_BYTES = 128
REVIEW_VERDICT_MAX_BYTES = 128
OUTPUT_POLICY = {
    'B': {'estimated_peak': 6000, 'max_tokens': 9000},
    'A': {'estimated_peak': 2400, 'max_tokens': 3600},
    'J2': {'estimated_peak': 12000, 'max_tokens': 18000},
    'review': {'estimated_peak': 9000, 'max_tokens': 13500},
}


class OutputOverflow(ValueError):
    """完整结果无法放进协议上界；与截断相同，只能拆一次。"""


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def repair_message(error):
    instruction = ('机检失败：只修指出的坏项及同类字段错误，保留其他裁定、编号、判定和差量，'
                   '返回完整本包JSON。上次答案的转述不能当原文证据。错误详情：')
    message = {'role': 'user', 'content': instruction + error}
    # 预留按实际JSON字节计算，包含引号转义、消息封套和数组分隔符。
    if len(json.dumps(message, ensure_ascii=False).encode()) + 2 > REPAIR_MAX_BYTES:
        message['content'] = '机检失败，重新核对本包全部字段、编号和原文指针，再给完整JSON。'
    return message


def review_shape_error(ident, field, detail, material, entity='某人'):
    paragraph = next(iter(sentences(material)), None)
    example = {'entity': entity, 'p': paragraph, 's': 1}
    return json.dumps({'verdict_id': ident, 'field': field, 'error': detail,
                      'legal_pointer_example': example,
                      'note': '样例只示范指针；原句没有直接署名时speaker_claims填[]，reason只写核对结论。'},
                     ensure_ascii=False, separators=(',', ':'))


def sentences(material):
    result = {}
    for paragraph in material['paragraphs']:
        # 按原文连续切句；不改字、不丢空白，句号从1开始。
        chunks = re.findall(r'.*?[。！？\n]+|.+$', paragraph['text'], re.S)
        result[paragraph['paragraph_id']] = chunks or [paragraph['text']]
    return result


def pointer_payload(material):
    return [[p, [[i, text] for i, text in enumerate(parts, 1)]]
            for p, parts in sentences(material).items()]


def resolve_pointer(pointer, material):
    if not isinstance(pointer, dict) or set(pointer) != {'p', 's'}:
        raise ValueError('引用只允许段号和句号指针')
    p, number = pointer['p'], pointer['s']
    table = sentences(material)
    if p not in table or type(number) is not int or not 1 <= number <= len(table[p]):
        raise ValueError('段号或句号指针无效')
    return {'p': p, 'q': table[p][number - 1]}


def hydrate_j2(payload, material):
    if payload.get('overflow') is True:
        raise OutputOverflow('J2完整内容超出当前段组上界')
    if set(payload) != set(SECTIONS):
        raise ValueError('J2须只交八个栏目')
    if any(not isinstance(payload[k], list) for k in SECTIONS):
        raise ValueError('J2栏目须为数组')
    if sum(len(payload[k]) for k in SECTIONS) > 24 or size(payload) > 10800:
        raise OutputOverflow('J2超过24行或10800字节返回上界')
    result = copy.deepcopy(payload)
    for section in SECTIONS:
        if not isinstance(result[section], list):
            raise ValueError('J2栏目须为数组')
        for row in result[section]:
            if not isinstance(row, dict):
                raise ValueError('J2条目须为对象')
            if size(row) > 432:
                raise OutputOverflow('J2单行超过432字节，不截删内容')
            refs = row.get('ev')
            if not isinstance(refs, list) or not 1 <= len(refs) <= 2:
                raise ValueError('J2须给1至2个证据指针')
            row['ev'] = [resolve_pointer(p, material) for p in refs]
    return result


def review_bound(rows):
    return 128 + len(rows) * REVIEW_VERDICT_MAX_BYTES + REVIEW_PATCH_MAX_BYTES + REVIEW_CLAIMS_MAX_BYTES


def check_review_shape(value, rows, material):
    if value.get('overflow') is True:
        raise OutputOverflow('复核差量超出当前条目组上界')
    if set(value) != {'verdicts', 'patches'}:
        raise ValueError('复核只交裁定与差量，不回传全量')
    if not isinstance(value['verdicts'], list) or not isinstance(value['patches'], list):
        raise ValueError('复核裁定和差量须为数组')
    wanted = {r['_id'] for r in rows}
    verdicts = value['verdicts']
    if len(verdicts) != len(wanted) or {r.get('id') for r in verdicts} != wanted:
        raise ValueError('当前条目组复核漏项、错号或重复')
    if size(value['patches']) > REVIEW_PATCH_MAX_BYTES:
        raise OutputOverflow('修订差量超过1024字节')
    claims_size = 0
    result = copy.deepcopy(value)
    for verdict in result['verdicts']:
        if type(verdict.get('accept')) is not bool or not isinstance(verdict.get('reason'), str) or not verdict['reason']:
            raise ValueError('复核裁定缺布尔判定或理由')
        claims = verdict.get('speaker_claims')
        if not isinstance(claims, list):
            raise ValueError('复核缺说话归属检查栏')
        claims_size += size(claims)
        bare = {**verdict, 'speaker_claims': []}
        if set(verdict) != {'id', 'accept', 'reason', 'speaker_claims'} or size(bare) > REVIEW_VERDICT_MAX_BYTES:
            raise ValueError(review_shape_error(verdict['id'], 'reason',
                                 '复核单项裁定超过128字节或多交字段', material))
        hydrated = []
        for index, claim in enumerate(claims):
            field = 'speaker_claims[' + str(index) + ']'
            if not isinstance(claim, dict) or set(claim) != {'entity', 'p', 's'}:
                raise ValueError(review_shape_error(verdict['id'], field,
                                 '说话证明须给人物与段号、句号', material))
            if size(claim) > REVIEW_CLAIM_MAX_BYTES:
                raise ValueError(review_shape_error(verdict['id'], field,
                                 '单条说话证明超过128字节，拒收且不截删', material))
            if not isinstance(claim['entity'], str) or not claim['entity']:
                raise ValueError(review_shape_error(verdict['id'], field + '.entity',
                                 '说话主体须为非空字符串', material))
            table = sentences(material)
            if not isinstance(claim['p'], str) or claim['p'] not in table:
                raise ValueError(review_shape_error(verdict['id'], field + '.p',
                                 '段号或句号指针无效：p须为提交的段号字符串', material, claim['entity']))
            if type(claim['s']) is not int or not 1 <= claim['s'] <= len(table[claim['p']]):
                raise ValueError(review_shape_error(verdict['id'], field + '.s',
                                 '段号或句号指针无效：s须为该段内的句号整数', material, claim['entity']))
            hydrated.append({'entity': claim['entity'], **resolve_pointer({'p': claim['p'], 's': claim['s']}, material)})
        verdict['speaker_claims'] = hydrated
    if claims_size > REVIEW_CLAIMS_MAX_BYTES or size(value) > review_bound(rows):
        raise OutputOverflow('复核说话证明或整体返回超过上界')
    return result


def bounded_packets(role, material, payload, maximum, review=False):
    """先分有界输入，再为每包留至少40%的输出余量。"""
    if maximum != OUTPUT_POLICY['review' if review else role]['max_tokens']:
        raise ValueError('输出上限须使用v28余量表')
    ceiling = math.floor(maximum * 0.6)
    if review:
        rows = payload['rows']
        count = max(1, (ceiling - 128 - REVIEW_PATCH_MAX_BYTES - REVIEW_CLAIMS_MAX_BYTES) // REVIEW_VERDICT_MAX_BYTES)
        if any(len(str(r.get('_id', '')).encode()) > 32 for r in rows):
            raise ValueError('候选编号超过协议上界')
        groups, group, group_bytes = [], [], 2
        input_bound = payload.get('input_bound', 23000)
        for row in rows:
            row_bytes = size(row) + 1
            if row_bytes + 2 > input_bound:
                raise OutputOverflow('单条复核材料超过输入上界，不截删')
            if group and (len(group) >= count or group_bytes + row_bytes > input_bound):
                groups.append(group)
                group, group_bytes = [], 2
            group.append(row)
            group_bytes += row_bytes
        if group or not groups:
            groups.append(group)
        return [(material, {**payload, 'rows': group, 'protocol': PROTOCOL,
                           'output_bound': review_bound(group)}) for group in groups]
    if role != 'J2':
        return [(material, payload)]
    # 24行×432字节 + 八栏封套432字节 = 10800；恰为18000的60%。
    if ceiling < 10800:
        raise ValueError('J2输出余量不足')
    groups, group, weight = [], [], 0
    for p in material['paragraphs']:
        addition = len(p['text'].encode())
        if group and (len(group) >= 36 or weight + addition > 6000):
            groups.append(group)
            group, weight = [], 0
        group.append(p)
        weight += addition
    if group:
        groups.append(group)
    return [(dict(material, paragraphs=group), {**payload,
             'paragraphs': pointer_payload(dict(material, paragraphs=group)),
             'protocol': PROTOCOL, 'output_bound': 10800, 'max_rows': 24}) for group in groups]


def split_packet(material, payload, review):
    units = payload['rows'] if review else material['paragraphs']
    if len(units) < 2:
        raise OutputOverflow('单条或单段无法继续拆分')
    middle = len(units) // 2
    result = []
    for group in (units[:middle], units[middle:]):
        if review:
            result.append((material, {**payload, 'rows': group, 'output_bound': review_bound(group)}))
        else:
            child = dict(material, paragraphs=group)
            paragraphs = pointer_payload(child) if payload.get('protocol') == PROTOCOL else [[p['paragraph_id'], p['text']] for p in group]
            result.append((child, {**payload, 'paragraphs': paragraphs}))
    return result


def merge_values(role, values, review=False):
    if review:
        return {'verdicts': [r for v in values for r in v['verdicts']],
                'patches': [r for v in values for r in v['patches']]}
    fields = SECTIONS if role == 'J2' else ('rows',)
    result = {field: [row for v in values for row in v[field]] for field in fields}
    if role == 'B':
        result['unresolved'] = [row for v in values for row in v.get('unresolved', [])]
    return result
