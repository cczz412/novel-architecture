# 执行身份：Codex
"""从当前提供的事实与原段取人物、称谓和对白线索；不包含书内映射。"""
import re
import hashlib
import json
from collections import Counter

SURNAMES = '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀羊甄曲封储靳段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司黎薄印宿白怀蒲鄂索咸赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎连茹习艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公'
QUOTES = r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"'
TITLE = r'(?:副|大)?(?:书记|局长|厅长|县长|队长|主任|老师|医生|法医|警官|记分员|保管员|首长)'
RELATIVE = r'(?:老|亲|自家|我家|咱们|我|你|他|她)?(?:爸(?:爸)?|妈(?:妈)?|爹娘|父母|爷爷|奶奶|姥姥|姥爷|娘|爹|闺女|儿子|女儿|婆婆|媳妇|姑姑|小姑|大伯|[一二三四五六七八九十大]+(?:哥|姐|弟|妹|嫂|叔)|长辈|大人|老两口|两口子)'
HUMAN_ACTION = r'放|递|腰板|声音|死|病|勉强|说|问|答|喊|走|坐|站|拿|跑|抱|端|收拾|洗|摸|拉|指|带|领|取|蹲|围|推|接|掏|抓|夹|扯|点头|添|靠近|觉得|心想|知道|看|听|想|笑|冲|皱|安排|要求|穿|抬|瞪|眼|脸|身体|心头|脾气|性格'
INNER = re.compile(r'心想|觉得|认为|明白|知道|便知|以为|意识到|放(?:在)?心上|记在心头|铁了心|生怕|担心|心疼|理亏|心(?:上|头|里|中|底)|感觉|预感|猜测|暗想|不甘心|郁闷|无力感|发懵|考虑|气得|抓狂|(?:难道|莫非|怎(?:么|样)|哪有)[^。！？]*[？?]')
SPEECH = re.compile(r'说(?!法|服|明书|不定|起来)|(?<!知|通|铁|大|小)(?<!恶心)道(?!路|理|具|德)|问(?!题)|喊|答(?!案)|回应|开口|补充|解释|叮嘱|呵斥|提醒|招呼|劝|要求|嘱咐|追问|厉喝|嘶吼|回了一句|吐出一句|接听')
WITHDRAW = re.compile(r'却|作罢|收回|还是继续|没有|算了|好吧|咽了回去|没说出口|欲言又止|最终没|打断|挂断|没等|来不及')

def narration(text):
    return re.sub(QUOTES, lambda m:' '*len(m[0]), text)

def quotes(text):
    return re.findall(QUOTES, text)

def nonverbal_quote(value):
    """引号只是排版；完成态动作串与无言符号不提供确认署名证据。"""
    body=value[1:-1].strip()
    if not re.search(r'[\u4e00-\u9fffA-Za-z0-9]',body):return True
    # 人称自述、问句、命令和计划仍可能是真发言，保留原署名判法。
    if re.search(r'我|你|您|咱|[？?！!]|请|别|不要|不能|应该|要|得|会|想|打算',body):return False
    if SPEECH.search(body):return False
    actions=re.findall(r'走|跑|站|坐|拿|放|递|推|拉|抓|夹|送|抬|低|转|点头|摇头|挥手|伸手',body)
    return bool(re.search(r'了|着|过',body) and len(actions)>=2)

