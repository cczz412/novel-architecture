# 执行身份：Codex
"""Conservative source-only C annotations; soft signals never confirm viewpoint."""
import re

INNER_SIGNALS = ('心想', '觉得', '以为', '意识到', '听见', '看到', '察觉', '发现')
ACTION = r'(?:站|坐|走|说|问|拿|放|吃|喝)'
CELLS = ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere')


def narration(text):
    return re.sub(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"', lambda m: ' ' * len(m[0]), text)


def separator(text):
    return bool(re.fullmatch(r'[\s*＊—_－·。…]+', text))


def hard_evidence(material, person, quote, paragraph, aliases):
    row = next((r for r in material['paragraphs'] if r['paragraph_id'] == paragraph), None)
    if not row or quote not in row['text'] or quote not in narration(row['text']):
        return False
    names = {person, *(a for a, name in aliases.items() if name == person)}
    return any(re.match(re.escape(name) + r'(?:正|正在|已经|还|又)?', quote) for name in names)


def carry_blocks(material, default, blocks):
    """Accept only independently confirmed blocks with exact narration evidence."""
    order = {r['paragraph_id']: i for i, r in enumerate(material['paragraphs'])}
    accepted = []
    for block in blocks:
        if not block.get('confirmed'):
            continue
        if block.get('start') not in order or block.get('end') not in order or order[block['start']] > order[block['end']]:
            raise ValueError('镜头块范围错误')
        if not hard_evidence(material, block['person'], block['quote'], block['start'], block.get('aliases', {})):
            raise ValueError('镜头依据不在引号外或主体不一致')
        accepted.append(block)
    values, current = {}, default
    for row in material['paragraphs']:
        if separator(row['text']):
            current = default
        for block in accepted:
            if row['paragraph_id'] == block['start']:
                current = block['person']
        values[row['paragraph_id']] = current
        if any(row['paragraph_id'] == b['end'] for b in accepted):
            current = default
    return values


def annotate(material, entities):
    people = {r['entity'] for r in entities.get('people', []) if r.get('entity')}
    aliases = {r['alias']: r['entity'] for r in entities.get('aliases', []) if r.get('alias') and r.get('entity') in people}
    names = {name: name for name in people}
    names.update(aliases)
    # 本轮没有模型确认的镜头块；软线索只记录，不决定人物标签。
    body = '\n'.join(narration(r['text']) for r in material['paragraphs'])
    default = '第一人称' if re.search(r'(?:^|[。！？\n])\s*我(?:的|们|在|走|说|看|想)', body) else '全知'
    viewpoints = carry_blocks(material, default, [])
    annotations, scenes, soft = [], [], []
    for row in material['paragraphs']:
        p, text = row['paragraph_id'], row['text']; plain = narration(text)
        quote = text[:min(40, len(text))]
        dialogue = bool(re.search(r'“[^”]+”|「[^」]+」|『[^』]+』|"[^"\n]+"', text))
        actions = []
        for name, entity in sorted(names.items(), key=lambda item: -len(item[0])):
            match = re.search(re.escape(name) + r'(?:正|正在|已经|还|又)?' + ACTION, plain)
            if match and not any(a['entity'] == entity for a in actions):
                actions.append({'entity': entity, 'ev': [{'p': p, 'q': text[match.start():match.end()]}]})
        annotations.append({'p': p, 'main_tag': '对话' if dialogue else '动作展开' if actions else '叙述带过',
                            'secondary_tag': '动作展开' if dialogue and actions else None,
                            'viewpoint': viewpoints[p], 'quote': quote, 'note': '程序版；未确认内心候选不提升人物视角'})
        for signal in INNER_SIGNALS:
            if signal in plain:
                soft.append({'p': p, 'signal': signal, 'confirmed': False})
        # 明写的到达/所在地点才记格；不把愿望、将去、比喻补成已到场景。
        match = re.search(r'(?:正在|身处|走进|进入)([^，。！？；“”「」\s]{2,16})(?:里|内)', plain)
        cells = {name: [] for name in CELLS}
        if match:
            cells['location'] = [{'text': match[1], 'ev': [{'p': p, 'q': text[match.start():match.end()]}]}]
        if actions or match:
            scenes.append({'paragraph_ids': [p], **cells, 'present': actions, 'tags': [], 'layer': '未知'})
    return {'paragraphs': annotations, 'scenes': scenes, 'chapter_default': default, 'soft_signals': soft,
            'method': 'program', 'model_confirmations': 0, 'formal': False}
