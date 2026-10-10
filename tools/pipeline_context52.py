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

# 执行身份：Codex；116：只认完整的主语前缀结构，未命中不签，不以动词表兜底。
SUBJECT_ADVERB = r'(?:但|而|可|于是|随后|随即|此时|这时|忽然|突然|又|却|便|就|也|才|仍|还|只|正|正在|已经|终于|继续|低声|轻声|大声|冷冷|缓缓|慢慢|轻轻|赶紧|连忙|立刻|认真|平静|严肃|悄悄|说完|说罢|完|罢)'
SUBJECT_QUANTIFIER = r'(?:这|那|这个|那个|这一个|那一个|一)?(?:位|名|个)'
SUBJECT_LIMITER = r'(?:旁边|前面|后面|左边|右边|身旁|身边|门口|屋里|只有|唯有)'
# 执行身份：Codex；119：复用称谓资源，亲属按修饰、中心语和后缀构词。
def nominal_slot(value):
    if not 1 <= len(value) <= 8:
        return False
    if re.fullmatch(TITLE, value) or re.fullmatch(RELATIVE, value):
        return True
    # 整槽须解析完：支系/辈分修饰＋亲属中心语（单字或同字重叠）＋名词后缀。
    # 中心语之后只允许亲、子或亲属关系后缀，不允许任意汉字尾巴。
    kinship = (r'(?:[曾玄高太外堂表姻伯叔舅姑姨祖]*)(?:[一二三四五六七八九十大小老]+)?'
               r'(?P<root>[爸妈父母爹娘爷奶公婆伯叔舅姑姨兄哥姐弟妹嫂婶孙侄甥儿女夫妻媳婿])'
               r'(?:(?P=root)|[亲子]|[夫妇公婆男女娘])?')
    # 师承、家仆和店铺称谓限通用构词；既有职业名仍由 TITLE 识别。
    social = r'师[父母兄弟姐妹]|[家男女]仆|家丁|店[主员]|伙计|管家|掌柜|丈夫'
    return bool(re.fullmatch(kinship, value) or re.fullmatch(social, value))


def subject_prefix_allowed(prefix, named=(), base=0):
    lead=prefix.strip()
    adverbs=r'(?:'+SUBJECT_ADVERB+r')*'
    if re.fullmatch(adverbs,lead):return True
    qualifier=r'(?:(?:'+SUBJECT_QUANTIFIER+'|'+SUBJECT_LIMITER+r'))?'
    if re.fullmatch(adverbs+qualifier,lead):return True
    # 领属者＋的＋名词槽＋当前人名：领属者不是动作主体。
    if '的' in lead:
        owner,noun=lead.split('的',1)
        owners={h[3] for h in named if base<=h[0] and h[1]<=base+len(prefix)}
        owner_start = any(re.fullmatch(adverbs + re.escape(name), owner) for name in owners)
        owner_start = owner_start or bool(re.fullmatch(adverbs + r'(?:我|你|您|他|她|咱)(?:们)?', owner))
        if owner_start and nominal_slot(noun):
            return True
    # 前面已有代词主语，不能越过其述语，把后面的姓名改作主语。
    if re.match(adverbs+r'(?:我|你|您|他|她|它|咱|对方|那人|这人|有人|一人|众人|大家|旁人|(?:一个|一位|一名)(?:人|男人|女人|老人))',lead):
        return False
    # 姓名占据分句起点，且后面还有非领属成分，说明这里已有外层主语。
    for hit in named:
        if not base<=hit[0] or hit[1]>base+len(prefix):continue
        before=prefix[:hit[0]-base];after=prefix[hit[1]-base:]
        if re.fullmatch(adverbs,before.strip()) and after and not after.startswith('的'):
            return False
    if lead.endswith('的'):return True
    # 单独前置的职业标记沿用原识别；领属同位语不使用该表。
    return bool(re.fullmatch(adverbs+qualifier+TITLE,lead))