def person_pool(material, facts=(), entities=None):
    entities = entities or {}
    raw=set()
    for row in list(facts)+list(entities.get('people',[])):
        raw.update(row.get(k) for k in ('subject','entity','speaker') if isinstance(row.get(k),str))
        raw.update(n for n in row.get('mentions',[]) if isinstance(n,str))
    texts='\n'.join(p['text'] for p in material['paragraphs'])
    names=set()
    for n in raw:
        if not n or n in ('未知','无名','无名说话人') or re.search(r'所有|众人|大家|人们|们$|一家|夫妇|两口|[和与及、]',n):continue
        if re.fullmatch(RELATIVE,n):continue
        proper=2<=len(n)<=3 and n[0] in SURNAMES and '的' not in n and not re.search(r'(?:村|镇|县|乡|屯|庄|街|省|市|区|洞|水)$',n)
        descriptor=bool(re.fullmatch(r'(?:中年|年轻|老年|陌生|那个|那|这)?(?:男|女)?(?:男人|女人|老人|青年|警察|女警|法医)',n))
        title=bool(re.fullmatch(TITLE,n))
        if not (proper or descriptor or title or n.startswith('阿') and len(n)<=4):continue
        # 不能只因某物出现在事实主体里就当人物；证据须接人物动作/言语。
        behavior=[m for m in re.finditer(re.escape(n)+r'(?:正|正在|已经|还|又|赶紧|便|也|一|的)?(?:'+HUMAN_ACTION+r')',narration(texts))
                  if not re.search(r'(?:个|把|将|只|的|围着|拿着|指着|抱着|看向)$',texts[max(0,m.start()-4):m.start()])]
        if descriptor or n.startswith('阿') and behavior or proper and (len(n)>=3 or behavior or any(r.get('entity')==n for r in entities.get('people',[]))) or title:
            names.add(n)
    return sorted(names,key=lambda n:(-len(n),n))

def resolve_title(term, material, names, entities=None, paragraph=None):
    """固定别名优先；亲属关系、代词和歧义都不猜。"""
    entities=entities or {};term=str(term).strip()
    text='\n'.join(p['text'] for p in material['paragraphs'])
    local=next((p['text'] for p in material['paragraphs'] if p['paragraph_id']==paragraph),'')
    alias={r['entity'] for r in entities.get('aliases',[]) if r.get('alias')==term
           and r.get('entity') in names and r.get('confirmation_status') not in ('待核','拒收')
           and (not r.get('scope') or paragraph is None or paragraph in r['scope'])}
    if len(alias)==1:return {'referent':next(iter(alias)),'method':'J2 aliases','status':'已确认'}
    if len(alias)>1:return {'referent':None,'method':'J2 aliases 冲突','status':'待核'}
    proper=[n for n in names if n[0] in SURNAMES and len(n)>=2 or n.startswith('阿')]
    if term in proper and not re.search(TITLE+'$',term) and not re.search(r'哥$',term):return {'referent':term,'method':'R1','status':'已确认'}
    if re.search(r'(?:别的|其他|另一个)'+re.escape(term),local) or re.search(r'别的|其他|另一个|两个|再要|多少',term) or term in ('对方','他们家','这两口子','来人','大人','长辈','儿子'):
        return {'referent':None,'method':'语境称谓','status':'待核'}
    matches=set();method='R2'
    if re.fullmatch('['+SURNAMES+'](?:'+TITLE+'|哥|姐|叔|婶)',term):
        matches={n for n in proper if n[0]==term[0] and not re.search(TITLE+'$',n) and not n.endswith(('哥','姐','叔','婶'))}
        if not matches and term in names:matches={term}
        if not matches:matches={n for n in proper if n[0]==term[0] and re.search(TITLE+'$',n)}
    if len(matches)!=1:
        matches={n for n in proper if len(term)>=2 and len(n)>=3 and n[1:]==term and not re.fullmatch(r'[一二三四五六七八九十]嫂',term)};method='R3'
    if len(matches)!=1:
        matches=set();method='R4'
        for n in proper:
            # 同位语须连续，禁止同句任意共现便绑定。
            if (len(term)>=2 and re.search(re.escape(term)+re.escape(n),text)) or (re.fullmatch(TITLE,term) and re.search(re.escape(n)+r'，[^。！？\n]{0,30}'+re.escape(term)+r'[，。]',text)):
                matches.add(n)
    if len(matches)!=1 and re.fullmatch(r'(?:中年|年轻|老年|陌生)?(?:男人|女人|女警)',term):
        matches=set();method='R5'
        for i,p in enumerate(material['paragraphs']):
            if term not in p['text']:continue
            nearby=''.join(x['text'] for x in material['paragraphs'][max(0,i-1):i+2])
            choices={n for n in proper if n in nearby and re.search(TITLE,n)}
            if len(choices)==1:
                matches=choices;break
    if len(matches)!=1:
        method='R6';matches={n for n in proper if len(term)>=2 and n.endswith(term) and not re.fullmatch(r'[一二三四五六七八九十]嫂',term)}
    if len(matches)==1:return {'referent':next(iter(matches)),'method':method,'status':'已确认'}
    return {'referent':None,'method':'无法唯一定位','status':'待核'}

