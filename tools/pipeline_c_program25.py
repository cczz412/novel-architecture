# 执行身份：Codex
"""Conservative source-only C annotations; soft signals never confirm viewpoint."""
import re

INNER_SIGNALS = ('心想', '觉得', '以为', '意识到', '听见', '看到', '察觉', '发现')
ACTION = r'(?:站|坐|走|说|问|拿|放|吃|喝)'
CELLS = ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere')
SCENE_ACTION_FILTER_ENABLED = False
# 执行身份：Codex；115：只改变主标签，关态保留旧C作逐字对照。
GENERAL_TAG_RULES_ENABLED = True
EVALUATIVE_JUDGMENT = re.compile(r'不配|无可厚非|凭什么|不该|不应当|不应该|理应|本该')


def narration(text):
    return re.sub(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"', lambda m: ' ' * len(m[0]), text)


def separator(text):
    symbols=re.sub(r'\s', '', text)
    return len(symbols)>=2 and bool(re.fullmatch(r'[*＊—_－·~～-]+', symbols))


def scene_fragment_issues(material, scenes):
    """先核原文分句边界，再核缺尾；完整署名和完整声音分句不靠尾字判错。"""
    texts={p['paragraph_id']:p['text'] for p in material['paragraphs']};issues=[]
    for scene in scenes:
        for field in (*CELLS,'present'):
            for cell in scene.get(field,[]):
                for ev in cell.get('ev',[]):
                    value=ev.get('q','').strip();text=texts.get(ev.get('p'),'')
                    if not value or not re.search(r'(?:说|道|问|喊|答|拿|听到|听见|一声|的|把|将|被|向|和|与)$',value):continue
                    ends=[m.end() for m in re.finditer(re.escape(value),text)]
                    at_boundary=any(i==len(text) or text[i] in '，,。！？!?；;：:“”「」『』"\n' for i in ends)
                    speech_tag=bool(re.search(r'(?:说|道|问|喊|答)$',value) and at_boundary)
                    complete_sound=bool(re.search(r'(?:嗯|哼|应|叹|吼|喊|叫|笑|咳|啐|哎|唉)(?:了)?一声$',value) and at_boundary)
                    if speech_tag or complete_sound:continue
                    dangling=bool(re.search(r'(?:的|把|将|被|向|和|与|听到|听见)$',value))
                    if not at_boundary or dangling or value.endswith('一声'):
                        issues.append({'p':ev.get('p'),'field':field,'text':value,'reason':'分句未完整或尾部缺成分'})
    return issues


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


def scene_cells(text, p, memory=False):
    """按通用动作、方位与机构后缀取格；每格保留原句。"""
    cells={k:[] for k in CELLS}
    if memory:return cells
    plain=narration(text)
    location=[]
    short=bool(len(text)<=20 and re.fullmatch(r'(?:[\u4e00-\u9fff]{1,10}(?:村|大队|镇|县|乡|屯|庄|街)[，。]?)+',text))
    if short:location.append(text)
    patterns=[
        r'在([^，。！？的\s]{1,6}?)[上里下边](?!来|去|上班|工作|读书)',
        r'(?:回到|走进|进入|跑到|走到|来到|凑到|端上|抱上|端去|靠近|进)([^，。！？\s]{1,3}?)(?=边|里|前|[，。]|时|去|$)',
        r'(?:回到|走进|走出|进入|端去|进)([^，。！？\s]{1,8}?(?:屋|房|家|室|局|厅|院))',
        r'往[^，。！？]{0,12}?(?:的)?([^的，。！？]{2})里[走去]',
        r'混在([^，。！？]{1,5})里',
        r'^(?:此时[，,])?\s*([^，。！？]{1,28}(?:办公室|室|局|厅|院|宿舍|店|馆|楼|站))[，,]']
    for pattern in patterns:
        for m in re.finditer(pattern,plain):
            v=m[1]
            clause=re.split(r'[，,。！？]',plain[:m.start()])[-1]
            if re.search(r'差点|险些|几乎|假如|如果|仿佛|好像',clause):continue
            # 操作对象、远程媒介不是人物所在地点；按前后语法判，不列书内对象名。
            after=plain[m.end():]
            if pattern==patterns[0] and (re.match(r'(?:敲|打|输|键入|编辑|浏览|查询|播放|点击)',after)
                    or re.match(r'(?:点(?:了)?点头|摇(?:了)?摇头|说|问|答|交谈|聊天)',after)
                    and re.search(r'电|网|通讯|通话|频道|连线',v)):continue
            if len(v)==1 and m.end()<len(plain) and plain[m.end()] in '前边':v+=plain[m.end()]
            location.append(v)
    objects=[]
    patterns=[
        r'(?:拿着|拿起|拿上|拿出|拿|接过|收拾|带上|指着|围着|端着|端起|提着|扛着|背着|戴着|打开|按下|握住)([^，。！？：]{1,14}?)(?=的手|[，。！？、]|蹲|走|来|在|领|和|呵呵|笑|说|喊|问|答|朝|向|$)',
        r'(?:取|领|拎|抓)了(?:个|把|只|根|条)?([^，。！？]{1,6}?)(?=[，。！？]|$)',
        r'(?:添|盛|舀)了([^，。！？]{1,14}?)(?=后|[，。！？])',
        r'把([^，。！？]{1,12}?)(?:弄脏|弄湿)',
        r'(?:将|把)([^，。！？]{1,12}?)(?:扔|塞|折好|装袋)',
        r'(?:塞进|扔在)([^，。！？]{1,12}?)(?=[，。！？]|上|里|$)',
        r'递(?:过来)?(?:一份|一张|一个)?([^，。！？]{1,5}?)[，。]',
        r'按下([^，。！？]{1,6}?(?:键|开关|按钮))',
    ]
    for pattern in patterns:objects.extend(m[1] for m in re.finditer(pattern,text))
    def clean(value):
        value=re.sub(r'^(?:他|她|你|我)的','',value).strip()
        value=re.sub(r'^(?:将|把)','',value);value=re.sub(r'全都$','',value)
        return value if value and not re.search(r'他|她|你|我|没|了|多少|气势',value) and not re.match(r'的|去|来|对方|一[看听想问说]',value) else None
    for field,values in [('location',location),('objects_visuals',objects)]:
        for value in dict.fromkeys(values):
            v=clean(value)
            if field=='objects_visuals' and v and re.fullmatch(r'[上下左右前后里外旁边面]+',v):continue
            if field=='location' and v:
                if re.fullmatch(r'[上下左右前后里外旁边]+',v) or re.match(r'(?:一|两|几)(?:个|名|位|份|张)',v):continue
                # 地点后缀之后的动作不能连进地点格，不列书内专用动作词。
                noun=re.match(r'(.{0,28}(?:房间|办公室|屋|房|家|室|厅|院|局|楼|店|馆|站))',v)
                if noun:v=noun[1]
            if v and v in text:cells[field].append({'text':v,'ev':[{'p':p,'q':v}]})
    for m in re.finditer(r'([^，。！？]{1,4}?声)(?=响|[，。])|([^，。！？]{1,3}地一声)|(一声(?:厉喝|怒喝|大喊|尖叫|惊呼|叹息|咳嗽|轻笑|冷笑))|([\u4e00-\u9fff]{1,3}一声)',plain):
        value=next(g for g in m.groups() if g)
        # 心理/感官比喻不落成现场声音；向前看本句即可，不能借后句猜。
        sentence=re.split(r'[。！？]',plain[:m.end()])[-1]
        if re.search(r'(?:脑|心|意识|耳)[^。！？]{0,24}(?:嗡|轰|仿佛|好像|似乎)',sentence):continue
        # “一声+发声动作”要把动作保全，避免切出人物名字的尾巴。
        if value.endswith('一声'):
            vocal=re.match(r'厉喝|怒喝|大喊|尖叫|惊呼|叹息|咳嗽|轻笑|冷笑',plain[m.end():])
            if vocal:value='一声'+vocal[0]
        # 声音保留完整分句；截出的语气词/人物名尾巴不能独立成为场景格。
        left=max(text.rfind(c,0,m.start()) for c in '，,。！？；;')+1
        ends=[text.find(c,m.end()) for c in '，,。！？；;']
        right=min((i for i in ends if i>=0),default=len(text))
        value=text[left:right].strip()
        if value:
            cells['sounds_smells'].append({'text':value,'ev':[{'p':p,'q':value}]})
    return cells


def annotate(material, entities, facts=(), initial_memory=False, j2_complete=None):
    from collections import Counter
    from pipeline_context52 import person_pool, name_map, mentions, INNER, memory_marks
    names=person_pool(material,facts,entities);mapping=name_map(material,names,entities)
    memory=memory_marks(material,entities,initial_memory)
    paragraphs=material['paragraphs'];order={p['paragraph_id']:i for i,p in enumerate(paragraphs)}
    default='第一人称' if re.search(r'(?:^|[。！？\n])\s*我(?:的|们|在|走|说|看|想)','\n'.join(narration(p['text']) for p in paragraphs)) else '全知'
    binds={};last=None
    for p in paragraphs:
        plain=narration(p['text']);hits=mentions(plain,mapping)
        if p['paragraph_id'] in memory['paragraph_ids']:continue
        for sig in INNER.finditer(plain):
            near=[h for h in hits if h[1]<=sig.start() and sig.start()-h[1]<=10]
            if near:binds.setdefault(p['paragraph_id'],near[-1][2])
            elif last and re.search(r'(?:他|她|自己)[^。！？]{0,40}$',plain[:sig.start()]):binds.setdefault(p['paragraph_id'],last)
        if hits:last=hits[0][2]
    segments=[];segment=[]
    for p in paragraphs:
        new_scene=separator(p['text']) or re.match(r'^(?:此时[，,])?\s*[^，。！？]{1,28}(?:办公室|宿舍|会议室)[，,]',narration(p['text']))
        if new_scene and segment:segments.append(segment);segment=[]
        segment.append(p)
    if segment:segments.append(segment)
    viewpoints={}
    for segment in segments:
        local={p['paragraph_id']:binds[p['paragraph_id']] for p in segment if p['paragraph_id'] in binds}
        counts=Counter(local.values())
        character_mode=bool(counts and max(counts.values())>=2 and max(counts.values())/sum(counts.values())>=.6)
        current=next(iter(local.values()),default) if character_mode else default
        for p in segment:
            if separator(p['text']):current=default
            if character_mode and p['paragraph_id'] in local:current=local[p['paragraph_id']]
            viewpoints[p['paragraph_id']]=current
    receipts=[];accepted_blocks=[]
    for block in entities.get('memories',[])+entities.get('viewpoint_blocks',[]):
        start,end,person=block.get('start'),block.get('end'),block.get('viewpoint',block.get('person'))
        if start not in order or end not in order or order[start]>order[end]:
            receipts.append({'block':block,'adopted':False,'reason':'范围不在本章'});continue
        if not person:
            receipts.append({'block':block,'adopted':False,'reason':'未给人物视角'});continue
        evidence_rows=[]
        for row in paragraphs[order[start]:order[end]+1]:
            plain=narration(row['text'])
            if any(re.search(re.escape(n)+r'.{0,10}(?:'+INNER.pattern+')',plain) for n,v in mapping.items() if v==person):
                evidence_rows.append(row['paragraph_id'])
        accepted=bool(evidence_rows)
        receipts.append({'block':block,'adopted':accepted,'evidence_paragraphs':evidence_rows,'reason':'块内有持有人内心原句' if accepted else '缺引号外持有人证据'})
        if accepted:
            accepted_blocks.append(block)
            for row in paragraphs[order[start]:order[end]+1]:viewpoints[row['paragraph_id']]=person
    annotations=[];scenes=[];soft=[]
    # 111第6条：正文可独立给出的视角不依赖J2整岗成功；有证据的块仍逐块采用。
    # J2缺失只影响依赖它的块，不把全章覆写为未定。
    action=re.compile(r'(?:站|坐|走|说|问|拿|放|吃|喝|跑|抱|端|收拾|洗|捞|摸|拉|指|带|领|取|割|蹲|围|推|接|掏|抓|夹|扯|点头|添|靠近|递|打开|握住|签下)')
    for row in paragraphs:
        p,text=row['paragraph_id'],row['text'];plain=narration(text)
        dialogue=bool(re.search(r'“[^”]+”|「[^」]+」|『[^』]+』|"[^"\n]+"',text))
        actions=[]
        for hit in mentions(plain,mapping):
            m=re.match(r'(?:正|正在|已经|还|又|赶紧|便)?'+action.pattern,plain[hit[1]:])
            if m and hit[2] not in [a['entity'] for a in actions]:
                end=min((i for c in '，,。！？；;：:' if (i:=text.find(c,hit[1]+m.end()))>=0),default=len(text))
                actions.append({'entity':hit[2],'ev':[{'p':p,'q':text[hit[0]:end]}]})
        psy=bool(INNER.search(plain));cells=scene_cells(text,p,p in memory['paragraph_ids'])
        # 113：只在开关开启且确有人的动作时抑制地点名词误开场景。
        if SCENE_ACTION_FILTER_ENABLED and actions:
            transition=re.search(r'回到|走进|走出|进入|跑到|走到|来到|离开|前往|抵达|翌日|次日|第二天|此时|这时|随后|后来|过了|天亮|天黑',plain)
            if not transition:cells['location']=[]
        main='对话' if dialogue else '动作展开' if actions else '心理' if psy else '场景' if cells['location'] and len(text)<24 else '叙述带过'
        if GENERAL_TAG_RULES_ENABLED:
            judgment=bool(EVALUATIVE_JUDGMENT.search(plain))
            pronoun_action=bool(re.match(r'^\s*(?:他们|她们|他|她)(?:(?:正|正在|已经|还|又|赶紧|便|就|也|轻轻|慢慢|立刻|随即|忽然|突然)\s*)*'+action.pattern,plain))
            psy=psy or judgment
            if not dialogue:
                if judgment:main='心理'
                elif pronoun_action:main='动作展开'
        secondary='心理' if psy and main!='心理' else '动作展开' if dialogue and actions else None
        annotations.append({'p':p,'main_tag':main,'secondary_tag':secondary,'viewpoint':viewpoints[p],
                            'quote':text[:40],'note':'程序旁路0；采用的J2块有原段依据'})
        soft.extend({'p':p,'signal':m[0],'confirmed':False} for m in INNER.finditer(plain))
        if actions or any(cells.values()):
            scenes.append({'paragraph_ids':[p],**cells,'present':actions,'tags':[],'layer':'回忆' if p in memory['paragraph_ids'] else '现场'})
    return {'paragraphs':annotations,'scenes':scenes,'chapter_default':default,'soft_signals':soft,
            'method':'program','model_confirmations':0,'formal':False,'C_mode':'program_bypass0','j2_complete':j2_complete,'viewpoint_dependency':'正文独立判断；J2块逐块核证',
            'bypass0_receipt':{'adopted':sum(r['adopted'] for r in receipts),'rejected':sum(not r['adopted'] for r in receipts),
                               'blocks':receipts,'people':names,'viewpoint_blocks':accepted_blocks,'new_requests':0},
            'bypass1':{'enabled':False,'requests':0},'memory_marks':memory,
            'scene_receipt':{'count':len(scenes),'empty_reason':'没有格或人物动作' if not scenes else None}}