def clause_subject(clause, base, named, current_clause=False):
    for hit in reversed(named):
        if not base<=hit[0] or hit[1]>base+len(clause):continue
        prefix=clause[:hit[0]-base];tail=clause[hit[1]-base:]
        if tail.startswith('的'):continue
        boundary=base+clause.rfind('的')
        if hit[1]<=boundary and not any(hit[1]<=other[0] and other[1]<=boundary for other in named):
            # “的”后没有名词中心语，且紧接言说位：保留外层主语。
            # 有后置姓名时仍属歧义，不能借此恢复宾语错签。
            if not (tail.endswith('的') and tail[:-1] and not any(other[0]>hit[0] for other in named if other[1]<=base+len(clause))):
                continue
        if not subject_prefix_allowed(prefix,named,base):continue
        return hit
    return None


def has_speech_clause(text):
    """显式言说或叙述冒号引语；纯引语轮次不作为弃签屏障。"""
    plain=narration(text)
    if re.search(r'[^\s：:]\s*[:：]\s*[“「『"]',text):return True
    return any(not speech_trigger_excluded(plain,m) for m in SPEECH.finditer(plain))


def subject_before(plain, pos, named, continuous=False):
    # 执行身份：Codex；连续分句模式仅供 J2 证据组使用，旧调用保持原判法。
    if continuous:
        start=max(plain.rfind(c,0,pos) for c in '。！？\n')+1
        clauses=[(start+m.start(),m[0]) for m in re.finditer(r'[^，,；;：:]+',plain[start:pos])]
        previous=None
        for base,clause in clauses:
            local=[h for h in named if base<=h[0] and h[1]<=base+len(clause)]
            ref=re.match(r'\s*(?:'+SUBJECT_ADVERB+r')*(前者|后者|他|她|它)(?!们)',clause)
            if ref:
                antecedents=[h for h in named if start<=h[0]<base]
                unique=list(dict.fromkeys(h[2] for h in antecedents))
                if ref[1] in ('前者','后者') and len(unique)==2:
                    entity=unique[0 if ref[1]=='前者' else -1]
                    previous=next(h for h in antecedents if h[2]==entity)
                elif len(unique)==1:
                    previous=antecedents[-1]
                else:previous=None
                continue
            hit=clause_subject(clause,base,named,current_clause=True)
            if hit:previous=hit
            elif local and not all(re.search(SPEECH_OBJECT,plain[:h[0]]) for h in local):previous=None
            elif re.match(r'\s*(?:有人|另一个人|大家|众人|他们|她们)',clause):previous=None
        return previous

    start=max(plain.rfind(c,0,pos) for c in '。！？\n')+1
    clauses=[(start+m.start(),m[0]) for m in re.finditer(r'[^，,；;：:]+',plain[start:pos])]
    for base,clause in reversed(clauses):
        hit=clause_subject(clause,base,named,current_clause=base==clauses[-1][0])
        if hit:return hit
        # 本分句有姓名但结构不够明确时，不能再借上一分句的姓名署名。
        if any(base<=h[0] and h[1]<=base+len(clause) for h in named):return None
        if re.match(r'\s*(?:'+SUBJECT_ADVERB+r')*(?:我|你|您|他|她|它|咱)',clause):return None
        st=clause.lstrip(' 　')
        if re.match(r'(?:后者|前者)',st):
            prev=[x for x in named if start<=x[0]<base]
            return (prev[-1] if st.startswith('后者') else prev[0]) if prev else None
        anon=re.search(UNNAMED_SUBJECT,clause)
        if anon and len(clause[:anon.start()].strip(' 　'))<=3 and not re.search(SPEECH_OBJECT,clause[:anon.start()]):return None
    return None