def name_map(material, names, entities=None):
    result={n:(resolve_title(n,material,names,entities)['referent'] or n) for n in names}
    for n in result:
        seen={n};target=result[n]
        while target in result and target not in seen:
            seen.add(target);target=result[target]
        result[n]=target
    for n in names:
        if len(n)>=3 and n[0] in SURNAMES:
            short=n[1:]
            if not re.fullmatch(TITLE,short) and sum(x.endswith(short) for x in names)==1:result[short]=result[n]
    for row in (entities or {}).get('aliases',[]):
        if row.get('entity') in names and row.get('alias'):
            answer=resolve_title(row['alias'],material,names,entities)
            if answer['referent']:result[row['alias']]=answer['referent']
    return result

def mentions(text, names):
    hits=[];occupied=set()
    for n,v in sorted(names.items(),key=lambda x:-len(x[0])):
        for m in re.finditer(re.escape(n),text):
            if re.match(r'办公室|院|职务|兼|局长',text[m.end():]) and re.fullmatch(TITLE,n):continue
            if any(i in occupied for i in range(m.start(),m.end())):continue
            hits.append((m.start(),m.end(),v,n));occupied.update(range(m.start(),m.end()))
    return sorted(hits)

SPEECH_EXCLUDED_WORDS = ('难道说', '难道', '莫非', '难不成', '莫不是', '怪不得', '难怪', '按说', '照说', '按理说', '照理说', '论理说', '应该说', '可以说', '换句话说', '也就是说', '就是说', '总的来说', '一般来说', '具体来说', '简单来说', '严格来说', '相对来说', '老实说', '说实话', '说实在的', '说真的', '说白了', '说到底', '说穿了', '话说回来', '不用说', '不消说', '比如说', '譬如说', '说明书', '说明', '小说', '学说', '传说', '解说词', '知道', '味道', '道理', '道路', '街道', '通道', '频道', '轨道', '隧道', '渠道', '管道', '跑道', '车道', '赛道', '走道', '过道', '地道', '霸道', '公道', '门道', '王道', '人道', '大道', '道具', '道德', '道士', '道观', '道长', '道家', '道教', '道法', '道袍', '一道', '两道', '几道', '这道', '那道', '问题', '学问', '疑问', '顾问', '问世', '问津', '答案', '报答', '据说', '听说', '传说中', '写道', '写着', '报道', '信上说', '书上说', '上面说', '上面写', '文件上说', '报纸上说', '新闻里说', '有人说')
SPEECH_INITIAL_WORDS = ('话说', '再说', '虽说', '要说', '且说', '却说')

# 执行身份：Codex；112：C1″结构主语、R1c与已采用C2词类。
SPEECH_OBJECT = r'(?:对|向|朝|冲着|对着|看向|看着|望着|回|让|叫|推了把|抱着|抱起|背着|拉着|指着|给|把|将|和|与|跟|被)$'
UNNAMED_SUBJECT = r'对方|那人|这人|有人|一人|一个人|一个|一位|一名|众人|大家|旁人'
C3N_ENABLED = False

