#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch08 空样本候选落盘脚本 v2：修正切窗到 700-900 字区间"""
import json, hashlib, os

BATCH_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BATCH_DIR, "raw")
SEG_DIR = os.path.join(BATCH_DIR, "segments")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(SEG_DIR, exist_ok=True)

CANDIDATES = [
    {
        "candidate_id": "DS08-001",
        "title": "1977：开局相亲女儿国王", "author": "天不负01", "platform": "起点中文网",
        "genre": "都市年代", "chapter": "第4章 七十年代从啃老开始",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/05_感情关系/1977：开局相亲女儿国王",
        "chapter_file": "004_第4章 七十年代从啃老开始.txt",
        "seg_start": "李长河没有着急去百货商店", "seg_end": "可以，太可以了",
        "judge": "PASS_SPARSE", "confidence": "high",
        "selection_reason": "李长河进新华书店，售货员带去库房找到65年最后一批高中教材（数学语文政治地理）。纯买书日常，硬事实约1条（买教材备战高考），无新身份/关系/资源/出口钉子。切窗避开开头海淀地理介绍和后续买数理化丛书及报刊。",
        "secondary_tags": ["sparse_1to2_facts_ok", "都市年代", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-002",
        "title": "1977：开局相亲女儿国王", "author": "天不负01", "platform": "起点中文网",
        "genre": "都市年代", "chapter": "第11章 莫谈国事",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/05_感情关系/1977：开局相亲女儿国王",
        "chapter_file": "011_第11章 莫谈国事！.txt",
        "seg_start": "与此同时，李长河他们点的餐也开始上了", "seg_end": "朱啉微微有些不满",
        "judge": "PASS_SPARSE", "confidence": "high",
        "selection_reason": "李长河与朱啉在老莫餐厅吃饭，李长河熟练切牛排剥虾挑虾线给朱啉，聊作家赚钱（卢梭伏尔泰巴尔扎克柳永司马相如靠吃软饭）。纯饭桌闲聊，硬事实约0条（无新身份/关系定锚，感情推进属软）。切窗避开开头老者搭话和结尾老者挖坑。",
        "secondary_tags": ["sparse_1to2_facts_ok", "都市年代", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-003",
        "title": "7号基地", "author": "净无痕", "platform": "起点中文网",
        "genre": "科幻游戏", "chapter": "第13章 告别",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/06_系统关卡/7号基地",
        "chapter_file": "013_第13章 告别.txt",
        "seg_start": "走到楼顶，只见米亚坐在椅子上弹奏着", "seg_end": "许末闭上眼睛",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "楼顶用餐时米亚问白薇救她的人会不会在附近，米亚弹乐器唱歌，许末哼《风之谷》米亚弹奏。夜晚休闲与情感交流，硬事实约0-1条（米亚多愁善感属人物特质，软）。无新身份/资源/出口钉子。切窗避开前半段白薇求职（含白薇留任硬钉子）和结尾许末回忆过去告别。",
        "secondary_tags": ["sparse_1to2_facts_ok", "科幻游戏", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-004",
        "title": "1987我的年代", "author": "树下和尚", "platform": "起点中文网",
        "genre": "都市年代", "chapter": "第8章 山水有时",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/05_感情关系/1987我的年代",
        "chapter_file": "008_第8章 ，山水有时.txt",
        "seg_start": "二姐渴了吧，来，喝杯水", "seg_end": "上湾村处于雪峰山脉山腰位置",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "李恒重生后主动给二姐李兰倒水献殷勤，父母李建国（脊椎病愧疚）与田润娥的家庭日常反应，李建国去陈家帮忙，李兰去打猪草。纯家庭琐事，硬事实约0条（家庭关系前章已交代，本段无新身份/出口钉子）。切窗避开后半段进山砍柴遇杨应文（新角色登场）。",
        "secondary_tags": ["sparse_1to2_facts_ok", "都市年代", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-005",
        "title": "一品特工祸妃", "author": "MS陌陌", "platform": "潇湘书院",
        "genre": "女频古言", "chapter": "第21章 美味烧鸡",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/07_历史世界规则/一品特工祸妃",
        "chapter_file": "021_021美味烧鸡.txt",
        "seg_start": "云无暇深夜才归", "seg_end": "月洛命人都散了",
        "judge": "PASS_SPARSE", "confidence": "high",
        "selection_reason": "傻王云无暇深夜带回醉楼烧鸡，把烧鸡捂怀里保温（里衣油渍），月洛吃鸡腿感动，让鱼子侍候云无暇沐浴。纯夫妻日常互动，硬事实约0条（感情推进属软，云无暇身份前章已定锚）。无新身份/关系/资源钉子。切窗避开沐浴后洞房玩笑。",
        "secondary_tags": ["sparse_1to2_facts_ok", "女频古言", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-006",
        "title": "伊塔之柱", "author": "寂静之翔", "platform": "起点中文网",
        "genre": "奇幻西幻", "chapter": "第8章 旅者之憩",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/06_系统关卡/伊塔之柱",
        "chapter_file": "0025_第八章 旅者之憩.txt",
        "seg_start": "雾气中笼罩着这样一个庞然大物", "seg_end": "她又回过头对艾德说道",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "方鸻一行抵达旅者之憩旅店，描写沼泽上旅店萧瑟景色、生锈的剑、篝火边老卫兵米奈斯、栈桥上冒险者与天蓝打招呼（干掉大姐头的玩笑）。整段以写景和寒暄为主，硬事实约1条（旅者之憩地点）。切窗避开后续职衔等级系统详细说明（硬世界规则）。",
        "secondary_tags": ["sparse_1to2_facts_ok", "奇幻西幻", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-007",
        "title": "光明壁垒", "author": "会说话的肘子", "platform": "起点中文网",
        "genre": "都市奇幻", "chapter": "第15章 余额",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/06_系统关卡/光明壁垒",
        "chapter_file": "0015_第15章 余额.txt",
        "seg_start": "公寓处于市中心的繁华地带", "seg_end": "顾慎没有犹豫",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "顾慎去大型超市采购，粉红滑轮机器人导购，看全息眼镜（12999）和头盔（39999）太贵，最终买平价无线耳机（200元），结账556.5元。纯逛超市购物日常，硬事实约0-1条（买耳机属行动铺陈）。切窗避开开头逃脱计划分析和结尾查余额五十万（新资源硬钉子）。",
        "secondary_tags": ["sparse_1to2_facts_ok", "都市奇幻", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-008",
        "title": "为什么它永无止境", "author": "柯遥42", "platform": "晋江文学城",
        "genre": "悬疑科幻", "chapter": "第15章 朗读",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/04_悬疑信息差/为什么它永无止境",
        "chapter_file": "0015_第15章 朗读.txt",
        "seg_start": "于是，赫斯塔低声念起书来", "seg_end": "赫斯塔能闻见从身后厨房传来的奶酪和面包的香味",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "赫斯塔给莉兹和图兰朗读爱伦坡《兰多的房间》，莉兹从声音感受到深情，图兰睡着，两人移步阳台看深夜谭伊市春寒景色。整段是读书与夜话写景，硬事实约0条（无新身份/关系/规则钉子）。切窗避开后续14型选拔规则、千叶监护令等世界设定说明。",
        "secondary_tags": ["sparse_1to2_facts_ok", "悬疑科幻", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-009",
        "title": "帝国吃相", "author": "牧尘客", "platform": "起点中文网",
        "genre": "历史穿越", "chapter": "第7章 吃饭和住宿",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/02_群像多线/帝国吃相",
        "chapter_file": "0007_第7章 吃饭和住宿.txt",
        "seg_start": "拿着这把焕然一新的匕首", "seg_end": "陈旭激动不已的在河边就着河水洗脸漱口之后",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "陈旭夜里打磨青铜匕首，规划吃饭（捕鱼）和住宿（修房）问题，第二天清晨去河边收鱼篓得半篓鱼。纯生存日常，硬事实约0-1条（青铜匕首资源前章已有）。无新身份/关系/出口钉子。切窗避开开头给小妹起名（定锚）和青铜器历史科普。",
        "secondary_tags": ["sparse_1to2_facts_ok", "历史穿越", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-010",
        "title": "帝国吃相", "author": "牧尘客", "platform": "起点中文网",
        "genre": "历史穿越", "chapter": "第11章 一天两顿",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/02_群像多线/帝国吃相",
        "chapter_file": "0011_第11章 一天两顿.txt",
        "seg_start": "除草吧，陈旭认命了", "seg_end": "但也清爽了许多",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "陈旭与母亲陈姜氏、小妹杏儿在田间除草一整天的劳动日常，三人汗透、杏儿小手受伤不叫嚷、清理五亩田。纯农活日常，硬事实约0条。切窗避开前半段秦朝亩产/田税/丁税等世界规则说明（硬设定）。",
        "secondary_tags": ["sparse_1to2_facts_ok", "历史穿越", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-011",
        "title": "2002谁说北电无大导", "author": "睡觉会变白", "platform": "起点中文网",
        "genre": "都市现言", "chapter": "第14章 陈砚挨批评了",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/05_感情关系/2002谁说北电无大导",
        "chapter_file": "14_第十四章 陈砚挨批评了.txt",
        "seg_start": "你还知道回来啊", "seg_end": "赵长林拿到剧本是饭也不吃了",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "陈砚去舅舅赵长林家吃饭，舅舅批评他抵押房子拍电影（200多万），追打后看剧本认可，舅妈王鹤夹菜劝和。家庭吃饭日常，硬事实约1条（抵押房子拍电影属背景铺陈，舅舅身份前段已交代）。切窗避开开头电影营销和结尾中影投资话题。",
        "secondary_tags": ["sparse_1to2_facts_ok", "都市现言", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-012",
        "title": "你们修仙，我种田", "author": "停电 shields", "platform": "起点中文网",
        "genre": "玄幻种田", "chapter": "第26章 编草",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/01_单主角升级线/你们修仙，我种田",
        "chapter_file": "0026_第26章 编草.txt",
        "seg_start": "他离开灵泉，巡视着灵田里的一切", "seg_end": "在灵田巡视一番后，陆玄便打开阵法",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "陆玄巡视灵田各灵植（血玉参、灵萤草、剑草、赤云松、暗髓芝）状态，给草傀儡喂灵石修复胸口大洞（两根灰草编织填补）。纯种田养护日常，硬事实约0-1条（草傀儡修复属资源状态变化，软）。无新身份/关系/出口钉子。切窗避开开头红须鲤入灵泉和结尾去集市买菜请客。",
        "secondary_tags": ["sparse_1to2_facts_ok", "玄幻种田", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-013",
        "title": "7号基地", "author": "净无痕", "platform": "起点中文网",
        "genre": "科幻游戏", "chapter": "第30章 斯特兰街道",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/06_系统关卡/7号基地",
        "chapter_file": "030_第30章 斯特兰街道.txt",
        "seg_start": "外面传来动静，是米亚", "seg_end": "许末走了出去，叶青蝶也转身离开",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "清晨米亚准备早餐，白薇来帮忙，许末下楼打招呼，米亚说要去艾尔莎家。叶青蝶（漂亮皮衣女子）来找许末，许末介绍后跟她出门，米亚白薇愣神。纯早晨日常+来客寒暄，硬事实约1条（叶青蝶来找许末，关系铺陈）。切窗避开开头许末练念力和后半段去斯特兰街道伏击眼镜蛇（含赛斯身世等硬钉子）。",
        "secondary_tags": ["sparse_1to2_facts_ok", "科幻游戏", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-014",
        "title": "为什么它永无止境", "author": "柯遥42", "platform": "晋江文学城",
        "genre": "悬疑科幻", "chapter": "第27章 安心",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/04_悬疑信息差/为什么它永无止境",
        "chapter_file": "0027_第27章 安心.txt",
        "seg_start": "也许有其他办法可以终止这件事", "seg_end": "赫斯塔把手轻轻放在心口",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "莉兹与赫斯塔聊肖恩骚扰事，莉兹讲阿斯基亚的价值观（祖母药师故事、柔弱者不该忍受欺凌、正义需人用汗水血去铺路），赫斯塔感动表示不再害怕。纯夜话价值观交流，硬事实约0-1条（肖恩骚扰属前章背景）。无新身份/关系/出口钉子。切窗避开后半段千叶来接、照片被印、抚养权争夺等硬事件。",
        "secondary_tags": ["sparse_1to2_facts_ok", "悬疑科幻", "PASS_SPARSE"],
    },
    {
        "candidate_id": "DS08-015",
        "title": "你们修仙，我种田", "author": "停电 shields", "platform": "起点中文网",
        "genre": "玄幻种田", "chapter": "第28章 新邻",
        "book_path": "/Users/a1234/挣钱/小说101-downloads/01_单主角升级线/你们修仙，我种田",
        "chapter_file": "0028_第28章 新邻.txt",
        "seg_start": "陆玄继续往前，经过一处别院时", "seg_end": "两年半",
        "judge": "PASS_SPARSE", "confidence": "medium",
        "selection_reason": "陆玄去散修集市闲逛，各摊主吆喝（法器、妖兽肉、回收二手法器），陆玄看摊位货物，在一名练气二层少女摊位前看到笼中锦彩鸡幼鸟，询问饲养周期。纯逛集市日常，硬事实约0-1条（锦彩鸡信息属资源背景，软）。切窗避开开头邻居王山登场（新角色硬钉子）和灵田变化说明。",
        "secondary_tags": ["sparse_1to2_facts_ok", "玄幻种田", "PASS_SPARSE"],
    },
]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

jsonl_lines = []
receipt = {"batch_id": "dense_screen_batch08_cnweb_sparse", "total": 0, "by_judge": {}, "by_genre": {}, "warnings": []}

for c in CANDIDATES:
    cid = c["candidate_id"]
    chapter_path = os.path.join(c["book_path"], "chapters_cache", c["chapter_file"])
    with open(chapter_path, "r", encoding="utf-8") as f:
        full_text = f.read()
    raw_file = f"{cid}_raw.txt"
    raw_path = os.path.join(RAW_DIR, raw_file)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    source_chapter_sha256 = sha256_file(raw_path)
    s_idx = full_text.find(c["seg_start"])
    e_idx = full_text.find(c["seg_end"])
    if s_idx < 0:
        print(f"[ERROR] {cid}: seg_start not found: {c['seg_start'][:30]}")
        continue
    if e_idx < 0:
        print(f"[ERROR] {cid}: seg_end not found: {c['seg_end'][:30]}")
        continue
    if e_idx <= s_idx:
        print(f"[ERROR] {cid}: seg_end before seg_start")
        continue
    char_start, char_end = s_idx, e_idx
    segment = full_text[char_start:char_end]
    seg_chars = len(segment.replace(" ", "").replace("\n", "").replace("\t", "").replace("\u3000", ""))
    estimated_tokens = int(seg_chars * 1.2)
    if seg_chars < 600 or seg_chars > 1050:
        receipt["warnings"].append(f"{cid}: seg_chars={seg_chars} out of 600-1050 range")
        print(f"[WARN] {cid}: seg_chars={seg_chars} out of range")
    segment_file = f"{cid}.txt"
    seg_path = os.path.join(SEG_DIR, segment_file)
    with open(seg_path, "w", encoding="utf-8") as f:
        f.write(segment)
    segment_sha256 = sha256_str(segment)
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
    assert raw_text[char_start:char_end] == segment, f"{cid}: segment mismatch"
    record = {
        "candidate_id": cid, "batch_id": "dense_screen_batch08_cnweb_sparse",
        "primary_type": "空样本", "secondary_tags": c["secondary_tags"],
        "confidence": c["confidence"], "selection_reason": c["selection_reason"],
        "rights_state": "RIGHTS_PENDING_FOR_TRAINING",
        "genre": c["genre"], "title": c["title"], "author": c["author"],
        "platform": c["platform"], "book_url": "local_corpus", "chapter_url": "local_corpus",
        "chapter": c["chapter"], "source_path": f"raw/{raw_file}", "raw_file": raw_file,
        "char_start": char_start, "char_end": char_end,
        "core_char_start": char_start, "core_char_end": char_end,
        "estimated_tokens": estimated_tokens, "segment_chars": seg_chars,
        "segment_file": f"segments/{segment_file}",
        "segment_sha256": segment_sha256, "source_chapter_sha256": source_chapter_sha256,
        "judge": c["judge"],
    }
    jsonl_lines.append(json.dumps(record, ensure_ascii=False))
    receipt["total"] += 1
    receipt["by_judge"][c["judge"]] = receipt["by_judge"].get(c["judge"], 0) + 1
    receipt["by_genre"][c["genre"]] = receipt["by_genre"].get(c["genre"], 0) + 1
    print(f"[OK] {cid} {c['genre']} {c['judge']} chars={seg_chars} tokens~{estimated_tokens}")

with open(os.path.join(BATCH_DIR, "CANDIDATES.jsonl"), "w", encoding="utf-8") as f:
    f.write("\n".join(jsonl_lines) + "\n")
with open(os.path.join(BATCH_DIR, "RECEIPT.json"), "w", encoding="utf-8") as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2)
print(f"\n[DONE] {receipt['total']} candidates. by_judge={receipt['by_judge']} by_genre={receipt['by_genre']}")
if receipt["warnings"]:
    print(f"[WARN] {len(receipt['warnings'])} warnings")