def unique_continuation(spans, rows, plain, named):
    """执行身份：Codex；118：仅沿紧邻的明确说话人承接，不从任意邻句借名。"""
    if not spans or not rows:
        return False
    previous = rows[-1]
    explicit = [e for e in previous['evidence'] if e['method'] in ('直接署名', '引语后署名', '唯一承接署名')]
    speakers = {e['entity'] for e in explicit}
    if len(speakers) != 1 or set(previous['speaker']) != speakers:
        return False
    holder = next(iter(speakers))
    if set(previous['narrative_people']) - speakers or previous.get('unresolved_subjects'):
        return False
    for ev in spans:
        if ev['method'] not in ('主语延续', '代词承接') or ev['entity'] != holder:
            return False
        before = plain[:ev['offset']]
        # 代词前须有本段同一实名主语；上一轮发言者不能单凭距离替代指代证据。
        if ev['method'] == '代词承接':
            if {h[2] for h in named if h[1] <= ev['offset']} != speakers:
                return False
            named_clauses = [m for m in re.finditer(r'[^，,。！？；;：:]+', before)
                             if any(m.start() <= h[0] and h[1] <= m.end() for h in named)]
            last_clause = named_clauses[-1] if named_clauses else None
            subject = clause_subject(last_clause[0], last_clause.start(), named) if last_clause else None
            if subject is None or subject[2] != holder:
                return False
        if any(h[1] <= ev['offset'] and h[2] != holder for h in named):
            return False
        # 多个代词或复数主语不唯一；无名主体也会结束承接。
        if re.search(r'(?:^|[。！？；;，,])\s*(?:' + SUBJECT_ADVERB + r')*(?:' + UNNAMED_SUBJECT + r')', before) or re.search(r'(?:他|她|它)们', before):
            return False
        if len(set(re.findall(r'他|她|它', before))) > 1:
            return False
        # 引语起点的偏移包含本次言说词；只剥去紧挨引语的连续言说触发位。
        antecedent = before.rstrip(' ：:，,')
        for verb in reversed(list(SPEECH.finditer(antecedent))):
            if verb.end() == len(antecedent) and not speech_trigger_excluded(antecedent, verb):
                antecedent = antecedent[:verb.start()].rstrip(' ：:，,')
            else:
                break
        if any(not speech_trigger_excluded(antecedent, v) for v in SPEECH.finditer(antecedent)):
            return False
    for ev in spans:
        ev.update(method='唯一承接署名', antecedent_p=previous['p'],
                  antecedent_offset=explicit[-1]['offset'])
    return True