def speech_trigger_excluded(plain, match):
    for word in SPEECH_EXCLUDED_WORDS:
        for hit in re.finditer(re.escape(word),plain):
            if hit.start()<=match.start() and match.end()<=hit.end():return True
    for word in SPEECH_INITIAL_WORDS:
        for hit in re.finditer(r'(?:^|[，,。！？!?；;：:、\s])('+re.escape(word)+')',plain):
            if hit.start(1)<=match.start() and match.end()<=hit.end(1):return True
    return False

def clause_subject(clause, base, named, current_clause=False):
    for hit in named:
        if not base<=hit[0] or hit[1]>base+len(clause):continue
        prefix=clause[:hit[0]-base];tail=clause[hit[1]-base:]
        if re.search(SPEECH_OBJECT,prefix) or tail.startswith('的'):continue
        # 执行身份：Codex；114：前置成分须能确认为句首状语，不能越过动作取宾语。
        lead=prefix
        # “某人的亲属／职务＋姓名”中取同位的姓名，前一姓名仍只是领属修饰。
        for prior in named:
            if base<=prior[0]<hit[0] and re.fullmatch(r'的(?:'+RELATIVE+'|'+TITLE+r')',clause[prior[1]-base:hit[0]-base]):
                lead=clause[:prior[0]-base];break
        adverb=r'\s*(?:(?:但|而|可|于是|随后|随即|此时|这时|忽然|突然|说完|说罢|完|罢)\s*)*'
        embedded=current_clause and re.fullmatch(adverb+r'(?:只|又|却)?(?:听|见)',lead)
        if not (re.fullmatch(adverb,lead) or embedded):continue
        # 无名主体已先出现时，后面的人名只能作候选，不能越过它取主语。
        anon=re.search(UNNAMED_SUBJECT,prefix)
        if anon and len(prefix[:anon.start()].strip())<=3 and not re.search(SPEECH_OBJECT,prefix[:anon.start()]):return None
        return hit
    return None

def subject_before(plain, pos, named):
    start=max(plain.rfind(c,0,pos) for c in '。！？\n')+1
    clauses=[(start+m.start(),m[0]) for m in re.finditer(r'[^，,；;：:]+',plain[start:pos])]
    for base,clause in reversed(clauses):
        hit=clause_subject(clause,base,named,current_clause=base==clauses[-1][0])
        if hit:return hit
        st=clause.lstrip(' 　')
        if re.match(r'(?:后者|前者)',st):
            prev=[x for x in named if start<=x[0]<base]
            return (prev[-1] if st.startswith('后者') else prev[0]) if prev else None
        anon=re.search(UNNAMED_SUBJECT,clause)
        if anon and len(clause[:anon.start()].strip(' 　'))<=3 and not re.search(SPEECH_OBJECT,clause[:anon.start()]):return None
    return None


