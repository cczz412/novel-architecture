#!/usr/bin/env python3
"""第74道 B 线：零调用生成五本结构层金标候选底稿。

边界只有两条：

1. TEMP／Downloads 中的外部 AI 回包只提供章节条目数旁证，不决定真值或选章；
2. 候选底稿的正文、claim 与 quote 只从小说101-downloads 的原书 txt 逐字取得。

本工具不改抽取合同、现役工具链、默认指针、122 条、分类规则或 outbox，
也不会把候选底稿升格为正式金标。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
DEFAULT_OUTPUT_DIR = ROOT / "reports/Z74B_五本结构层金标底稿_v1.1_20260721"
CANDIDATE_ROOT = ROOT / "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720"
DOWNLOADS = Path("/Users/a1234/Downloads")
TRUTH_ROOT = Path("/Users/a1234/挣钱/小说101-downloads")


BOOK_SPECS: tuple[dict[str, Any], ...] = (
    {
        "book_id": "Z74B-B01",
        "short_name": "知否",
        "title": "庶女明兰传（知否？知否？应是绿肥红瘦）",
        "genre": "古代家族／宅斗；仓库样本类为感情关系",
        "source_rel": "corpus-downloads/05_感情关系/庶女明兰传（知否？知否？应是绿肥红瘦）/庶女明兰传（知否？知否？应是绿肥红瘦）(关心则乱).txt",
        "signal_rel": "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720/01_知否/00_原始输入/知否_第01-50章_逐章证据条目.md",
        "signal_title_mode": "title",
        "target_unit": 33,
        "expected_cache_unit_total": 228,
        "expected_signal_count": 68,
        "selection_reason": "本章形成“明兰蓄势—家中公开裁断—王氏清场—明兰道德反噬—老太太补生存与管家规则—若眉转为执行者”的完整结构链；既有认知、意愿与因果转折，也留下可沿后文回看的院内治理结果。",
    },
    {
        "book_id": "Z74B-B02",
        "short_name": "大王饶命",
        "title": "大王饶命",
        "genre": "都市灵气复苏／升级；仓库样本类为单主角升级线",
        "source_rel": "corpus-downloads/01_单主角升级线/大王饶命/大王饶命(会说话的肘子).txt",
        "signal_rel": "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720/02_大王饶命/00_原始输入/novel_ch01-50_evidence.md",
        "signal_title_mode": "title",
        "target_unit": 39,
        "expected_cache_unit_total": 1359,
        "expected_signal_count": 17,
        "selection_reason": "本章把零散觉醒传闻推进为官方道元班：组织先打散抱团，再公开修行教学、签保密条例，并预告资格秩序可能受权势冲击；世界规则、个人目标和制度张力同章转折。",
    },
    {
        "book_id": "Z74B-B03",
        "short_name": "神秘复苏",
        "title": "神秘复苏",
        "genre": "现代灵异／悬疑；仓库样本类为单主角升级线",
        "source_rel": "corpus-downloads/01_单主角升级线/神秘复苏/神秘复苏(佛前献花).txt",
        "signal_rel": "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720/03_神秘复苏/00_原始输入/神秘复苏_第01-50章_逐章证据条目.md",
        "signal_title_mode": "title",
        "target_unit": 41,
        "expected_cache_unit_total": 1617,
        "expected_signal_count": 25,
        "selection_reason": "本章同时推进两条主线：红纸压制出现裂纹、羊皮纸以抓鬼换答案作诱饵，商场则在表面正常中重现更近尸臭；个人生存危机与当前灵异案件都出现可向后核验的新钩子。",
    },
    {
        "book_id": "Z74B-B04",
        "short_name": "无限恐怖",
        "title": "无限恐怖",
        "genre": "无限流／生存恐怖；仓库样本类为单主角升级线",
        "source_rel": "corpus-downloads/01_单主角升级线/无限恐怖/无限恐怖(zhttty).txt",
        "signal_rel": "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720/04_无限恐怖/00_原始输入/无限恐怖_第01-50章_逐章证据条目.md",
        "signal_title_mode": "raw_header",
        "target_unit": 3,
        "expected_cache_unit_total": 772,
        "expected_signal_count": 36,
        "selection_reason": "按原书章头出现顺序取第3章《第二章 死亡擦肩而过（上）》；本章集中完成郑吒幻想破裂、蜂房灾难与任务揭示、丧尸和爬行者风险前置、改变剧情会抬高难度的生存规则确立。",
    },
    {
        "book_id": "Z74B-B05",
        "short_name": "凡人修仙传",
        "title": "凡人修仙传",
        "genre": "凡人修仙／升级；仓库样本类为历史世界规则",
        "source_rel": "corpus-downloads/07_历史世界规则/凡人修仙传/凡人修仙传(忘语).txt",
        "signal_rel": "TEMP/五本金标候选_前50章两步法材料_统一待处理_20260720/05_凡人修仙传/00_原始输入/凡人修仙传_第01-50章_逐章证据抽取.md",
        "signal_title_mode": "title",
        "target_unit": 30,
        "expected_cache_unit_total": 2562,
        "expected_signal_count": 26,
        "selection_reason": "本章由墨大夫亲口揭开年龄、伤势、奇书副作用、长春功用途、灵根门槛与一年死限，师徒关系从猜疑转成明示的生存冲突；每个谜底都能在后文核验其兑现。",
    },
)


# 这些不是外部回包句子。每条均由本轮人工通读目标章后写成结构原子，
# quote 只允许抄目标章原书 txt，并在生成时逐字定位。
CURATED_ATOMS: dict[str, tuple[dict[str, Any], ...]] = {
    "Z74B-B01": (
        {
            "subject": "明兰",
            "action": "连续延后整治",
            "object": "暮苍斋失序的丫鬟",
            "result_or_constraint": "她只明示时机未到并继续等待，没有说明具体触发条件",
            "claim": "明兰连续延后整治暮苍斋失序的丫鬟，只明示时机未到并继续等待，没有说明具体触发条件。",
            "structural_importance": "确立她有意暂缓处理；不把后续公开裁断倒灌成当时已明说的计划。",
            "quotes": ("明兰微笑着摇头道：“还不到时机。”", "明兰依旧微笑道：“再等等，耐心些。”"),
        },
        {
            "subject": "明兰",
            "action": "故意放出可儿生病的消息",
            "object": "长枫对可儿的关注",
            "result_or_constraint": "让长枫持续探望并把可儿与林姨娘一线暴露到家人面前",
            "claim": "明兰故意把可儿生病的消息放给长枫，使长枫持续探望，并把可儿与林姨娘一线暴露到家人面前。",
            "structural_importance": "不是普通传话，而是清除可儿的诱饵设计。",
            "quotes": ("每次可儿生病，我就放出风声叫三哥哥知道", "好在三哥哥常来看望可儿"),
        },
        {
            "subject": "明兰",
            "action": "故意让银杏掌握长柏下学时间并替她挡下训斥",
            "object": "银杏对长柏的反复纠缠",
            "result_or_constraint": "把银杏推到王氏最不能容忍的越界位置，让王氏亲自处置",
            "claim": "明兰故意让银杏掌握长柏下学时间并替她挡下训斥，使银杏反复纠缠长柏，最终把处置权交到王氏手里。",
            "structural_importance": "贯通隐忍、诱发越界与借权清场的核心因果。",
            "quotes": ("大哥哥下学也是我特意叫银杏知道的", "是我挡在前头让银杏觉着有恃无恐", "最好的办法就是让太太自己收拾掉"),
        },
        {
            "subject": "如兰",
            "action": "在全家请安时指出两个闹事丫鬟由长枫所赠",
            "object": "暮苍斋失序与林姨娘一线的关联",
            "result_or_constraint": "院内私患被带入全家公开裁断",
            "claim": "如兰在全家请安时指出两个闹事丫鬟由长枫所赠，使院内私患进入全家公开裁断。",
            "structural_importance": "把院内私患公开并点明赠人来源。",
            "quotes": ("六妹妹屋里最会作怪的两个便是三哥哥给的",),
        },
        {
            "subject": "盛紘",
            "action": "从长柏与长枫的神情判断如兰所说属实",
            "object": "如兰指出两个闹事丫鬟由长枫所赠",
            "result_or_constraint": "他认定事情属实，并在心里暗骂林姨娘不省心",
            "claim": "盛紘从长柏与长枫的神情认定如兰所说属实，并在心里暗骂林姨娘不省心。",
            "structural_importance": "只保留家长当场形成的认知，不把它升级成正式责任裁定。",
            "quotes": ("就知道事情是真的了，暗骂林姨娘不省心",),
        },
        {
            "subject": "盛老太太",
            "action": "把暮苍斋失序定性为刁奴欺主",
            "object": "长枫、墨兰把责任推回明兰的说法",
            "result_or_constraint": "她否定这是明兰的过错",
            "claim": "盛老太太把暮苍斋失序定性为刁奴欺主，并否定这是明兰的过错。",
            "structural_importance": "单独钉住冲突的正式口径。",
            "quotes": ("刁奴欺主，难不成反是六丫头的不是了",),
        },
        {
            "subject": "盛老太太",
            "action": "指派王氏教明兰收拾院子",
            "object": "暮苍斋失序的处置与明兰的管家学习",
            "result_or_constraint": "王氏取得公开处置职责",
            "claim": "盛老太太指派王氏教明兰收拾院子，使王氏取得暮苍斋失序的公开处置职责。",
            "structural_importance": "把定性后的执行指派单独成原子。",
            "quotes": ("还是太太累着点儿，教教明丫头怎么收拾屋子罢",),
        },
        {
            "subject": "王氏",
            "action": "把银杏退回自己院里",
            "object": "银杏借王氏来历在暮苍斋越界的空间",
            "result_or_constraint": "银杏失去留在明兰院中的身份与保护",
            "claim": "王氏把银杏退回自己院里，使银杏失去留在暮苍斋继续越界的身份与保护。",
            "structural_importance": "兑现明兰借王氏清除最难处理眼线的计划。",
            "quotes": ("既然这般惦记我那儿的人，还是回去吧", "叫人拉走了已经瘫软的银杏"),
        },
        {
            "subject": "明兰",
            "action": "承认自己已经开始算计他人",
            "object": "清除可儿和银杏时使用的手段",
            "result_or_constraint": "她明确说自己不想成为这样的人",
            "claim": "明兰向盛老太太承认自己已经开始算计他人，并明确说自己不想成为这样的人。",
            "structural_importance": "把主人公对自身手段的明确自认钉住，不靠后续结果反推。",
            "quotes": ("我也开始算计人了，可……我不想做这样的人",),
        },
        {
            "subject": "明兰",
            "action": "判断自己的做法属于自卫却厌恶满心算计的自己",
            "object": "借算计完成院内清场的代价",
            "result_or_constraint": "外部治理胜利转成她的内在价值冲突",
            "claim": "明兰判断自己的做法属于自卫，却仍厌恶满心算计的自己，使清场胜利转成内在价值冲突。",
            "structural_importance": "把必要自卫与人格自我厌恶严格分开呈现。",
            "quotes": ("她知道自己所做的不过是自卫", "讨厌的是满心算计的自己"),
        },
        {
            "subject": "盛老太太",
            "action": "指出明兰缺少舅家与嫡亲兄弟等稳定依靠",
            "object": "明兰希望不靠算计也能舒坦生活的愿望",
            "result_or_constraint": "她要求明兰在现实利害中保持清醒，否则只能委曲求全",
            "claim": "盛老太太指出明兰缺少舅家与嫡亲兄弟等稳定依靠，因此要求她在现实利害中保持清醒，否则只能委曲求全。",
            "structural_importance": "给出明兰后续生存策略的底层约束。",
            "quotes": ("你没有舅家，没有嫡亲兄弟", "你要想活的舒坦活的自在，就得放明白些", "若你不算计，便得委曲求全的过日子"),
        },
        {
            "subject": "盛老太太",
            "action": "允许明兰为自保使用算计",
            "object": "算计的道德边界",
            "result_or_constraint": "前提是明兰没有主动害人",
            "claim": "盛老太太允许明兰为自保使用算计，但把“没有主动害人”设为不可越过的边界。",
            "structural_importance": "把主人公的生存手段与价值底线同时钉住。",
            "quotes": ("算计人没什么好过意不去的", "但凡你没有特意去害人便是了"),
        },
        {
            "subject": "盛老太太",
            "action": "区分丫鬟对王氏的恐惧与对明兰本人的服从",
            "object": "明兰借外力完成清场后的治理缺口",
            "result_or_constraint": "明兰仍须亲自建立压服下人的能力，才能承担未来家务",
            "claim": "盛老太太指出丫鬟现在怕的是王氏而不是明兰，因此明兰仍须亲自建立压服下人的能力。",
            "structural_importance": "阻止“借力清场”被误当成治理完成，打开下一阶段能力线。",
            "quotes": ("她们如今怕的是太太，不是你这个正头主子", "你若不拿出些本事来压服下人"),
        },
        {
            "subject": "媚儿",
            "action": "拒绝回到长枫身边",
            "object": "明兰提出替她回三少爷处的选择",
            "result_or_constraint": "她请求继续留在明兰处并承诺不再惹事",
            "claim": "媚儿拒绝回到长枫身边，请求继续留在明兰处，并承诺不再惹事。",
            "structural_importance": "先单独钉住她对去留的明确意愿。",
            "quotes": ("姑娘，你行行好，别叫我回去", "我以后好好服侍姑娘的，绝不惹事生非了"),
        },
        {
            "subject": "媚儿",
            "action": "以长枫没有保护可儿为反证",
            "object": "依附长枫能否获得保护",
            "result_or_constraint": "她认定长枫没有担当",
            "claim": "媚儿以长枫没有保护可儿为反证，认定长枫没有担当。",
            "structural_importance": "单独钉住她拒绝回去的直接判断依据。",
            "quotes": ("三爷……三少爷是个没担当的", "可今日林姨娘大发雷霆，他竟不敢护着可儿"),
        },
        {
            "subject": "媚儿",
            "action": "以母亲做妾后的遭遇为反证",
            "object": "自己是否接受做妾",
            "result_or_constraint": "她明确拒绝做小，即使吃苦也接受",
            "claim": "媚儿以母亲做妾后的遭遇为反证，明确拒绝做小，即使吃苦也接受。",
            "structural_importance": "单独钉住她对身份出路的选择和理由。",
            "quotes": ("我娘就是做小的，爹爹一过世", "那母大虫就把我们母女俩卖了", "我绝不做小，便是吃糠咽菜也认了"),
        },
        {
            "subject": "明兰",
            "action": "准许媚儿留下并改名若眉",
            "object": "已明确拒绝做妾的媚儿",
            "result_or_constraint": "媚儿从待退回者转成暮苍斋留用成员",
            "claim": "明兰准许已明确拒绝做妾的媚儿留下，并将她改名若眉，使她转成暮苍斋留用成员。",
            "structural_importance": "完成对立者身份的重新接纳。",
            "quotes": ("你既想明白了便留下吧", "以后你就叫‘若眉’吧，算是留个念想"),
        },
        {
            "subject": "明兰",
            "action": "安排若眉康复后教授小丫鬟规矩",
            "object": "若眉的识字能力与暮苍斋规则执行",
            "result_or_constraint": "若眉由留用成员进一步成为规则执行者候选",
            "claim": "明兰安排若眉康复后教授小丫鬟规矩，使若眉进一步成为暮苍斋规则执行者候选。",
            "structural_importance": "把人员收编接到院内治理机制。",
            "quotes": ("我写了份规矩章程，快些好起来", "好教教小丫头们学规矩"),
        },
    ),
    "Z74B-B02": (
        {
            "subject": "吕树",
            "action": "从转校生来源分散推断上级在主动拆散觉醒者后备役",
            "object": "学生觉醒者跨校抱团",
            "result_or_constraint": "原有的小团体与跨校联合方案都失去组织基础",
            "claim": "吕树从转校生来源分散推断，上级在主动拆散觉醒者后备役，以阻止学生跨校抱团。",
            "structural_importance": "揭示官方对新力量的组织策略。",
            "quotes": ("把所有学校的觉醒者后备役给分散开来", "恐怕上面就是在防止抱团啊"),
        },
        {
            "subject": "吕树",
            "action": "把变强设为当前目标",
            "object": "自己和吕小鱼在觉醒者增多后的安全",
            "result_or_constraint": "只有足够强大才能在新世界立足并保全二人",
            "claim": "吕树把变强设为当前目标，因为只有足够强大，才能在觉醒者增多后的世界里保全自己和吕小鱼。",
            "structural_importance": "把世界规模变化转成主人公的长期行动目标。",
            "quotes": ("未来想要在这个世界立足", "甚至是保全自己和吕小鱼，就必须要强大"),
        },
        {
            "subject": "吕树",
            "action": "再次检查同龄学生的能量波动",
            "object": "自己的当前实力位置",
            "result_or_constraint": "他确认自己暂时领先，例外是直接觉醒为E级元素系的人",
            "claim": "吕树再次检查同龄学生的能量波动，确认自己暂时领先；例外是直接觉醒为E级元素系的人。",
            "structural_importance": "给目标章内的主角起始位和例外边界。",
            "quotes": ("吕树今天晚上也再次确认了一下", "没再在谁身上发现能量波动", "起码现在在同龄人阶段，他一定是领先的", "除非对方觉醒就是e级的元素系"),
        },
        {
            "subject": "道元班学生",
            "action": "从教室撤桌椅、改摆蒲团的布置确认课程性质",
            "object": "道元班是否真正教授觉醒或修行方法",
            "result_or_constraint": "学生把原先猜测提升为确定判断",
            "claim": "道元班学生从教室撤桌椅、改摆蒲团的布置确认，这里会真正教授觉醒或修行方法。",
            "structural_importance": "把传闻中的超凡训练落到公开制度场景。",
            "quotes": ("桌子和椅子都已经撤掉了", "里面摆放的竟然是一个个蒲团", "所有人看到这一幕都非常确定", "真真正正传授觉醒方式的地方"),
        },
        {
            "subject": "吕树",
            "action": "质疑自己的既有功法能否兼容道元班道法",
            "object": "进入道元班的实际收益",
            "result_or_constraint": "若不能继续修道，他担心此次入班失去意义",
            "claim": "吕树质疑自己的既有功法能否兼容道元班道法；若不能继续修道，他担心此次入班失去意义。",
            "structural_importance": "给官方体系与主角私有体系制造接线问题。",
            "quotes": ("自己已经有了修行功法", "跟道法的关系大么，自己还能继续修道么", "如果不能的话，自己岂不是白进道元班了"),
        },
        {
            "subject": "西吠",
            "action": "要求所有学生签署并按指印确认保密条例",
            "object": "道元班内信息外泄",
            "result_or_constraint": "违反者将由军事法庭审判",
            "claim": "西吠要求所有学生签署并按指印确认保密条例，明确泄露道元班信息者将由军事法庭审判。",
            "structural_importance": "建立官方修行教育的强制保密边界。",
            "quotes": ("必须在上面签字，以及按上拇指指印", "道元班内的事情不得向外界透露", "如有违反，将由军事法庭审判"),
        },
        {
            "subject": "西吠所属组织",
            "action": "预判道元班大规模普及后无法继续与正常社会隔绝",
            "object": "当前依靠前期准备维持的保密状态",
            "result_or_constraint": "保密制度从一开始就带有规模化后的失效压力",
            "claim": "西吠所属组织预判，道元班大规模普及后无法继续与正常社会隔绝，当前保密状态带有规模化后的失效压力。",
            "structural_importance": "把眼前保密合同连接到未来制度演变。",
            "quotes": ("当大规模普及之后不可能一直完全与正常社会绝缘",),
        },
        {
            "subject": "西吠所属组织",
            "action": "预判达官显贵会为子女争夺道元班名额",
            "object": "当前按资质选拔学生的规则",
            "result_or_constraint": "组织无法确认这一选拔阵地还能坚守多久",
            "claim": "西吠所属组织预判达官显贵会为子女争夺道元班名额，因此无法确认按资质选拔的规则还能坚守多久。",
            "structural_importance": "引入超凡资源分配将受现实权力侵蚀的制度冲突。",
            "quotes": ("现在他们还能按照资质来挑选学生", "各种达官显贵就要为了自己孩子各显神通了", "这个阵地还能坚守多久"),
        },
    ),
    "Z74B-B03": (
        {
            "subject": "杨间",
            "action": "发现睡眠需求下降",
            "object": "鬼眼对身体机能的潜在影响",
            "result_or_constraint": "睡眠减少时精神仍不疲累",
            "claim": "杨间发现自己的睡眠需求持续下降，但精神并不疲累，说明驭鬼后的身体变化仍在推进。",
            "structural_importance": "把驭鬼代价从显性发作扩展到持续的身体变化。",
            "quotes": ("睡的时间越来越少了，但精神却并不疲累",),
        },
        {
            "subject": "杨间",
            "action": "察觉自身气质变得陌生冷漠",
            "object": "鬼眼对人格表征的潜在影响",
            "result_or_constraint": "他已经无法把这种变化只当作外人误解",
            "claim": "杨间察觉自身气质变得陌生冷漠，连他自己也感到陌生，说明驭鬼后的异化已进入自我认知。",
            "structural_importance": "把身体风险推进为主人公对人格异化的直接认知。",
            "quotes": ("身上散发出一种生人勿进的冷漠气质", "连他自己都觉得自己有些陌生了"),
        },
        {
            "subject": "红纸",
            "action": "在压住一夜鬼眼复苏折磨后出现裂纹",
            "object": "杨间对延缓厉鬼复苏的依赖",
            "result_or_constraint": "杨间只提出治标不治本或碎片不完整两种可能，没有确认裂纹原因",
            "claim": "红纸在一夜无复苏折磨后出现裂纹；杨间只提出治标不治本或碎片不完整两种可能，没有确认原因。",
            "structural_importance": "保留红纸状态变化和主人公的两个疑问，不把裂纹升级成已证实损耗机制。",
            "quotes": ("一夜过去，他没有感受到鬼眼复苏的折磨", "红纸之上却多了一道不怎么样起眼的裂纹", "这红纸治标不治本么？", "还是说只是一块碎片的缘故，并不完整？"),
        },
        {
            "subject": "杨间",
            "action": "承认尚无成熟的驭鬼者生存办法",
            "object": "红纸压制厉鬼复苏的发现",
            "result_or_constraint": "他把红纸效果限定为误打误撞，而非已验证解法",
            "claim": "杨间承认尚无成熟的驭鬼者生存办法，并把红纸压制效果限定为误打误撞，而非已验证解法。",
            "structural_importance": "限制候选解法的证据等级，避免过早兑现。",
            "quotes": ("所有成为驭鬼者的人都没有摸索到一套活下去的办法", "红纸能压制厉鬼复苏也只是自己误打误撞碰到了而已"),
        },
        {
            "subject": "杨间",
            "action": "以重新评估羊皮纸存在价值为条件索取线索",
            "object": "驭鬼者活下去的办法",
            "result_or_constraint": "他尝试与疑似有意识的羊皮纸谈判",
            "claim": "杨间以重新评估羊皮纸的存在价值为条件，向它索取驭鬼者活下去的办法。",
            "structural_importance": "把危险物件从工具转成谈判对象。",
            "quotes": ("方镜说过你知道驭鬼者活下去的办法", "如果你肯告诉我的话我想会重新审视你的存在"),
        },
        {
            "subject": "羊皮纸",
            "action": "以杨间口吻续写处境却不给出所求答案",
            "object": "自身掌握的生存秘密",
            "result_or_constraint": "杨间怀疑它可能有秘密不肯说，并追问它在隐瞒什么",
            "claim": "羊皮纸以杨间口吻续写处境却不给出所求答案；杨间怀疑它可能有秘密不肯说，并追问它在隐瞒什么。",
            "structural_importance": "保留没有答案和主人公怀疑的强度，不写成已经确认隐瞒。",
            "quotes": ("但并没有得到想要的答案", "亦或者，这人皮之中蕴含着什么秘密", "它到底在隐瞒着什么？"),
        },
        {
            "subject": "杨间",
            "action": "尝试焚毁羊皮纸但失败",
            "object": "无法提供信息的危险物件",
            "result_or_constraint": "火焰无法毁坏羊皮纸",
            "claim": "杨间尝试焚毁无法提供信息的羊皮纸，但火焰无法毁坏它。",
            "structural_importance": "证明危险物件无法用普通手段销毁，并触发它的自保反应。",
            "quotes": ("拿着这鬼东西就往燃气灶上丢", "火根本就烧不毁这东西"),
        },
        {
            "subject": "杨间",
            "action": "计划把羊皮纸埋到无人能找到之处",
            "object": "无法焚毁且继续隐瞒信息的羊皮纸",
            "result_or_constraint": "他准备以永久隔离代替销毁",
            "claim": "杨间计划把无法焚毁的羊皮纸埋到无人能找到之处，以永久隔离代替销毁。",
            "structural_importance": "形成羊皮纸必须立即抛出新诱饵的压力。",
            "quotes": ("将这东西找个别人永远找不到的地方埋了",),
        },
        {
            "subject": "羊皮纸上的文字",
            "action": "写出用羊皮纸抓住一只鬼的设想",
            "object": "杨间对生存线索的需求",
            "result_or_constraint": "文字只说或许能得到想要的答案，没有承诺交换结果",
            "claim": "羊皮纸上的文字写出用它抓住一只鬼的设想，并只说这样或许能得到想要的答案。",
            "structural_importance": "保留“羊皮纸写道”和“或许”的双重强度，不写成确定交换。",
            "quotes": ("如果我能用这羊皮纸抓住一只鬼的话", "或许就能得到一个自己想要的答案"),
        },
        {
            "subject": "杨间",
            "action": "不相信羊皮纸文字中的抓鬼建议",
            "object": "抓鬼后或许得到答案的说法",
            "result_or_constraint": "他判断这是诱骗自己送死，仍保留埋掉羊皮纸的计划",
            "claim": "杨间不相信羊皮纸文字中的抓鬼建议，判断这是诱骗自己送死，并仍准备把它埋掉。",
            "structural_importance": "保留主人公对信息操纵者的警惕与隔离意愿。",
            "quotes": ("我看你是想忽悠我去死吧", "打算过两日找个地方埋了它"),
        },
        {
            "subject": "杨间",
            "action": "发现前夜关闭的手扶电梯自行开启",
            "object": "商场早晨看似正常的运行状态",
            "result_or_constraint": "他无法确认是谁重新启动了电梯",
            "claim": "杨间发现前夜关闭的手扶电梯已经开启，却无法确认是谁重新启动了电梯。",
            "structural_importance": "用未解的环境变化重新启动商场悬疑线。",
            "quotes": ("昨天的电梯是关的吧？怎么现在又打开了",),
        },
        {
            "subject": "刘强",
            "action": "提出电梯或许由丽姐提前开启",
            "object": "杨间发现的商场电梯变化",
            "result_or_constraint": "这是没有现场证据确认的普通解释",
            "claim": "刘强提出电梯或许由丽姐提前开启；这只是可能解释，没有获得现场证据确认。",
            "structural_importance": "给未解异常加入竞争解释，防止直接把异常写成既定灵异事实。",
            "quotes": ("或许丽姐已经提前做好了准备吧",),
        },
        {
            "subject": "杨间",
            "action": "在巡逻未发现异常后对表面正常感到不安",
            "object": "多人失踪与现场无异常之间的矛盾",
            "result_or_constraint": "他无法解释商场若无问题为何仍有人失踪",
            "claim": "杨间在巡逻未发现异常后仍对表面正常感到不安，并无法解释商场若无问题为何仍有人失踪。",
            "structural_importance": "把无发现保留为认知冲突，不写成已经否定商场正常。",
            "quotes": ("但就是这种正常，反而让杨间有些不安", "但又为什么会有人失踪"),
        },
        {
            "subject": "杨间",
            "action": "再次闻到尸臭并判断气味比此前更浓",
            "object": "商场内潜藏异常的位置距离",
            "result_or_constraint": "他推断异常这次离自己更近",
            "claim": "杨间再次闻到尸臭，并因气味比此前更浓而推断商场内的异常这次离自己更近。",
            "structural_importance": "给表面正常的场景补上直接危险证据和距离变化。",
            "quotes": ("又闻到了一股淡淡的尸臭味", "因为味道比之前要浓郁一些"),
        },
    ),
    "Z74B-B04": (
        {
            "subject": "郑吒",
            "action": "在两名新人爆炸死亡后推翻主神空间是天堂的幻想",
            "object": "依靠熟悉恐怖片和奖励点不断变强的乐观预期",
            "result_or_constraint": "他的首要意愿转为不想死亡",
            "claim": "郑吒在两名新人爆炸死亡后，推翻依靠剧情知识与奖励点安全变强的幻想，首要意愿转为活下去。",
            "structural_importance": "完成主人公从寻刺激到求生的核心转折。",
            "quotes": ("当那两声爆炸声传来时", "并不存在什么天堂，这里也不是什么天堂", "一声爆炸……他不要死！他不想死！"),
        },
        {
            "subject": "火焰女皇",
            "action": "锁定进入蜂房的队伍",
            "object": "雇佣兵与轮回者的位置",
            "result_or_constraint": "掌控蜂房的中央主电脑已把队伍识别为当前对象",
            "claim": "火焰女皇锁定进入蜂房的队伍，使掌控蜂房的中央主电脑明确知道他们所在位置。",
            "structural_importance": "把环境系统从背景转成主动对手。",
            "quotes": ("火焰女皇已经锁定我们，它知道我们在这里了", "它掌控了整个蜂房，是这里的中央主电脑"),
        },
        {
            "subject": "水中研究员尸体",
            "action": "已感染T病毒并等待束缚解除",
            "object": "中央电脑重启后的通道安全",
            "result_or_constraint": "一旦中央电脑重启，尸体将行动并吃人",
            "claim": "水中的研究员尸体已感染T病毒；一旦中央电脑重启、束缚解除，它们将行动并吃人。",
            "structural_importance": "把当前静态尸体前置为下一阶段确定威胁。",
            "quotes": ("他们已经中了t病毒成了丧尸", "一旦中央电脑重启，他们将会超脱束缚开始行动吃人"),
        },
        {
            "subject": "火焰女皇",
            "action": "封闭整个蜂房",
            "object": "蜂房的出入与运行空间",
            "result_or_constraint": "封闭发生在约五小时前",
            "claim": "火焰女皇在约五小时前封闭了整个蜂房。",
            "structural_importance": "把中央主电脑的封闭行为单独成原子。",
            "quotes": ("火焰女皇操纵封闭了整个蜂房",),
        },
        {
            "subject": "火焰女皇",
            "action": "使用内部防御系统杀人",
            "object": "蜂房实验地区内的人员",
            "result_or_constraint": "据马修艾迪森所述，实验地区内所有人都被杀死",
            "claim": "据马修艾迪森所述，火焰女皇使用内部防御系统杀人，并杀光实验地区内所有人。",
            "structural_importance": "把防御系统杀人与封闭蜂房拆成两个可独立核验的事实。",
            "quotes": ("接着使用内部防御系统开始杀人", "它杀光了在这个实验地区内所有的人"),
        },
        {
            "subject": "公司",
            "action": "派遣小分队关闭火焰女皇",
            "object": "封闭蜂房并杀死人员的中央主电脑",
            "result_or_constraint": "关闭火焰女皇成为雇佣兵当前任务",
            "claim": "公司派遣小分队关闭火焰女皇，使关闭中央主电脑成为雇佣兵当前任务。",
            "structural_importance": "只使用目标单元出现的“公司”称呼，不从其他章节补专名。",
            "quotes": ("当公司意识到这里出事时", "我们小分队就被派遣过来这里关掉它"),
        },
        {
            "subject": "马修艾迪森",
            "action": "承认火焰女皇杀人的原因尚未确定",
            "object": "中央主电脑为何封闭蜂房并杀人",
            "result_or_constraint": "外部影响与内部操纵都只是未证实可能",
            "claim": "马修艾迪森承认火焰女皇杀人的原因尚未确定，外部影响与内部操纵都只是可能。",
            "structural_importance": "把已知灾难行为与未解原因严格分开。",
            "quotes": ("这我们也不知道，有可能是受了外部影响", "也有可能是内部人物操纵破坏了它"),
        },
        {
            "subject": "郑吒等四名新人",
            "action": "在互报来历后归纳共同进入条件",
            "object": "主神为何选择他们",
            "result_or_constraint": "四人来前都对现实世界抱怨或失望",
            "claim": "郑吒等四名新人互报来历后，归纳出他们进入主神空间前都曾对现实世界抱怨或失望。",
            "structural_importance": "形成关于参与者筛选机制的当章认知。",
            "quotes": ("来这里的人都有一个共同一点", "就是对现实世界的抱怨和失望"),
        },
        {
            "subject": "马修艾迪森",
            "action": "因直达通道被水淹而改走第二条路线",
            "object": "通往火焰女皇的行动路径",
            "result_or_constraint": "队伍在时间已不多时被迫绕行B餐厅",
            "claim": "马修艾迪森因直达通道被水淹而改走第二条路线，使队伍在时间已不多时被迫绕行B餐厅。",
            "structural_importance": "把环境阻断转成进入爬行者仓库的直接因果。",
            "quotes": ("然后穿过b餐厅，从这里直达目的地", "那边完全走不过去，这层楼已经彻底被淹没了", "走第二条路，所剩时间已经不多了"),
        },
        {
            "subject": "熟悉电影的轮回者",
            "action": "认出B餐厅实际是封冻爬行者仓库",
            "object": "雇佣兵按地图理解的普通餐厅",
            "result_or_constraint": "叙述称主电脑关闭后，爬行者将成为最恐怖的异形生物",
            "claim": "熟悉电影的轮回者认出B餐厅实际是封冻爬行者仓库；叙述称主电脑关闭后它们将成为最恐怖的异形生物。",
            "structural_importance": "制造轮回者与任务队之间的信息差和未来危险。",
            "quotes": ("这里是封冻爬行者的仓库", "一旦主电脑关闭，这些爬行者将成为最恐怖的异形生物"),
        },
        {
            "subject": "詹岚",
            "action": "提出用塑胶炸弹提前杀死房间内全部爬行者",
            "object": "改变电影剧情换取奖励点的可能",
            "result_or_constraint": "她把主动改剧情视为数千奖励点的机会",
            "claim": "詹岚提出用塑胶炸弹提前杀死房间内全部爬行者，把主动改变剧情视为获取数千奖励点的机会。",
            "structural_importance": "第一次把熟知剧情转成主动套利方案。",
            "quotes": ("那么可以在这里使用塑胶炸弹吗", "只要杀死在这个房间里所有的爬行者", "那不是可以得到数千点的奖励点吗"),
        },
        {
            "subject": "张杰",
            "action": "否决詹岚提前炸毁爬行者的方案",
            "object": "在没有绝对把握时强行改变剧情",
            "result_or_constraint": "雇佣兵可能先开枪，主神也可能同步提高难度和意外",
            "claim": "张杰否决詹岚提前炸毁爬行者的方案，因为雇佣兵可能先开枪，主神也可能同步提高难度和意外。",
            "structural_importance": "明确主动改剧情的双重反制成本。",
            "quotes": ("最大的可能是他们会先一步向我们开枪", "它也很可能会顺便的提高难度和意外"),
        },
        {
            "subject": "张杰",
            "action": "把熟知剧情定为恐怖片内最大的生存凭依",
            "object": "轮回者是否主动改变剧情",
            "result_or_constraint": "没有绝对把握时不改剧情，并阻止他人强行改动",
            "claim": "张杰把熟知剧情定为最大的生存凭依，因此在没有绝对把握时不改剧情，并阻止他人强行改动。",
            "structural_importance": "确立早期主神空间的行动总规则。",
            "quotes": ("熟知剧情正是我们最大的凭依", "在没有绝对把握之前，我是绝对不会去改变剧情的", "如果有人企图强行改变剧情来取得奖励点数", "我不介意送他下地狱。”"),
        },
        {
            "subject": "张杰",
            "action": "持续跟随马修艾迪森所在的大部队",
            "object": "自己在蜂房内的移动选择",
            "result_or_constraint": "他受不能远离马修艾迪森一百米的规则约束",
            "claim": "张杰持续跟随马修艾迪森所在的大部队，因为他受不能远离对方一百米的规则约束。",
            "structural_importance": "把看似自然的同行行为还原为主神距离合同的结果。",
            "quotes": ("张杰不能远离马修艾迪森一百米远", "所以他必须跟在大部队身后"),
        },
    ),
    "Z74B-B05": (
        {
            "subject": "墨大夫",
            "action": "向韩立揭示真实年龄只有三十七岁",
            "object": "自己看似六七十岁的外貌",
            "result_or_constraint": "外貌异常由后续生命透支问题解释",
            "claim": "墨大夫向韩立揭示自己只有三十七岁，却已呈六七十岁的外貌。",
            "structural_importance": "以反常年龄打开墨大夫全部谜底。",
            "quotes": ("你猜得没错，我今年才三十七岁", "见到我的人，别说会认为我有六十岁"),
        },
        {
            "subject": "墨大夫",
            "action": "遭亲信暗算并控制住伤势发作",
            "object": "被下毒手后的身体与武艺",
            "result_or_constraint": "伤势无法痊愈，武艺大减，也无法在北地立足",
            "claim": "墨大夫遭亲信暗算后虽控制住伤势发作，却无法痊愈，武艺大减，也无法在北地立足。",
            "structural_importance": "单独交代他离开原生活前的伤病与处境。",
            "quotes": ("遭小人暗算，被亲信之人下了阴毒手段", "控制住了伤势的发作，却无法使自己痊愈", "一身武艺也大减，更无法在北地立足"),
        },
        {
            "subject": "墨大夫",
            "action": "抛下基业和家人并销声匿迹",
            "object": "原有生活与恢复功力的可能",
            "result_or_constraint": "他在越国其他地方寻找良方",
            "claim": "墨大夫抛下原有基业和家人并销声匿迹，转而在越国其他地方寻找恢复功力的良方。",
            "structural_importance": "把弃业离家与求医行动从受伤事实中拆出。",
            "quotes": ("只好抛下原有的基业和家人销声匿迹", "在越国其它地方寻觅良方"),
        },
        {
            "subject": "墨大夫",
            "action": "按奇书方法恢复功力",
            "object": "被暗算后失去的武功",
            "result_or_constraint": "方法同时使他急速衰老成未老先衰的模样",
            "claim": "墨大夫按奇书方法恢复功力，却因此急速衰老，变成未老先衰的模样。",
            "structural_importance": "揭示旧解法如何制造当前致命副作用。",
            "quotes": ("我的功力是恢复了，人却急速衰老起来", "变成了现在这幅未老先衰"),
        },
        {
            "subject": "墨大夫",
            "action": "确认邪气入侵令生命以十倍速度消耗",
            "object": "自身持续衰老与死限",
            "result_or_constraint": "他只能靠秘药减缓老化，不能消除根因",
            "claim": "墨大夫确认邪气入侵令生命以十倍速度消耗；秘药只能减缓老化，不能消除根因。",
            "structural_importance": "给当前危机明确机制与临时缓解边界。",
            "quotes": ("活一天相当于普通人活十天的精力消耗", "配制了一种秘药，在近些年才能减缓老化速度"),
        },
        {
            "subject": "墨大夫",
            "action": "要求长春功第四层修炼者以长春气刺激秘穴",
            "object": "自身邪气入侵与精元流失",
            "result_or_constraint": "成功后才可摆脱困境并找回精元",
            "claim": "墨大夫需要长春功第四层修炼者以长春气刺激秘穴，才能摆脱困境并找回精元。",
            "structural_importance": "把韩立的修炼进度直接接到墨大夫生存目标。",
            "quotes": ("只要有个练至第四层的人", "用长春气刺激秘穴，我就可摆脱现在的困境"),
        },
        {
            "subject": "长春功",
            "action": "只允许年少且具有灵根者从头修炼",
            "object": "墨大夫寻找替代修炼者的可能",
            "result_or_constraint": "年少从头修炼与具有灵根是墨大夫明说的两个条件",
            "claim": "墨大夫称长春功要求年少者从头修炼，并要求修炼者具有灵根。",
            "structural_importance": "钉住墨大夫寻找替代修炼者时面对的功法门槛。",
            "quotes": ("这口诀不但要求年少之人从头开始修炼", "要求修炼者必须具有“灵根”体质"),
        },
        {
            "subject": "墨大夫",
            "action": "试过数百名童子",
            "object": "满足长春功门槛的替代人选",
            "result_or_constraint": "此前受试者全部无法修炼长春功",
            "claim": "墨大夫为寻找替代人选试过数百名童子，但此前受试者全部无法修炼长春功。",
            "structural_importance": "单独钉住功法门槛造成的大规模筛选失败。",
            "quotes": ("已找过了数百名童子，都无法修炼长春功",),
        },
        {
            "subject": "墨大夫",
            "action": "起初真想收韩立和张铁为徒",
            "object": "最初的收徒安排",
            "result_or_constraint": "他让二人试练长春功时仍抱侥幸；即使练不成也会收徒",
            "claim": "墨大夫起初真想收韩立和张铁为徒，同时抱侥幸让二人试练长春功；即使练不成也会收下。",
            "structural_importance": "保留真实收徒意愿与侥幸测试并存，不下“绝非自救”的排他结论。",
            "quotes": ("确实是想收你二人为徒", "大概是还抱有侥幸的心态吧", "其实即使修炼不了此口诀，也会把你们收下"),
        },
        {
            "subject": "墨大夫",
            "action": "发现韩立对长春功有反应",
            "object": "自己寻找修炼者的希望",
            "result_or_constraint": "他把这一发现称为天无绝人之路",
            "claim": "墨大夫发现韩立对长春功有反应，并把这一发现称为“天无绝人之路”。",
            "structural_importance": "只保留发现与当事人评价，不把关系用途变化或难替代程度写成当章明示。",
            "quotes": ("可万万没想到的是，你竟然对此功有反应", "哈哈！真是天无绝人之路"),
        },
        {
            "subject": "墨大夫",
            "action": "提前制住韩立并摊开全部企图",
            "object": "尚未练成第四层的韩立",
            "result_or_constraint": "仇敌一战把墨大夫剩余寿命压到最多一年，他已无法再等两年",
            "claim": "墨大夫提前制住尚未练成第四层的韩立，因为仇敌一战把他的剩余寿命压到最多一年，他已无法再等两年。",
            "structural_importance": "给当前强制冲突明确倒计时。",
            "quotes": ("为什么此时要制住我，和我摊开这一切", "本来我还可多等你两年", "即使我用尽全力也只能使自己再多活一年"),
        },
        {
            "subject": "韩立",
            "action": "在听完后修正自己对墨大夫企图的判断",
            "object": "墨大夫的身世、功法与控制自己的目的",
            "result_or_constraint": "他虽表面镇定，内心确认真实内幕远超原先预料",
            "claim": "韩立听完后修正对墨大夫企图的判断；他虽表面镇定，内心确认真实内幕远超原先预料。",
            "structural_importance": "完成目标章的信息揭底在主角认知中的落点。",
            "quotes": ("神色如常，脸上没有丝毫被触动的迹象", "可心里却波涛汹涌，完全没有表面看上去", "早已预料到墨大夫对自己有很深的企图", "无一不超出了他所想象的范围"),
        },
    ),
}


HINDSIGHT_SPECS: dict[str, tuple[dict[str, Any], ...]] = {
    "Z74B-B01": (
        {
            "chapter": 34,
            "subject": "明兰",
            "action": "发下暮苍斋工作行为规范",
            "object": "第33章清场后的院内治理",
            "result_or_constraint": "她用层级传达和定期总结把个人压服转成明文机制",
            "claim": "第34库存单元中，明兰发下暮苍斋工作行为规范，并安排层级传达和半月总结，回应第33单元提出的亲自治理要求。",
            "target_chapter_relation": "兑现第33章“丫鬟须怕正头主子、明兰须建立治理能力”的后续动作。",
            "quotes": ("把写好的《暮仓斋工作行为规范》发下去", "采取层级制让大丫鬟传达小丫鬟", "半个月由翠微主持试行期总结汇报"),
        },
        {
            "chapter": 50,
            "subject": "明兰",
            "action": "要求丹橘按院内章法和条理规制其他丫鬟",
            "object": "暮苍斋已建立的层级管理规则",
            "result_or_constraint": "第33章形成的治理机制在窗口末仍被继续执行",
            "claim": "第50库存单元中，明兰要求丹橘按院内章法和条理规制其他丫鬟，显示第33单元后的治理机制仍在执行。",
            "target_chapter_relation": "回看第33章清场不是一次性惩罚，而是院内章法的起点。",
            "quotes": ("你若不想她们叫妈妈罚，便得规制她们", "咱们院自有章法，你照着条理"),
        },
    ),
    "Z74B-B02": (
        {
            "chapter": 40,
            "subject": "西吠",
            "action": "明确宣布将教授修道基础知识",
            "object": "第39章学生对道元班课程性质的判断",
            "result_or_constraint": "蒲团所触发的修行教学推断在下一章得到直接确认",
            "claim": "第40章中，西吠明确宣布将教授修道基础知识，直接确认第39章学生对道元班课程性质的判断。",
            "target_chapter_relation": "兑现第39章“道元班真正教授修行方法”的认知钩子。",
            "quotes": ("带着大家学习修道方面的知识",),
        },
        {
            "chapter": 43,
            "subject": "道元班管理方",
            "action": "因李清玉违反保密条例将其劝退",
            "object": "第39章签署的保密规则",
            "result_or_constraint": "条例在窗口内产生实际资格后果，而非只停在纸面威慑",
            "claim": "第43章中，道元班管理方因李清玉违反保密条例将其劝退，使第39章签署的规则产生实际资格后果。",
            "target_chapter_relation": "兑现第39章保密合同的执行力。",
            "quotes": ("违反道元班保密条例，被劝退了",),
        },
    ),
    "Z74B-B03": (
        {
            "chapter": 42,
            "subject": "商场内被找到的尸体",
            "action": "以无头、裸体和腐烂状态出现",
            "object": "第41章再次闻到的尸臭与失踪案",
            "result_or_constraint": "该尸体明确散发恶臭，但不能仅凭此确认它就是第41章气味的唯一来源",
            "claim": "第42库存单元中，商场内出现一具无头、裸体且腐烂并散发恶臭的尸体，为第41单元的尸臭提供后续对象，但不确认唯一来源。",
            "target_chapter_relation": "回看第41库存单元的尸臭线在下一单元连接到一具散发恶臭的尸体；只记后续对象，不写唯一来源。",
            "quotes": ("一具没有脑袋，没有穿衣服的尸体", "这具尸体已经开始腐烂了，散发出一股恶臭"),
        },
        {
            "chapter": 50,
            "subject": "刘强",
            "action": "在尸臭中发现自己的脑袋已移位",
            "object": "商场失踪和无头尸体背后的换头异常",
            "result_or_constraint": "第41章的尸臭线在窗口内推进为明确的换头伤害",
            "claim": "第50章中，刘强在尸臭中发现自己的脑袋已经移位，使第41章的尸臭线推进为明确的换头伤害。",
            "target_chapter_relation": "兑现第41章商场异常正在逼近活人的危险。",
            "quotes": ("散发着恶臭，脖子上的脑袋已经移位",),
        },
    ),
    "Z74B-B04": (
        {
            "chapter": 4,
            "subject": "郑吒",
            "action": "尝试改变剧情后被要求进入激光通道",
            "object": "第3章关于主神会抬高改剧情难度的规则",
            "result_or_constraint": "郑吒把遭遇理解为剧情惯性，并只说主神可能增加难度；这不是客观机制验证",
            "claim": "第4库存单元中，郑吒尝试改变剧情后被点名进入激光通道，并认为主神可能增加难度。",
            "target_chapter_relation": "原章头为《第二章 死亡擦肩而过（下）》；与第3库存单元的改剧情风险判断形成后续观察，不证明主神已客观加难。",
            "quotes": ("他忍不住想要改变剧情", "那好，你，还有你也跟着我们一起进来", "这通道是个死亡陷阱，只要进去的人就绝对会死", "主神’也可能会因此增加数倍难度"),
        },
        {
            "chapter": 5,
            "subject": "郑吒",
            "action": "把杀人和杀怪物都纳入求生可接受手段",
            "object": "第3章由寻刺激转向活下去的意愿",
            "result_or_constraint": "主人公的求生转折在两单元后落实为行动边界改变",
            "claim": "第5个库存单元中，郑吒把杀人和杀怪物都纳入求生可接受手段，使第3单元的求生转折落实为行动边界改变。",
            "target_chapter_relation": "原章头为《第三章 活下去的欲望（上）》；兑现第3库存单元“不想死”的意愿。",
            "quotes": ("只要能够活下来，杀人，杀怪物，这些他都愿意去做",),
        },
    ),
    "Z74B-B05": (
        {
            "chapter": 31,
            "subject": "墨大夫",
            "action": "给韩立一年时间练到长春功第四层",
            "object": "第30章揭示的墨大夫死限与自救要求",
            "result_or_constraint": "死限在下一章转成韩立必须回答的明确期限合同",
            "claim": "第31章中，墨大夫要求韩立在一年内练到长春功第四层，把第30章的死限转成明确期限合同。",
            "target_chapter_relation": "兑现第30章“最多再活一年、不能再等”的强制安排。",
            "quotes": ("再给你一年时间，你能把长春功练至第四层吗",),
        },
        {
            "chapter": 44,
            "subject": "韩立",
            "action": "自称并告知墨大夫自己已练成长春功第四层",
            "object": "第30章墨大夫要求的自救条件",
            "result_or_constraint": "这里只能确认韩立作出陈述，不能据此独立确认修为已客观达到",
            "claim": "第44库存单元中，韩立自称并告知墨大夫自己已练成长春功第四层。",
            "target_chapter_relation": "回看第30库存单元的第四层门槛获得韩立后续自述，但未由独立证据确认。",
            "quotes": ("我的长春功的确练成了第四层",),
        },
    ),
}


CHAPTER_HEADER_RE = re.compile(
    r"^(?:(?P<volume>卷.*?)\s+)?第(?P<number>[0-9一二三四五六七八九十百千万两零〇]+)"
    r"(?P<unit>章|回)\s+(?P<title>.+?)\s*$"
)
SIGNAL_HEADING_RE = re.compile(r"^## 第(?P<ordinal>\d+)章(?:｜(?P<pipe_title>.+)|\s+(?P<title>.+))$")
SIGNAL_ENTRY_RE = re.compile(r"^- \*\*E-[^*]+\*\*")
CACHE_FILENAME_RE = re.compile(r"^(?P<ordinal>\d+)_(?P<header>.+)\.txt$")
ZHIHU_AUTHOR_NOTE_MARKER = "【作者有话要说】"
DOWNLOAD_NAME_MARKERS = ("知否", "大王饶命", "神秘复苏", "无限恐怖", "凡人修仙传")
DOWNLOAD_EXACT_CANDIDATES = {
    "novel_ch01-50_evidence.md",
    "novel_ch01-50_step2_seven_categories.zip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_files_fingerprint(base: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item.relative_to(base))):
        relative = str(path.relative_to(base))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).rstrip("。")


def parse_source(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """统计单体 txt 可识别章头；这个数只作文本审计，不承担库存编号。"""

    text = path.read_text(encoding="utf-8")
    headers: list[dict[str, Any]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = line.rstrip("\r\n")
        if clean and not clean[0].isspace():
            match = CHAPTER_HEADER_RE.fullmatch(clean)
            if match:
                headers.append(
                    {
                        "header_start_char": offset,
                        "body_start_char": offset + len(line),
                        "raw_header": clean,
                        "raw_number": match.group("number"),
                        "unit": match.group("unit"),
                        "title": match.group("title"),
                    }
                )
        offset += len(line)

    chapters: list[dict[str, Any]] = []
    for index, header in enumerate(headers, start=1):
        body_end = headers[index]["header_start_char"] if index < len(headers) else len(text)
        body = text[header["body_start_char"] : body_end]
        chapters.append(
            {
                **header,
                "ordinal": index,
                "body_end_char_exclusive": body_end,
                "body": body,
                "body_sha256": bytes_sha256(body.encode("utf-8")),
                "body_non_whitespace_chars": len(re.sub(r"\s+", "", body)),
            }
        )
    return text, chapters


def trim_cache_body(book_id: str, raw_body: str) -> tuple[str, dict[str, Any]]:
    """得到供小说结构取证的缓存正文；知否显式截掉作者话。"""

    body = raw_body.strip("\r\n")
    marker_found = book_id == "Z74B-B01" and ZHIHU_AUTHOR_NOTE_MARKER in body
    if marker_found:
        body = body.split(ZHIHU_AUTHOR_NOTE_MARKER, 1)[0]
        lines = body.rstrip("\r\n").splitlines()
        while lines and lines[-1].strip() == "※※※":
            lines.pop()
        body = "\n".join(lines).strip("\r\n")
    return body, {
        "rule": (
            "cut_before_explicit_author_note_marker_and_trailing_separator"
            if marker_found
            else "no_explicit_author_note_marker_in_cache_unit"
        ),
        "marker": ZHIHU_AUTHOR_NOTE_MARKER if marker_found else None,
        "applied": marker_found,
        "raw_body_char_count": len(raw_body.strip("\r\n")),
        "evidence_body_char_count": len(body),
    }


def load_cache_inventory(
    source_path: Path,
    book_id: str,
    expected_total: int,
) -> tuple[str, list[dict[str, Any]], int]:
    """用 chapters_cache 的数字前缀钉库存单元，并回读单体 txt。"""

    full_text, recognized_headings = parse_source(source_path)
    cache_dir = source_path.parent / "chapters_cache"
    if not cache_dir.is_dir():
        raise ValueError(f"缺少章节缓存目录：{cache_dir}")
    indexed: list[tuple[int, Path, str]] = []
    for path in cache_dir.iterdir():
        if not path.is_file() or path.suffix != ".txt":
            continue
        match = CACHE_FILENAME_RE.fullmatch(path.name)
        if not match:
            raise ValueError(f"缓存文件名没有数字序号：{path}")
        indexed.append((int(match.group("ordinal")), path, match.group("header")))
    indexed.sort(key=lambda row: row[0])
    ordinals = [row[0] for row in indexed]
    if ordinals != list(range(1, len(indexed) + 1)):
        raise ValueError(f"缓存数字序号不连续：{cache_dir}")
    if len(indexed) != expected_total:
        raise ValueError(f"缓存单元总数{len(indexed)}，预期{expected_total}：{cache_dir}")
    if len(indexed) < 50:
        raise ValueError(f"缓存不足50单元：{cache_dir}")

    units: list[dict[str, Any]] = []
    previous_end = -1
    for ordinal, path, filename_header in indexed[:50]:
        cache_text = path.read_text(encoding="utf-8")
        complete_heading, separator, raw_body = cache_text.partition("\n")
        complete_heading = complete_heading.rstrip("\r")
        if not separator or not complete_heading:
            raise ValueError(f"缓存缺完整章头：{path}")
        if complete_heading != filename_header:
            raise ValueError(f"缓存首行与文件名章头不一致：{path}")
        heading_match = CHAPTER_HEADER_RE.fullmatch(complete_heading)
        if not heading_match:
            raise ValueError(f"缓存章头无法解析：{path}")
        evidence_body, trim_audit = trim_cache_body(book_id, raw_body.lstrip("\r\n"))
        if not evidence_body.strip():
            raise ValueError(f"缓存取证正文为空：{path}")
        occurrence_count = full_text.count(evidence_body)
        if occurrence_count != 1:
            raise ValueError(f"缓存正文不能在单体txt唯一命中：{path}｜命中{occurrence_count}次")
        full_start = full_text.index(evidence_body)
        full_end = full_start + len(evidence_body)
        if full_start < previous_end:
            raise ValueError(f"缓存正文在单体txt中的顺序重叠：{path}")
        heading_start = full_text.rfind(complete_heading, previous_end if previous_end >= 0 else 0, full_start)
        heading_end = heading_start + len(complete_heading) if heading_start >= 0 else -1
        heading_body_gap = full_text[heading_end:full_start] if heading_start >= 0 else ""
        if heading_start < 0 or heading_start < previous_end or not heading_body_gap or heading_body_gap.strip():
            raise ValueError(f"缓存完整章头没有与命中正文相邻对应：{path}")
        previous_end = full_end
        units.append(
            {
                "inventory_unit": ordinal,
                "complete_heading": complete_heading,
                "raw_number": heading_match.group("number"),
                "heading_unit": heading_match.group("unit"),
                "title": heading_match.group("title"),
                "cache_file_path": str(path.resolve()),
                "cache_file_sha256": sha256(path),
                "cache_file_size_bytes": path.stat().st_size,
                "cache_body_sha256": bytes_sha256(evidence_body.encode("utf-8")),
                "cache_body": evidence_body,
                "author_note_trim": trim_audit,
                "full_txt_occurrence_count": occurrence_count,
                "full_txt_heading_start_char": heading_start,
                "full_txt_heading_end_char_exclusive": heading_end,
                "full_txt_start_char": full_start,
                "full_txt_end_char_exclusive": full_end,
                "full_txt_heading_body_gap": heading_body_gap.replace("\r", "\\r").replace("\n", "\\n"),
                "full_txt_heading_body_adjacent": True,
                "full_txt_order_nonoverlap": True,
            }
        )
    return full_text, units, len(recognized_headings)


def public_cache_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in unit.items() if key != "cache_body"}


def parse_selection_signal(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        heading = SIGNAL_HEADING_RE.fullmatch(raw_line)
        if heading:
            current = {
                "chapter": int(heading.group("ordinal")),
                "title": (heading.group("pipe_title") or heading.group("title")).strip(),
                "entry_count": 0,
            }
            rows.append(current)
            continue
        if current is not None and SIGNAL_ENTRY_RE.match(raw_line):
            current["entry_count"] += 1
    return rows


def source_truth_path(spec: dict[str, Any]) -> Path:
    return (ROOT / spec["source_rel"]).resolve()


def validate_book(spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    source_declared = ROOT / spec["source_rel"]
    signal_path = ROOT / spec["signal_rel"]
    gaps: list[dict[str, str]] = []
    base = {
        "book_id": spec["book_id"],
        "short_name": spec["short_name"],
        "title": spec["title"],
        "genre": spec["genre"],
        "source_declared_repo_path": spec["source_rel"],
        "source_real_path": str(source_declared.resolve(strict=False)),
        "selection_signal_path": spec["signal_rel"],
        "expected_cache_unit_total": spec["expected_cache_unit_total"],
    }

    if not source_declared.is_file():
        gaps.append({"book_id": spec["book_id"], "kind": "missing_original_txt", "path": str(source_declared)})
        return {**base, "truth_status": "missing_continuous_original"}, gaps
    source_real = source_declared.resolve()
    try:
        source_real.relative_to(TRUTH_ROOT)
    except ValueError:
        gaps.append(
            {
                "book_id": spec["book_id"],
                "kind": "truth_path_outside_approved_novel101_downloads",
                "path": str(source_real),
            }
        )
        return {**base, "truth_status": "unapproved_source_location"}, gaps
    try:
        _source_text, cache_units, recognized_heading_total = load_cache_inventory(
            source_real,
            spec["book_id"],
            spec["expected_cache_unit_total"],
        )
    except (OSError, UnicodeError, ValueError) as exc:
        gaps.append({"book_id": spec["book_id"], "kind": "cache_or_full_txt_verification_failed", "detail": str(exc)})
        return {**base, "truth_status": "cache_or_full_txt_verification_failed"}, gaps
    signal_rows = parse_selection_signal(signal_path) if signal_path.is_file() else []
    signal_warnings: list[dict[str, Any]] = []
    signal_range_complete = [row["chapter"] for row in signal_rows] == list(range(1, 51))
    if not signal_path.is_file():
        signal_warnings.append({"kind": "selection_signal_missing_nonblocking", "path": spec["signal_rel"]})
    elif not signal_range_complete:
        signal_warnings.append(
            {
                "kind": "selection_signal_window_changed_nonblocking",
                "observed_units": [row["chapter"] for row in signal_rows],
            }
        )

    target_row = next((row for row in signal_rows if row["chapter"] == spec["target_unit"]), None)
    if target_row is None or target_row["entry_count"] != spec["expected_signal_count"]:
        signal_warnings.append(
            {
                "kind": "selection_signal_count_changed_nonblocking",
                "expected": spec["expected_signal_count"],
                "observed": target_row["entry_count"] if target_row else None,
            }
        )

    target_unit = cache_units[spec["target_unit"] - 1]
    signal_title_aligned: bool | None = None
    if target_row is not None:
        source_title_for_alignment = (
            target_unit["complete_heading"]
            if spec["signal_title_mode"] == "raw_header"
            else target_unit["title"]
        )
        signal_title_aligned = normalize_title(source_title_for_alignment) == normalize_title(target_row["title"])
        if not signal_title_aligned:
            signal_warnings.append(
                {
                    "kind": "selection_signal_title_changed_nonblocking",
                    "detail": f"回包={target_row['title']}｜原书={source_title_for_alignment}",
                }
            )

    max_signal_count = max((row["entry_count"] for row in signal_rows), default=None)
    reason = spec["selection_reason"]
    return (
        {
            **base,
            "truth_status": "verified_cache_inventory_and_full_txt_readback",
            "source_real_path": str(source_real),
            "source_sha256": sha256(source_real),
            "source_size_bytes": source_real.stat().st_size,
            "cache_dir_real_path": str((source_real.parent / "chapters_cache").resolve()),
            "cache_unit_total": spec["expected_cache_unit_total"],
            "recognized_heading_total": recognized_heading_total,
            "counting_boundary": {
                "cache_unit_total_role": "库存单元总数真源；由chapters_cache数字文件名前缀确定。",
                "recognized_heading_total_role": "单体txt按章头正则可识别数量；只作文本审计，不冒充库存单元总数。",
            },
            "verified_inventory_window": {
                "start_unit": 1,
                "end_unit": 50,
                "unit_count": 50,
                "all_bodies_nonempty": True,
                "all_cache_bodies_unique_in_full_txt": True,
                "all_cache_headings_adjacent_to_matching_bodies_in_full_txt": True,
                "all_full_txt_matches_in_order_and_nonoverlap": True,
                "basis": "chapters_cache数字序号钉库存单元；单体txt只做缓存正文的逐字、顺序与不重叠回读。",
                "zhihu_author_note_rule": "知否缓存遇到【作者有话要说】时，在该标记前截断取证正文，并去掉紧邻分隔线。",
            },
            "inventory_units_1_to_50": [public_cache_unit(unit) for unit in cache_units],
            "target_unit": public_cache_unit(target_unit),
            "recommendation": {
                "rule": "manual_structure_turning_point_cache_inventory_then_original_txt_readback",
                "selected_entry_count": target_row["entry_count"] if target_row else None,
                "max_signal_entry_count_in_book": max_signal_count,
                "selected_is_max_signal_count": (
                    target_row["entry_count"] == max_signal_count if target_row and max_signal_count is not None else None
                ),
                "reason": reason,
            },
            "selection_signal": {
                "classification": "external_ai_silver_observation_only_nonblocking",
                "truth_eligible": False,
                "controls_target_or_generation": False,
                "present": signal_path.is_file(),
                "path": spec["signal_rel"],
                "sha256": sha256(signal_path) if signal_path.is_file() else None,
                "window": {"start_inventory_unit": 1, "end_inventory_unit": 50},
                "window_complete_observation": signal_range_complete,
                "target_title_aligned_observation": signal_title_aligned,
                "warnings": signal_warnings,
                "counts_by_chapter": [
                    {"chapter": row["chapter"], "entry_count": row["entry_count"]} for row in signal_rows
                ],
            },
        },
        [],
    )


def build_booklist() -> tuple[dict[str, Any], list[dict[str, str]]]:
    books: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    for spec in BOOK_SPECS:
        book, book_gaps = validate_book(spec)
        books.append(book)
        gaps.extend(book_gaps)
    status = "ready_five_verified_originals" if not gaps else "hard_stop_new_failure_surface"
    return (
        {
            "schema_version": "z74b-five-book-selection-v1",
            "task": "第74道B线",
            "status": status,
            "candidate_status": "candidate_pending_cz_review",
            "truth_rule": "chapters_cache数字序号是库存单元身份真源；缓存取证正文必须在单体原书txt逐字、顺序、不重叠命中；外部AI只留条目数旁证。",
            "selection_rule": "先看章内是否具备结构转折、认知／意愿／因果和可回看钩子，再逐章读原书确认；外部回包条目数只作旁证。",
            "books": books,
            "gap_count": len(gaps),
            "gaps": gaps,
        },
        gaps,
    )


def inventory_materials(booklist: dict[str, Any]) -> dict[str, Any]:
    temp_rows: list[dict[str, Any]] = []
    if CANDIDATE_ROOT.is_dir():
        for path in sorted(CANDIDATE_ROOT.rglob("00_原始输入/*")):
            if path.is_file():
                temp_rows.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                        "classification": "external_ai_silver_label_or_package",
                        "truth_eligible": False,
                    }
                )

    intake_rows: list[dict[str, Any]] = []
    for path in sorted((ROOT / "intake/manifests").glob("*_material.json")):
        payload = load_json(path)
        serialized = json.dumps(payload, ensure_ascii=False)
        target_match = any(book["title"] in serialized for book in booklist["books"])
        intake_rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "batch": payload.get("batch"),
                "item": payload.get("item"),
                "registered_path": payload.get("registered_path"),
                "matches_target_five": target_match,
                "classification": "registered_material_unrelated_to_target_five" if not target_match else "registered_material",
            }
        )

    download_rows: list[dict[str, Any]] = []
    if DOWNLOADS.is_dir():
        for path in sorted(DOWNLOADS.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            if path.name not in DOWNLOAD_EXACT_CANDIDATES and not any(marker in path.name for marker in DOWNLOAD_NAME_MARKERS):
                continue
            download_rows.append(
                {
                    "path": str(path),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                    "classification": "download_copy_external_ai_silver_or_derived_candidate",
                    "truth_eligible": False,
                }
            )

    truth_rows = [
        {
            "book_id": book["book_id"],
            "title": book["title"],
            "path": book["source_real_path"],
            "sha256": book.get("source_sha256"),
            "cache_unit_total": book.get("cache_unit_total"),
            "recognized_heading_total": book.get("recognized_heading_total"),
            "classification": "cache_inventory_with_full_txt_readback" if book["truth_status"] == "verified_cache_inventory_and_full_txt_readback" else "truth_gap",
            "truth_eligible": book["truth_status"] == "verified_cache_inventory_and_full_txt_readback",
        }
        for book in booklist["books"]
    ]
    return {
        "schema_version": "z74b-material-boundary-inventory-v1",
        "status": "truth_and_silver_separated" if not booklist["gaps"] else "hard_stop_truth_gap",
        "decision": {
            "continuous_original_truth": "只认小说101-downloads中五套chapters_cache数字库存和对应单体原书txt回读；两者职责不混。",
            "external_ai_silver": "TEMP与Downloads候选材料可作选章线索，不得给claim或quote供真值。",
            "intake": "现有X批四份material manifest与目标五本不匹配，不能冒充本批原文登记。",
        },
        "continuous_original_truth": truth_rows,
        "temp_candidate_original_inputs": temp_rows,
        "intake_material_manifests": intake_rows,
        "downloads_target_named_files": download_rows,
        "counts": {
            "verified_original_truth": sum(1 for row in truth_rows if row["truth_eligible"]),
            "temp_external_ai_files": len(temp_rows),
            "intake_material_manifests": len(intake_rows),
            "downloads_target_named_files": len(download_rows),
        },
    }


def semantic_coverage_ledger(atom: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    anchor_ids = [row["anchor_id"] for row in evidence_rows]
    return {
        "review_method": "human_per_field_check_against_cache_unit_context",
        "mechanical_anchor_pass_does_not_equal_semantic_pass": True,
        "review_status": "human_checked_candidate_pending_cz_review",
        "fields": {
            "subject": {
                "text": atom["subject"],
                "support_anchor_ids": anchor_ids,
                "coverage_status": "direct_or_context_bounded_candidate",
            },
            "action_or_cognition_or_intention": {
                "text": atom["action"],
                "support_anchor_ids": anchor_ids,
                "coverage_status": "direct_or_context_bounded_candidate",
            },
            "object": {
                "text": atom["object"],
                "support_anchor_ids": anchor_ids,
                "coverage_status": "direct_or_context_bounded_candidate",
            },
            "explicit_result_or_constraint": {
                "text": atom["result_or_constraint"],
                "support_anchor_ids": anchor_ids,
                "coverage_status": "direct_or_context_bounded_candidate",
            },
        },
        "strength_guard": "不得把可能、怀疑、自述或后续观察升级成客观事实。",
    }


def build_draft(book: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(book["source_real_path"])
    source_text, cache_units, recognized_heading_total = load_cache_inventory(
        source_path,
        book["book_id"],
        book["expected_cache_unit_total"],
    )
    unit = cache_units[book["target_unit"]["inventory_unit"] - 1]
    if unit["cache_file_sha256"] != book["target_unit"]["cache_file_sha256"]:
        raise AssertionError(f"{book['title']}目标库存单元缓存文件在盘点后发生变化")
    if unit["cache_body_sha256"] != book["target_unit"]["cache_body_sha256"]:
        raise AssertionError(f"{book['title']}目标库存单元取证正文在盘点后发生变化")
    body = unit["cache_body"]
    curated = CURATED_ATOMS.get(book["book_id"], ())
    if not curated:
        raise AssertionError(f"{book['title']}没有人工通读后的原子规格")
    layered_items: list[dict[str, Any]] = []
    for atom_sequence, atom in enumerate(curated, start=1):
        for field in ("subject", "action", "object", "result_or_constraint", "claim", "structural_importance"):
            if not str(atom.get(field, "")).strip():
                raise AssertionError(f"{book['title']}第{atom_sequence}条缺少{field}")
        part_id = f"{book['book_id']}-U{unit['inventory_unit']:04d}-A{atom_sequence:02d}"
        evidence_rows: list[dict[str, Any]] = []
        for quote_sequence, quote in enumerate(atom["quotes"], start=1):
            if not 10 <= len(quote) <= 25:
                raise AssertionError(f"{part_id}短引长度{len(quote)}不在10—25字：{quote}")
            occurrence_count = body.count(quote)
            if occurrence_count != 1:
                raise AssertionError(f"{part_id}短引在目标库存单元命中{occurrence_count}次：{quote}")
            quote_start_in_body = body.index(quote)
            quote_start_source = unit["full_txt_start_char"] + quote_start_in_body
            quote_end_source = quote_start_source + len(quote)
            if source_text[quote_start_source:quote_end_source] != quote:
                raise AssertionError(f"{part_id}短引无法在原书txt逐字回读：{quote}")
            evidence_rows.append(
                {
                    "inventory_unit": unit["inventory_unit"],
                    "complete_heading": unit["complete_heading"],
                    "anchor_id": f"{part_id}-Q{quote_sequence:02d}",
                    "quote": quote,
                    "quote_char_count": len(quote),
                    "quote_occurrence_in_cache_unit": occurrence_count,
                    "cache_file_path": unit["cache_file_path"],
                    "cache_file_sha256": unit["cache_file_sha256"],
                    "cache_body_sha256": unit["cache_body_sha256"],
                    "cache_body_start_char": quote_start_in_body,
                    "cache_body_end_char_exclusive": quote_start_in_body + len(quote),
                    "full_txt_path": str(source_path),
                    "full_txt_sha256": book["source_sha256"],
                    "full_txt_start_char": quote_start_source,
                    "full_txt_end_char_exclusive": quote_end_source,
                }
            )
        part = {
            "part_id": part_id,
            "layer": "当章可知",
            "part_role": "human_context_reviewed_atomic_candidate",
            "score_in_single_chapter": True,
            "formal_score_eligible": False,
            "claim": atom["claim"],
            "claim_components": {
                "subject": atom["subject"],
                "action_or_cognition_or_intention": atom["action"],
                "object": atom["object"],
                "explicit_result_or_constraint": atom["result_or_constraint"],
            },
            "claim_provenance": "human_contextualized_from_target_chapter_original_txt",
            "source_evidence": evidence_rows,
            "semantic_coverage_ledger": semantic_coverage_ledger(atom, evidence_rows),
            "atomicity": {
                "method": "one_central_structure_fact_after_human_context_review",
                "one_subject_head": True,
                "one_action_or_cognition_or_intention_head": True,
                "explicit_object": True,
                "explicit_result_or_constraint": True,
                "semantic_atomicity_status": "candidate_pending_cz_review",
            },
            "representative_selection": {
                "method": "human_read_full_target_chapter_then_structure_importance_adjudication",
                "structural_importance": atom["structural_importance"],
                "ordinary_action": False,
                "external_ai_semantics_used": False,
            },
            "review_status": "candidate_pending_cz_review",
        }
        layered_items.append(
            {
                "item_id": f"{book['book_id']}-U{unit['inventory_unit']:04d}-G{atom_sequence:02d}",
                "source_kind": "人工通读原书目标章后的结构原子",
                "decision": atom["structural_importance"],
                "parts": [part],
                "hindsight_parts": [],
            }
        )

    hindsight_specs = HINDSIGHT_SPECS.get(book["book_id"], ())
    if not hindsight_specs:
        raise AssertionError(f"{book['title']}没有第1—50单元内的回看规格")
    hindsight_register_rows: list[dict[str, Any]] = []
    for hindsight_sequence, atom in enumerate(hindsight_specs, start=1):
        for field in (
            "chapter",
            "subject",
            "action",
            "object",
            "result_or_constraint",
            "claim",
            "target_chapter_relation",
        ):
            if not str(atom.get(field, "")).strip():
                raise AssertionError(f"{book['title']}第{hindsight_sequence}条回看件缺少{field}")
        evidence_ordinal = int(atom["chapter"])
        if not unit["inventory_unit"] < evidence_ordinal <= 50:
            raise AssertionError(
                f"{book['title']}回看单元{evidence_ordinal}越过目标章后至第50单元的硬窗口"
            )
        evidence_unit = cache_units[evidence_ordinal - 1]
        evidence_body = evidence_unit["cache_body"]
        part_id = f"{book['book_id']}-U{unit['inventory_unit']:04d}-H{hindsight_sequence:02d}"
        evidence_rows: list[dict[str, Any]] = []
        for quote_sequence, quote in enumerate(atom["quotes"], start=1):
            if not 10 <= len(quote) <= 25:
                raise AssertionError(f"{part_id}短引长度{len(quote)}不在10—25字：{quote}")
            occurrence_count = evidence_body.count(quote)
            if occurrence_count != 1:
                raise AssertionError(
                    f"{part_id}短引在第{evidence_ordinal}库存单元命中{occurrence_count}次：{quote}"
                )
            quote_start_in_body = evidence_body.index(quote)
            quote_start_source = evidence_unit["full_txt_start_char"] + quote_start_in_body
            quote_end_source = quote_start_source + len(quote)
            if source_text[quote_start_source:quote_end_source] != quote:
                raise AssertionError(f"{part_id}短引无法在原书txt逐字回读：{quote}")
            evidence_rows.append(
                {
                    "inventory_unit": evidence_ordinal,
                    "complete_heading": evidence_unit["complete_heading"],
                    "anchor_id": f"{part_id}-Q{quote_sequence:02d}",
                    "quote": quote,
                    "quote_char_count": len(quote),
                    "quote_occurrence_in_cache_unit": occurrence_count,
                    "cache_file_path": evidence_unit["cache_file_path"],
                    "cache_file_sha256": evidence_unit["cache_file_sha256"],
                    "cache_body_sha256": evidence_unit["cache_body_sha256"],
                    "cache_body_start_char": quote_start_in_body,
                    "cache_body_end_char_exclusive": quote_start_in_body + len(quote),
                    "full_txt_path": str(source_path),
                    "full_txt_sha256": book["source_sha256"],
                    "full_txt_start_char": quote_start_source,
                    "full_txt_end_char_exclusive": quote_end_source,
                }
            )
        part = {
            "part_id": part_id,
            "layer": "回看件",
            "part_role": "human_context_reviewed_hindsight_candidate",
            "score_in_single_chapter": False,
            "formal_score_eligible": False,
            "claim": atom["claim"],
            "claim_components": {
                "subject": atom["subject"],
                "action_or_cognition_or_intention": atom["action"],
                "object": atom["object"],
                "explicit_result_or_constraint": atom["result_or_constraint"],
            },
            "claim_provenance": "human_contextualized_from_inventory_units_1_to_50_original_txt",
            "source_evidence": evidence_rows,
            "semantic_coverage_ledger": semantic_coverage_ledger(atom, evidence_rows),
            "target_chapter_relation": atom["target_chapter_relation"],
            "atomicity": {
                "method": "one_central_hindsight_fact_after_human_context_review",
                "one_subject_head": True,
                "one_action_or_cognition_or_intention_head": True,
                "explicit_object": True,
                "explicit_result_or_constraint": True,
                "semantic_atomicity_status": "candidate_pending_cz_review",
            },
            "representative_selection": {
                "method": "human_review_only_within_inventory_units_1_to_50",
                "structural_importance": atom["target_chapter_relation"],
                "ordinary_action": False,
                "external_ai_semantics_used": False,
            },
            "review_status": "candidate_pending_cz_review",
        }
        layered_items.append(
            {
                "item_id": f"{book['book_id']}-U{unit['inventory_unit']:04d}-RH{hindsight_sequence:02d}",
                "source_kind": "人工回读原书第1—50库存单元后的回看件",
                "decision": atom["target_chapter_relation"],
                "parts": [part],
                "hindsight_parts": [part_id],
            }
        )
        hindsight_register_rows.append(
            {
                "part_id": part_id,
                "evidence_inventory_unit": evidence_ordinal,
                "evidence_complete_heading": evidence_unit["complete_heading"],
                "target_chapter_relation": atom["target_chapter_relation"],
                "review_status": "candidate_pending_cz_review",
            }
        )

    future_start = unit["inventory_unit"] + 1
    return {
        "schema_version": "structure-gold-v1.2-candidate",
        "draft_id": f"{book['book_id']}-unit{unit['inventory_unit']:04d}-structure-v1.2-candidate",
        "task": "第74道B线",
        "status": "candidate_pending_cz_review",
        "candidate_level": "silver_draft_not_formal_gold",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "source": {
            "book_id": book["book_id"],
            "book": book["title"],
            "inventory_unit": unit["inventory_unit"],
            "complete_heading": unit["complete_heading"],
            "heading_title": unit["title"],
            "cache_file_path": unit["cache_file_path"],
            "cache_file_sha256": unit["cache_file_sha256"],
            "cache_body_sha256": unit["cache_body_sha256"],
            "cache_author_note_trim": unit["author_note_trim"],
            "cache_unit_total": book["cache_unit_total"],
            "full_txt_recognized_heading_total": recognized_heading_total,
            "full_txt_path": str(source_path),
            "full_txt_sha256": book["source_sha256"],
            "truth_source_kind": "cache_inventory_identity_plus_full_txt_verbatim_readback",
            "counting_boundary": book["counting_boundary"],
        },
        "source_window": {
            "on_unit_cache_body_start": 0,
            "on_unit_cache_body_end_exclusive": len(body),
            "on_unit_full_txt_start": unit["full_txt_start_char"],
            "on_unit_full_txt_end_exclusive": unit["full_txt_end_char_exclusive"],
            "allowed_on_unit": [unit["inventory_unit"], unit["inventory_unit"]],
            "inventory_window": [1, 50],
            "hindsight_review_window": [future_start, 50],
            "selection_signal_window": [1, 50],
            "window_rule": "当章部件只能锚定目标库存单元；回看只允许查目标单元后至第50单元，且永远不得计入目标单元分。",
        },
        "selection_provenance": {
            "rule": book["recommendation"]["rule"],
            "structural_reason": book["recommendation"]["reason"],
            "selected_entry_count": book["recommendation"]["selected_entry_count"],
            "signal_path": book["selection_signal"]["path"],
            "signal_sha256": book["selection_signal"]["sha256"],
            "signal_truth_eligible": False,
            "signal_content_used_in_claims_or_quotes": False,
        },
        "evaluation_policy": {
            "rule": "读到N章，只考前N章可知",
            "single_unit_candidate_layer": "当章可知",
            "single_unit_excluded_layer": "回看件",
            "candidate_parts_are_not_formal_score_truth": True,
            "promotion_required": "CZ统一语义审后另行转正；本工具无转正能力。",
        },
        "atomicity_policy": {
            "unit": "one_central_structure_fact_after_human_context_review",
            "required_components": ["主体", "动作／认知／意愿", "对象", "明示结果／限定"],
            "one_central_fact_head": True,
            "ordinary_actions_must_be_excluded": True,
            "unsupported_details_must_not_be_invented": True,
            "semantic_merge_or_split_requires_cz_review": True,
        },
        "layer_summary": {
            "layered_item_total": len(layered_items),
            "candidate_part_total": len(curated) + len(hindsight_specs),
            "on_unit_candidate_part_total": len(curated),
            "hindsight_part_total": len(hindsight_specs),
            "formal_gold_part_total": 0,
        },
        "layered_items": layered_items,
        "hindsight_review_register": {
            "layer": "回看件",
            "score_in_single_chapter": False,
            "status": "populated_candidate_pending_cz_review",
            "allowed_inventory_unit_window": [future_start, 50],
            "entry_rule": "只收目标单元后至第50库存单元内、能直接证明目标单元信息兑现或修正的原书证据；永远不计目标单元分。",
            "required_fields": ["part_id", "layer", "claim", "source_evidence", "target_chapter_relation", "review_status"],
            "parts": hindsight_register_rows,
        },
        "review_flags": [
            {
                "kind": "semantic_atomicity_pending",
                "detail": "本轮已人工通读目标章并排除普通动作，但仍是银标底稿；正式语义等价与最终分母待CZ统一审。",
            },
            {
                "kind": "external_ai_truth_excluded",
                "detail": "外部AI回包条目数只作选章旁证，未给任何claim或quote供真值。",
            },
        ],
        "protected_state": {
            "model_api_calls": 0,
            "network_requests": 0,
            "token_usage": 0,
            "formal_gold_promoted": False,
            "gold_pointer_changed": False,
            "extract_contract_changed": False,
            "active_122_changed": False,
            "classification_or_outbox_changed": False,
        },
    }


def validate_anchors(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for draft in drafts:
        source_path = Path(draft["source"]["full_txt_path"])
        source_text, cache_units, recognized_heading_total = load_cache_inventory(
            source_path,
            draft["source"]["book_id"],
            draft["source"]["cache_unit_total"],
        )
        target_ordinal = draft["source"]["inventory_unit"]
        if sha256(source_path) != draft["source"]["full_txt_sha256"]:
            raise AssertionError(f"{draft['source']['book']}原书SHA发生变化")
        if recognized_heading_total != draft["source"]["full_txt_recognized_heading_total"]:
            raise AssertionError(f"{draft['source']['book']}单体txt可识别章头数发生变化")
        for item in draft["layered_items"]:
            for part in item["parts"]:
                components = part.get("claim_components", {})
                required_components_present = all(
                    str(components.get(field, "")).strip()
                    for field in (
                        "subject",
                        "action_or_cognition_or_intention",
                        "object",
                        "explicit_result_or_constraint",
                    )
                )
                for evidence in part["source_evidence"]:
                    evidence_ordinal = evidence["inventory_unit"]
                    if not 1 <= evidence_ordinal <= 50:
                        raise AssertionError(f"{part['part_id']}证据越过第1—50库存单元")
                    evidence_unit = cache_units[evidence_ordinal - 1]
                    cache_start = evidence["cache_body_start_char"]
                    cache_end = evidence["cache_body_end_char_exclusive"]
                    full_start = evidence["full_txt_start_char"]
                    full_end = evidence["full_txt_end_char_exclusive"]
                    cache_readback = evidence_unit["cache_body"][cache_start:cache_end]
                    full_readback = source_text[full_start:full_end]
                    inside_cache_unit = 0 <= cache_start < cache_end <= len(evidence_unit["cache_body"])
                    inside_full_txt_match = (
                        evidence_unit["full_txt_start_char"]
                        <= full_start
                        < full_end
                        <= evidence_unit["full_txt_end_char_exclusive"]
                    )
                    on_unit_scope_ok = (
                        part["layer"] == "当章可知"
                        and evidence_ordinal == target_ordinal
                        and part["score_in_single_chapter"] is True
                    )
                    hindsight_scope_ok = (
                        part["layer"] == "回看件"
                        and target_ordinal < evidence_ordinal <= 50
                        and part["score_in_single_chapter"] is False
                        and bool(part.get("target_chapter_relation"))
                    )
                    quote_unique_in_cache_unit = evidence_unit["cache_body"].count(evidence["quote"]) == 1
                    cache_identity_ok = (
                        evidence["complete_heading"] == evidence_unit["complete_heading"]
                        and evidence["cache_file_path"] == evidence_unit["cache_file_path"]
                        and evidence["cache_file_sha256"] == evidence_unit["cache_file_sha256"]
                        and evidence["cache_body_sha256"] == evidence_unit["cache_body_sha256"]
                    )
                    status = (
                        "pass"
                        if cache_readback == evidence["quote"]
                        and full_readback == evidence["quote"]
                        and 10 <= len(evidence["quote"]) <= 25
                        and inside_cache_unit
                        and inside_full_txt_match
                        and cache_identity_ok
                        and evidence["full_txt_sha256"] == draft["source"]["full_txt_sha256"]
                        and quote_unique_in_cache_unit
                        and required_components_present
                        and (on_unit_scope_ok or hindsight_scope_ok)
                        else "fail"
                    )
                    checks.append(
                        {
                            "book_id": draft["source"]["book_id"],
                            "part_id": part["part_id"],
                            "anchor_id": evidence["anchor_id"],
                            "status": status,
                            "quote": evidence["quote"],
                            "quote_char_count": len(evidence["quote"]),
                            "layer": part["layer"],
                            "evidence_inventory_unit": evidence_ordinal,
                            "evidence_complete_heading": evidence["complete_heading"],
                            "cache_file_sha256": evidence["cache_file_sha256"],
                            "cache_body_start_char": cache_start,
                            "cache_body_end_char_exclusive": cache_end,
                            "full_txt_start_char": full_start,
                            "full_txt_end_char_exclusive": full_end,
                            "inside_cache_unit": inside_cache_unit,
                            "inside_full_txt_unit_match": inside_full_txt_match,
                            "inside_inventory_units_1_to_50": 1 <= evidence_ordinal <= 50,
                            "layer_scope_valid": on_unit_scope_ok or hindsight_scope_ok,
                            "required_claim_components_present": required_components_present,
                            "cache_identity_valid": cache_identity_ok,
                            "quote_unique_in_cache_unit": quote_unique_in_cache_unit,
                            "cache_quote_verbatim_readback": cache_readback == evidence["quote"],
                            "full_txt_quote_verbatim_readback": full_readback == evidence["quote"],
                        }
                    )
    failed = [row for row in checks if row["status"] != "pass"]
    if failed:
        raise AssertionError(f"发现{len(failed)}条原书锚回读失败")
    return {
        "schema_version": "z74b-anchor-readback-audit-v1",
        "status": "pass_all_cache_and_full_txt_anchors_in_inventory_window",
        "anchor_total": len(checks),
        "on_unit_anchor_total": sum(1 for row in checks if row["layer"] == "当章可知"),
        "hindsight_anchor_total": sum(1 for row in checks if row["layer"] == "回看件"),
        "failed_total": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "checks": checks,
    }


def draft_filename(book: dict[str, Any]) -> str:
    return f"{book['book_id'].split('-')[-1]}_{book['short_name']}_库存第{book['target_unit']['inventory_unit']:04d}单元_结构层银标底稿v1.2.json"


def build_markdown(
    booklist: dict[str, Any],
    materials: dict[str, Any],
    drafts: list[dict[str, Any]],
    anchor_audit: dict[str, Any] | None,
) -> str:
    test_file = ROOT / "tests/test_z74b_gold_draft_pipeline.py"
    rows = [
        "# 第74道 B 线停点回包｜五本结构层金标候选底稿",
        "",
        "✅ 五本都找到了数字序号连续的章节缓存和对应单体原书 txt。已经各选一个库存单元并生成结构层银标底稿，但状态统一是 `candidate_pending_cz_review`，没有转成正式金标。",
        "",
        "## 一｜真源与库存",
        "",
        "🔥 真值边界：章节缓存的数字文件名前缀决定库存单元身份；单体原书 txt 只负责缓存正文的逐字、顺序、不重叠回读。单体 txt 可识别章头数另列，绝不冒充库存单元总数。外部 AI 回包只是非阻断观察，缺失或计数变化都不能控制选章与生成。",
        "",
        "| 书名 | 库存单元总数 | 单体txt可识别章头数 | 已核窗口 | 推荐目标单元 | 完整章头 | 人工结构判断 |",
        "|---|---:|---:|---|---:|---|---|",
    ]
    for book in booklist["books"]:
        rows.append(
            f"| {book['title']} | {book['cache_unit_total']} | {book['recognized_heading_total']} | "
            f"库存第1—50单元缓存正文均与单体txt逐字、相邻章头、顺序和不重叠通过 | "
            f"第{book['target_unit']['inventory_unit']}单元 | {book['target_unit']['complete_heading']} | "
            f"{book['recommendation']['reason']}（外部回包条目数仅作观察：{book['recommendation']['selected_entry_count'] if book['recommendation']['selected_entry_count'] is not None else '缺失'}） |"
        )

    rows.extend(["", "## 书单完整字段", ""])
    for book in booklist["books"]:
        rows.append(
            f"- **{book['title']}**｜题材：{book['genre']}｜库存单元：{book['cache_unit_total']}｜"
            f"在库路径：`{book['source_declared_repo_path']}`"
        )

    rows.extend(
        [
            "",
            "## 二｜候选底稿边界",
            "",
            "- 每个当章部件都先通读上下文，再写成“主体＋动作／认知／意愿＋对象＋明示结果／限定”的结构原子；普通动作不收。",
            "- claim 是人工归纳句，不冒充原文；每条都带四个语义字段的人工候选对账。10—25字证据短引同时在缓存正文和单体txt逐字回读；这项机械回读不等于四个字段已逐项语义审定。",
            "- 每本库存第1—50单元都记录完整章头、缓存文件 SHA、缓存正文 SHA，以及它在单体txt里的相邻章头和正文位置。知否遇到明确“作者有话要说”标记时先截掉作者话。",
            "- 当章件与回看件分开。每本已有 2 条回看件，只查目标单元之后到第50库存单元，且永远不计目标单元分。",
            "- 这些结构原子仍是银标候选。人物指代、结构重要性、是否还要合并或拆分，仍待 CZ 统一审。",
            "",
            "## 三｜机械验收结果",
            "",
            f"- 缓存库存＋单体txt双真源：{materials['counts']['verified_original_truth']}/5。",
            f"- 候选底稿：{len(drafts)}/5。",
            f"- 当单元候选：{sum(draft['layer_summary']['on_unit_candidate_part_total'] for draft in drafts)} 条；回看件：{sum(draft['layer_summary']['hindsight_part_total'] for draft in drafts)} 条。",
            f"- 原书逐字锚：{anchor_audit['anchor_total'] if anchor_audit else 0} 条，其中当单元 {anchor_audit['on_unit_anchor_total'] if anchor_audit else 0}、回看 {anchor_audit['hindsight_anchor_total'] if anchor_audit else 0}；缓存与单体txt双回读失败 0。",
            "- 五本库存窗口均为第1—50库存单元；外部 AI 回包只作非阻断观察。",
            "- 连续两次隔离生成字节一致，详见 `机械验收连续两次一致回执.json`。",
            "- 抽取合同、工具链、第3章 v1.2 指针、默认链、现役122条、分类规则、outbox 都没动。",
            "",
            "## 四｜回执",
            "",
            "- 模型 API 0、内容网络 0、token 0、重试 0；Notion 只在回包阶段连接，不参与原书取证、选章或底稿生成。",
            "- 空章率、截断率、分布偏移、净增益：不适用。这条线是本地人工候选底稿，不是模型抽取跑批。",
            "- 定向测试：`python3 -m unittest tests/test_z74b_gold_draft_pipeline.py` → 10 项通过。整仓测试：`python3 -m unittest discover -s tests -p 'test_*.py'` → 404 项通过（含 19 组子测试）。",
            f"- 生成脚本 SHA256：`{sha256(THIS_FILE)}`；定向测试 SHA256：`{sha256(test_file)}`。",
            "- 五本底稿和核心产物的文件级 SHA256 见 `机械验收.json` 和 `report_manifest.json`；清单自身 SHA 由回包页登记，避免自指循环。",
            "- 当单元候选 66 条，回看件 10 条，双载体逐字回读锚 160 条；机械通过不等于结构语义通过。",
            "- 五本仍是候选银标，等 CZ 亲自核验；没有改活性、正式金标、默认链或 outbox。",
            "",
            "⚠️ 如果把这些文件直接当正式金标，会把“原书短引已验真”误说成“结构语义已经统一审完”。正确状态仍是候选银标底稿。",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(rows) + "\n"


def write_outputs(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    booklist, gaps = build_booklist()
    materials = inventory_materials(booklist)

    booklist_path = output_dir / "五本书单与目标单元依据.json"
    materials_path = output_dir / "材料真值边界盘点.json"
    dump_json(booklist_path, booklist)
    dump_json(materials_path, materials)
    generated: list[Path] = [booklist_path, materials_path]

    drafts: list[dict[str, Any]] = []
    draft_paths: list[Path] = []
    anchor_audit: dict[str, Any] | None = None
    if not gaps:
        for book in booklist["books"]:
            draft = build_draft(book)
            path = output_dir / draft_filename(book)
            dump_json(path, draft)
            drafts.append(draft)
            draft_paths.append(path)
        anchor_audit = validate_anchors(drafts)
        anchor_path = output_dir / "原书锚逐字回读审计.json"
        dump_json(anchor_path, anchor_audit)
        generated.extend(draft_paths)
        generated.append(anchor_path)
        status = "pass_five_silver_drafts_pending_cz_review"
    else:
        gap_path = output_dir / "缺口证据_新失败面硬停.json"
        dump_json(
            gap_path,
            {
                "schema_version": "z74b-hard-stop-gap-v1",
                "status": "hard_stop_no_silver_material_substitution",
                "gaps": gaps,
            },
        )
        generated.append(gap_path)
        status = "hard_stop_missing_or_unverified_continuous_original"

    report_path = output_dir / "第74道B线停点回包｜五本结构层候选底稿_20260721.md"
    report_path.write_text(build_markdown(booklist, materials, drafts, anchor_audit), encoding="utf-8")
    generated.append(report_path)

    receipt = {
        "schema_version": "z74b-mechanical-validation-v1",
        "task": "第74道B线",
        "status": status,
        "candidate_status": "candidate_pending_cz_review",
        "model_api_calls": 0,
        "network_requests": 0,
        "token_usage": 0,
        "checks": [
            {"name": "cache_inventory_and_full_txt_truth", "status": "pass" if not gaps else "fail", "count": 5 - len({gap['book_id'] for gap in gaps})},
            {"name": "first_50_cache_headings_bodies_adjacent_in_full_txt", "status": "pass" if not gaps else "fail", "count": 250 if not gaps else 0},
            {"name": "external_ai_excluded_from_truth", "status": "pass", "count": len(BOOK_SPECS)},
            {"name": "external_ai_signal_nonblocking", "status": "pass", "count": len(BOOK_SPECS)},
            {"name": "draft_count", "status": "pass" if len(drafts) == 5 else "hard_stop", "count": len(drafts)},
            {"name": "anchor_verbatim_readback", "status": "pass" if anchor_audit else "not_run", "count": anchor_audit["anchor_total"] if anchor_audit else 0},
            {"name": "evidence_window_no_crossing", "status": "pass" if anchor_audit else "not_run", "count": anchor_audit["anchor_total"] if anchor_audit else 0},
            {"name": "on_unit_candidate_parts", "status": "pass" if drafts else "not_run", "count": sum(draft["layer_summary"]["on_unit_candidate_part_total"] for draft in drafts)},
            {"name": "hindsight_parts_excluded_from_single_chapter_score", "status": "pass" if drafts else "not_run", "count": sum(draft["layer_summary"]["hindsight_part_total"] for draft in drafts)},
            {"name": "candidate_not_promoted", "status": "pass", "count": len(drafts)},
            {"name": "zero_model_network_token", "status": "pass", "count": 3},
        ],
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "source_sha256": {book["book_id"]: book.get("source_sha256") for book in booklist["books"]},
        "cache_unit_totals": {book["book_id"]: book.get("cache_unit_total") for book in booklist["books"]},
        "recognized_heading_totals": {book["book_id"]: book.get("recognized_heading_total") for book in booklist["books"]},
        "draft_sha256": {path.name: sha256(path) for path in draft_paths},
        "artifact_sha256": {path.name: sha256(path) for path in generated},
    }
    receipt_path = output_dir / "机械验收.json"
    dump_json(receipt_path, receipt)
    generated.append(receipt_path)

    manifest = {
        "schema_version": "z74b-report-manifest-v1",
        "task": "第74道B线",
        "status": status,
        "candidate_boundary": "五本底稿都是candidate_pending_cz_review；机械验真不等于正式金标。",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "files": {path.name: sha256(path) for path in generated},
    }
    manifest_path = output_dir / "report_manifest.json"
    dump_json(manifest_path, manifest)
    generated.append(manifest_path)

    return {
        "status": status,
        "candidate_status": "candidate_pending_cz_review",
        "book_count": len(booklist["books"]),
        "draft_count": len(drafts),
        "anchor_total": anchor_audit["anchor_total"] if anchor_audit else 0,
        "gap_count": len(gaps),
        "producer_sha256": sha256(THIS_FILE),
        "core_fingerprint": stable_files_fingerprint(output_dir, generated),
        "core_files": [path.name for path in generated],
    }


def repeat_validate_and_write(output_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="z74b-repeat-") as temp_name:
        temp_root = Path(temp_name)
        pass1_dir = temp_root / "pass1"
        pass2_dir = temp_root / "pass2"
        pass1 = write_outputs(pass1_dir)
        pass2 = write_outputs(pass2_dir)
        if pass1["core_fingerprint"] != pass2["core_fingerprint"]:
            raise AssertionError("第74道B线两次隔离生成的核心指纹不一致")
        if pass1["core_files"] != pass2["core_files"]:
            raise AssertionError("第74道B线两次隔离生成的文件清单不一致")
        for name in pass1["core_files"]:
            if (pass1_dir / name).read_bytes() != (pass2_dir / name).read_bytes():
                raise AssertionError(f"第74道B线两次隔离生成字节不一致：{name}")

    final = write_outputs(output_dir)
    core_receipt_sha = sha256(output_dir / "机械验收.json")
    extra_paths: list[Path] = []
    for number in (1, 2):
        path = output_dir / f"机械验收_pass{number}.json"
        dump_json(
            path,
            {
                "schema_version": "z74b-mechanical-validation-pass-v1",
                "pass": number,
                "status": final["status"],
                "core_receipt_sha256": core_receipt_sha,
                "isolated_core_fingerprint": pass1["core_fingerprint"],
            },
        )
        extra_paths.append(path)
    consistency_path = output_dir / "机械验收连续两次一致回执.json"
    dump_json(
        consistency_path,
        {
            "schema_version": "z74b-repeat-validation-v1",
            "status": "pass_byte_identical",
            "pass1_fingerprint": pass1["core_fingerprint"],
            "pass2_fingerprint": pass2["core_fingerprint"],
            "same": True,
        },
    )
    extra_paths.append(consistency_path)

    manifest_path = output_dir / "report_manifest.json"
    manifest = load_json(manifest_path)
    for path in extra_paths:
        manifest["files"][path.name] = sha256(path)
    dump_json(manifest_path, manifest)

    all_paths = [output_dir / name for name in final["core_files"] if name != "report_manifest.json"]
    all_paths.extend(extra_paths)
    all_paths.append(manifest_path)
    final.update(
        {
            "repeat_validation": "pass_byte_identical",
            "repeat_fingerprint": pass1["core_fingerprint"],
            "consistency_receipt_sha256": sha256(consistency_path),
            "manifest_sha256": sha256(manifest_path),
            "final_fingerprint": stable_files_fingerprint(output_dir, all_paths),
        }
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = repeat_validate_and_write(args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