def speech_table(material, facts=(), entities=None, names=None, source_groups=False):
    """署名与对白轮次分开记录；推定轮次不能冒作直接署名证据。"""
    # 执行身份：Codex；J2 按引号定位连续跨度；其他调用仍返回旧对白表。
    if source_groups:
        from pipeline_output28 import sentences
        table=sentences(material)
        mapping={n:n for n in (names or person_pool(material,facts,entities))}
        units=[(p,n,t) for p,parts in table.items() for n,t in enumerate(parts,1)
               if t.strip('“”「」『』\"。！？\n \t')]
        groups=[];layouts={}
        def slices(pid, begin, end):
            result=[];offset=0
            for n,t in enumerate(table[pid],1):
                a,b=max(begin,offset),min(end,offset+len(t))
                if a<b:result.append([pid,n,a-offset,b-offset])
                offset+=len(t)
            return result
        pairs={'“':'”','「':'」','『':'』','‘':'’','"':'"',"'":"'"}
        for pi,para in enumerate(material['paragraphs']):
            pid=para['paragraph_id'];text=''.join(table[pid]);stack=[];opened=None;blocks=[]
            for at,char in enumerate(text):
                if stack and char==stack[-1]:
                    stack.pop()
                    if not stack:blocks.append((opened,at+1));opened=None
                elif char in pairs:
                    if not stack:opened=at
                    stack.append(pairs[char])
            if opened is not None:blocks.append((opened,len(text)))
            plain=list(text)
            for a,b in blocks:plain[a:b]=' '*(b-a)
            plain=''.join(plain);named=mentions(plain,mapping)
            layouts[pid]={'index':pi,'text':text,'plain':plain,'named':named,'blocks':blocks}
            for a,b in blocks:
                span=slices(pid,a,b);support=[];person=None;method=None
                # 当前引语前的叙述只能回到上一个引语末端，不能跨越另一轮发言。
                boundary=max([0]+[y for x,y in blocks if y<=a])
                prefix=plain[boundary:a]
                local=[(x-boundary,y-boundary,n,l) for x,y,n,l in named if x>=boundary and y<=a]
                subject=subject_before(prefix,len(prefix),local,continuous=True)
                anonymous_shift=bool(re.search(r'(?:见|看到|看见|望见)[^。！？]{0,8}(?:一个|一位|一名|有人)',prefix))
                if anonymous_shift:subject=None
                if subject and prefix[subject[1]:].strip(' ，,：:'):
                    person=subject[2];support=slices(pid,boundary+subject[0],a);method='attached_narration'
                if person is None and not anonymous_shift:
                    # 句号后的引语紧贴一条动作句；须只有一个明确人物且没有另一轮引语。
                    adjacent=[h for h in local if not prefix[:h[0]].strip()]
                    if len(local)==1 and adjacent and prefix[adjacent[0][1]:].strip(' ，,。！？：:'):
                        person=adjacent[0][2];support=slices(pid,boundary+adjacent[0][0],a);method='attached_action'
                if person is None:
                    after=plain[b:];post=mentions(after,mapping)
                    if post and not after[:post[0][0]].strip(' ，,') and SPEECH.match(after[post[0][1]:]):
                        person=post[0][2];support=slices(pid,b,b+post[0][1]+1);method='post_speech'
                body=text[a+1:b].rstrip('”」』’\"\'')
                identified=[h for h in mentions(body,mapping)
                            if re.fullmatch(r'\s*我(?:叫|是)',body[:h[0]])
                            and re.match(r'[，,。！？!？\s]|$',body[h[1]:])]
                if len(identified)==1 and (person is None or person==identified[0][2]):
                    person=identified[0][2];support=slices(pid,a+1,a+1+identified[0][1]);method='self_introduction'
                if person is None and a==0 and pi:
                    prev=material['paragraphs'][pi-1];prevtext=prev['text'];prevnamed=mentions(prevtext,mapping)
                    if not any(ch in prevtext for ch in pairs) and len(prevnamed)==1:
                        hit=prevnamed[0]
                        subj=clause_subject(prevtext,0,prevnamed)
                        # 接邻段动作或明示发言，禁止仅凭一个人名搭接。
                        if subj==hit and (re.search(HUMAN_ACTION,prevtext[hit[1]:]) or SPEECH.search(prevtext[hit[1]:])):
                            person=hit[2];support=slices(prev['paragraph_id'],0,len(''.join(table[prev['paragraph_id']])));method='adjacent_narration'
                keys={(p,n) for p,n,_,_ in span}
                indexes=[i for i,(p,n,t) in enumerate(units) if (p,n) in keys]
                nearby=units[max(0,min(indexes)-1):max(indexes)+2] if indexes else []
                candidate_basis={}
                for p,n,t in nearby:
                    for x,y,name,_ in mentions(t,mapping):candidate_basis.setdefault(name,[]).append([p,n,x,y])
                candidates=set(candidate_basis)
                if person:candidates.add(person)
                groups.append({'kind':'speech','span':span,'basis':support,'entity':person,
                               'method':method,'candidates':sorted(candidates),'candidate_basis':candidate_basis,
                               'start':a,'end':b,'closed':bool(text[b-1:b]==pairs[text[a]])})
        # 执行身份：Codex；甲档只接未闭引号。闭合的两轮发言不能靠相邻升级为甲。
        by_paragraph={p: [g for g in groups if g['span'][0][0]==p] for p in table}
        order=list(table)
        for group in groups:
            pid=group['span'][0][0];layout=layouts[pid];i=layout['index']
            previous=by_paragraph[order[i-1]] if i else []
            if (group['entity'] is None and group['start']==0 and previous
                    and previous[-1]['end']==len(layouts[order[i-1]]['text'])
                    and not previous[-1]['closed'] and previous[-1]['entity']):
                group.update(entity=previous[-1]['entity'],basis=previous[-1]['basis'],method='unclosed_continuation')
                group['candidates']=sorted(set(group['candidates'])|{group['entity']})
            group['tier']='program' if group['entity'] is not None else None
            group['model_basis']={};group['window']=order[max(0,i-1):i+2]
            if group['entity'] is not None or layout['plain'].strip():continue
            target=(i,group['start'])
            # 乙档来源只能是窗口内原本有署名的发言者或叙述主语。
            # 不能从前一段的模型推断、条目持有人或回忆锚点接力借名。
            def offer(name, point, basis):
                low,high=sorted((point,target))
                if any(low<(layouts[g['span'][0][0]]['index'],g['start'])<high
                       and g['entity'] and g['entity']!=name for g in groups):return
                group['model_basis'].setdefault(name,[])
                for piece in basis:
                    if piece not in group['model_basis'][name]:group['model_basis'][name].append(piece)
            for near in group['window']:
                info=layouts[near];ni=info['index']
                if not info['text'].strip():continue
                for origin in by_paragraph[near]:
                    # 只读原始同段署名；跨段承接得来的来源不是窗口内的实名。
                    if (origin is not group and origin['entity'] and origin['basis']
                            and all(piece[0]==near for piece in origin['basis'])):
                        offer(origin['entity'],(ni,origin['start']),origin['basis'])
                for clause in re.finditer(r'[^，,。！？!?；;：:]+',info['plain']):
                    hit=clause_subject(clause[0],clause.start(),info['named'],current_clause=True)
                    if hit:offer(hit[2],(ni,hit[0]),slices(near,hit[0],clause.end()))
            # 没有可读内容的隔段不构成对话窗口；不越过它寻找候选。
            if not layout['text'].strip():group['model_basis']={}
            for name,basis in group['model_basis'].items():
                group['candidate_basis'][name]=basis
            group['candidates']=sorted(set(group['candidates'])|set(group['model_basis']))
        return groups
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
        # 执行身份：Codex；118：唯一承接须有紧邻明确言说依据；其他弃签屏障保留。
        continuation = not unresolved_subjects and unique_continuation(spans, rows, plain, named)
        precision_rejected=bool(named or unresolved_subjects) and has_speech_clause(text) and not continuation and not any(e['method'] in ('直接署名','引语后署名') for e in spans)
        pending_speakers=[]
        if precision_rejected:
            pending_speakers.extend(persons);persons=[];spans=[]
        # 已存事实有显式上下文认定，仍标为候选，不伪造直接署名。
        if event and not persons and not unresolved_subjects and not precision_rejected:
            for f in facts:
                if not any(e.get('paragraph_id','').endswith(':'+p['paragraph_id']) for e in f.get('evidence',[])):continue
                hint=re.search(r'据上下文为([^）)；，。]+)',f.get('text',''))
                if hint and hint[1] in mapping:
                    persons=[mapping[hint[1]]];spans=[{'entity':persons[0],'offset':0,'method':'B上下文候选'}];break
        rows.append({'p':p['paragraph_id'],'speaker':list(dict.fromkeys(persons))[-1:], 'speech_event':event,
                     'recipients':list(dict.fromkeys(recipients)), 'evidence':spans,
                     'precision_rejected':precision_rejected,'pending_speaker_candidates':pending_speakers,
                     'dialogue':bool(spoken),'narration_length':len(plain.strip()),
                     'narrative_people':list(dict.fromkeys(h[2] for h in named)),
                     **({'unresolved_subjects':list(dict.fromkeys(unresolved_subjects))} if unresolved_subjects else {})})
        if named:last_person=named[0][2]
    # 111第3条引用的邻段明示：不跨段猜轮次，不从下段任意人名借署名。
    for i,row in enumerate(rows[:-1]):
        if row['speaker'] or not row['dialogue'] or row['precision_rejected']:
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
                    if row['precision_rejected']:
                        row['pending_speaker_candidates']=sorted(set(row['pending_speaker_candidates'])|other)
                    else:
                        row['speaker']=[next(iter(other))];row['evidence']=[{'entity':row['speaker'][0],'offset':0,'method':'双人轮次候选'}]
            if len(row['speaker'])==1:previous=row['speaker'][0]
        following=None
        for i in reversed(group):
            row=rows[i]
            if not row['speaker'] and following and not row.get('unresolved_subjects'):
                other=participants-{following}
                if len(other)==1:
                    if row['precision_rejected']:
                        row['pending_speaker_candidates']=sorted(set(row['pending_speaker_candidates'])|other)
                    else:
                        row['speaker']=[next(iter(other))];row['evidence']=[{'entity':row['speaker'][0],'offset':0,'method':'双人轮次候选'}]
            if len(row['speaker'])==1:following=row['speaker'][0]
    return rows

def memory_marks(material, entities=None, initial=False):
    paragraphs=material['paragraphs'];order={p['paragraph_id']:i for i,p in enumerate(paragraphs)}
    marked=set();open_block=initial;started=[]
    for i,p in enumerate(paragraphs):
        plain=narration(p['text']).strip()
        # Grok Bot 作业外 v111（外部审查③）：回到现场的退出条件对本章开启与跨章继承的回忆一视同仁，不再只认 initial。
        if re.fullmatch(r'[\s*＊—_－·。…]+',p['text']) or open_block and re.match(r'^(?:此时|这时|等|午饭|下午|晚上|“)',p['text']) and not re.search(r'自从|当初|以前|曾经',plain):
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