def speech_table(material, facts=(), entities=None, names=None):
    """署名与对白轮次分开记录；推定轮次不能冒作直接署名证据。"""
    names=names or person_pool(material,facts,entities)
    mapping=name_map(material,names,entities)
    rows=[];last_person=None;fullplain=narration('\n'.join(p['text'] for p in material['paragraphs']));position=0
    for p in material['paragraphs']:
        text=p['text'];plain=fullplain[position:position+len(text)];position+=len(text)+1;named=mentions(plain,mapping)
        spans=[];persons=[];recipients=[];unresolved_subjects=[]
        quote_spans=list(re.finditer(QUOTES,text))
        nonverbal=[m for m in quote_spans if nonverbal_quote(m[0])]
        spoken=[m for m in quote_spans if m not in nonverbal]
        for match in spoken:
            prefix=plain[:match.start()];suffix=plain[match.end():]
            pre=mentions(prefix,mapping)
            subject_shift=bool(re.search(r'(?:见|看到|看见|望见)[^。！？]{0,8}(?:一个|一位|一名|有人)[^。！？]*[:：]\s*$',prefix))
            if subject_shift:pre=[]
            pre=[x for x in pre if not re.search(r'(?:对|向|朝|冲着|对着|看向|看着|望着|回|让|叫|推了把|抱着|抱起|背着|拉着|指着|给)$',prefix[max(0,x[0]-4):x[0]])]
            post=mentions(suffix,mapping)
            holder=None;method=None
            if re.search(r'[:：]\s*$',prefix) and pre:
                subject=subject_before(plain,match.start(),named)
                if subject:holder=subject[2];method='直接署名'
            elif post:
                lead=suffix[:post[0][0]].strip(' ，,。')
                if (not lead and not re.match(r'(?:死|被|已经死)',suffix[post[0][1]:])) or re.fullmatch(r'说完|后者|说罢|(?:公安|副)?'+TITLE,lead):
                    holder=post[0][2];method='引语后署名'
            if holder is None and re.search(r'[:：]\s*$',prefix) and not pre and not subject_shift and re.search(r'(?:他|她)[^。！？]*$',prefix) and last_person:
                holder=last_person;method='代词承接'
            if holder:persons.append(holder);spans.append({'entity':holder,'offset':match.start(),'method':method})
            q=match[0][1:-1]
            call=re.match(r'(?:嗯[，,、 ]*|说[，, ]*|明白[，, ]*)?([^，,。！？啊…]{1,8})(?:啊)?[，,！!]',q)
            if call:
                term=call[1];r=resolve_title(term,material,names,entities,p['paragraph_id'])
                if r['referent']:recipients.append(mapping.get(r['referent'],r['referent']))
                elif term in mapping:recipients.append(mapping[term])
        event=bool(spoken)
        for v in SPEECH.finditer(plain):
            if speech_trigger_excluded(plain,v):continue
            before=plain[:v.start()];after=plain[v.start():]
            if any(v.end()<=m.start() and re.fullmatch(r'[\s:：，,]*',plain[v.end():m.start()]) for m in nonverbal):continue
            if re.search(r'(?:没|不|别|想|听|据|传|所|啥也没|并未|没有|还想|(?:没|不|别|未|没有)[再多]{1,2})$',before) or re.match(r'开口就是',after) or re.match(r'说(?:不定|起来|服|法|明书)',after):continue
            if re.search(r'对(?:于)?[^。！？：:，,着过了走回跑\n]{1,12}?来$',before) and re.match(r'说(?:[，,、]|道理)',after):continue
            event=True
            # 106第9条：逗号后的复数亲属主语会结束前一实名主语的延续。
            # 只消费已有别名；亲属关系未确认时保留待核，不能借前句的人名。
            relatives=list(re.finditer(r'(?:^|[，,])((?:爸妈|父母|爹娘|老两口|两口子))(?=都|也|只|不|会|却|便|就)',before))
            if not persons and relatives and not any(x[0]>=relatives[-1].end() for x in named if x[1]<=v.start()):
                term=relatives[-1][1]
                resolved=resolve_title(term,material,names,entities,p['paragraph_id'])
                if resolved['referent']:
                    persons.append(resolved['referent']);spans.append({'entity':resolved['referent'],'offset':v.start(),'method':'亲属主语别名'})
                else:unresolved_subjects.append(term)
                continue
            subject=subject_before(plain,v.start(),named)
            if subject is None and not before.strip() and re.match(r'说(?:完|罢)',after):
                # 只取本分句或紧邻下一分句开头的主语，不再跨到更后的分句。
                parts=re.split(r'([，,；;：:。！？\n])',plain[v.end():],maxsplit=2)
                tail=parts[0]
                subject=clause_subject(tail,v.end(),named)
                if subject is None and len(parts)>=3 and parts[1] in '，,':
                    following=parts[2];base=v.end()+len(tail)+1
                    next_subject=clause_subject(following,base,named)
                    if (next_subject and not following[:next_subject[0]-base].strip()
                            and not re.search(r'被|遭(?:到|受)?',following)):
                        subject=next_subject
                if subject is None and rows and rows[-1]['dialogue'] and len(rows[-1]['speaker'])==1 and not mentions(tail,mapping):
                    holder=rows[-1]['speaker'][0]
                    persons.append(holder);spans.append({'entity':holder,'offset':v.start(),'method':'主语延续'})
            eligible=[subject] if subject else []
            if not persons and eligible:
                holder=eligible[-1][2];persons.append(holder);spans.append({'entity':holder,'offset':v.start(),'method':'直接署名'})
            elif not persons and re.search(r'(?:他|她|后者)[^。！？]{0,8}$',before) and last_person:
                persons.append(last_person);spans.append({'entity':last_person,'offset':v.start(),'method':'代词承接'})
            elif (not persons and not named and rows and not quotes(text)
                  and re.match(r'^(?:看到|见到|听到)',before) and re.search(r'[，,](?:便|就|会)[^。！？]{0,6}$',before)
                  and rows[-1]['speaker']==[last_person] and not rows[-1]['dialogue']):
                persons.append(last_person);spans.append({'entity':last_person,'offset':v.start(),'method':'主语延续'})
        if not event:
            call=re.search(r'叫([^，。！？]{1,8})(?:帮|来|去)',plain)
            if call:
                event=True
                prior=[h for h in named if h[1]<=call.start()]
                if prior:persons=[prior[-1][2]];spans=[{'entity':persons[0],'offset':call.start(),'method':'直接署名'}]
        # 已存事实有显式上下文认定，仍标为候选，不伪造直接署名。
        if event and not persons and not unresolved_subjects:
            for f in facts:
                if not any(e.get('paragraph_id','').endswith(':'+p['paragraph_id']) for e in f.get('evidence',[])):continue
                hint=re.search(r'据上下文为([^）)；，。]+)',f.get('text',''))
                if hint and hint[1] in mapping:
                    persons=[mapping[hint[1]]];spans=[{'entity':persons[0],'offset':0,'method':'B上下文候选'}];break
        rows.append({'p':p['paragraph_id'],'speaker':list(dict.fromkeys(persons))[-1:], 'speech_event':event,
                     'recipients':list(dict.fromkeys(recipients)), 'evidence':spans,
                     'dialogue':bool(spoken),'narration_length':len(plain.strip()),
                     'narrative_people':list(dict.fromkeys(h[2] for h in named)),
                     **({'unresolved_subjects':list(dict.fromkeys(unresolved_subjects))} if unresolved_subjects else {})})
        if named:last_person=named[0][2]
    # 111第3条引用的邻段明示：不跨段猜轮次，不从下段任意人名借署名。
    for i,row in enumerate(rows[:-1]):
        if row['speaker'] or not row['dialogue']:
            continue
        current=material['paragraphs'][i]['text'].strip()
        following=narration(material['paragraphs'][i+1]['text'])
        hits=mentions(following,mapping)
        anonymous_turn=bool(re.search(r'(?:见|看到|看见|望见)[^。！？]{0,8}(?:一个|一位|一名|有人)[^。！？]*[:：]\s*$',narration(current).rstrip()))
        introduced=[h for h in hits if not re.match(r'的',following[h[1]:])]
        if anonymous_turn and re.match(r'^(?:那人|这人|这个人|那个身影)',following) and len(introduced)==1:
            row['speaker']=[introduced[0][2]]
            row['evidence']=[{'entity':introduced[0][2],'offset':0,'method':'紧邻下段明示',
                              'support_p':material['paragraphs'][i+1]['paragraph_id']}]
            continue
        if not re.fullmatch(QUOTES,current):
            continue
        explicit=[h for h in hits if not following[:h[0]].strip()
                  and re.match(r'(?:说完|说罢)',following[h[1]:])]
        if len(explicit)==1:
            row['speaker']=[explicit[0][2]]
            row['evidence']=[{'entity':explicit[0][2],'offset':0,'method':'紧邻下段明示',
                              'support_p':material['paragraphs'][i+1]['paragraph_id']}]
    # 连续对白轮内两个人才补；长叙述断轮，呼语始终当受话人。
    groups=[];group=[];context=[];group_context=[]
    for i,row in enumerate(rows):
        if not row['dialogue'] and (row['narration_length']>40 or row['narration_length']>24 and len(row['narrative_people'])==2):
            if group:groups.append((group,group_context));group=[]
            context=row['narrative_people'] or context
        elif row['dialogue']:
            if not group:group_context=context
            group.append(i)
    if group:groups.append((group,group_context))
    for group,context in groups:
        participants=set(n for i in group for n in rows[i]['speaker']+rows[i]['recipients'])
        if len(participants)<2 and len(set(context)|participants)==2:participants.update(context)
        if len(participants)!=2:
            frequencies=Counter(n for i in group for n in rows[i]['speaker']+rows[i]['recipients'])
            if len(frequencies)>2 and frequencies.most_common()[1][1]>=2:
                participants={n for n,_ in frequencies.most_common(2)}
            else:continue
        previous=None
        for i in group:
            row=rows[i]
            if not row['speaker'] and not row.get('unresolved_subjects'):
                other=participants-set(row['recipients']) if row['recipients'] else participants-{previous} if previous else set()
                if len(other)==1:
                    row['speaker']=[next(iter(other))];row['evidence']=[{'entity':row['speaker'][0],'offset':0,'method':'双人轮次候选'}]
            if len(row['speaker'])==1:previous=row['speaker'][0]
        following=None
        for i in reversed(group):
            row=rows[i]
            if not row['speaker'] and following and not row.get('unresolved_subjects'):
                other=participants-{following}
                if len(other)==1:
                    row['speaker']=[next(iter(other))];row['evidence']=[{'entity':row['speaker'][0],'offset':0,'method':'双人轮次候选'}]
            if len(row['speaker'])==1:following=row['speaker'][0]
    return rows

def memory_marks(material, entities=None, initial=False):
    paragraphs=material['paragraphs'];order={p['paragraph_id']:i for i,p in enumerate(paragraphs)}
    marked=set();open_block=initial;started=[]
    for i,p in enumerate(paragraphs):
        plain=narration(p['text']).strip()
        if re.fullmatch(r'[\s*＊—_－·。…]+',p['text']) or initial and open_block and re.match(r'^(?:此时|这时|等|午饭|下午|晚上|“)',p['text']) and not re.search(r'自从|当初|以前|曾经',plain):
            open_block=False;initial=False
        if re.match(r'^(?:当初|自从|那时|以前|曾经|那年|小时候|[\u4e00-\u9fff]{1,4}自从)',plain):
            open_block=True;started.append(p['paragraph_id'])
        if open_block:marked.add(p['paragraph_id'])
    for b in (entities or {}).get('memories',[]):
        if b.get('start') in order and b.get('end') in order and order[b['start']]<=order[b['end']]:
            marked.update(p['paragraph_id'] for p in paragraphs[order[b['start']]:order[b['end']]+1])
    return {'paragraph_ids':sorted(marked),'open_at_end':open_block,'starts':started}

def entity_bindings(material, facts, entities=None):
    names=person_pool(material,facts,entities);rows=[]
    for fact in facts:
        for term in dict.fromkeys([fact.get('subject')]+fact.get('mentions',[])):
            if not isinstance(term,str) or not term:continue
            pids=[e['paragraph_id'].rsplit(':',1)[-1] for e in fact.get('evidence',[])]
            p=pids[0] if pids else None
            r=resolve_title(term,material,names,entities,p)
            rows.append({'fact_key':fact['local_key'],'term':term,**r,'paragraph_ids':pids,
                         'evidence':fact.get('evidence',[]),'version':1,
                         'binding_id':hashlib.sha256((fact['local_key']+'|'+term).encode()).hexdigest()[:24]})
    return {'execution_identity':'Codex','version':1,'book_id':material['book_id'],'chapter':material['chapter'],
            'rows':rows,'source_digest':hashlib.sha256(json.dumps(facts,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'real_model_requests':0,'original_facts_unchanged':True}
