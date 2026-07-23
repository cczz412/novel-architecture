#!/usr/bin/env python3
"""第83道：冻结 v3 主请求，改用程序复查与单条定点重写。

本工具刻意拆成多个可停点阶段。主采样、语义分流、定点重写与最终判分
各有独立工件；任何阶段失败都不会触发整章重抽。程序只聚合完整人工判词，
不把词面匹配或低成本分流冒充正式语义真值。
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pipeline_inspector
import z68_revised_request_pilot as z68
import z75_multidirection_score as z75_score
import z77_fact_sheet_v2_pilot as z77
import z79_fact_sheet_v3_pilot as z79
from zbatch_modules import (
    api_transport,
    candidate_envelope,
    neutral_extract,
    stage_sampling,
    z83_retry_transport,
)
from zbatch_modules.anchor_kit import validate_anchors
from zbatch_modules.evidence_catalog import nonspace_chars
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 13, 19)
RUN_ID = "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
FORMAL_RETRY_RUN_NAME = re.compile(rf"{re.escape(RUN_ID)}_transport_retry[0-9]{{2}}")
APPROVED_SEED_SOURCE_NAME = f"{RUN_ID}_transport_retry01"
APPROVED_SEED_SOURCE_MAIN_TREE_SHA256 = (
    "ca9c6217c4e2341c65703cb5d42413af44f88816e9f3b3968b64337454f1cb4b"
)
APPROVED_COMPLETED_SEED_SOURCE_NAME = f"{RUN_ID}_transport_retry03"
APPROVED_COMPLETED_SEED_TARGET_NAME = f"{RUN_ID}_transport_retry04"
APPROVED_QUOTE_CONSTRAINT_TARGET_NAME = f"{RUN_ID}_transport_retry05"
APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME = f"{RUN_ID}_transport_retry06"
APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME = f"{RUN_ID}_transport_retry07"
APPROVED_PUNCTUATION_UNIT_TARGET_NAME = f"{RUN_ID}_transport_retry08"
APPROVED_CAPACITY_OVERRIDE_TARGET_NAME = f"{RUN_ID}_transport_retry09"
APPROVED_THIRTEEN_RETRY_TARGET_NAME = f"{RUN_ID}_transport_retry10"
APPROVED_COUNT_CONTRACT_TARGET_NAME = f"{RUN_ID}_transport_retry11"
APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME = f"{RUN_ID}_transport_retry12"
APPROVED_ATOMIC_SPLIT_TARGET_NAME = f"{RUN_ID}_transport_retry13"
APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME = (
    "Z94_X01_Flash局部语义包_步二单臂_v1.0_20260723"
)
APPROVED_Z94_TENCENT_FLASH_TARGET_NAME = (
    "Z94_X01_Flash局部语义包_步二腾讯通道_v1.0_20260723"
)
APPROVED_COMPLETED_SEED_MAIN_TREE_SHA256 = (
    "da4fea7ee2b7b7388694777ae57e019283a60894cd2e4d137347b37d4f1c7bc3"
)
APPROVED_COMPLETED_EVENT_SHA256 = {
    3: "295c7f19dc46bd3c56e984ec701d40dcb34a68eef0a20ec3474cfb5f723d150a",
    13: "aeefcee35c56e52f82dc7382d1073902311c68947d4d8c518cfbf23816808898",
    19: "2f7b9713149183a73d4b1b17a620cba3dabe146ff5935d8a43f1e15bd8243d30",
}
APPROVED_RETRY03_INSPECTOR_HARD_STOP_SHA256 = (
    "a45e85e5d1228183dfc9485c81f63a936aa631682f347e87b5ab6e9fbf150688"
)
APPROVED_RETRY03_INSPECTOR_REQUEST_SHA256 = (
    "9c3701537e0cba49c207f6ebb9de13c549807724b99b7aada0151ea6fb179d13"
)
APPROVED_RETRY03_INSPECTOR_RAW_SHA256 = (
    "d8940c706b97064be328e0d35d940bf5499560bbde583a264b7a143067c2ac99"
)
APPROVED_RETRY04_INSPECTOR_HARD_STOP_SHA256 = (
    "6d785c56faef00b1a56b0fea64a05125964e5f9d094583da9231932b3d8b5a86"
)
APPROVED_RETRY04_INSPECTOR_PREFLIGHT_SHA256 = (
    "e8787ea19c676e9e8155b59634c67dd62e9c53428a081881eb845684aa24264f"
)
APPROVED_RETRY04_INSPECTOR_REQUEST_SHA256 = (
    "3dc9965ef61d4d8053c390c0b34dc2dfd3b1d485ceb12e689f792a1c72758154"
)
APPROVED_RETRY04_INSPECTOR_RAW_SHA256 = (
    "d7e5ff2a400ac589269148a8b9f18064e3c6ab3cf5b7df5158248e238c415b6a"
)
APPROVED_RETRY04_RUN_MANIFEST_SHA256 = (
    "df6f65ce0e5f8a1f2b5ba6ca15461e6150eae0052730fcb6418212c9fc434555"
)
APPROVED_RETRY04_INSPECTOR_TREE = {
    "files": 14,
    "bytes": 195016,
    "sha256": "6e3dca22248e428b8bf41c4a9a02bae9fdfe703c7399ba47868b49c02d57297c",
}
APPROVED_RETRY05_INSPECTOR_PREFLIGHT_SHA256 = (
    "5973c753f0bf5108219505b131947d4e368102106656bc6cf0fe0f5b7a65bdba"
)
APPROVED_RETRY05_CHAPTER3_API_BATCH_SHA256 = (
    "d80115114ed19f4128e22472e81742a2f6bd7ad7d23a11b0d7734d936e660a42"
)
APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256 = (
    "264769277875dd093d6ab6e8c9cf32651be3a66b4f3829cb1ae6468abfe19bf2"
)
APPROVED_RETRY05_CHAPTER3_RAW_SHA256 = (
    "075332f6abed75c111bf50a212d2629b1da72e6506787566d01fb3ba4a5c0c51"
)
APPROVED_RETRY05_CHAPTER3_ROUTING_SHA256 = (
    "9435c912ba6ede57fc5fc12f71009b97427db9884cef7cce4a1c628d654a1e13"
)
APPROVED_RETRY05_CHAPTER3_RECEIPT_SHA256 = (
    "7b74905ec3e799852ba534fd1c01208ef5d44b55be3e2073a99bedaaf00be6e2"
)
APPROVED_RETRY05_CHAPTER13_API_BATCH_SHA256 = (
    "9426803437305e8bbea57509402213726c8fecd335f80b4447c234f3eaaed3d4"
)
APPROVED_RETRY05_CHAPTER13_REQUEST_SHA256 = (
    "c158338001720bf49adc8a2e793b7843707ef45e64349935aee62d5b40af6dbb"
)
APPROVED_RETRY05_CHAPTER13_RAW_SHA256 = (
    "7b1b06339866023f0e4bdc79e42e2305725e4504b9fd1e030f20b35dd67d1768"
)
APPROVED_RETRY05_CHAPTER13_HARD_STOP_SHA256 = (
    "f4d9ec6a2efc067cda149dc44cf9e20214f3b1462a4b10c426fcae2ba4ad6e54"
)
APPROVED_RETRY05_INSPECTOR_HARD_STOP_SHA256 = (
    "5b2a3b0150586f25fad9811af0e7c0cfe035ea3d8f5249521c67e33b08c412f5"
)
APPROVED_RETRY05_RUN_MANIFEST_SHA256 = (
    "1b5ecbaf198c3c5648483631f1996d6c3b5d9691d8d549b37eb41bcf694d0906"
)
APPROVED_RETRY05_INSPECTOR_TREE = {
    "files": 30,
    "bytes": 404593,
    "sha256": "29f3969e3867eb5d6617bc4a34e2540c158c20390070736f394a89b4696486ee",
}
APPROVED_RETRY06_INSPECTOR_PREFLIGHT_SHA256 = (
    "18230d8798a195da2791ca060d5ee491f8b9a622c2c8ccd3a66413103baed574"
)
APPROVED_RETRY06_CHAPTER3_API_BATCH_SHA256 = (
    "d80115114ed19f4128e22472e81742a2f6bd7ad7d23a11b0d7734d936e660a42"
)
APPROVED_RETRY06_CHAPTER3_QUOTE_AUDIT_SHA256 = (
    "ed4eaf615ef2fbec961c74a6a8a6af747d65168785d656274c93a849c406d862"
)
APPROVED_RETRY06_CHAPTER3_REUSE_RECEIPT_SHA256 = (
    "f82d0e10eb46cbdc0125a1b5dfe7f1b922a43ed5d0e90b9ea220438435a62fd1"
)
APPROVED_RETRY06_CHAPTER3_ROUTING_SHA256 = (
    "1f2bf9fa18a450202b0e2cc32c73529b1879b24faed677d11397ca5f7ec5d01a"
)
APPROVED_RETRY06_CHAPTER13_API_BATCH_SHA256 = (
    "9426803437305e8bbea57509402213726c8fecd335f80b4447c234f3eaaed3d4"
)
APPROVED_RETRY06_CHAPTER13_REQUEST_SHA256 = (
    "c158338001720bf49adc8a2e793b7843707ef45e64349935aee62d5b40af6dbb"
)
APPROVED_RETRY06_CHAPTER13_RAW_SHA256 = (
    "3c56cef1677174117599e7e8d8fa08c504b9a0a93dc754bda04fa16c187223f4"
)
APPROVED_RETRY06_CHAPTER13_HARD_STOP_SHA256 = (
    "4688617a765c8f09acab9fe3530140288b6a981d805d95ba1bc9e962ed21d409"
)
APPROVED_RETRY06_INSPECTOR_HARD_STOP_SHA256 = (
    "76fe6392731afce39a727278631303b0a529a2251c76663e0194accf9c4da7b1"
)
APPROVED_RETRY06_RUN_MANIFEST_SHA256 = (
    "2b940f573bcfcc2b1183c39db19cc4d7646d4d9741b0c271be4ed98160912999"
)
APPROVED_RETRY06_INSPECTOR_TREE = {
    "files": 18,
    "bytes": 305495,
    "sha256": "a50aa4e0d71b4b65890f451e5a99c252cf42b8da8d25ae856870a98da0ba18d9",
}
APPROVED_RETRY07_PREFLIGHT_SHA256 = (
    "546fd7ae43480d3c8055f7b7728f045be302dafc13262cc4b5b0f8c9eeffe815"
)
APPROVED_RETRY07_PREPARED_VERIFICATION_SHA256 = (
    "d4e2b9d0512a864df8c8c9e39d41c155a951fe04bab04ccddf61072dcdd014d0"
)
APPROVED_RETRY07_HARD_STOP_SHA256 = (
    "d69bbb65a5abde17537d4d4142931e7ad261002c750b63c610b87854ea5fe9bb"
)
APPROVED_RETRY07_RUN_MANIFEST_SHA256 = (
    "5c70ee7aed73102df2451961fd55263217331598123c79253dc50d84aa3e32d5"
)
APPROVED_RETRY07_REVIEW_TICKET_SHA256 = (
    "e039f35907abe1a0504800e9f3f91439c35b66be49bd3bbdd0f74ffec5cb4412"
)

V3_RUN_DIR = (
    ROOT / "runs/Z79_X01_事实说明书注入包v3_三章复验_v1.0_20260721_transport_retry01"
)
V3_REPORT_DIR = ROOT / "reports/Z79_事实说明书注入包v3三章复验_20260721"
V3_PACKAGE = V3_RUN_DIR / "prompt_candidates/事实说明书注入包_v3.json"
V3_PACKAGE_SHA256 = "a302920537349d37c75d5bac9df19a83bfab667891458ef65de9d98e84bc2116"
V3_REQUEST_SHA256 = {
    3: "18fe2a9e9d2f0a4d48b5b4de29803a90c0db0fe1087080ff8f68d00b81e98eb4",
    13: "87fbc6a359731ef2f1af2b6c04df5d79accf9e9a70a9feb5a51e9444abad0c0b",
    19: "6828a9b36e0a45720b3e9080054373cc8ab31c2501c007f4b68e175eda1f55cf",
}
V3_CONTRACT = V3_RUN_DIR / "provenance/sensenova_stage_sampling_z79_v1.json"
V3_CONTRACT_SHA256 = "a3a6416157c2372c778ba167d9330289696d1dbb1b04974cd07aed4415c620b6"
V3_ADJUDICATION = V3_REPORT_DIR / "adjudications/语义人工复核源.json"
V3_ADJUDICATION_SHA256 = (
    "820a742e641cbb2beb9ab0e2b49cf9b00000c59eabd55600bca6755a057f4b6d"
)
OLD_ARM_BASELINE = (
    ROOT / "runs/Z77_X01_事实说明书注入包v2_三章复验_v1.0_20260721/"
    "provenance/source_observation/旧臂2逐条判分账.json"
)
OLD_ARM_BASELINE_SHA256 = (
    "f7482387740646f28545a73fef6b5af3ef82ae03b4a7a1f6a4758bba9efe52ca"
)
CURRENT_RECORDS = V3_RUN_DIR / "inputs/current_formal_records_122.json"
CURRENT_RECORDS_SHA256 = (
    "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba"
)
GOLD_POINTER = ROOT / "config/gold/X01_ch0003_structure_gold_current.json"
GOLD_POINTER_SHA256 = "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c"
GOLD_FILE = ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json"
GOLD_FILE_SHA256 = "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e"
INSPECTOR_CONTRACT = ROOT / "governance/contracts/semantic_inspector_v1.json"
INSPECTOR_CONTRACT_SHA256 = (
    "5a0ccbd262b34c2d074e34a9ca435d489313d0ce5daf02f887c1fe4f91c57158"
)
INSPECTOR_BASE_MAX_TOKENS = 8000
INSPECTOR_COMPAT_MAX_TOKENS = 32000
LOCAL_INSPECTOR_CONTRACT = Path("provenance/semantic_inspector_v1_32k.json")
LOCAL_INSPECTOR_CONTRACT_RECEIPT = Path(
    "provenance/semantic_inspector_v1_32k_diff.json"
)
RETRY03_INSPECTOR_REFERENCE = Path(
    "provenance/retry03_inspector_8k_hard_stop_reference.json"
)
RETRY04_INSPECTOR_REFERENCE = Path(
    "provenance/retry04_inspector_quote_drift_hard_stop_reference.json"
)
RETRY05_INSPECTOR_REFERENCE = Path(
    "provenance/retry05_inspector_chapter3_reuse_and_chapter13_reject_reference.json"
)
RETRY06_INSPECTOR_REFERENCE = Path(
    "provenance/retry06_inspector_chapter3_reuse_and_chapter13_punctuation_reject_reference.json"
)
RETRY07_PUNCTUATION_EQUIVALENCE = Path(
    "provenance/quote_punctuation_equivalence_v1.json"
)
RETRY08_PUNCTUATION_UNIT_EQUIVALENCE = Path(
    "provenance/quote_punctuation_unit_equivalence_v1.json"
)
RETRY08_INSPECTOR_REUSE_RECEIPT = Path(
    "review/retry08_inspector_reuse_receipt.json"
)
RETRY09_ADJUDICATION_REUSE_RECEIPT = Path(
    "review/retry09_adjudication_reuse_receipt.json"
)
RETRY12_ANCHOR_EXTRA_FIELD_LEDGER = Path(
    "repair/diagnostics/anchor_extra_field_strip.jsonl"
)
RETRY07_PREFLIGHT_HARD_STOP_REFERENCE = Path(
    "provenance/retry07_preflight_hard_stop_reference.json"
)
RETRY05_VERBATIM_QUOTE_SYSTEM_LINE = (
    "短引字段必须逐字复制输入中的对应全文（含章节标题等噪声前缀），"
    "一字不得增删改、不得缩写截取清洗。"
)
RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS = 6

LOCAL_TRANSPORT = Path("provenance/sensenova_stage_sampling_z83_v1.json")
MAIN_SEED_MANIFEST = Path("main/main_seed_manifest.json")
PROFILE = z79.PROFILE
MAX_TARGETED_RETRIES_PER_EVENT = 1
MAX_TARGETED_RETRIES_PER_CHAPTER = 3
MAX_TARGETED_RETRIES_TOTAL = 6
MAX_NETWORK_ATTEMPTS = 27
MAX_INSPECTOR_LOGICAL_CALLS = len(TARGET_CHAPTERS)
OLD25_FIELD_RECALL_REVIEW_THRESHOLD = 0.20
OLD25_COMPARABLE_FIELDS = {
    "A": ("direct_cause", "delta"),
    "B": ("trigger_condition", "trigger_action"),
    "C": ("reader_expectation", "payoff_test"),
    "D": ("condition", "consequence", "scope_exception"),
}
CURRENT_VERDICTS = ("not_observed", "partially_preserved", "preserved")
CURRENT_RANK = {value: index for index, value in enumerate(CURRENT_VERDICTS)}
GOLD_VERDICTS = {
    "strict_hit",
    "semantic_shadow",
    "coverage_only_invalid_support",
    "miss",
}
ANCHOR_VERDICTS = {"valid", "invalid"}
RISK_VERDICTS = {"clear", "retry_required"}

RETRY_REASON_TEXT = {
    "SEMANTIC_ANCHOR_UNSUPPORTED": "事件句含未被所挂锚直接支撑的主张；只可补挂当前冻结目录内真实支撑锚，或删去无支撑措辞。",
    "OLD25_COMPLETENESS_DEGRADED": "事件对原文明示的前提、条件、动作、结果或限定保留不完整；重读本章后补齐原文明示组成，禁止新增事实。",
    "CONCLUSION_COMPONENTS_COMPRESSED": "排除或确认结论被概括压缩；把原文明示的各项结论分别、完整写出。",
    "INSTRUCTION_COMPONENTS_COMPRESSED": "命令或嘱咐的行动要求、回报要求、违反后果有缺失；只补原文明示的组成。",
    "MULTI_FACT_COMPRESSED": "一条事件压入多个可独立判断的事实头；按原文真假边界拆成原子事件。",
}
RETRY11_VISIBLE_PERMISSION_TEXT = {
    "SEMANTIC_ANCHOR_UNSUPPORTED": (
        "只准补挂当前冻结目录内真实支撑锚，或删去无支撑措辞。"
    ),
    "OLD25_COMPLETENESS_DEGRADED": (
        "只准在同一条替换事件中补齐原文明示的前提、条件、动作、结果或限定。"
    ),
    "CONCLUSION_COMPONENTS_COMPRESSED": (
        "只准在同一条替换事件中逐项完整写出原文明示的排除或确认结论。"
    ),
    "INSTRUCTION_COMPONENTS_COMPRESSED": (
        "只准在同一条替换事件中完整写出原文明示的行动要求、回报要求或违反后果。"
    ),
    "MULTI_FACT_COMPRESSED": (
        "只准在同一条替换事件中按原文边界写清事实，禁止拆成多条替换事件。"
    ),
}
RETRY11_EXACT_COUNT_CONTRACT = (
    "【本条输出份数硬合同｜优先级最高】\n"
    "replacement_events 数组必须恰好包含1条替换事件；禁止拆分、禁止合并、"
    "禁止新增事件、禁止删除事件。\n"
    "无论原事件包含几个事实头，本轮都不得返回第2条。"
)
MECHANICAL_RETRY_REASON_TEXT = {
    "EVENT_TOO_LONG": "这条事件超过长度上限；只把同一事实头压回上限内，若原文含多个独立事实头可拆成多条。",
    "ANCHOR_ID_INVALID": "这条事件含格式错误或目录外锚；只从当前冻结证据目录逐字复制真实支撑锚ID。",
}
FORBIDDEN_MODEL_TOKENS = (
    "GOLD-C0003",
    "B-C0013-02",
    "B-C0019-04",
    "旧25",
    "金标v1.2",
    "现役122条",
)
FORCED_STRONG_RISKS = {
    "multi_fact",
    "cross_subject",
    "conclusion_compression",
    "instruction_compression",
    "old25_candidate",
}

RETRY09_CHAPTER3_OVERRIDE = {
    "EV-C0003-05": {
        "current_event_sha256": "66b19036662e6dbe8ac821772e4df01054b71493649f755a76d9fe0a4f954dc4",
        "source_identity_sha256": "9c046e4968c974cb0ef23de98362486376cc6dc4f69993958ba8cf6324aa6c34",
    },
    "EV-C0003-08": {
        "current_event_sha256": "eb2a537af1a746a219f4f5ed8168708796e0418c207e910bd94cadc6cb9b4973",
        "source_identity_sha256": "b168fed050e23e7b06ba0d4f20c7125c7f56fdc4dd891db0e246543c43ad89b4",
    },
    "EV-C0003-09": {
        "current_event_sha256": "7411278aa9d5bc83cc653a8cd3a3882660104760672122c5501e10d3a2026ff6",
        "source_identity_sha256": "2473ae2dabf1e485cd2662460b362eb642c04e59e127e81f9e75970d17041313",
    },
    "EV-C0003-10": {
        "current_event_sha256": "3df58f8ab8ee01590067360b607a6d2ba2d1cfa68d9122c24799181deda4997e",
        "source_identity_sha256": "2e5bf72c8c474169ec8aefe9ff3adc0d3bf498a88cbf5e2247912cb0641994d1",
    },
}
RETRY10_APPROVED_EVENT_IDS = (
    "EV-C0003-05",
    "EV-C0003-08",
    "EV-C0003-09",
    "EV-C0003-10",
    "EV-C0013-06",
    "EV-C0013-35",
    "EV-C0013-46",
    "EV-C0019-05",
    "EV-C0019-25",
    "EV-C0019-34",
    "EV-C0019-40",
    "EV-C0019-46",
    "EV-C0019-47",
)
RETRY11_APPROVED_EVENT_IDS = (
    "EV-C0013-06",
    "EV-C0003-05",
    "EV-C0003-08",
    "EV-C0003-09",
    "EV-C0003-10",
    "EV-C0013-35",
    "EV-C0013-46",
    "EV-C0019-05",
    "EV-C0019-25",
    "EV-C0019-34",
    "EV-C0019-40",
    "EV-C0019-46",
    "EV-C0019-47",
)
RETRY12_APPROVED_EVENT_IDS = RETRY11_APPROVED_EVENT_IDS
RETRY10_EFFECTIVE_PER_CHAPTER = {3: 4, 13: 3, 19: 6}
RETRY10_EFFECTIVE_TOTAL = 13
RETRY09_ADJUDICATION_SHA256 = (
    "dd954f9fdc420872a2d6f52e4b3cff9a89364463ea69da3bff33f8addd8fa292"
)
RETRY09_CAPACITY_HARD_STOP_SHA256 = (
    "fa82f2140d9f271a9a19004843578a6ad9359071c6d69d221ee16b40193e993a"
)
RETRY09_INSPECTOR_REUSE_SHA256 = (
    "c43df2c1c4ce925082169215760c9489e48c6e274787fe4ccd7abf2d3cd624d8"
)
RETRY09_RUN_MANIFEST_SHA256 = (
    "a1b087cb7e1e02854eb7611a8f8dc1c7480bd5f4b7f93b6205684fea17d4e838"
)
RETRY10_FIFTH_REQUEST = (
    ROOT
    / "runs"
    / APPROVED_THIRTEEN_RETRY_TARGET_NAME
    / "repair/requests/targeted_retry/"
    "z83_repair_ch0013_ev-c0013-06_request.json"
)
RETRY10_FIFTH_REQUEST_SHA256 = (
    "568bc504d1248e127290b437cfddf2e497d15817d56507a05850047262b30aa7"
)
RETRY10_FIFTH_PREPARED_REQUEST = (
    ROOT
    / "runs"
    / APPROVED_THIRTEEN_RETRY_TARGET_NAME
    / "repair/prepared_requests/z83_repair_ch0013_ev-c0013-06.json"
)
RETRY10_FIFTH_PREPARED_REQUEST_SHA256 = (
    "31d13537019a81c976f681cd7e9fabdfb70fe740c11126751ecf86dfb0e98e42"
)
RETRY10_PREFLIGHT_RECEIPT = (
    ROOT
    / "runs"
    / APPROVED_THIRTEEN_RETRY_TARGET_NAME
    / "repair/retry_preflight.json"
)
RETRY10_PREFLIGHT_RECEIPT_SHA256 = (
    "e5cb50558f53b4247eda8c86c8d71439ad2bd66c2b80e67247180cfc2cacfdf7"
)
RETRY11_PREFLIGHT_RECEIPT = (
    ROOT
    / "runs"
    / APPROVED_COUNT_CONTRACT_TARGET_NAME
    / "repair/retry_preflight.json"
)
RETRY11_PREFLIGHT_RECEIPT_SHA256 = (
    "56fd8233838e312455235f806faa4eff22651e60831c722aafe37b5e86797405"
)
RETRY08_FROZEN_REVIEW_SHA256 = {
    "semantic_hard_stop": "803e0737e4e8c5e03670001f3bd821b82688048c11906235369b21eddfc321ca",
    "combined_routing": "8c244e3dc5608afb2c77bde3f5c6b795f30673d174621dba5fcb8842805baaa1",
    "chapter13_raw_rebuild": "08870f91c1349c56e1e5345de0c67e21dd0f57110fd8768a0613f2e4e3ae712e",
    "chapter19_raw_rebuild": "ca5beef70ecc678f5f01e3d32e56b876b05bc8221b5ef3b03f6a814821c659ff",
    "program_risks": "26d2bca70b3c7b7421536a76fb4b050fa8b5f0ba2dc75e2abd69a9d13d39125b",
}

CLAUSE_SPLIT_RE = re.compile(r"[，；。！？、]|并且|以及|同时|随后|然后")
NAME_LIKE_RE = re.compile(
    r"[\u4e00-\u9fff·]{2,12}(?:说|问|答|要求|命令|嘱咐|发现|确认|决定|返回|前往|离开|进入)"
)
CONCLUSION_RE = re.compile(r"确认|排除|没有|并无|不是|未发现|无证据|结论|证明")
INSTRUCTION_RE = re.compile(
    r"命令|要求|嘱咐|不得|不要|必须|应当|回来|返回|禀报|汇报|否则|后果|殉职"
)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    z77.write_json_atomic(path, value)


def append_jsonl(path: Path, value: Any) -> None:
    z77.append_jsonl(path, value)


def sha256_file(path: Path) -> str:
    return z68.sha256_file(path)


def canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_differences(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    """列出结构化差异；用于证明兼容轮只有一个参数变化。"""

    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                rows.append({"path": child, "before": "<missing>", "after": after[key]})
            elif key not in after:
                rows.append(
                    {"path": child, "before": before[key], "after": "<missing>"}
                )
            else:
                rows.extend(_json_differences(before[key], after[key], child))
        return rows
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        rows = []
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            rows.extend(_json_differences(left, right, f"{path}[{index}]"))
        return rows
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def _formal_completed_seed_target(run_dir: Path) -> bool:
    return run_dir.name in {
        APPROVED_COMPLETED_SEED_TARGET_NAME,
        APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
        APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
        APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
        APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
        APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
        APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        APPROVED_COUNT_CONTRACT_TARGET_NAME,
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    }


def _formal_punctuation_unit_target(run_dir: Path) -> bool:
    return run_dir.name in {
        APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
        APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
        APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        APPROVED_COUNT_CONTRACT_TARGET_NAME,
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    }


def _formal_thirteen_retry_target(run_dir: Path) -> bool:
    return run_dir.name in {
        APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        APPROVED_COUNT_CONTRACT_TARGET_NAME,
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
    }


def _formal_atomic_split_target(run_dir: Path) -> bool:
    """识别单对象原子化合同；不能并回 retry10～12 的数组合同。"""

    return run_dir.name in {
        APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    }


def _uses_retry11_request_contract(run_dir: Path) -> bool:
    return run_dir.name in {
        APPROVED_COUNT_CONTRACT_TARGET_NAME,
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
    }


def _formal_anchor_field_strip_target(run_dir: Path) -> bool:
    return run_dir.name == APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME


def _approved_thirteen_event_ids(run_dir: Path) -> tuple[str, ...]:
    if run_dir.name == APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME:
        return RETRY12_APPROVED_EVENT_IDS
    if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME:
        return RETRY11_APPROVED_EVENT_IDS
    if run_dir.name == APPROVED_THIRTEEN_RETRY_TARGET_NAME:
        return RETRY10_APPROVED_EVENT_IDS
    raise ZBatchError("当前运行不是已拍13条特批轮")


def _retry09_reuse_status(run_dir: Path) -> str:
    if run_dir.name == APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME:
        return "pass_zero_call_reuse_246_rows_lock_13_sources_probe_first_retry12"
    return (
        "pass_zero_call_reuse_246_rows_lock_13_sources_and_probe_first"
        if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME
        else "pass_zero_call_reuse_246_rows_and_lock_13_sources"
    )


def _retry05_system_prompt_suffix(run_dir: Path) -> str | None:
    return (
        RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
        if run_dir.name
        in {
            APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
            APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
            APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
            APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
            APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
            APPROVED_THIRTEEN_RETRY_TARGET_NAME,
            APPROVED_COUNT_CONTRACT_TARGET_NAME,
            APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
            APPROVED_ATOMIC_SPLIT_TARGET_NAME,
            APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
            APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
        }
        else None
    )


def _retry03_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_COMPLETED_SEED_SOURCE_NAME


def _retry04_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_COMPLETED_SEED_TARGET_NAME


def _retry05_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_QUOTE_CONSTRAINT_TARGET_NAME


def _retry06_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME


def _retry07_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME


def _retry08_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_PUNCTUATION_UNIT_TARGET_NAME


def _retry09_run_dir() -> Path:
    return ROOT / "runs" / APPROVED_CAPACITY_OVERRIDE_TARGET_NAME


def _retry07_preflight_hard_stop_reference() -> dict[str, Any]:
    source = _retry07_run_dir()
    report = ROOT / "reports/Z83_程序侧治法_retry07发网前终审硬停_20260722"
    paths = {
        "preflight": source / "preflight.json",
        "prepared_verification": source / "prepared_verification.json",
        "hard_stop": source / "main/hard_stop.json",
        "run_manifest": source / "run_manifest.json",
        "review_ticket": report / "发网前独立终审票.json",
    }
    expected = {
        "preflight": APPROVED_RETRY07_PREFLIGHT_SHA256,
        "prepared_verification": APPROVED_RETRY07_PREPARED_VERIFICATION_SHA256,
        "hard_stop": APPROVED_RETRY07_HARD_STOP_SHA256,
        "run_manifest": APPROVED_RETRY07_RUN_MANIFEST_SHA256,
        "review_ticket": APPROVED_RETRY07_REVIEW_TICKET_SHA256,
    }
    for label, path in paths.items():
        _assert_file(path, expected[label], f"retry07 {label}")
    hard_stop = read_json(paths["hard_stop"])
    manifest = read_json(paths["run_manifest"])
    if (
        hard_stop.get("stage")
        != "independent_engineering_preflight_before_claim_and_network"
        or hard_stop.get("model_api_calls") != 0
        or hard_stop.get("network_attempts") != 0
        or hard_stop.get("inspector_claim_created") is not False
        or manifest.get("status") != "preflight_hard_stop"
        or manifest.get("model_api_calls") != 0
        or manifest.get("network_attempts") != 0
    ):
        raise ZBatchError("retry07发网前硬停封存状态不能机械复证")
    return {
        "schema_version": "z83-retry07-preflight-hard-stop-reference-v1",
        "source_run_dir": source.relative_to(ROOT).as_posix(),
        "paths": {key: path.relative_to(ROOT).as_posix() for key, path in paths.items()},
        "sha256": expected,
        "status": "sealed_zero_call_preflight_hard_stop",
        "model_api_calls": 0,
        "network_attempts": 0,
        "artifacts_imported_as_result": False,
    }


def _retry03_inspector_reference() -> dict[str, Any]:
    source = _retry03_run_dir()
    hard_stop_path = source / "review/inspector/hard_stop.json"
    request_path = (
        source / "review/inspector/ch0003/run/requests/semantic_route/"
        "Z83-MAIN-CH0003-API_request.json"
    )
    raw_path = (
        source / "review/inspector/ch0003/run/responses/semantic_route/"
        "Z83-MAIN-CH0003-API_raw.json"
    )
    _assert_file(
        hard_stop_path,
        APPROVED_RETRY03_INSPECTOR_HARD_STOP_SHA256,
        "retry03检查员硬停票",
    )
    _assert_file(
        request_path,
        APPROVED_RETRY03_INSPECTOR_REQUEST_SHA256,
        "retry03检查员8k请求",
    )
    _assert_file(
        raw_path, APPROVED_RETRY03_INSPECTOR_RAW_SHA256, "retry03检查员截断响应"
    )
    hard_stop = read_json(hard_stop_path)
    request = read_json(request_path)
    raw = read_json(raw_path)
    choices = raw.get("choices") if isinstance(raw, dict) else None
    finish_reason = (
        choices[0].get("finish_reason")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict)
        else None
    )
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if (
        not isinstance(hard_stop, dict)
        or hard_stop.get("status") != "hard_stop_no_resume_or_result_selection"
        or "finish_reason=length" not in str(hard_stop.get("error") or "")
        or not isinstance(request, dict)
        or request.get("body", {}).get("max_tokens") != INSPECTOR_BASE_MAX_TOKENS
        or finish_reason != "length"
        or not isinstance(usage, dict)
        or usage.get("total_tokens") != 20359
    ):
        raise ZBatchError("retry03检查员8k截断旁账不能机械复现")
    return {
        "schema_version": "z83-inspector-8k-hard-stop-reference-v1",
        "source_run_dir": source.relative_to(ROOT).as_posix(),
        "hard_stop_path": hard_stop_path.relative_to(ROOT).as_posix(),
        "hard_stop_sha256": sha256_file(hard_stop_path),
        "request_path": request_path.relative_to(ROOT).as_posix(),
        "request_sha256": sha256_file(request_path),
        "raw_response_path": raw_path.relative_to(ROOT).as_posix(),
        "raw_response_sha256": sha256_file(raw_path),
        "finish_reason": "length",
        "visible_usage": usage,
        "rejected_as_result": True,
        "imported_as_result": False,
        "imported_into_inspector_usage": False,
    }


def _retry04_inspector_reference() -> dict[str, Any]:
    source = _retry04_run_dir()
    inspector_root = source / "review/inspector"
    hard_stop_path = source / "review/inspector/hard_stop.json"
    preflight_path = source / "review/inspector_32k_preflight.json"
    request_path = (
        source / "review/inspector/ch0003/run/requests/semantic_route/"
        "Z83-MAIN-CH0003-API_request.json"
    )
    raw_path = (
        source / "review/inspector/ch0003/run/responses/semantic_route/"
        "Z83-MAIN-CH0003-API_raw.json"
    )
    manifest_path = source / "run_manifest.json"
    for path, expected, label in (
        (
            hard_stop_path,
            APPROVED_RETRY04_INSPECTOR_HARD_STOP_SHA256,
            "retry04检查员短引改写硬停票",
        ),
        (
            preflight_path,
            APPROVED_RETRY04_INSPECTOR_PREFLIGHT_SHA256,
            "retry04检查员32k预验票",
        ),
        (
            request_path,
            APPROVED_RETRY04_INSPECTOR_REQUEST_SHA256,
            "retry04检查员第3章请求",
        ),
        (
            raw_path,
            APPROVED_RETRY04_INSPECTOR_RAW_SHA256,
            "retry04检查员第3章原始响应",
        ),
        (
            manifest_path,
            APPROVED_RETRY04_RUN_MANIFEST_SHA256,
            "retry04顶层硬停状态票",
        ),
    ):
        _assert_file(path, expected, label)
    if z68.tree_fingerprint(inspector_root) != APPROVED_RETRY04_INSPECTOR_TREE:
        raise ZBatchError("retry04检查员封存子树漂移")
    hard_stop = read_json(hard_stop_path)
    preflight = read_json(preflight_path)
    request = read_json(request_path)
    raw = read_json(raw_path)
    manifest = read_json(manifest_path)
    rows = preflight.get("rows") if isinstance(preflight, dict) else None
    choices = raw.get("choices") if isinstance(raw, dict) else None
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    parsed = json.loads(content) if isinstance(content, str) else None
    results = parsed.get("results") if isinstance(parsed, dict) else None
    first_result = results[0] if isinstance(results, list) and results else None
    evidence = first_result.get("evidence") if isinstance(first_result, dict) else None
    first_evidence = evidence[0] if isinstance(evidence, list) and evidence else None
    body = request.get("body") if isinstance(request, dict) else None
    messages = body.get("messages") if isinstance(body, dict) else None
    user_payload = (
        json.loads(messages[1]["content"])
        if isinstance(messages, list)
        and len(messages) == 2
        and isinstance(messages[1], dict)
        and isinstance(messages[1].get("content"), str)
        else None
    )
    input_items = user_payload.get("items") if isinstance(user_payload, dict) else None
    first_input = (
        input_items[0] if isinstance(input_items, list) and input_items else None
    )
    input_anchors = (
        first_input.get("anchors") if isinstance(first_input, dict) else None
    )
    first_input_anchor = (
        input_anchors[0] if isinstance(input_anchors, list) and input_anchors else None
    )
    expected_input_quote = "第3章梅丽莎（第一更求推荐票）\n　　确定了计划，周"
    if (
        not isinstance(hard_stop, dict)
        or hard_stop.get("status") != "hard_stop_no_resume_or_result_selection"
        or "改写了短引" not in str(hard_stop.get("error") or "")
        or not isinstance(preflight, dict)
        or preflight.get("status") != "pass_zero_call_single_variable_8000_to_32000"
        or not isinstance(rows, list)
        or [row.get("chapter") for row in rows if isinstance(row, dict)]
        != list(TARGET_CHAPTERS)
        or not isinstance(body, dict)
        or not isinstance(messages, list)
        or len(messages) != 2
        or not isinstance(messages[0], dict)
        or body.get("max_tokens") != INSPECTOR_COMPAT_MAX_TOKENS
        or body.get("reasoning_effort") != "medium"
        or messages[0].get("content") != pipeline_inspector.SYSTEM_PROMPT
        or not isinstance(raw, dict)
        or not isinstance(first_choice, dict)
        or first_choice.get("finish_reason") != "stop"
        or raw.get("usage", {}).get("total_tokens") != 24630
        or not isinstance(first_result, dict)
        or first_result.get("item_id") != "EV-C0003-01"
        or not isinstance(first_evidence, dict)
        or first_evidence.get("anchor_id") != "E0002"
        or first_evidence.get("quote") != "确定了计划，周"
        or not isinstance(first_input_anchor, dict)
        or first_input_anchor.get("anchor_id") != "E0002"
        or first_input_anchor.get("quote") != expected_input_quote
        or not isinstance(manifest, dict)
        or manifest.get("status") != "main_inspector_hard_stop"
    ):
        raise ZBatchError("retry04检查员短引改写硬停不能机械复现")
    candidate_request_sha = {
        str(row["chapter"]): row["candidate_request_sha256"]
        for row in rows
        if isinstance(row, dict)
    }
    return {
        "schema_version": "z83-inspector-retry04-quote-drift-reference-v1",
        "source_run_dir": source.relative_to(ROOT).as_posix(),
        "hard_stop_path": hard_stop_path.relative_to(ROOT).as_posix(),
        "hard_stop_sha256": sha256_file(hard_stop_path),
        "request_preflight_path": preflight_path.relative_to(ROOT).as_posix(),
        "request_preflight_sha256": sha256_file(preflight_path),
        "candidate_request_sha256": candidate_request_sha,
        "chapter3_actual_request_path": request_path.relative_to(ROOT).as_posix(),
        "chapter3_actual_request_sha256": sha256_file(request_path),
        "chapter3_raw_response_sha256": sha256_file(raw_path),
        "run_manifest_sha256": sha256_file(manifest_path),
        "inspector_tree": APPROVED_RETRY04_INSPECTOR_TREE,
        "finish_reason": "stop",
        "visible_usage": raw["usage"],
        "failed_item_id": "EV-C0003-01",
        "failed_anchor_id": "E0002",
        "input_quote": expected_input_quote,
        "returned_quote": "确定了计划，周",
        "rejected_as_result": True,
        "imported_as_result": False,
    }


def _retry05_inspector_reference() -> dict[str, Any]:
    """冻结 retry05：只准复用第3章通过件，第13章拒收件只作反证旁账。"""

    source = _retry05_run_dir()
    inspector_root = source / "review/inspector"
    paths = {
        "preflight": source / "review/inspector_32k_preflight.json",
        "chapter3_api_batch": inspector_root / "ch0003/api_batch.json",
        "chapter3_request": (
            inspector_root
            / "ch0003/run/requests/semantic_route/Z83-MAIN-CH0003-API_request.json"
        ),
        "chapter3_raw": (
            inspector_root
            / "ch0003/run/responses/semantic_route/Z83-MAIN-CH0003-API_raw.json"
        ),
        "chapter3_routing": inspector_root / "ch0003/run/routing_result.json",
        "chapter3_receipt": inspector_root / "ch0003/run/run_receipt.json",
        "chapter13_api_batch": inspector_root / "ch0013/api_batch.json",
        "chapter13_request": (
            inspector_root
            / "ch0013/run/requests/semantic_route/Z83-MAIN-CH0013-API_request.json"
        ),
        "chapter13_raw": (
            inspector_root
            / "ch0013/run/responses/semantic_route/Z83-MAIN-CH0013-API_raw.json"
        ),
        "chapter13_hard_stop": inspector_root / "ch0013/run/hard_stop.json",
        "inspector_hard_stop": inspector_root / "hard_stop.json",
        "run_manifest": source / "run_manifest.json",
    }
    expected = {
        "preflight": APPROVED_RETRY05_INSPECTOR_PREFLIGHT_SHA256,
        "chapter3_api_batch": APPROVED_RETRY05_CHAPTER3_API_BATCH_SHA256,
        "chapter3_request": APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256,
        "chapter3_raw": APPROVED_RETRY05_CHAPTER3_RAW_SHA256,
        "chapter3_routing": APPROVED_RETRY05_CHAPTER3_ROUTING_SHA256,
        "chapter3_receipt": APPROVED_RETRY05_CHAPTER3_RECEIPT_SHA256,
        "chapter13_api_batch": APPROVED_RETRY05_CHAPTER13_API_BATCH_SHA256,
        "chapter13_request": APPROVED_RETRY05_CHAPTER13_REQUEST_SHA256,
        "chapter13_raw": APPROVED_RETRY05_CHAPTER13_RAW_SHA256,
        "chapter13_hard_stop": APPROVED_RETRY05_CHAPTER13_HARD_STOP_SHA256,
        "inspector_hard_stop": APPROVED_RETRY05_INSPECTOR_HARD_STOP_SHA256,
        "run_manifest": APPROVED_RETRY05_RUN_MANIFEST_SHA256,
    }
    for key, path in paths.items():
        _assert_file(path, expected[key], f"retry05 {key}")
    if z68.tree_fingerprint(inspector_root) != APPROVED_RETRY05_INSPECTOR_TREE:
        raise ZBatchError("retry05检查员封存子树漂移")

    preflight = read_json(paths["preflight"])
    rows = preflight.get("rows") if isinstance(preflight, dict) else None
    request_shas = {
        str(row["chapter"]): row["candidate_request_sha256"]
        for row in rows or []
        if isinstance(row, dict)
    }
    chapter3_receipt = read_json(paths["chapter3_receipt"])
    chapter13_stop = read_json(paths["chapter13_hard_stop"])
    global_stop = read_json(paths["inspector_hard_stop"])
    manifest = read_json(paths["run_manifest"])
    if (
        preflight.get("status")
        != "pass_zero_call_single_variable_retry04_to_retry05_verbatim_quote"
        or set(request_shas) != {"3", "13", "19"}
        or chapter3_receipt.get("status") != "complete"
        or chapter3_receipt.get("logical_model_calls") != 1
        or chapter3_receipt.get("network_attempts") != 1
        or "改写了短引" not in str(chapter13_stop.get("reason") or "")
        or global_stop.get("completed_chapters") != [3]
        or global_stop.get("batch_invocations") != 2
        or manifest.get("status") != "main_inspector_hard_stop"
    ):
        raise ZBatchError("retry05第3章通过／第13章拒收旁账不能机械复现")
    return {
        "schema_version": "z83-inspector-retry05-reuse-reference-v1",
        "source_run_dir": source.relative_to(ROOT).as_posix(),
        "source_inspector_tree": APPROVED_RETRY05_INSPECTOR_TREE,
        "paths": {
            key: path.relative_to(ROOT).as_posix() for key, path in paths.items()
        },
        "sha256": expected,
        "candidate_request_sha256": request_shas,
        "chapter3": {
            "status": "approved_reuse_only",
            "request_sha256": expected["chapter3_request"],
            "raw_response_sha256": expected["chapter3_raw"],
            "routing_sha256": expected["chapter3_routing"],
            "receipt_sha256": expected["chapter3_receipt"],
            "source_usage": chapter3_receipt.get("usage"),
            "source_usage_imported": False,
            "source_network_attempt_imported": False,
        },
        "chapter13": {
            "status": "rejected_never_reuse",
            "request_sha256": expected["chapter13_request"],
            "raw_response_sha256": expected["chapter13_raw"],
            "hard_stop_sha256": expected["chapter13_hard_stop"],
            "imported_as_result": False,
        },
    }


def _retry06_inspector_reference() -> dict[str, Any]:
    """冻结 retry06：第13章拒收件只证明标点等价病例，绝不捞回。"""

    source = _retry06_run_dir()
    inspector_root = source / "review/inspector"
    paths = {
        "preflight": source / "review/inspector_32k_preflight.json",
        "chapter3_api_batch": inspector_root / "ch0003/api_batch.json",
        "chapter3_quote_audit": inspector_root / "ch0003/quote_fill_audit.json",
        "chapter3_reuse_receipt": inspector_root / "ch0003/reuse_receipt.json",
        "chapter3_routing": inspector_root / "ch0003/reused_routing_result.json",
        "chapter13_api_batch": inspector_root / "ch0013/api_batch.json",
        "chapter13_request": (
            inspector_root
            / "ch0013/run/requests/semantic_route/Z83-MAIN-CH0013-API_request.json"
        ),
        "chapter13_raw": (
            inspector_root
            / "ch0013/run/responses/semantic_route/Z83-MAIN-CH0013-API_raw.json"
        ),
        "chapter13_hard_stop": inspector_root / "ch0013/run/hard_stop.json",
        "inspector_hard_stop": inspector_root / "hard_stop.json",
        "run_manifest": source / "run_manifest.json",
    }
    expected = {
        "preflight": APPROVED_RETRY06_INSPECTOR_PREFLIGHT_SHA256,
        "chapter3_api_batch": APPROVED_RETRY06_CHAPTER3_API_BATCH_SHA256,
        "chapter3_quote_audit": APPROVED_RETRY06_CHAPTER3_QUOTE_AUDIT_SHA256,
        "chapter3_reuse_receipt": APPROVED_RETRY06_CHAPTER3_REUSE_RECEIPT_SHA256,
        "chapter3_routing": APPROVED_RETRY06_CHAPTER3_ROUTING_SHA256,
        "chapter13_api_batch": APPROVED_RETRY06_CHAPTER13_API_BATCH_SHA256,
        "chapter13_request": APPROVED_RETRY06_CHAPTER13_REQUEST_SHA256,
        "chapter13_raw": APPROVED_RETRY06_CHAPTER13_RAW_SHA256,
        "chapter13_hard_stop": APPROVED_RETRY06_CHAPTER13_HARD_STOP_SHA256,
        "inspector_hard_stop": APPROVED_RETRY06_INSPECTOR_HARD_STOP_SHA256,
        "run_manifest": APPROVED_RETRY06_RUN_MANIFEST_SHA256,
    }
    for key, path in paths.items():
        _assert_file(path, expected[key], f"retry06 {key}")
    if z68.tree_fingerprint(inspector_root) != APPROVED_RETRY06_INSPECTOR_TREE:
        raise ZBatchError("retry06检查员封存子树漂移")

    preflight = read_json(paths["preflight"])
    preflight_rows = preflight.get("rows") if isinstance(preflight, dict) else None
    request_shas = {
        str(row["chapter"]): row["candidate_request_sha256"]
        for row in preflight_rows or []
        if isinstance(row, dict)
    }
    chapter3_receipt = read_json(paths["chapter3_reuse_receipt"])
    chapter13_stop = read_json(paths["chapter13_hard_stop"])
    global_stop = read_json(paths["inspector_hard_stop"])
    manifest = read_json(paths["run_manifest"])
    chapter13_batch = pipeline_inspector.validate_review_batch(
        read_json(paths["chapter13_api_batch"])
    )
    _, chapter13_content = _read_response_content(paths["chapter13_raw"])
    chapter13_transport_items, _ = pipeline_inspector.split_by_rule_gate(
        chapter13_batch
    )
    expected_items = {
        str(item["item_id"]): {
            str(anchor["anchor_id"]): str(anchor["quote"]) for anchor in item["anchors"]
        }
        for item in chapter13_transport_items
    }
    parsed_content = json.loads(chapter13_content)
    raw_results = parsed_content.get("results")
    quote_rows: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    if not isinstance(raw_results, list):
        raise ZBatchError("retry06第13章原始回包缺results")
    for result in raw_results:
        if not isinstance(result, dict):
            raise ZBatchError("retry06第13章原始回包结果行非法")
        item_id = str(result.get("item_id") or "")
        if item_id not in expected_items or item_id in seen_items:
            raise ZBatchError("retry06第13章原始回包item_id非法或重复")
        seen_items.add(item_id)
        evidence = result.get("evidence")
        if not isinstance(evidence, list):
            raise ZBatchError("retry06第13章原始回包evidence非法")
        for evidence_index, row in enumerate(evidence):
            if not isinstance(row, dict):
                raise ZBatchError("retry06第13章原始回包证据行非法")
            anchor_id = str(row.get("anchor_id") or "")
            model_quote = row.get("quote")
            formal_quote = expected_items[item_id].get(anchor_id)
            if not isinstance(model_quote, str) or not isinstance(formal_quote, str):
                raise ZBatchError("retry06第13章原始回包锚ID非法")
            if (
                sum(not char.isspace() for char in model_quote)
                < RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
            ):
                raise ZBatchError("retry06第13章模型短引低于6个非空白字符")
            normalized_model, _ = pipeline_inspector.normalize_quote_punctuation(
                model_quote
            )
            normalized_formal, _ = pipeline_inspector.normalize_quote_punctuation(
                formal_quote
            )
            if normalized_model not in normalized_formal:
                raise ZBatchError("retry06第13章除已拍标点等价外仍有内容差异")
            quote_rows.append(
                pipeline_inspector._quote_fill_audit_record(
                    item_id=item_id,
                    evidence_index=evidence_index,
                    anchor_id=anchor_id,
                    model_quote=model_quote,
                    formal_quote=formal_quote,
                    minimum_quote_nonspace_chars=(RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS),
                    evidence_quote_policy=(
                        pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
                    ),
                )
            )
    if seen_items != set(expected_items):
        raise ZBatchError("retry06第13章原始回包未覆盖全部检查条目")
    full_parse_failure: str | None = None
    try:
        pipeline_inspector.parse_model_output(
            chapter13_content,
            chapter13_transport_items,
            evidence_quote_policy=(
                pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
            ),
            minimum_quote_nonspace_chars=RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
        )
    except pipeline_inspector.InspectorError as exc:
        full_parse_failure = str(exc)
    rescued = [row for row in quote_rows if row.get("normalization_required_for_match")]
    if (
        preflight.get("status")
        != "pass_zero_call_retry05_to_retry06_program_only_no_request_change"
        or set(request_shas) != {"3", "13", "19"}
        or any(row.get("differences") for row in preflight_rows or [])
        or chapter3_receipt.get("status") != "reused_verified_no_new_model_call"
        or chapter3_receipt.get("model_api_calls") != 0
        or chapter3_receipt.get("network_attempts") != 0
        or "逐字连续子串" not in str(chapter13_stop.get("reason") or "")
        or global_stop.get("completed_chapters") != [3]
        or global_stop.get("new_attempted_chapters") != [13]
        or global_stop.get("batch_invocations") != 1
        or manifest.get("status") != "main_inspector_hard_stop"
        or len(quote_rows) != 64
        or len(rescued) != 1
        or rescued[0].get("item_id") != "EV-C0013-03"
        or rescued[0].get("anchor_id") != "E0006"
        or rescued[0].get("model_quote")
        != "恩.史密斯.”\n　　值夜者？“正义”和“倒吊人”提"
        or rescued[0].get("formal_quote")
        != "恩.史密斯。”\n　　值夜者？“正义”和“倒吊人”提"
        or full_parse_failure != "EV-C0013-03.evidence.reason 必须是非空字符串"
    ):
        raise ZBatchError("retry06第13章标点等价拒收旁账不能机械复现")
    return {
        "schema_version": "z83-inspector-retry06-punctuation-reject-reference-v1",
        "source_run_dir": source.relative_to(ROOT).as_posix(),
        "source_inspector_tree": APPROVED_RETRY06_INSPECTOR_TREE,
        "paths": {
            key: path.relative_to(ROOT).as_posix() for key, path in paths.items()
        },
        "sha256": expected,
        "candidate_request_sha256": request_shas,
        "chapter3": {
            "status": "approved_reuse_only",
            "source_retry05_response_reused": True,
            "source_usage_imported": False,
            "source_network_attempt_imported": False,
            "reuse_receipt_sha256": expected["chapter3_reuse_receipt"],
            "routing_sha256": expected["chapter3_routing"],
        },
        "chapter13": {
            "status": "rejected_never_reuse",
            "request_sha256": expected["chapter13_request"],
            "raw_response_sha256": expected["chapter13_raw"],
            "hard_stop_sha256": expected["chapter13_hard_stop"],
            "model_evidence_rows": len(quote_rows),
            "anchor_ids_legal": True,
            "normalization_rescued_rows": 1,
            "rescued_item_id": "EV-C0013-03",
            "rescued_anchor_id": "E0006",
            "observed_byte_level_difference": {
                "offset": 5,
                "model_character": ".",
                "model_codepoint": "U+002E",
                "formal_character": "。",
                "formal_codepoint": "U+3002",
                "authority_wording_discrepancy": (
                    "续令写右引号替换；封存原始字节实际为句号全半角替换"
                ),
            },
            "model_quote": rescued[0]["model_quote"],
            "formal_quote": rescued[0]["formal_quote"],
            "imported_as_result": False,
            "full_response_contract_still_invalid": True,
            "full_parse_failure": full_parse_failure,
        },
        "chapter19": {"status": "not_called"},
    }


def _build_inspector_compatibility(
    run_dir: Path,
    *,
    max_tokens: int,
    allow_test_run_dir: bool,
) -> dict[str, Any]:
    if max_tokens not in {INSPECTOR_BASE_MAX_TOKENS, INSPECTOR_COMPAT_MAX_TOKENS}:
        raise ZBatchError("检查员输出上限只允许8000或已拍的32000")
    if not allow_test_run_dir:
        if (
            _formal_completed_seed_target(run_dir)
            and max_tokens != INSPECTOR_COMPAT_MAX_TOKENS
        ):
            raise ZBatchError(
                "retry04至retry12必须使用已拍的检查员32000上限"
            )
        if (
            max_tokens == INSPECTOR_COMPAT_MAX_TOKENS
            and not _formal_completed_seed_target(run_dir)
        ):
            raise ZBatchError(
                "检查员32000兼容参数只准落在已拍的retry04至retry12"
            )
    if max_tokens == INSPECTOR_BASE_MAX_TOKENS:
        return {
            "schema_version": "z83-inspector-compatibility-v1",
            "status": "baseline_8000",
            "max_tokens": INSPECTOR_BASE_MAX_TOKENS,
            "contract_path": INSPECTOR_CONTRACT.relative_to(ROOT).as_posix(),
            "contract_sha256": INSPECTOR_CONTRACT_SHA256,
            "differences": [],
        }

    baseline = read_json(INSPECTOR_CONTRACT)
    candidate = copy.deepcopy(baseline)
    stage = candidate["profiles"][pipeline_inspector.DEFAULT_PROFILE]["stages"][
        "semantic_route"
    ]
    if stage.get("max_tokens") != INSPECTOR_BASE_MAX_TOKENS:
        raise ZBatchError("检查员基线合同不再是8000，拒绝生成兼容件")
    stage["max_tokens"] = INSPECTOR_COMPAT_MAX_TOKENS
    differences = _json_differences(baseline, candidate)
    expected_difference = [
        {
            "path": f"$.profiles.{pipeline_inspector.DEFAULT_PROFILE}.stages.semantic_route.max_tokens",
            "before": INSPECTOR_BASE_MAX_TOKENS,
            "after": INSPECTOR_COMPAT_MAX_TOKENS,
        }
    ]
    if differences != expected_difference:
        raise ZBatchError("检查员32k隔离合同不止改了max_tokens")
    contract_path = run_dir / LOCAL_INSPECTOR_CONTRACT
    write_json(contract_path, candidate)
    reference = _retry03_inspector_reference()
    write_json(run_dir / RETRY03_INSPECTOR_REFERENCE, reference)
    receipt = {
        "schema_version": "z83-inspector-compatibility-v1",
        "status": "single_variable_8000_to_32000",
        "max_tokens": INSPECTOR_COMPAT_MAX_TOKENS,
        "baseline_contract_path": INSPECTOR_CONTRACT.relative_to(ROOT).as_posix(),
        "baseline_contract_sha256": INSPECTOR_CONTRACT_SHA256,
        "contract_path": LOCAL_INSPECTOR_CONTRACT.as_posix(),
        "contract_sha256": sha256_file(contract_path),
        "differences": differences,
        "retry03_rejected_response_reference_sha256": canonical_sha(reference),
        "retry03_rejected_response_imported": False,
    }
    if run_dir.name == APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME:
        mapping_contract = pipeline_inspector.quote_punctuation_equivalence_contract()
        mapping_path = run_dir / RETRY07_PUNCTUATION_EQUIVALENCE
        write_json(mapping_path, mapping_contract)
        retry06_reference = _retry06_inspector_reference()
        write_json(run_dir / RETRY06_INSPECTOR_REFERENCE, retry06_reference)
        retry05_reference = _retry05_inspector_reference()
        write_json(run_dir / RETRY05_INSPECTOR_REFERENCE, retry05_reference)
        receipt.update(
            {
                "punctuation_equivalence_path": (
                    RETRY07_PUNCTUATION_EQUIVALENCE.as_posix()
                ),
                "punctuation_equivalence_sha256": (
                    pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                ),
                "punctuation_equivalence_file_sha256": sha256_file(mapping_path),
                "retry06_punctuation_reject_reference_sha256": canonical_sha(
                    retry06_reference
                ),
                "retry05_chapter3_reuse_reference_sha256": canonical_sha(
                    retry05_reference
                ),
                "retry06_rejected_response_imported": False,
            }
        )
    if _formal_punctuation_unit_target(run_dir):
        mapping_contract = (
            pipeline_inspector.quote_punctuation_unit_equivalence_contract()
        )
        mapping_path = run_dir / RETRY08_PUNCTUATION_UNIT_EQUIVALENCE
        write_json(mapping_path, mapping_contract)
        retry07_reference = _retry07_preflight_hard_stop_reference()
        write_json(run_dir / RETRY07_PREFLIGHT_HARD_STOP_REFERENCE, retry07_reference)
        retry06_reference = _retry06_inspector_reference()
        write_json(run_dir / RETRY06_INSPECTOR_REFERENCE, retry06_reference)
        retry05_reference = _retry05_inspector_reference()
        write_json(run_dir / RETRY05_INSPECTOR_REFERENCE, retry05_reference)
        receipt.update(
            {
                "punctuation_unit_equivalence_path": (
                    RETRY08_PUNCTUATION_UNIT_EQUIVALENCE.as_posix()
                ),
                "punctuation_unit_equivalence_sha256": (
                    pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                ),
                "punctuation_unit_equivalence_file_sha256": sha256_file(
                    mapping_path
                ),
                "retry07_preflight_hard_stop_reference_sha256": canonical_sha(
                    retry07_reference
                ),
                "retry06_punctuation_reject_reference_sha256": canonical_sha(
                    retry06_reference
                ),
                "retry05_chapter3_reuse_reference_sha256": canonical_sha(
                    retry05_reference
                ),
                "retry07_artifacts_imported_as_result": False,
                "retry06_rejected_response_imported": False,
            }
        )
    write_json(run_dir / LOCAL_INSPECTOR_CONTRACT_RECEIPT, receipt)
    if run_dir.name == APPROVED_QUOTE_CONSTRAINT_TARGET_NAME:
        write_json(
            run_dir / RETRY04_INSPECTOR_REFERENCE,
            _retry04_inspector_reference(),
        )
    if run_dir.name == APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME:
        write_json(
            run_dir / RETRY05_INSPECTOR_REFERENCE,
            _retry05_inspector_reference(),
        )
    return receipt


def _verify_inspector_compatibility(run_dir: Path, expected: Mapping[str, Any]) -> Path:
    max_tokens = expected.get("max_tokens")
    if max_tokens == INSPECTOR_BASE_MAX_TOKENS:
        if (run_dir / LOCAL_INSPECTOR_CONTRACT).exists():
            raise ZBatchError("8k基线目录意外出现32k隔离合同")
        return INSPECTOR_CONTRACT
    if max_tokens != INSPECTOR_COMPAT_MAX_TOKENS:
        raise ZBatchError("检查员兼容登记的输出上限非法")
    contract_path = run_dir / LOCAL_INSPECTOR_CONTRACT
    receipt_path = run_dir / LOCAL_INSPECTOR_CONTRACT_RECEIPT
    reference_path = run_dir / RETRY03_INSPECTOR_REFERENCE
    if (
        not contract_path.is_file()
        or not receipt_path.is_file()
        or not reference_path.is_file()
    ):
        raise ZBatchError("检查员32k隔离合同或来源旁账不齐")
    receipt = read_json(receipt_path)
    reference = read_json(reference_path)
    if receipt != expected or reference != _retry03_inspector_reference():
        raise ZBatchError("检查员32k兼容收据或retry03来源旁账漂移")
    if run_dir.name == APPROVED_QUOTE_CONSTRAINT_TARGET_NAME:
        retry04_reference_path = run_dir / RETRY04_INSPECTOR_REFERENCE
        if (
            not retry04_reference_path.is_file()
            or read_json(retry04_reference_path) != _retry04_inspector_reference()
        ):
            raise ZBatchError("retry05缺retry04短引改写硬停冻结旁账")
    if run_dir.name == APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME:
        retry05_reference_path = run_dir / RETRY05_INSPECTOR_REFERENCE
        if (
            not retry05_reference_path.is_file()
            or read_json(retry05_reference_path) != _retry05_inspector_reference()
        ):
            raise ZBatchError("retry06缺retry05第3章复用／第13章拒收冻结旁账")
    if run_dir.name == APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME:
        retry06_reference_path = run_dir / RETRY06_INSPECTOR_REFERENCE
        retry05_reference_path = run_dir / RETRY05_INSPECTOR_REFERENCE
        mapping_path = run_dir / RETRY07_PUNCTUATION_EQUIVALENCE
        expected_retry06_reference = _retry06_inspector_reference()
        expected_retry05_reference = _retry05_inspector_reference()
        expected_mapping = pipeline_inspector.quote_punctuation_equivalence_contract()
        if (
            not retry06_reference_path.is_file()
            or read_json(retry06_reference_path) != expected_retry06_reference
            or not retry05_reference_path.is_file()
            or read_json(retry05_reference_path) != expected_retry05_reference
            or not mapping_path.is_file()
            or read_json(mapping_path) != expected_mapping
            or receipt.get("punctuation_equivalence_sha256")
            != pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
            or receipt.get("punctuation_equivalence_file_sha256")
            != sha256_file(mapping_path)
            or receipt.get("retry06_punctuation_reject_reference_sha256")
            != canonical_sha(expected_retry06_reference)
            or receipt.get("retry05_chapter3_reuse_reference_sha256")
            != canonical_sha(expected_retry05_reference)
            or receipt.get("retry06_rejected_response_imported") is not False
        ):
            raise ZBatchError("retry07缺固定标点映射或retry06封存拒收旁账")
    if _formal_punctuation_unit_target(run_dir):
        retry07_reference_path = run_dir / RETRY07_PREFLIGHT_HARD_STOP_REFERENCE
        retry06_reference_path = run_dir / RETRY06_INSPECTOR_REFERENCE
        retry05_reference_path = run_dir / RETRY05_INSPECTOR_REFERENCE
        mapping_path = run_dir / RETRY08_PUNCTUATION_UNIT_EQUIVALENCE
        expected_retry07_reference = _retry07_preflight_hard_stop_reference()
        expected_retry06_reference = _retry06_inspector_reference()
        expected_retry05_reference = _retry05_inspector_reference()
        expected_mapping = (
            pipeline_inspector.quote_punctuation_unit_equivalence_contract()
        )
        if (
            not retry07_reference_path.is_file()
            or read_json(retry07_reference_path) != expected_retry07_reference
            or not retry06_reference_path.is_file()
            or read_json(retry06_reference_path) != expected_retry06_reference
            or not retry05_reference_path.is_file()
            or read_json(retry05_reference_path) != expected_retry05_reference
            or not mapping_path.is_file()
            or read_json(mapping_path) != expected_mapping
            or receipt.get("punctuation_unit_equivalence_sha256")
            != pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
            or receipt.get("punctuation_unit_equivalence_file_sha256")
            != sha256_file(mapping_path)
            or receipt.get("retry07_preflight_hard_stop_reference_sha256")
            != canonical_sha(expected_retry07_reference)
            or receipt.get("retry06_punctuation_reject_reference_sha256")
            != canonical_sha(expected_retry06_reference)
            or receipt.get("retry05_chapter3_reuse_reference_sha256")
            != canonical_sha(expected_retry05_reference)
            or receipt.get("retry07_artifacts_imported_as_result") is not False
            or receipt.get("retry06_rejected_response_imported") is not False
        ):
            raise ZBatchError("retry08／retry09缺标点单元合同或retry07／retry06封存旁账")
    baseline = read_json(INSPECTOR_CONTRACT)
    candidate = read_json(contract_path)
    differences = _json_differences(baseline, candidate)
    if (
        differences != receipt.get("differences")
        or receipt.get("contract_sha256") != sha256_file(contract_path)
        or receipt.get("retry03_rejected_response_reference_sha256")
        != canonical_sha(reference)
        or receipt.get("retry03_rejected_response_imported") is not False
    ):
        raise ZBatchError("检查员32k隔离合同不能证明单变量")
    return contract_path


def _assert_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file() or sha256_file(path) != expected_sha256:
        raise ZBatchError(f"{label}不存在或 SHA 漂移：{path}")


def source_pins() -> dict[str, Any]:
    rows = [
        (V3_PACKAGE, V3_PACKAGE_SHA256, "v3注入包"),
        (V3_CONTRACT, V3_CONTRACT_SHA256, "v3运输合同"),
        (V3_ADJUDICATION, V3_ADJUDICATION_SHA256, "v3语义判词"),
        (OLD_ARM_BASELINE, OLD_ARM_BASELINE_SHA256, "旧臂2旧25基线"),
        (CURRENT_RECORDS, CURRENT_RECORDS_SHA256, "现役122条隔离副本"),
        (GOLD_POINTER, GOLD_POINTER_SHA256, "正式金标指针"),
        (GOLD_FILE, GOLD_FILE_SHA256, "正式金标v1.2"),
        (INSPECTOR_CONTRACT, INSPECTOR_CONTRACT_SHA256, "Z76检查员合同"),
    ]
    result = []
    for path, expected, label in rows:
        _assert_file(path, expected, label)
        result.append(
            {
                "label": label,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected,
            }
        )
    for chapter, expected in V3_REQUEST_SHA256.items():
        path = V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
        _assert_file(path, expected, f"v3第{chapter}章请求")
        result.append(
            {
                "label": f"v3第{chapter}章请求",
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected,
            }
        )
    return {"status": "pass", "rows": result}


def protected_snapshot() -> dict[str, Any]:
    """只钉正式入口和本轮冻结底稿；不把本轮新目录纳入保护树。"""

    return {
        "source_pins": source_pins(),
        "existing_formal": z79.assert_protected(),
        "v3_run_tree": z68.tree_fingerprint(V3_RUN_DIR),
        "v3_report_tree": z68.tree_fingerprint(V3_REPORT_DIR),
    }


def assert_safe_run_dir(run_dir: Path, *, allow_test_run_dir: bool = False) -> None:
    if allow_test_run_dir:
        return
    resolved = run_dir.resolve(strict=False)
    default = DEFAULT_RUN_DIR.resolve(strict=False)
    formal_runs_root = (ROOT / "runs").resolve(strict=False)
    is_approved_retry = (
        resolved.parent == formal_runs_root
        and FORMAL_RETRY_RUN_NAME.fullmatch(resolved.name) is not None
    )
    is_approved_z94 = (
        resolved.parent == formal_runs_root
        and resolved.name
        in {
            APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
            APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
        }
    )
    if resolved != default and not is_approved_retry and not is_approved_z94:
        raise ZBatchError(
            "第83道正式轮只准使用原运行目录，或同级的新编号目录 "
            f"{RUN_ID}_transport_retryNN，或已拍第94道步二唯一运行目录"
        )


def _copy_file(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    source_resolved = source.resolve()
    root_resolved = ROOT.resolve()
    source_value = (
        source_resolved.relative_to(root_resolved).as_posix()
        if source_resolved.is_relative_to(root_resolved)
        else source_resolved.as_posix()
    )
    return {
        "source": source_value,
        "source_sha256": sha256_file(source),
        "target": target.as_posix(),
        "target_sha256": sha256_file(target),
    }


def _copy_inputs(run_dir: Path) -> list[dict[str, Any]]:
    receipts = []
    for chapter in TARGET_CHAPTERS:
        chapter_matches = sorted(
            (V3_RUN_DIR / "inputs/chapters").glob(f"{chapter:04d}_*.txt")
        )
        if len(chapter_matches) != 1:
            raise ZBatchError(f"v3第{chapter}章冻结正文数不是1")
        receipts.append(
            _copy_file(
                chapter_matches[0],
                run_dir / "inputs/chapters" / chapter_matches[0].name,
            )
        )
        receipts.append(
            _copy_file(
                V3_RUN_DIR / f"inputs/evidence_catalogs/ch{chapter:04d}.json",
                run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json",
            )
        )
    receipts.extend(
        [
            _copy_file(
                CURRENT_RECORDS, run_dir / "inputs/current_formal_records_122.json"
            ),
            _copy_file(
                OLD_ARM_BASELINE, run_dir / "provenance/score_only/旧臂2旧25基线.json"
            ),
            _copy_file(
                V3_ADJUDICATION, run_dir / "provenance/score_only/v3语义判词基线.json"
            ),
            _copy_file(
                GOLD_POINTER, run_dir / "provenance/score_only/正式金标指针.json"
            ),
            _copy_file(
                GOLD_FILE, run_dir / "provenance/score_only/第3章结构层金标v1.2.json"
            ),
            _copy_file(V3_PACKAGE, run_dir / "prompt_frozen/事实说明书注入包_v3.json"),
            _copy_file(V3_CONTRACT, run_dir / LOCAL_TRANSPORT),
        ]
    )
    for chapter in TARGET_CHAPTERS:
        receipts.append(
            _copy_file(
                V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json",
                run_dir / f"prepared_requests/ch{chapter:04d}.json",
            )
        )
    return receipts


def load_bundle(run_dir: Path) -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(
        run_dir / LOCAL_TRANSPORT, profile=PROFILE
    )


def _model_visible_text(body: Mapping[str, Any]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ZBatchError("请求缺 messages")
    return "\n".join(
        str(row.get("content", "")) for row in messages if isinstance(row, dict)
    )


def forbidden_model_hits(messages_or_body: Any) -> list[str]:
    if isinstance(messages_or_body, dict) and "messages" in messages_or_body:
        text = _model_visible_text(messages_or_body)
    else:
        text = json.dumps(messages_or_body, ensure_ascii=False)
    return [token for token in FORBIDDEN_MODEL_TOKENS if token in text]


def _assert_frozen_body(chapter: int, body: Mapping[str, Any]) -> None:
    source = read_json(V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json")
    if body != source:
        raise ZBatchError(f"第{chapter}章主请求不再等于v3冻结请求")
    if forbidden_model_hits(body):
        raise ZBatchError(f"第{chapter}章主请求含判分侧材料")
    bundle = load_bundle_for_body_validation()
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage("neutral_extract"),
    )
    if rebuilt != body:
        raise ZBatchError(f"第{chapter}章主请求不能由v3合同重建")


def load_bundle_for_body_validation() -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(V3_CONTRACT, profile=PROFILE)


def call_artifacts_present(run_dir: Path) -> list[str]:
    candidates = (
        run_dir / "main/run_claim.json",
        run_dir / "main/call_attempts.jsonl",
        run_dir / "main/usage.jsonl",
        run_dir / "main/requests",
        run_dir / "main/responses",
        run_dir / "repair/run_claim.json",
        run_dir / "repair/call_attempts.jsonl",
        run_dir / "review/inspector",
        run_dir / "final_review/inspector",
    )
    return [
        path.relative_to(run_dir).as_posix() for path in candidates if path.exists()
    ]


def _verify_copied_inputs(
    run_dir: Path, preflight: Mapping[str, Any]
) -> dict[str, Any]:
    rows = preflight.get("copied_inputs")
    expected_count = len(TARGET_CHAPTERS) * 3 + 7
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ZBatchError(f"第83道隔离副本收据数量错误：应{expected_count}")
    run_root = run_dir.resolve()
    repo_root = ROOT.resolve()
    seen_targets: set[str] = set()
    checks = []
    for index, value in enumerate(rows):
        if not isinstance(value, dict):
            raise ZBatchError(f"隔离副本收据第{index}行不是对象")
        source_value = value.get("source")
        target_value = value.get("target")
        if not isinstance(source_value, str) or not isinstance(target_value, str):
            raise ZBatchError(f"隔离副本收据第{index}行缺路径")
        source = (ROOT / source_value).resolve()
        target = Path(target_value).resolve()
        if not source.is_relative_to(repo_root) or not target.is_relative_to(run_root):
            raise ZBatchError(f"隔离副本收据第{index}行越出允许目录")
        relative_target = target.relative_to(run_root).as_posix()
        if relative_target in seen_targets:
            raise ZBatchError(f"隔离副本收据目标重复：{relative_target}")
        seen_targets.add(relative_target)
        if not source.is_file() or not target.is_file():
            raise ZBatchError(f"隔离副本缺文件：{relative_target}")
        source_sha = sha256_file(source)
        target_sha = sha256_file(target)
        if (
            source_sha != value.get("source_sha256")
            or target_sha != value.get("target_sha256")
            or source.read_bytes() != target.read_bytes()
        ):
            raise ZBatchError(f"隔离副本与冻结来源不再逐字一致：{relative_target}")
        checks.append({"target": relative_target, "sha256": target_sha, "passed": True})
    return {"status": "pass", "count": len(checks), "checks": checks}


def prepare(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    inspector_max_tokens: int = INSPECTOR_BASE_MAX_TOKENS,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    assert_safe_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    pins = source_pins()
    protected = protected_snapshot()
    run_dir.mkdir(parents=True)
    inspector_compatibility = _build_inspector_compatibility(
        run_dir,
        max_tokens=inspector_max_tokens,
        allow_test_run_dir=allow_test_run_dir,
    )
    copied = _copy_inputs(run_dir)
    rows = []
    for chapter in TARGET_CHAPTERS:
        target = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        body = read_json(target)
        _assert_frozen_body(chapter, body)
        rows.append(
            {
                "chapter": chapter,
                "source_sha256": V3_REQUEST_SHA256[chapter],
                "prepared_sha256": sha256_file(target),
                "byte_identical_to_v3": target.read_bytes()
                == (
                    V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
                ).read_bytes(),
                "forbidden_model_hits": forbidden_model_hits(body),
            }
        )
    preflight = {
        "schema_version": "z83-preflight-v1",
        "status": "pass_zero_call_prepared",
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "main_samples_per_chapter": 1,
        "prompt_policy": "v3三章完整请求逐字复用；主Prompt零改动",
        "semantic_truth_policy": "程序只生成路由与齐套检查；正式语义判词必须人工逐条绑定最终事件SHA",
        "inspector_compatibility": inspector_compatibility,
        "retry_limits": {
            "per_event": MAX_TARGETED_RETRIES_PER_EVENT,
            "per_chapter": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "total": MAX_TARGETED_RETRIES_TOTAL,
        },
        "source_pins": pins,
        "copied_inputs": copied,
        "protected_before": protected,
        "rows": rows,
        "producer": {
            "path": Path(__file__).relative_to(ROOT).as_posix(),
            "sha256": sha256_file(Path(__file__)),
        },
        "producer_dependencies": {
            "pipeline_inspector": {
                "path": Path(pipeline_inspector.__file__)
                .resolve()
                .relative_to(ROOT)
                .as_posix(),
                "sha256": sha256_file(Path(pipeline_inspector.__file__).resolve()),
            },
            "api_transport": {
                "path": Path(api_transport.__file__)
                .resolve()
                .relative_to(ROOT)
                .as_posix(),
                "sha256": sha256_file(Path(api_transport.__file__).resolve()),
            },
        },
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z83-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "main": "not_started",
            "review": "not_started",
            "repair": "not_started",
            "final": "not_started",
        },
    )
    verify_prepared(
        run_dir, require_zero_call=True, allow_test_run_dir=allow_test_run_dir
    )
    return preflight


def verify_prepared(
    run_dir: Path,
    *,
    require_zero_call: bool,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    assert_safe_run_dir(run_dir, allow_test_run_dir=allow_test_run_dir)
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第83道预演状态漂移")
    if source_pins() != preflight.get("source_pins"):
        raise ZBatchError("第83道冻结源漂移")
    if protected_snapshot() != preflight.get("protected_before"):
        raise ZBatchError("第83道保护件漂移")
    isolated_inputs = _verify_copied_inputs(run_dir, preflight)
    inspector_contract_path = _verify_inspector_compatibility(
        run_dir,
        preflight.get("inspector_compatibility") or {},
    )
    producer = ROOT / str(preflight["producer"]["path"])
    if sha256_file(producer) != preflight["producer"]["sha256"]:
        raise ZBatchError("第83道运行器 prepare 后漂移")
    producer_dependencies = preflight.get("producer_dependencies")
    if not isinstance(producer_dependencies, dict):
        raise ZBatchError("第83道预演缺检查员依赖程序锁定账")
    for dependency_name in ("pipeline_inspector", "api_transport"):
        dependency = producer_dependencies.get(dependency_name)
        if not isinstance(dependency, dict):
            raise ZBatchError(f"第83道预演缺{dependency_name}锁定账")
        dependency_path = ROOT / str(dependency.get("path") or "")
        if not dependency_path.is_file() or sha256_file(
            dependency_path
        ) != dependency.get("sha256"):
            raise ZBatchError(f"{dependency_name} prepare 后漂移")
    checks = []
    for chapter in TARGET_CHAPTERS:
        target = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        source = V3_RUN_DIR / f"prepared_requests/ch{chapter:04d}.json"
        body = read_json(target)
        _assert_frozen_body(chapter, body)
        passed = (
            target.read_bytes() == source.read_bytes()
            and sha256_file(target) == V3_REQUEST_SHA256[chapter]
            and not forbidden_model_hits(body)
        )
        if not passed:
            raise ZBatchError(f"第{chapter}章冻结请求复验失败")
        checks.append(
            {"chapter": chapter, "passed": True, "sha256": sha256_file(target)}
        )
    artifacts = call_artifacts_present(run_dir)
    if require_zero_call and artifacts:
        raise ZBatchError(f"第83道零调用目录出现调用工件：{artifacts}")
    receipt = {
        "schema_version": "z83-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "prompt_unchanged": True,
        "checks": checks,
        "protected_unchanged": True,
        "isolated_inputs": isolated_inputs,
        "inspector_contract_path": (
            inspector_contract_path.relative_to(ROOT).as_posix()
            if inspector_contract_path.is_relative_to(ROOT)
            else inspector_contract_path.as_posix()
        ),
        "inspector_contract_sha256": sha256_file(inspector_contract_path),
        "call_artifacts": artifacts,
    }
    write_json(run_dir / "prepared_verification.json", receipt)
    return receipt


def _acquire_claim(path: Path, schema_version: str) -> dict[str, Any]:
    claim = {
        "schema_version": schema_version,
        "status": "claimed_do_not_resume",
        "pid": os.getpid(),
        "claimed_at": z68.now_iso(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError(f"阶段已经开跑或曾中断，拒绝重复：{path}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _require_api_key_before_claim() -> None:
    if not os.environ.get("SENSENOVA_API_KEY"):
        raise ZBatchError("缺少 SENSENOVA_API_KEY；发网前0调用拒绝，未创建运行占用票")


def _chapter_text_path(run_dir: Path, chapter: int) -> Path:
    matches = sorted((run_dir / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"第{chapter}章隔离正文数不是1")
    return matches[0]


def _catalog(run_dir: Path, chapter: int) -> list[dict[str, Any]]:
    data = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ZBatchError(f"第{chapter}章冻结目录为空")
    return entries


def _assert_batch_quotes_equal_frozen_catalog(
    run_dir: Path,
    chapter: int,
    batch: Mapping[str, Any],
) -> None:
    """证明程序回填的短引直接来自本运行隔离冻结目录。"""

    catalog = {
        str(row["anchor_id"]): str(row["quote"]) for row in _catalog(run_dir, chapter)
    }
    validated = pipeline_inspector.validate_review_batch(batch)
    for item in validated["items"]:
        for anchor in item["anchors"]:
            anchor_id = str(anchor["anchor_id"])
            if anchor_id not in catalog or str(anchor["quote"]) != catalog[anchor_id]:
                raise ZBatchError(
                    f"第{chapter}章{item['item_id']}检查批短引不等于冻结证据目录：{anchor_id}"
                )


def _usage_summary(*paths: Path) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    successful = 0
    for path in paths:
        for row in z68.read_jsonl(path):
            successful += 1
            for key, value in (row.get("usage") or {}).items():
                if isinstance(value, int):
                    totals[key] += value
    return {"successful_responses": successful, "usage_totals": dict(totals)}


def _stage_relative(stage_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(stage_dir).as_posix()
    except ValueError as exc:
        raise ZBatchError(f"调用工件越出阶段目录：{path}") from exc


def _transport_paths(stage_dir: Path, stage: str, case_id: str) -> dict[str, Path]:
    return {
        "request": stage_dir / f"requests/{stage}/{case_id}_request.json",
        "raw_response": stage_dir / f"responses/{stage}/{case_id}_raw.json",
        "response_meta": stage_dir / f"responses/{stage}/{case_id}_meta.json",
    }


def _transport_receipt_fields(
    stage_dir: Path, stage: str, case_id: str
) -> dict[str, Any]:
    paths = _transport_paths(stage_dir, stage, case_id)
    for label, path in paths.items():
        if not path.is_file():
            raise ZBatchError(f"调用工件缺失：{label}={path}")
    return {
        "case_id": case_id,
        "request_path": _stage_relative(stage_dir, paths["request"]),
        "request_sha256": sha256_file(paths["request"]),
        "raw_response_path": _stage_relative(stage_dir, paths["raw_response"]),
        "raw_response_sha256": sha256_file(paths["raw_response"]),
        "response_meta_path": _stage_relative(stage_dir, paths["response_meta"]),
        "response_meta_sha256": sha256_file(paths["response_meta"]),
    }


def _read_response_content(path: Path) -> tuple[dict[str, Any], str]:
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise ZBatchError(f"原始响应顶层不是对象：{path}")
    content, finish_reason = api_transport.response_content(raw)
    if finish_reason != "stop":
        raise ZBatchError(f"原始响应未正常结束：{path}")
    if raw.get("model") != api_transport.PINNED_MODEL:
        raise ZBatchError(f"原始响应模型不等于冻结模型：{path}")
    return raw, content


def _verify_successful_exchange(
    *,
    stage_dir: Path,
    stage: str,
    case_id: str,
    expected_body: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """从落盘请求、响应、元数据和运输账重建一次成功调用。"""

    paths = _transport_paths(stage_dir, stage, case_id)
    expected_paths = {
        "request_path": _stage_relative(stage_dir, paths["request"]),
        "raw_response_path": _stage_relative(stage_dir, paths["raw_response"]),
        "response_meta_path": _stage_relative(stage_dir, paths["response_meta"]),
    }
    for key, expected in expected_paths.items():
        if receipt.get(key) != expected:
            raise ZBatchError(f"{case_id}调用账路径不等于固定落盘位置：{key}")
    for label, path, sha_key in (
        ("请求", paths["request"], "request_sha256"),
        ("原始响应", paths["raw_response"], "raw_response_sha256"),
        ("响应元数据", paths["response_meta"], "response_meta_sha256"),
    ):
        if not path.is_file() or receipt.get(sha_key) != sha256_file(path):
            raise ZBatchError(f"{case_id}{label}缺失或 SHA 与调用账不符")
    request_record = read_json(paths["request"])
    if (
        not isinstance(request_record, dict)
        or request_record.get("stage") != stage
        or request_record.get("case_id") != case_id
        or request_record.get("body") != expected_body
        or request_record.get("_security") != "no_api_key_no_authorization"
    ):
        raise ZBatchError(f"{case_id}实发请求记录不能由冻结合同重建")
    raw, content = _read_response_content(paths["raw_response"])
    meta = read_json(paths["response_meta"])
    request_sha = sha256_file(paths["request"])
    raw_sha = sha256_file(paths["raw_response"])
    if (
        not isinstance(meta, dict)
        or meta.get("request_sha256") != request_sha
        or meta.get("raw_response_sha256") != raw_sha
        or meta.get("requested_model") != api_transport.PINNED_MODEL
        or meta.get("response_model") != api_transport.PINNED_MODEL
        or meta.get("finish_reason") != "stop"
    ):
        raise ZBatchError(f"{case_id}响应元数据与请求／原始响应不一致")
    all_attempts = z68.read_jsonl(stage_dir / "call_attempts.jsonl")
    retry13_attempts = bool(all_attempts) and all(
        row.get("schema") == z83_retry_transport.ATTEMPT_LEDGER_SCHEMA
        for row in all_attempts
    )
    attempts = (
        [row for row in all_attempts if row.get("logical_request_id") == case_id]
        if retry13_attempts
        else [
            row
            for row in all_attempts
            if row.get("stage") == stage and row.get("case_id") == case_id
        ]
    )
    if not attempts or any(
        row.get("request_sha256") != request_sha for row in attempts
    ):
        raise ZBatchError(f"{case_id}运输尝试账未绑定实发请求")
    if retry13_attempts:
        z83_retry_transport.validate_attempt_rows(attempts)
        expected_wire_sha = hashlib.sha256(
            _wire_body_bytes(expected_body)
        ).hexdigest()
        if any(
            row.get("request_artifact_sha256") != request_sha
            or row.get("wire_body_sha256") != expected_wire_sha
            for row in attempts
        ):
            raise ZBatchError(
                f"{case_id}retry13尝试账未绑定冻结请求工件或实发正文"
            )
    usage_rows = [
        row
        for row in z68.read_jsonl(stage_dir / "usage.jsonl")
        if row.get("stage") == stage and row.get("case_id") == case_id
    ]
    if len(usage_rows) != 1:
        raise ZBatchError(f"{case_id}成功 usage 账不是唯一一条")
    usage = usage_rows[0]
    if (
        usage.get("request_sha256") != request_sha
        or usage.get("raw_response_sha256") != raw_sha
        or usage.get("finish_reason") != "stop"
        or usage.get("usage")
        != (raw.get("usage") if isinstance(raw.get("usage"), dict) else {})
    ):
        raise ZBatchError(f"{case_id}usage 账与原始响应不一致")
    return raw, content


def _assert_seed_source_dir(
    source_run_dir: Path,
    target_run_dir: Path,
    *,
    allow_test_run_dir: bool,
) -> str:
    source = source_run_dir.resolve(strict=False)
    target = target_run_dir.resolve(strict=False)
    if source == target:
        raise ZBatchError("主样张复用来源不能等于目标运行目录")
    if target.name in {
        APPROVED_COMPLETED_SEED_TARGET_NAME,
        APPROVED_QUOTE_CONSTRAINT_TARGET_NAME,
        APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME,
        APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME,
        APPROVED_PUNCTUATION_UNIT_TARGET_NAME,
        APPROVED_CAPACITY_OVERRIDE_TARGET_NAME,
        APPROVED_THIRTEEN_RETRY_TARGET_NAME,
        APPROVED_COUNT_CONTRACT_TARGET_NAME,
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME,
        APPROVED_ATOMIC_SPLIT_TARGET_NAME,
        APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    }:
        if source.name == APPROVED_COMPLETED_SEED_SOURCE_NAME:
            return "completed_main_retry03"
        raise ZBatchError(
            "retry04至retry12只接受各续令批准的retry03完整三章"
        )
    if allow_test_run_dir:
        manifest_path = source / "main/run_manifest.json"
        if (
            manifest_path.is_file()
            and read_json(manifest_path).get("status")
            == "completed_candidate_silver_only"
        ):
            return "completed_main"
        return "interrupted_prefix"
    runs_root = (ROOT / "runs").resolve(strict=False)
    if source.parent != runs_root or target.parent != runs_root:
        raise ZBatchError("主样张复用来源或目标越出正式 runs 目录")
    if source.name == APPROVED_SEED_SOURCE_NAME:
        return "interrupted_prefix"
    raise ZBatchError(
        "主样张复用只接受已审retry01前缀，或续令②／③批准的"
        "retry03到retry12完整三章"
    )


def _seed_source(
    source_run_dir: Path,
    target_run_dir: Path,
    *,
    allow_test_run_dir: bool,
) -> dict[str, Any]:
    """只认完整成功回包；中断请求与检查员截断件都不得混入样张。"""

    source_kind = _assert_seed_source_dir(
        source_run_dir,
        target_run_dir,
        allow_test_run_dir=allow_test_run_dir,
    )
    source_stage = source_run_dir / "main"
    hard_stop_path = source_stage / "hard_stop.json"
    run_manifest_path = source_stage / "run_manifest.json"
    run_claim_path = source_stage / "run_claim.json"
    for label, path in (
        ("来源阶段状态票", run_manifest_path),
        ("来源运行占用票", run_claim_path),
        ("来源调用尝试账", source_stage / "call_attempts.jsonl"),
        ("来源成功用量账", source_stage / "usage.jsonl"),
        ("来源主样张账", source_stage / "main_sample_ledger.jsonl"),
    ):
        if not path.is_file():
            raise ZBatchError(f"{label}缺失：{path}")
    source_manifest = read_json(run_manifest_path)
    source_claim = read_json(run_claim_path)
    if not isinstance(source_manifest, dict) or not isinstance(source_claim, dict):
        raise ZBatchError("来源阶段状态票或占用票格式错误")
    hard_stop: dict[str, Any] | None = None
    if source_kind == "interrupted_prefix":
        if not hard_stop_path.is_file():
            raise ZBatchError(f"来源硬停票缺失：{hard_stop_path}")
        hard_stop = read_json(hard_stop_path)
        if (
            not isinstance(hard_stop, dict)
            or hard_stop.get("status") != "hard_stop_no_unapproved_repair"
            or hard_stop.get("error_type") != "KeyboardInterrupt"
            or hard_stop.get("targeted_retry_count") != 0
            or hard_stop.get("protected_unchanged") is not True
        ):
            raise ZBatchError("主样张复用来源不是未改结果的 KeyboardInterrupt 封存停点")
        if source_manifest.get("run_claim") != source_claim or any(
            source_manifest.get(key) != value for key, value in hard_stop.items()
        ):
            raise ZBatchError("来源硬停票、阶段状态票与占用票不一致")
    else:
        metrics_path = source_stage / "01_extract/metrics.json"
        mechanical_path = source_stage / "mechanical_verification.json"
        if hard_stop_path.exists():
            raise ZBatchError("完整三章来源主阶段意外含硬停票")
        for label, path in (
            ("来源主指标账", metrics_path),
            ("来源机械复验票", mechanical_path),
        ):
            if not path.is_file():
                raise ZBatchError(f"{label}缺失：{path}")
        metrics = read_json(metrics_path)
        mechanical = read_json(mechanical_path)
        if (
            source_manifest.get("status") != "completed_candidate_silver_only"
            or source_manifest.get("run_claim") != source_claim
            or source_manifest.get("chapters_completed") != list(TARGET_CHAPTERS)
            or source_manifest.get("targeted_retry_count") != 0
            or metrics.get("status") != "completed_candidate_silver_only"
            or metrics.get("chapters_completed") != list(TARGET_CHAPTERS)
            or metrics.get("targeted_retry_logical_calls") != 0
            or mechanical.get("status") != "pass"
            or mechanical.get("gates")
            != {
                "outside_catalog_anchor_zero": True,
                "length_rejection_zero": True,
                "whole_chapter_invalidation_zero": True,
            }
        ):
            raise ZBatchError("retry03完整三章来源状态、机械闸或零重写账不成立")
    source_tree = z68.tree_fingerprint(source_stage)
    if not allow_test_run_dir:
        expected_tree = (
            APPROVED_SEED_SOURCE_MAIN_TREE_SHA256
            if source_kind == "interrupted_prefix"
            else APPROVED_COMPLETED_SEED_MAIN_TREE_SHA256
        )
        if source_tree.get("sha256") != expected_tree:
            raise ZBatchError("已审主样张来源树指纹漂移")

    ledger_rows = z68.read_jsonl(source_stage / "main_sample_ledger.jsonl")
    if not ledger_rows:
        raise ZBatchError("主样张复用来源没有任何完整成功回包")
    chapters: list[int] = []
    successful_cases: list[str] = []
    analyses: dict[int, dict[str, Any]] = {}
    for row in ledger_rows:
        if not isinstance(row, dict):
            raise ZBatchError("来源主样张账含非对象")
        chapter = row.get("chapter")
        if isinstance(chapter, bool) or not isinstance(chapter, int):
            raise ZBatchError("来源主样张账章号错误")
        chapters.append(chapter)
        case_id = f"z83_main_ch{chapter:04d}"
        successful_cases.append(case_id)
        prepared_path = target_run_dir / f"prepared_requests/ch{chapter:04d}.json"
        if not prepared_path.is_file() or sha256_file(
            prepared_path
        ) != V3_REQUEST_SHA256.get(chapter):
            raise ZBatchError(f"第{chapter}章目标冻结请求缺失或 SHA 漂移")
        if (
            row.get("schema_version") != "z83-main-sample-exchange-v1"
            or row.get("case_id") != case_id
            or row.get("prepared_request_sha256") != sha256_file(prepared_path)
        ):
            raise ZBatchError(f"第{chapter}章来源主样张账未绑定同一冻结请求")
        _, content = _verify_successful_exchange(
            stage_dir=source_stage,
            stage="neutral_extract",
            case_id=case_id,
            expected_body=read_json(prepared_path),
            receipt=row,
        )
        parsed = candidate_envelope.parse_json_content(content)
        source_model = (
            source_stage / f"01_extract/model_json_original/ch{chapter:04d}.json"
        )
        source_audit = source_stage / f"01_extract/initial_audits/ch{chapter:04d}.json"
        if (
            not source_model.is_file()
            or row.get("parsed_model_path")
            != _stage_relative(source_stage, source_model)
            or row.get("parsed_model_file_sha256") != sha256_file(source_model)
            or row.get("parsed_model_canonical_sha256") != canonical_sha(parsed)
            or parsed != read_json(source_model)
            or not source_audit.is_file()
        ):
            raise ZBatchError(f"第{chapter}章来源解析件不能从原始响应重建")
        analysis = z77.analyze_main_response(
            parsed,
            chapter=chapter,
            catalog=_catalog(target_run_dir, chapter),
        )
        if analysis != read_json(source_audit) or analysis.get("hard_reasons"):
            raise ZBatchError(f"第{chapter}章来源初审票漂移或含新失败面")
        if len(analysis.get("eligible") or []) > MAX_TARGETED_RETRIES_PER_CHAPTER:
            raise ZBatchError(f"第{chapter}章来源机械坏条超过章级预算")
        analyses[chapter] = analysis

    expected_prefix = list(TARGET_CHAPTERS[: len(chapters)])
    if source_kind == "interrupted_prefix":
        if (
            chapters != expected_prefix
            or hard_stop is None
            or hard_stop.get("sampled_chapters") != chapters
        ):
            raise ZBatchError("来源完整成功章不是目标章顺序前缀，拒绝结果挑选")
    elif chapters != list(TARGET_CHAPTERS):
        raise ZBatchError("retry03完整来源没有逐章覆盖3／13／19")

    source_event_sha256 = (
        {
            str(chapter): sha256_file(
                source_stage / f"01_extract/events/ch{chapter:04d}.json"
            )
            for chapter in chapters
        }
        if source_kind != "interrupted_prefix"
        else {}
    )
    if not allow_test_run_dir and source_kind == "completed_main_retry03":
        if source_event_sha256 != {
            str(chapter): value
            for chapter, value in APPROVED_COMPLETED_EVENT_SHA256.items()
        }:
            raise ZBatchError("retry03三章事件SHA与续令②批准值不一致")

    attempts = z68.read_jsonl(source_stage / "call_attempts.jsonl")
    usage_rows = z68.read_jsonl(source_stage / "usage.jsonl")
    expected_attempts = (
        hard_stop.get("network_attempts")
        if source_kind == "interrupted_prefix" and hard_stop is not None
        else source_manifest.get("network_attempts")
    )
    if expected_attempts != len(attempts):
        raise ZBatchError("来源状态票调用数与尝试账不一致")
    attempt_cases = [str(row.get("case_id") or "") for row in attempts]
    usage_cases = [str(row.get("case_id") or "") for row in usage_rows]
    if usage_cases != successful_cases:
        raise ZBatchError("来源成功用量账与完整主样张账不一一对应")
    attempts_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call_number, row in enumerate(attempts, 1):
        if not isinstance(row, dict):
            raise ZBatchError("来源调用尝试账含非对象")
        case_id = str(row.get("case_id") or "")
        request_path = source_stage / f"requests/neutral_extract/{case_id}_request.json"
        if (
            row.get("call_number") != call_number
            or row.get("max_calls") != MAX_NETWORK_ATTEMPTS
            or row.get("stage") != "neutral_extract"
            or not request_path.is_file()
            or row.get("request_sha256") != sha256_file(request_path)
        ):
            raise ZBatchError("来源调用尝试账序号、阶段或请求 SHA 错误")
        attempts_by_case[case_id].append(row)
    route = api_transport.TransportRoute.from_mapping(load_bundle(target_run_dir).route)
    for case_id, rows in attempts_by_case.items():
        if [row.get("attempt") for row in rows] != list(range(1, len(rows) + 1)) or len(
            rows
        ) > route.network_attempts:
            raise ZBatchError(f"来源{case_id}运输重试序号或上限错误")
    imported_attempts = [
        row for row in attempts if str(row.get("case_id") or "") in successful_cases
    ]
    if [row.get("call_number") for row in imported_attempts] != list(
        range(1, len(imported_attempts) + 1)
    ):
        raise ZBatchError("来源完整样张调用不是尝试账前缀，拒绝结果挑选")
    incomplete_attempts = [
        row for row in attempts if str(row.get("case_id") or "") not in successful_cases
    ]
    next_case = (
        f"z83_main_ch{TARGET_CHAPTERS[len(chapters)]:04d}"
        if len(chapters) < len(TARGET_CHAPTERS)
        else None
    )
    if any(str(row.get("case_id") or "") != next_case for row in incomplete_attempts):
        raise ZBatchError("来源尝试账在完整章之后混入非下一章调用")
    if source_kind != "interrupted_prefix" and incomplete_attempts:
        raise ZBatchError("retry03完整来源仍含未完成主采样尝试")

    request_cases = {
        path.name.removesuffix("_request.json")
        for path in (source_stage / "requests/neutral_extract").glob("*_request.json")
    }
    raw_cases = {
        path.name.removesuffix("_raw.json")
        for path in (source_stage / "responses/neutral_extract").glob("*_raw.json")
    }
    meta_cases = {
        path.name.removesuffix("_meta.json")
        for path in (source_stage / "responses/neutral_extract").glob("*_meta.json")
    }
    if request_cases != set(attempt_cases):
        raise ZBatchError("来源实发请求集合与尝试账不一致")
    if raw_cases != set(successful_cases) or meta_cases != set(successful_cases):
        raise ZBatchError("来源存在未入账成功响应，拒绝结果挑选")

    provenance_files = (
        [
            ("hard_stop.json", "source_hard_stop.json"),
            ("run_manifest.json", "source_run_manifest.json"),
            ("run_claim.json", "source_run_claim.json"),
            ("call_attempts.jsonl", "source_call_attempts.jsonl"),
            ("usage.jsonl", "source_usage.jsonl"),
            ("main_sample_ledger.jsonl", "source_main_sample_ledger.jsonl"),
        ]
        if source_kind == "interrupted_prefix"
        else [
            ("run_manifest.json", "source_run_manifest.json"),
            ("run_claim.json", "source_run_claim.json"),
            ("call_attempts.jsonl", "source_call_attempts.jsonl"),
            ("usage.jsonl", "source_usage.jsonl"),
            ("main_sample_ledger.jsonl", "source_main_sample_ledger.jsonl"),
            ("01_extract/metrics.json", "source_metrics.json"),
            ("mechanical_verification.json", "source_mechanical_verification.json"),
        ]
    )
    return {
        "source_kind": source_kind,
        "source_run_dir": source_run_dir.relative_to(ROOT).as_posix()
        if source_run_dir.resolve().is_relative_to(ROOT.resolve())
        else source_run_dir.resolve().as_posix(),
        "hard_stop_sha256": sha256_file(hard_stop_path)
        if hard_stop_path.is_file()
        else None,
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "run_claim_sha256": sha256_file(run_claim_path),
        "source_main_tree": source_tree,
        "source_event_sha256": source_event_sha256,
        "chapters": chapters,
        "ledger_rows": ledger_rows,
        "analyses": analyses,
        "imported_attempt_rows": imported_attempts,
        "imported_usage_rows": usage_rows,
        "all_source_attempt_rows": attempts,
        "incomplete_attempt_rows": incomplete_attempts,
        "provenance_files": provenance_files,
    }


def verify_main_seed(
    run_dir: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    manifest_path = run_dir / MAIN_SEED_MANIFEST
    manifest = read_json(manifest_path)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "z83-main-seed-v1"
        or manifest.get("status") != "validated_complete_responses_only"
    ):
        raise ZBatchError("主样张复用清单格式或状态错误")
    source_value = manifest.get("source_run_dir")
    if not isinstance(source_value, str) or not source_value:
        raise ZBatchError("主样张复用清单缺来源目录")
    source_run_dir = Path(source_value)
    if not source_run_dir.is_absolute():
        source_run_dir = ROOT / source_run_dir
    discovered = _seed_source(
        source_run_dir.resolve(),
        run_dir.resolve(),
        allow_test_run_dir=allow_test_run_dir,
    )
    for key in (
        "source_kind",
        "source_run_dir",
        "hard_stop_sha256",
        "run_manifest_sha256",
        "run_claim_sha256",
        "source_main_tree",
        "source_event_sha256",
        "chapters",
        "imported_attempt_rows",
        "imported_usage_rows",
        "incomplete_attempt_rows",
    ):
        if manifest.get(key) != discovered[key]:
            raise ZBatchError(f"主样张复用清单与封存来源不一致：{key}")

    provenance_copies = manifest.get("provenance_copies")
    provenance_files = discovered["provenance_files"]
    if not isinstance(provenance_copies, list) or len(provenance_copies) != len(
        provenance_files
    ):
        raise ZBatchError("主样张复用来源旁账不齐")
    source_stage = source_run_dir / "main"
    provenance_root = (run_dir / "main/seed_provenance").resolve()
    for row, (source_name, target_name) in zip(
        provenance_copies,
        provenance_files,
        strict=True,
    ):
        if not isinstance(row, dict):
            raise ZBatchError("主样张复用来源旁账含非对象")
        source = Path(str(row.get("source") or ""))
        if not source.is_absolute():
            source = ROOT / source
        source = source.resolve()
        target = Path(str(row.get("target") or "")).resolve()
        expected_source = (source_stage / source_name).resolve()
        expected_target = (provenance_root / target_name).resolve()
        if (
            source != expected_source
            or target != expected_target
            or not target.is_relative_to(provenance_root)
            or not source.is_file()
            or not target.is_file()
            or sha256_file(source) != row.get("source_sha256")
            or sha256_file(target) != row.get("target_sha256")
            or source.read_bytes() != target.read_bytes()
        ):
            raise ZBatchError("主样张复用来源旁账缺失或漂移")

    stage_dir = run_dir / "main"
    operational_rows = manifest.get("operational_sample_rows")
    if (
        not isinstance(operational_rows, list)
        or operational_rows != discovered["ledger_rows"]
    ):
        raise ZBatchError("主样张复用操作账与来源完整样张账不一致")
    current_ledger = z68.read_jsonl(stage_dir / "main_sample_ledger.jsonl")
    if current_ledger[: len(operational_rows)] != operational_rows:
        raise ZBatchError("主样张总账没有以复用样张为前缀")
    current_attempts = z68.read_jsonl(stage_dir / "call_attempts.jsonl")
    current_usage = z68.read_jsonl(stage_dir / "usage.jsonl")
    if (
        current_attempts[: len(discovered["imported_attempt_rows"])]
        != discovered["imported_attempt_rows"]
        or current_usage[: len(discovered["imported_usage_rows"])]
        != discovered["imported_usage_rows"]
    ):
        raise ZBatchError("主样张复用的调用／用量前缀账漂移")

    for row in operational_rows:
        chapter = int(row["chapter"])
        case_id = f"z83_main_ch{chapter:04d}"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        _, content = _verify_successful_exchange(
            stage_dir=stage_dir,
            stage="neutral_extract",
            case_id=case_id,
            expected_body=read_json(prepared_path),
            receipt=row,
        )
        parsed = candidate_envelope.parse_json_content(content)
        model_path = stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        audit_path = stage_dir / f"01_extract/initial_audits/ch{chapter:04d}.json"
        if (
            parsed != read_json(model_path)
            or read_json(audit_path) != discovered["analyses"][chapter]
        ):
            raise ZBatchError(f"第{chapter}章复用样张或初审票漂移")
    return {
        "schema_version": "z83-main-seed-verification-v1",
        "status": "pass",
        "source_kind": discovered["source_kind"],
        "source_run_dir": discovered["source_run_dir"],
        "chapters": discovered["chapters"],
        "imported_network_attempts": len(discovered["imported_attempt_rows"]),
        "source_incomplete_attempts_not_imported": len(
            discovered["incomplete_attempt_rows"]
        ),
        "source_hard_stop_sha256": discovered["hard_stop_sha256"],
        "source_main_tree": discovered["source_main_tree"],
        "source_event_sha256": discovered["source_event_sha256"],
        "no_incomplete_response_imported": True,
    }


def seed_main_samples(
    run_dir: Path,
    source_run_dir: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """把封存运行中的完整响应前缀复制进新运行；不复制未完成调用。"""

    verify_prepared(
        run_dir,
        require_zero_call=True,
        allow_test_run_dir=allow_test_run_dir,
    )
    discovered = _seed_source(
        source_run_dir.resolve(),
        run_dir.resolve(),
        allow_test_run_dir=allow_test_run_dir,
    )
    stage_dir = run_dir / "main"
    provenance_dir = stage_dir / "seed_provenance"
    source_stage = source_run_dir / "main"
    provenance_copies = []
    for source_name, target_name in discovered["provenance_files"]:
        provenance_copies.append(
            _copy_file(source_stage / source_name, provenance_dir / target_name)
        )
    for row in discovered["ledger_rows"]:
        chapter = int(row["chapter"])
        case_id = f"z83_main_ch{chapter:04d}"
        source_paths = _transport_paths(source_stage, "neutral_extract", case_id)
        target_paths = _transport_paths(stage_dir, "neutral_extract", case_id)
        for label in ("request", "raw_response", "response_meta"):
            _copy_file(source_paths[label], target_paths[label])
        _copy_file(
            source_stage / f"01_extract/model_json_original/ch{chapter:04d}.json",
            stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json",
        )
        _copy_file(
            source_stage / f"01_extract/initial_audits/ch{chapter:04d}.json",
            stage_dir / f"01_extract/initial_audits/ch{chapter:04d}.json",
        )
        append_jsonl(stage_dir / "main_sample_ledger.jsonl", row)
    for row in discovered["imported_attempt_rows"]:
        append_jsonl(stage_dir / "call_attempts.jsonl", row)
    for row in discovered["imported_usage_rows"]:
        append_jsonl(stage_dir / "usage.jsonl", row)

    manifest = {
        "schema_version": "z83-main-seed-v1",
        "status": "validated_complete_responses_only",
        "created_at": z68.now_iso(),
        "source_kind": discovered["source_kind"],
        "source_run_dir": discovered["source_run_dir"],
        "hard_stop_sha256": discovered["hard_stop_sha256"],
        "run_manifest_sha256": discovered["run_manifest_sha256"],
        "run_claim_sha256": discovered["run_claim_sha256"],
        "source_main_tree": discovered["source_main_tree"],
        "source_event_sha256": discovered["source_event_sha256"],
        "chapters": discovered["chapters"],
        "operational_sample_rows": discovered["ledger_rows"],
        "imported_attempt_rows": discovered["imported_attempt_rows"],
        "imported_usage_rows": discovered["imported_usage_rows"],
        "incomplete_attempt_rows": discovered["incomplete_attempt_rows"],
        "provenance_copies": provenance_copies,
        "policy": "完整请求+响应+元数据+usage+解析件齐套才复用；未完成调用只留来源旁账，不进入样张",
    }
    write_json(run_dir / MAIN_SEED_MANIFEST, manifest)
    receipt = verify_main_seed(run_dir, allow_test_run_dir=allow_test_run_dir)
    master = read_json(run_dir / "run_manifest.json")
    master["status"] = "prepared_with_validated_main_seed"
    master["main"] = "seeded_not_started"
    master["main_seed"] = receipt
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def _verify_retry_exchange(
    *,
    run_dir: Path,
    stage_dir: Path,
    receipt: Mapping[str, Any],
    expected_messages: list[dict[str, str]],
    allow_multiple: bool,
    retry12_event_id: str | None = None,
    retry12_plan_ordinal: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_id = str(receipt.get("case_id") or "")
    if not case_id:
        raise ZBatchError("定点重写账缺 case_id")
    bundle = load_bundle(run_dir)
    expected_body = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(expected_messages),
        contract=bundle.stage("targeted_retry"),
    )
    _, content = _verify_successful_exchange(
        stage_dir=stage_dir,
        stage="targeted_retry",
        case_id=case_id,
        expected_body=expected_body,
        receipt=receipt,
    )
    parsed = candidate_envelope.parse_json_content(content)
    parsed_for_validation = parsed
    strip_rows: list[dict[str, Any]] = []
    if _formal_anchor_field_strip_target(run_dir):
        if not retry12_event_id or not isinstance(retry12_plan_ordinal, int):
            raise ZBatchError(f"{case_id}缺retry12重建上下文")
        parsed_for_validation, strip_rows = _normalize_retry12_anchor_extras(
            run_dir=run_dir,
            parsed=parsed,
            chapter=int(receipt["chapter"]),
            event_id=retry12_event_id,
            case_id=case_id,
            plan_ordinal=retry12_plan_ordinal,
            raw_response_path=_transport_paths(
                stage_dir,
                "targeted_retry",
                case_id,
            )["raw_response"],
        )
    replacements = z77.validate_replacements(
        parsed_for_validation,
        catalog=_catalog(run_dir, int(receipt["chapter"])),
        allow_multiple=allow_multiple,
    )
    if receipt.get("replacement_count") != len(replacements) or receipt.get(
        "replacement_sha256"
    ) != canonical_sha(replacements):
        raise ZBatchError(f"{case_id}替换结果不能从原始响应重建")
    if _formal_anchor_field_strip_target(run_dir):
        strip_receipt = receipt.get("anchor_extra_field_strip")
        if (
            not isinstance(strip_receipt, dict)
            or strip_receipt.get("diagnostic_only") is not True
            or strip_receipt.get("row_count") != len(strip_rows)
            or strip_receipt.get("rows_canonical_sha256")
            != canonical_sha(strip_rows)
            or strip_receipt.get("formal_replacement_uses_sanitized_copy") is not True
            or strip_receipt.get("formal_quote_source")
            != "frozen_evidence_catalog_by_anchor_id"
        ):
            raise ZBatchError(f"{case_id}锚字段剥离摘要不能从原始响应重建")
    elif strip_rows:
        raise ZBatchError(f"{case_id}非retry12运行出现锚字段剥离旁账")
    return replacements, strip_rows


def _closed_mechanical_retry_reasons(
    violations: Sequence[Any],
) -> tuple[list[str], list[str]]:
    raw = [str(value) for value in violations]
    codes: set[str] = set()
    for violation in raw:
        if violation.startswith("event_nonspace_chars="):
            codes.add("EVENT_TOO_LONG")
        elif violation.startswith(
            (
                "anchor_id_not_string",
                "anchor_id_bad_format:",
                "anchor_id_not_in_catalog:",
            )
        ):
            codes.add("ANCHOR_ID_INVALID")
        else:
            raise ZBatchError(f"机械重试出现未授权原因类型：{violation}")
    if not codes:
        raise ZBatchError("机械重试缺封闭原因码")
    ordered = sorted(codes)
    return ordered, [MECHANICAL_RETRY_REASON_TEXT[code] for code in ordered]


def _mechanical_retry(
    *,
    transport: api_transport.ApiTransport,
    stage_dir: Path,
    run_dir: Path,
    chapter: int,
    row: Mapping[str, Any],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = f"z83_main_ch{chapter:04d}_{str(row['event_id']).lower()}"
    raw_violations = list(row["violations"])
    reason_codes, model_visible_reasons = _closed_mechanical_retry_reasons(
        raw_violations
    )
    messages = z77.build_retry_messages(
        chapter=chapter,
        original_event=row["original_event"],
        violations=model_visible_reasons,
        chapter_text=_chapter_text_path(run_dir, chapter).read_text(encoding="utf-8"),
        catalog=catalog,
    )
    if forbidden_model_hits(messages):
        raise ZBatchError("机械定点重写请求夹入判分侧材料")
    result = transport.call(stage="targeted_retry", case_id=case_id, messages=messages)
    parsed = candidate_envelope.parse_json_content(result.content)
    allow_multiple = "EVENT_TOO_LONG" in reason_codes
    replacements = z77.validate_replacements(
        parsed, catalog=catalog, allow_multiple=allow_multiple
    )
    return replacements, {
        "kind": "existing_mechanical_retry",
        "chapter": chapter,
        **_transport_receipt_fields(stage_dir, "targeted_retry", case_id),
        "original_event_id": row["event_id"],
        "original_event_index": int(row["index"]),
        "reason_codes": reason_codes,
        "raw_violations_local_only": raw_violations,
        "raw_violations_sent_to_model": False,
        "attempt": 1,
        "replacement_count": len(replacements),
        "original_event_sha256": canonical_sha(row["original_event"]),
        "replacement_sha256": canonical_sha(replacements),
    }


def _build_event_lineage(
    *,
    chapter: int,
    original: Mapping[str, Any],
    final: Mapping[str, Any],
    replacements: Mapping[int, list[dict[str, Any]]],
    retry_receipts: Mapping[int, Mapping[str, Any]],
    stage: str,
    prior_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    original_events = original.get("events")
    final_events = final.get("events")
    if not isinstance(original_events, list) or not isinstance(final_events, list):
        raise ZBatchError(f"第{chapter}章血缘输入缺events")
    rows: list[dict[str, Any]] = []
    descendants: dict[str, list[str]] = {}
    serial = 0
    for index, original_event in enumerate(original_events):
        if not isinstance(original_event, dict):
            raise ZBatchError(f"第{chapter}章血缘原事件不是对象")
        input_event_id = str(original_event.get("event_id") or "")
        input_event_sha = canonical_sha(original_event)
        if prior_rows is None:
            source_event_id = input_event_id
            source_event_sha = input_event_sha
            source_identity_sha = canonical_sha(
                {
                    "source_event_id": source_event_id,
                    "source_event_sha256": source_event_sha,
                }
            )
            prior_retry_count = 0
            history = [
                {
                    "stage": "main_sample",
                    "event_id": input_event_id,
                    "event_sha256": input_event_sha,
                }
            ]
        else:
            prior = prior_rows.get(input_event_id)
            if (
                not isinstance(prior, Mapping)
                or prior.get("current_event_sha256") != input_event_sha
            ):
                raise ZBatchError(f"第{chapter}章{input_event_id}无法接续稳定血缘")
            source_event_id = str(prior["source_event_id"])
            source_event_sha = str(prior["source_event_sha256"])
            source_identity_sha = str(prior["source_identity_sha256"])
            prior_retry_count = int(prior["retry_count"])
            history = copy.deepcopy(prior["history"])
        replaced = index in replacements
        output_count = len(replacements[index]) if replaced else 1
        if output_count < 1:
            raise ZBatchError(f"第{chapter}章{input_event_id}替换结果为空")
        retry_count = prior_retry_count + (1 if replaced else 0)
        if retry_count > MAX_TARGETED_RETRIES_PER_EVENT:
            raise ZBatchError(f"稳定源事件{source_event_id}超过每源事件1次重写上限")
        for ordinal in range(1, output_count + 1):
            if serial >= len(final_events):
                raise ZBatchError(f"第{chapter}章血缘输出数超过最终事件数")
            current_event = final_events[serial]
            if not isinstance(current_event, dict):
                raise ZBatchError(f"第{chapter}章血缘最终事件不是对象")
            current_history = copy.deepcopy(history)
            if replaced:
                receipt = retry_receipts.get(index)
                if not isinstance(receipt, Mapping):
                    raise ZBatchError(f"第{chapter}章{input_event_id}缺重写票")
                current_history.append(
                    {
                        "stage": stage,
                        "input_event_id": input_event_id,
                        "input_event_sha256": input_event_sha,
                        "reason_codes": list(receipt["reason_codes"]),
                        "replacement_ordinal": ordinal,
                        "replacement_count": output_count,
                    }
                )
            current_event_id = str(current_event.get("event_id") or "")
            rows.append(
                {
                    "chapter": chapter,
                    "current_event_id": current_event_id,
                    "current_event_sha256": canonical_sha(current_event),
                    "source_event_id": source_event_id,
                    "source_event_sha256": source_event_sha,
                    "source_identity_sha256": source_identity_sha,
                    "retry_count": retry_count,
                    "history": current_history,
                }
            )
            descendants.setdefault(input_event_id, []).append(current_event_id)
            serial += 1
    if serial != len(final_events):
        raise ZBatchError(f"第{chapter}章血缘未覆盖全部最终事件")
    document = {
        "schema_version": "z83-event-lineage-v1",
        "chapter": chapter,
        "stage": stage,
        "row_count": len(rows),
        "rows": rows,
    }
    return document, descendants


def run_main(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    seed_path = run_dir / MAIN_SEED_MANIFEST
    if _formal_completed_seed_target(run_dir) and not seed_path.is_file():
        raise ZBatchError(
            "retry04至retry12必须先完整复用已审retry03三章，禁止误发主采样"
        )
    verify_prepared(
        run_dir,
        require_zero_call=not seed_path.is_file(),
        allow_test_run_dir=allow_test_run_dir,
    )
    seed_receipt = (
        verify_main_seed(run_dir, allow_test_run_dir=allow_test_run_dir)
        if seed_path.is_file()
        else None
    )
    completed_seed_mode = bool(
        seed_receipt is not None
        and seed_receipt.get("source_kind") == "completed_main_retry03"
    )
    if completed_seed_mode:
        if seed_receipt.get("chapters") != list(TARGET_CHAPTERS) or seed_receipt.get(
            "source_event_sha256"
        ) != {
            str(chapter): value
            for chapter, value in APPROVED_COMPLETED_EVENT_SHA256.items()
        }:
            raise ZBatchError("完整复用主阶段来源不是续令批准的retry03三章")
        for chapter in TARGET_CHAPTERS:
            audit = read_json(
                run_dir / f"main/01_extract/initial_audits/ch{chapter:04d}.json"
            )
            if audit.get("hard_reasons") or audit.get("eligible"):
                raise ZBatchError(
                    f"完整复用第{chapter}章冻结样张出现机械重写候选，零新调用闸硬停"
                )
    else:
        _require_api_key_before_claim()
    stage_dir = run_dir / "main"
    claim = _acquire_claim(stage_dir / "run_claim.json", "z83-main-run-claim-v1")
    preflight = read_json(run_dir / "preflight.json")
    transport = api_transport.ApiTransport.from_bundle(
        load_bundle(run_dir), run_dir=stage_dir, max_calls=MAX_NETWORK_ATTEMPTS
    )
    seeded_chapters: list[int] = []
    newly_sampled_chapters: list[int] = []
    sampled_chapters: list[int] = []
    completed: list[int] = []
    retry_total = 0
    retry_by_chapter: Counter[int] = Counter()
    retry_ledger: list[dict[str, Any]] = []
    main_sample_ledger: list[dict[str, Any]] = []
    model_by_chapter: dict[int, dict[str, Any]] = {}
    eligible_by_chapter: dict[int, list[dict[str, Any]]] = {}
    try:
        if seed_receipt is not None:
            seeded_chapters = list(seed_receipt["chapters"])
            seeded_rows = z68.read_jsonl(stage_dir / "main_sample_ledger.jsonl")
            main_sample_ledger.extend(seeded_rows)
            for chapter in seeded_chapters:
                model_json = read_json(
                    stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
                )
                analysis = z77.analyze_main_response(
                    model_json,
                    chapter=chapter,
                    catalog=_catalog(run_dir, chapter),
                )
                if analysis != read_json(
                    stage_dir / f"01_extract/initial_audits/ch{chapter:04d}.json"
                ):
                    raise ZBatchError(f"第{chapter}章复用样张初审票不能机械复现")
                model_by_chapter[chapter] = model_json
                eligible_by_chapter[chapter] = list(analysis["eligible"])
                sampled_chapters.append(chapter)
        # 先收齐三章主样张并统一过 1/3/6 预算闸；此闸之前不发任何定点重写。
        for chapter in TARGET_CHAPTERS:
            if chapter in model_by_chapter:
                continue
            prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
            prepared = read_json(prepared_path)
            _assert_frozen_body(chapter, prepared)
            case_id = f"z83_main_ch{chapter:04d}"
            result = transport.call(
                stage="neutral_extract", case_id=case_id, messages=prepared["messages"]
            )
            actual = read_json(
                stage_dir / f"requests/neutral_extract/{case_id}_request.json"
            )
            if (
                actual.get("body") != prepared
                or result.request_record.get("body") != prepared
            ):
                raise ZBatchError(f"第{chapter}章实际主请求不等于冻结v3请求")
            model_json = candidate_envelope.parse_json_content(result.content)
            model_path = (
                stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
            )
            write_json(model_path, model_json)
            sample_receipt = {
                "schema_version": "z83-main-sample-exchange-v1",
                "chapter": chapter,
                **_transport_receipt_fields(stage_dir, "neutral_extract", case_id),
                "prepared_request_path": f"prepared_requests/ch{chapter:04d}.json",
                "prepared_request_sha256": sha256_file(prepared_path),
                "parsed_model_path": _stage_relative(stage_dir, model_path),
                "parsed_model_file_sha256": sha256_file(model_path),
                "parsed_model_canonical_sha256": canonical_sha(model_json),
            }
            main_sample_ledger.append(sample_receipt)
            append_jsonl(stage_dir / "main_sample_ledger.jsonl", sample_receipt)
            catalog = _catalog(run_dir, chapter)
            analysis = z77.analyze_main_response(
                model_json, chapter=chapter, catalog=catalog
            )
            write_json(
                stage_dir / f"01_extract/initial_audits/ch{chapter:04d}.json", analysis
            )
            if analysis["hard_reasons"]:
                raise ZBatchError(
                    f"第{chapter}章出现非授权新失败面：{analysis['hard_reasons']}"
                )
            eligible = list(analysis["eligible"])
            if len(eligible) > MAX_TARGETED_RETRIES_PER_CHAPTER:
                raise ZBatchError(
                    f"第{chapter}章机械坏条超过{MAX_TARGETED_RETRIES_PER_CHAPTER}，发送前硬停"
                )
            model_by_chapter[chapter] = model_json
            eligible_by_chapter[chapter] = eligible
            sampled_chapters.append(chapter)
            newly_sampled_chapters.append(chapter)
        total_eligible = sum(len(rows) for rows in eligible_by_chapter.values())
        if completed_seed_mode and total_eligible != 0:
            raise ZBatchError("完整复用三章必须保持机械重写候选0")
        if total_eligible > MAX_TARGETED_RETRIES_TOTAL:
            raise ZBatchError("三章机械坏条合计超过全轮6条，定点重写发送前硬停")
        for chapter in TARGET_CHAPTERS:
            model_json = model_by_chapter[chapter]
            eligible = eligible_by_chapter[chapter]
            catalog = _catalog(run_dir, chapter)
            replacements: dict[int, list[dict[str, Any]]] = {}
            receipt_by_index: dict[int, dict[str, Any]] = {}
            for row in eligible:
                fixed, receipt = _mechanical_retry(
                    transport=transport,
                    stage_dir=stage_dir,
                    run_dir=run_dir,
                    chapter=chapter,
                    row=row,
                    catalog=catalog,
                )
                index = int(row["index"])
                replacements[index] = fixed
                retry_total += 1
                retry_by_chapter[chapter] += 1
                receipt_by_index[index] = receipt
            final_json = z77.apply_replacements(
                model_json, chapter=chapter, replacements=replacements
            )
            materialized, audit = neutral_extract.process_model_data(
                final_json, chapter=chapter, catalog=catalog
            )
            lineage, descendants = _build_event_lineage(
                chapter=chapter,
                original=model_json,
                final=materialized,
                replacements=replacements,
                retry_receipts=receipt_by_index,
                stage="main_mechanical_retry",
            )
            for index, receipt in sorted(receipt_by_index.items()):
                source_event_id = str(model_json["events"][index]["event_id"])
                receipt["source_event_id"] = source_event_id
                receipt["source_event_sha256"] = canonical_sha(
                    model_json["events"][index]
                )
                receipt["source_identity_sha256"] = next(
                    row["source_identity_sha256"]
                    for row in lineage["rows"]
                    if row["source_event_id"] == source_event_id
                )
                receipt["materialized_event_ids"] = descendants[source_event_id]
                receipt["source_retry_count_after"] = 1
                retry_ledger.append(receipt)
                append_jsonl(stage_dir / "targeted_retry_ledger.jsonl", receipt)
            write_json(
                stage_dir / f"01_extract/model_json/ch{chapter:04d}.json", final_json
            )
            write_json(
                stage_dir / f"01_extract/events/ch{chapter:04d}.json", materialized
            )
            write_json(
                stage_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit
            )
            write_json(
                stage_dir / f"01_extract/event_lineage/ch{chapter:04d}.json", lineage
            )
            if (
                completed_seed_mode
                and sha256_file(stage_dir / f"01_extract/events/ch{chapter:04d}.json")
                != APPROVED_COMPLETED_EVENT_SHA256[chapter]
            ):
                raise ZBatchError(f"完整复用第{chapter}章物化事件SHA偏离批准样张")
            completed.append(chapter)
    except BaseException as exc:
        attempts = z68.read_jsonl(stage_dir / "call_attempts.jsonl")
        hard_stop = {
            "schema_version": "z83-main-hard-stop-v1",
            "status": "hard_stop_no_unapproved_repair",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "seeded_chapters": seeded_chapters,
            "newly_sampled_chapters": newly_sampled_chapters,
            "sampled_chapters": sampled_chapters,
            "completed_chapters": completed,
            "eligible_retry_candidates_by_chapter": {
                str(chapter): len(eligible_by_chapter.get(chapter, []))
                for chapter in TARGET_CHAPTERS
            },
            "network_attempts": len(attempts),
            "network_attempts_imported": (
                int(seed_receipt["imported_network_attempts"])
                if seed_receipt is not None
                else 0
            ),
            "source_incomplete_attempts_not_imported": (
                int(seed_receipt["source_incomplete_attempts_not_imported"])
                if seed_receipt is not None
                else 0
            ),
            "targeted_retry_count": retry_total,
            "protected_unchanged": protected_snapshot()
            == preflight["protected_before"],
        }
        write_json(stage_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            stage_dir / "run_manifest.json", {**hard_stop, "run_claim": claim}
        )
        raise
    attempts = z68.read_jsonl(stage_dir / "call_attempts.jsonl")
    usage = _usage_summary(stage_dir / "usage.jsonl")
    metrics = {
        "schema_version": "z83-main-metrics-v1",
        "status": "completed_candidate_silver_only",
        "chapters_sampled": sampled_chapters,
        "chapters_completed": completed,
        "seeded_chapters": seeded_chapters,
        "newly_sampled_chapters": newly_sampled_chapters,
        "main_logical_calls": len(TARGET_CHAPTERS),
        "main_live_logical_calls": len(newly_sampled_chapters),
        "main_reused_logical_samples": len(seeded_chapters),
        "targeted_retry_logical_calls": retry_total,
        "network_attempts": len(attempts),
        "network_attempts_imported": (
            int(seed_receipt["imported_network_attempts"])
            if seed_receipt is not None
            else 0
        ),
        "network_attempts_this_run": len(attempts)
        - (
            int(seed_receipt["imported_network_attempts"])
            if seed_receipt is not None
            else 0
        ),
        "source_incomplete_attempts_not_imported": (
            int(seed_receipt["source_incomplete_attempts_not_imported"])
            if seed_receipt is not None
            else 0
        ),
        "main_seed": seed_receipt,
        "completed_seed_zero_new_call_gate": {
            "applied": completed_seed_mode,
            "new_main_samples": len(newly_sampled_chapters),
            "new_targeted_retries": retry_total,
            "passed": (
                not completed_seed_mode
                or (not newly_sampled_chapters and retry_total == 0)
            ),
        },
        **usage,
        "targeted_retry_ledger": retry_ledger,
        "main_sample_ledger": main_sample_ledger,
        "pre_retry_budget_gate": {
            "all_three_chapters_collected_before_retry": sampled_chapters
            == list(TARGET_CHAPTERS),
            "eligible_by_chapter": {
                str(chapter): len(eligible_by_chapter[chapter])
                for chapter in TARGET_CHAPTERS
            },
            "eligible_total": sum(len(rows) for rows in eligible_by_chapter.values()),
            "limit_total": MAX_TARGETED_RETRIES_TOTAL,
            "passed": True,
        },
        "retry_by_chapter": {
            str(chapter): retry_by_chapter[chapter] for chapter in TARGET_CHAPTERS
        },
    }
    write_json(stage_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        stage_dir / "run_manifest.json",
        {
            "schema_version": "z83-main-run-manifest-v1",
            "status": "completed_candidate_silver_only",
            "chapters_completed": completed,
            "run_claim": claim,
            "network_attempts": len(attempts),
            "seeded_chapters": seeded_chapters,
            "newly_sampled_chapters": newly_sampled_chapters,
            "network_attempts_imported": (
                int(seed_receipt["imported_network_attempts"])
                if seed_receipt is not None
                else 0
            ),
            "source_incomplete_attempts_not_imported": (
                int(seed_receipt["source_incomplete_attempts_not_imported"])
                if seed_receipt is not None
                else 0
            ),
            "main_seed": seed_receipt,
            "targeted_retry_count": retry_total,
        },
    )
    master = read_json(run_dir / "run_manifest.json")
    master["status"] = "main_completed"
    master["main"] = "completed_candidate_silver_only"
    write_json_atomic(run_dir / "run_manifest.json", master)
    return metrics


def _event_file(stage_dir: Path, chapter: int) -> Path:
    return stage_dir / f"01_extract/events/ch{chapter:04d}.json"


def _model_file(stage_dir: Path, chapter: int) -> Path:
    return stage_dir / f"01_extract/model_json/ch{chapter:04d}.json"


def verify_event_stage(
    run_dir: Path, stage_dir: Path, *, schema_version: str
) -> dict[str, Any]:
    isolated_inputs = _verify_copied_inputs(
        run_dir, read_json(run_dir / "preflight.json")
    )
    checks = []
    for chapter in TARGET_CHAPTERS:
        catalog = _catalog(run_dir, chapter)
        model_json = read_json(_model_file(stage_dir, chapter))
        stored = read_json(_event_file(stage_dir, chapter))
        reasons, audit = neutral_extract.audit_event_envelope(
            model_json, chapter, catalog
        )
        rebuilt = neutral_extract.materialize_events(model_json, catalog, chapter)
        outside = len(audit.get("missing_catalog_anchor_ids") or [])
        overlength = sum(
            1
            for row in model_json["events"]
            if nonspace_chars(str(row["event"])) > z77.MAX_EVENT_NONSPACE_CHARS
        )
        passed = (
            not reasons
            and audit.get("status") == "pass"
            and stored == rebuilt
            and outside == 0
            and overlength == 0
        )
        if not passed:
            raise ZBatchError(f"第{chapter}章{stage_dir.name}机械复验失败")
        checks.append(
            {
                "chapter": chapter,
                "event_count": len(model_json["events"]),
                "outside_catalog_anchor_count": outside,
                "overlength_event_count": overlength,
                "whole_chapter_invalidated": False,
                "event_file_sha256": sha256_file(_event_file(stage_dir, chapter)),
                "model_file_sha256": sha256_file(_model_file(stage_dir, chapter)),
            }
        )
    receipt = {
        "schema_version": schema_version,
        "status": "pass",
        "checks": checks,
        "gates": {
            "outside_catalog_anchor_zero": True,
            "length_rejection_zero": True,
            "whole_chapter_invalidation_zero": True,
        },
        "secret_scan": z77.secret_scan(stage_dir),
        "isolated_inputs": isolated_inputs,
        "protected_unchanged": protected_snapshot()
        == read_json(run_dir / "preflight.json")["protected_before"],
    }
    if not receipt["secret_scan"]["passed"] or not receipt["protected_unchanged"]:
        raise ZBatchError("机械复验发现密钥痕迹或保护件漂移")
    write_json(stage_dir / "mechanical_verification.json", receipt)
    return receipt


def verify_main(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    verify_prepared(
        run_dir,
        require_zero_call=False,
        allow_test_run_dir=allow_test_run_dir,
    )
    manifest = read_json(run_dir / "main/run_manifest.json")
    if manifest.get("status") != "completed_candidate_silver_only":
        raise ZBatchError("第83道主采样尚未完成")
    receipt = verify_event_stage(
        run_dir, run_dir / "main", schema_version="z83-main-mechanical-verification-v1"
    )
    for chapter in TARGET_CHAPTERS:
        actual = read_json(
            run_dir
            / f"main/requests/neutral_extract/z83_main_ch{chapter:04d}_request.json"
        )
        prepared = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        if actual.get("body") != prepared:
            raise ZBatchError(f"第{chapter}章实发主请求漂移")
    receipt["actual_main_requests_equal_frozen_v3"] = True
    write_json(run_dir / "main/mechanical_verification.json", receipt)
    return receipt


def _chapter_docs(run_dir: Path) -> dict[int, dict[str, Any]]:
    return {
        chapter: {
            "text": _chapter_text_path(run_dir, chapter).read_text(encoding="utf-8")
        }
        for chapter in TARGET_CHAPTERS
    }


def _event_risks(event: Mapping[str, Any], support_text: str) -> list[str]:
    text = str(event.get("event", ""))
    risks: set[str] = set()
    if len([part for part in CLAUSE_SPLIT_RE.split(text) if part.strip()]) >= 5:
        risks.add("multi_fact")
    if len(set(NAME_LIKE_RE.findall(text))) >= 2:
        risks.add("cross_subject")
    if "等" in text and CONCLUSION_RE.search(support_text):
        risks.add("conclusion_compression")
    if INSTRUCTION_RE.search(support_text):
        has_action = bool(re.search(r"不得|不要|必须|应当|要求|命令|嘱咐", text))
        support_has_report = bool(re.search(r"回来|返回|禀报|汇报", support_text))
        event_has_report = bool(re.search(r"回来|返回|禀报|汇报", text))
        support_has_consequence = bool(
            re.search(r"否则|后果|殉职|惩罚|处罚", support_text)
        )
        event_has_consequence = bool(re.search(r"否则|后果|殉职|惩罚|处罚", text))
        if (
            (support_has_report and not event_has_report)
            or (support_has_consequence and not event_has_consequence)
            or not has_action
        ):
            risks.add("instruction_compression")
    return sorted(risks)


def _bigrams(text: str) -> set[str]:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _record_text(record: Mapping[str, Any]) -> str:
    return "；".join(_record_fields(record).values())


def _record_fields(record: Mapping[str, Any]) -> dict[str, str]:
    record_type = str(record.get("type") or "")
    fields = OLD25_COMPARABLE_FIELDS.get(record_type)
    if fields is None:
        raise ZBatchError(f"旧25正式记录类型无法机械预筛：{record_type}")
    return {
        field: str(record[field])
        for field in fields
        if isinstance(record.get(field), str) and str(record[field]).strip()
    }


def _rank_events_for_record(
    record: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    target = _bigrams(_record_text(record))
    record_anchor_ids = {
        str(anchor.get("anchor_id"))
        for anchor in record.get("anchors", [])
        if isinstance(anchor, dict) and anchor.get("anchor_id")
    }
    ranked = []
    for event in events:
        tokens = _bigrams(str(event.get("event", "")))
        overlap = len(target.intersection(tokens))
        recall = overlap / len(target) if target else 0.0
        event_anchor_ids = {
            str(anchor.get("anchor_id"))
            for anchor in event.get("anchors", [])
            if isinstance(anchor, dict) and anchor.get("anchor_id")
        }
        shared_anchor_ids = sorted(record_anchor_ids.intersection(event_anchor_ids))
        ranked.append(
            {
                "event_id": event.get("event_id"),
                "lexical_overlap": overlap,
                "record_bigram_recall": round(recall, 6),
                "shared_anchor_ids": shared_anchor_ids,
                "shared_anchor_count": len(shared_anchor_ids),
                "event_sha256": canonical_sha(event),
            }
        )
    ranked.sort(
        key=lambda row: (
            -row["shared_anchor_count"],
            -row["record_bigram_recall"],
            -row["lexical_overlap"],
            str(row["event_id"]),
        )
    )
    return ranked[:5]


def _field_coverage(
    record: Mapping[str, Any],
    ranked: Sequence[Mapping[str, Any]],
    event_map: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_ids = [
        str(row["event_id"]) for row in ranked if row["shared_anchor_count"] > 0
    ] or [str(row["event_id"]) for row in ranked]
    rows = []
    for field, value in _record_fields(record).items():
        target = _bigrams(value)
        best_id = None
        best_recall = 0.0
        combined_tokens: set[str] = set()
        for event_id in candidate_ids:
            tokens = _bigrams(str(event_map[event_id].get("event", "")))
            combined_tokens.update(tokens)
            recall = len(target.intersection(tokens)) / len(target) if target else 0.0
            if recall > best_recall:
                best_recall = recall
                best_id = event_id
        combined_recall = (
            len(target.intersection(combined_tokens)) / len(target) if target else 0.0
        )
        rows.append(
            {
                "field": field,
                "source_value": value,
                "candidate_event_ids": candidate_ids,
                "best_event_id": best_id,
                "best_event_bigram_recall": round(best_recall, 6),
                "combined_bigram_recall": round(combined_recall, 6),
                "mechanical_only_not_semantic_truth": True,
            }
        )
    return rows


def _old25_mechanical_prefilter(
    record: Mapping[str, Any],
    ranked: Sequence[Mapping[str, Any]],
    event_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """按正式锚和正式字段找疑似缺项；只负责送审，不产语义真值。"""

    field_rows = _field_coverage(record, ranked, event_map)
    shared_anchor_ids = sorted(
        {
            str(anchor_id)
            for row in ranked
            for anchor_id in row.get("shared_anchor_ids", [])
        }
    )
    risk_codes: list[str] = []
    if not shared_anchor_ids:
        risk_codes.append("no_shared_formal_anchor")
    for row in field_rows:
        if row["combined_bigram_recall"] < OLD25_FIELD_RECALL_REVIEW_THRESHOLD:
            risk_codes.append(f"field_low_coverage:{row['field']}")
    return {
        "decision": "review_candidate" if risk_codes else "pass_candidate",
        "risk_codes": risk_codes,
        "shared_formal_anchor_ids": shared_anchor_ids,
        "field_review_threshold": OLD25_FIELD_RECALL_REVIEW_THRESHOLD,
        "field_coverage": field_rows,
        "field_policy": "只比中性事件应承载的事实字段；story_line/future_use/source_level/scope_mode等分类或登记字段不做词面漏项判定",
        "mechanical_only_not_semantic_truth": True,
    }


def _gold_parts() -> dict[str, dict[str, Any]]:
    return z75_score.load_formal_gold(GOLD_POINTER)["parts"]


def _event_map(stage_dir: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for chapter in TARGET_CHAPTERS:
        document = read_json(_event_file(stage_dir, chapter))
        rows = document.get("events") if isinstance(document, dict) else None
        if not isinstance(rows, list):
            raise ZBatchError(f"第{chapter}章事件工件缺events数组")
        for row in rows:
            if not isinstance(row, dict):
                raise ZBatchError(f"第{chapter}章事件工件含非对象")
            event_id = str(row.get("event_id"))
            if event_id in result:
                raise ZBatchError(f"事件ID跨章重复：{event_id}")
            result[event_id] = dict(row)
    return result


def _lineage_file(stage_dir: Path, chapter: int) -> Path:
    return stage_dir / f"01_extract/event_lineage/ch{chapter:04d}.json"


def _load_stage_lineage(stage_dir: Path) -> dict[str, dict[str, Any]]:
    events = _event_map(stage_dir)
    result: dict[str, dict[str, Any]] = {}
    for chapter in TARGET_CHAPTERS:
        document = read_json(_lineage_file(stage_dir, chapter))
        rows = document.get("rows") if isinstance(document, dict) else None
        if (
            document.get("schema_version") != "z83-event-lineage-v1"
            or document.get("chapter") != chapter
            or not isinstance(rows, list)
            or document.get("row_count") != len(rows)
        ):
            raise ZBatchError(f"第{chapter}章稳定血缘账合同错误")
        for row in rows:
            if not isinstance(row, dict):
                raise ZBatchError(f"第{chapter}章稳定血缘账含非对象")
            event_id = str(row.get("current_event_id") or "")
            event = events.get(event_id)
            retry_count = row.get("retry_count")
            expected_identity = canonical_sha(
                {
                    "source_event_id": row.get("source_event_id"),
                    "source_event_sha256": row.get("source_event_sha256"),
                }
            )
            if (
                event is None
                or event_id in result
                or row.get("chapter") != chapter
                or row.get("current_event_sha256") != canonical_sha(event)
                or row.get("source_identity_sha256") != expected_identity
                or isinstance(retry_count, bool)
                or not isinstance(retry_count, int)
                or not 0 <= retry_count <= MAX_TARGETED_RETRIES_PER_EVENT
                or not isinstance(row.get("history"), list)
                or not row["history"]
            ):
                raise ZBatchError(f"第{chapter}章{event_id}稳定血缘账不自洽")
            result[event_id] = dict(row)
    if set(result) != set(events):
        raise ZBatchError("稳定血缘账未覆盖全部当前事件")
    return result


def _validate_main_lineage(run_dir: Path) -> dict[str, Any]:
    stage_dir = run_dir / "main"
    lineage = _load_stage_lineage(stage_dir)
    ledger = z68.read_jsonl(stage_dir / "targeted_retry_ledger.jsonl")
    ledger_by_source: dict[str, dict[str, Any]] = {}
    for row in ledger:
        source_identity = str(row.get("source_identity_sha256") or "")
        if not source_identity or source_identity in ledger_by_source:
            raise ZBatchError("主采样机械重写账稳定源身份为空或重复")
        ledger_by_source[source_identity] = dict(row)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lineage.values():
        by_source[str(row["source_identity_sha256"])].append(row)
    original_sources: set[str] = set()
    for chapter in TARGET_CHAPTERS:
        original = read_json(
            stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        )
        for event in original["events"]:
            identity = canonical_sha(
                {
                    "source_event_id": event["event_id"],
                    "source_event_sha256": canonical_sha(event),
                }
            )
            original_sources.add(identity)
            descendants = by_source.get(identity, [])
            if (
                not descendants
                or any(
                    row["source_event_id"] != event["event_id"] for row in descendants
                )
                or any(
                    row["source_event_sha256"] != canonical_sha(event)
                    for row in descendants
                )
                or len({row["retry_count"] for row in descendants}) != 1
            ):
                raise ZBatchError(f"主采样源事件{event['event_id']}血缘断裂")
            retry_count = descendants[0]["retry_count"]
            ledger_row = ledger_by_source.get(identity)
            if retry_count == 0:
                if ledger_row is not None or len(descendants) != 1:
                    raise ZBatchError(
                        f"未重写源事件{event['event_id']}出现异常分叉或票据"
                    )
            else:
                descendant_ids = sorted(row["current_event_id"] for row in descendants)
                if (
                    ledger_row is None
                    or ledger_row.get("source_event_id") != event["event_id"]
                    or ledger_row.get("source_event_sha256") != canonical_sha(event)
                    or sorted(ledger_row.get("materialized_event_ids", []))
                    != descendant_ids
                    or ledger_row.get("source_retry_count_after") != 1
                ):
                    raise ZBatchError(
                        f"已重写源事件{event['event_id']}的血缘与票据不符"
                    )
    if set(by_source) != original_sources or set(ledger_by_source) != {
        identity for identity, rows in by_source.items() if rows[0]["retry_count"] == 1
    }:
        raise ZBatchError("主采样稳定源集合或机械重写票集合不一致")
    return {
        "status": "pass",
        "current_event_count": len(lineage),
        "stable_source_count": len(by_source),
        "retried_source_count": len(ledger_by_source),
        "rows": lineage,
    }


def _validate_retry13_atomic_plan_identity(run_dir: Path) -> dict[str, Any]:
    """核验 retry13 的父／子声明，不调用旧版 ``retry_plan`` 数组合同。"""

    path = run_dir / "repair/atomic_plan.json"
    if not path.is_file():
        raise ZBatchError("retry13缺原子化计划")
    plan = read_json(path)
    parents = plan.get("parents") if isinstance(plan, dict) else None
    tasks = plan.get("tasks") if isinstance(plan, dict) else None
    pending = plan.get("pending_parent_ids") if isinstance(plan, dict) else None
    if (
        plan.get("schema_version") != "z83-retry13-atomic-plan-v1"
        or plan.get("run_id") != run_dir.name
        or plan.get("status") != "ready_zero_call"
        or plan.get("parent_count") != 13
        or plan.get("atomic_split_total") != 25
        or plan.get("logical_request_count") != 32
        or plan.get("network_attempt_budget") != 36
        or pending != []
        or not isinstance(parents, list)
        or len(parents) != 13
        or not isinstance(tasks, list)
        or len(tasks) != 32
    ):
        raise ZBatchError("retry13原子化计划不是13父／32子／无pending冻结态")
    if not all(isinstance(row, dict) for row in parents + tasks):
        raise ZBatchError("retry13原子化计划父／子行含非对象")

    parent_by_id: dict[str, dict[str, Any]] = {}
    declared_task_ids: set[str] = set()
    source_identities: set[str] = set()
    for parent in parents:
        event_id = str(parent.get("event_id") or "")
        task_ids = parent.get("task_ids")
        fact_count = parent.get("fact_count")
        if (
            not event_id
            or event_id in parent_by_id
            or not isinstance(task_ids, list)
            or not all(isinstance(value, str) and value for value in task_ids)
            or isinstance(fact_count, bool)
            or not isinstance(fact_count, int)
            or fact_count < 1
            or len(task_ids) != fact_count
            or len(task_ids) != len(set(task_ids))
            or parent.get("route") == "pending_cz_not_sent"
            or parent.get("counts_as_one_parent_rewrite") is not True
            or parent.get("facts_may_not_be_added_or_dropped") is not True
        ):
            raise ZBatchError(f"retry13父源计划行不合同：{event_id or '<empty>'}")
        source_identity = str(parent.get("source_identity_sha256") or "")
        if not source_identity or source_identity in source_identities:
            raise ZBatchError("retry13父源稳定身份为空或重复")
        source_identities.add(source_identity)
        parent_by_id[event_id] = dict(parent)
        declared_task_ids.update(task_ids)

    task_by_id: dict[str, dict[str, Any]] = {}
    task_ids_by_parent: dict[str, list[str]] = defaultdict(list)
    chapter_counts: Counter[int] = Counter()
    for task in tasks:
        task_id = str(task.get("task_id") or "")
        parent_id = str(task.get("parent_event_id") or "")
        parent = parent_by_id.get(parent_id)
        chapter = task.get("chapter")
        required_anchor_ids = task.get("required_anchor_ids")
        if (
            not task_id
            or task_id in task_by_id
            or parent is None
            or isinstance(chapter, bool)
            or not isinstance(chapter, int)
            or chapter not in TARGET_CHAPTERS
            or chapter != parent.get("chapter")
            or task.get("parent_event_sha256") != parent.get("event_sha256")
            or task.get("source_event_id") != parent.get("source_event_id")
            or task.get("source_event_sha256") != parent.get("source_event_sha256")
            or task.get("source_identity_sha256")
            != parent.get("source_identity_sha256")
            or not isinstance(required_anchor_ids, list)
            or not required_anchor_ids
            or not all(
                isinstance(value, str) and value for value in required_anchor_ids
            )
            or len(required_anchor_ids) != len(set(required_anchor_ids))
            or task.get("anchor_binding_policy") != "exact_program_prechecked_set"
            or task.get("single_object_required") is not True
            or task.get("output_contract")
            != "z83-one-to-one-single-object-repair-v1"
        ):
            raise ZBatchError(f"retry13子请求计划行不合同：{task_id or '<empty>'}")
        task_by_id[task_id] = dict(task)
        task_ids_by_parent[parent_id].append(task_id)
        chapter_counts[int(chapter)] += 1
    if set(task_by_id) != declared_task_ids:
        raise ZBatchError("retry13父源声明的子任务集合与32条任务不一致")
    for event_id, parent in parent_by_id.items():
        if task_ids_by_parent[event_id] != parent["task_ids"]:
            raise ZBatchError(f"retry13父源子任务顺序或集合漂移：{event_id}")
    if chapter_counts != Counter({3: 7, 13: 7, 19: 18}):
        raise ZBatchError("retry13子请求章分布不等于7／7／18")
    return {
        "path": path,
        "sha256": sha256_file(path),
        "plan": plan,
        "parents": parent_by_id,
        "tasks": task_by_id,
        "chapter_counts": {str(chapter): chapter_counts[chapter] for chapter in TARGET_CHAPTERS},
    }


def _validate_retry13_repair_lineage(run_dir: Path) -> dict[str, Any]:
    """把13个父源账接到32个原子后代；其余事件仍保持一对一。"""

    main_rows = _validate_main_lineage(run_dir)["rows"]
    repair_rows = _load_stage_lineage(run_dir / "repair")
    atomic = _validate_retry13_atomic_plan_identity(run_dir)
    parent_by_id = atomic["parents"]
    ledger_path = run_dir / "repair/targeted_retry_ledger.jsonl"
    if not ledger_path.is_file():
        raise ZBatchError("retry13缺父源定点重写账")
    ledger = z68.read_jsonl(ledger_path)
    ledger_by_input: dict[str, dict[str, Any]] = {}
    descendant_ids: set[str] = set()
    descendants_by_chapter: Counter[int] = Counter()
    for row in ledger:
        event_id = str(row.get("original_event_id") or "")
        parent = parent_by_id.get(event_id)
        materialized = row.get("materialized_event_ids")
        child_results = row.get("child_results")
        if (
            parent is None
            or event_id in ledger_by_input
            or row.get("schema_version")
            != "z83-retry13-parent-rewrite-ledger-v1"
            or not isinstance(materialized, list)
            or not all(isinstance(value, str) and value for value in materialized)
            or len(materialized) != len(set(materialized))
            or not isinstance(child_results, list)
            or not all(isinstance(child, dict) for child in child_results)
            or row.get("chapter") != parent.get("chapter")
            or row.get("replacement_count") != int(parent["fact_count"])
            or len(materialized) != int(parent["fact_count"])
            or len(child_results) != int(parent["fact_count"])
            or [str(child.get("task_id") or "") for child in child_results]
            != list(parent["task_ids"])
            or row.get("original_event_sha256") != parent.get("event_sha256")
            or row.get("source_event_id") != parent.get("source_event_id")
            or row.get("source_event_sha256") != parent.get("source_event_sha256")
            or row.get("source_identity_sha256")
            != parent.get("source_identity_sha256")
            or row.get("fact_closed_set_semantic_review")
            != "pending_not_inferred_from_sha"
        ):
            raise ZBatchError(f"retry13父源定点重写账不合同：{event_id or '<empty>'}")
        preimage = {key: value for key, value in row.items() if key != "row_sha256"}
        if row.get("row_sha256") != canonical_sha(preimage):
            raise ZBatchError(f"retry13父源定点重写账行SHA不能重建：{event_id}")
        overlap = descendant_ids.intersection(materialized)
        if overlap:
            raise ZBatchError(f"retry13原子后代ID重复：{sorted(overlap)}")
        descendant_ids.update(materialized)
        descendants_by_chapter[int(row["chapter"])] += len(materialized)
        ledger_by_input[event_id] = dict(row)
    if set(ledger_by_input) != set(parent_by_id) or len(descendant_ids) != 32:
        raise ZBatchError("retry13父源账不是13条或没有声明32个唯一后代")
    if descendants_by_chapter != Counter({3: 7, 13: 7, 19: 18}):
        raise ZBatchError("retry13物化后代章分布不等于7／7／18")

    used_current_ids: set[str] = set()
    for input_event_id, prior in main_rows.items():
        ledger_row = ledger_by_input.get(input_event_id)
        if ledger_row is None:
            descendants = [
                row for row in repair_rows.values() if row["history"] == prior["history"]
            ]
            expected_retry_count = prior["retry_count"]
            if len(descendants) != 1:
                raise ZBatchError(f"retry13未重写当前事件{input_event_id}血缘不是一对一")
        else:
            descendants = [
                row
                for row in repair_rows.values()
                if len(row["history"]) == len(prior["history"]) + 1
                and row["history"][:-1] == prior["history"]
                and row["history"][-1].get("stage")
                == "semantic_targeted_retry_atomic_program_split"
                and row["history"][-1].get("input_event_id") == input_event_id
            ]
            expected_retry_count = prior["retry_count"] + 1
            actual_descendant_ids = sorted(
                str(row["current_event_id"]) for row in descendants
            )
            if (
                not descendants
                or expected_retry_count > MAX_TARGETED_RETRIES_PER_EVENT
                or input_event_id not in parent_by_id
                or ledger_row.get("original_event_sha256")
                != prior["current_event_sha256"]
                or ledger_row.get("source_event_id") != prior["source_event_id"]
                or ledger_row.get("source_event_sha256")
                != prior["source_event_sha256"]
                or ledger_row.get("source_identity_sha256")
                != prior["source_identity_sha256"]
                or ledger_row.get("source_retry_count_before") != prior["retry_count"]
                or ledger_row.get("source_retry_count_after") != expected_retry_count
                or sorted(ledger_row["materialized_event_ids"])
                != actual_descendant_ids
            ):
                raise ZBatchError(f"retry13父源{input_event_id}血缘与物化账不一致")
        for row in descendants:
            current_id = str(row["current_event_id"])
            if (
                current_id in used_current_ids
                or row["source_event_id"] != prior["source_event_id"]
                or row["source_event_sha256"] != prior["source_event_sha256"]
                or row["source_identity_sha256"] != prior["source_identity_sha256"]
                or row["retry_count"] != expected_retry_count
            ):
                raise ZBatchError(f"retry13父源{input_event_id}稳定身份接续错误")
            used_current_ids.add(current_id)
    if used_current_ids != set(repair_rows):
        raise ZBatchError("retry13稳定血缘未覆盖全部最终事件")
    if descendant_ids != set(repair_rows).intersection(descendant_ids):
        raise ZBatchError("retry13父源账声明了不存在的物化后代")
    if len(main_rows) != 156 or len(repair_rows) != 175:
        raise ZBatchError("retry13事件总量不等于主样156／物化后175")
    return {
        "status": "pass",
        "current_event_count": len(repair_rows),
        "semantic_retry_count": len(ledger),
        "parent_rewrite_count": 13,
        "logical_request_count": 32,
        "targeted_descendant_ids": sorted(descendant_ids),
        "targeted_descendant_count": 32,
        "declared_review_event_ids": sorted(descendant_ids),
        "declared_review_event_count_by_chapter": {
            str(chapter): descendants_by_chapter[chapter]
            for chapter in TARGET_CHAPTERS
        },
        "atomic_plan_sha256": atomic["sha256"],
        "targeted_retry_ledger_sha256": sha256_file(ledger_path),
        "rows": repair_rows,
    }


def _validate_repair_lineage(run_dir: Path) -> dict[str, Any]:
    if _formal_atomic_split_target(run_dir):
        return _validate_retry13_repair_lineage(run_dir)

    main_rows = _validate_main_lineage(run_dir)["rows"]
    repair_rows = _load_stage_lineage(run_dir / "repair")
    plan = _validate_retry_plan(run_dir, run_dir / "repair/retry_plan.json")
    task_ids = {str(row["event_id"]) for row in plan["tasks"]}
    ledger = z68.read_jsonl(run_dir / "repair/targeted_retry_ledger.jsonl")
    ledger_by_input: dict[str, dict[str, Any]] = {}
    for row in ledger:
        event_id = str(row.get("original_event_id") or "")
        if not event_id or event_id in ledger_by_input:
            raise ZBatchError("语义定点重写账输入事件为空或重复")
        ledger_by_input[event_id] = dict(row)
    if set(ledger_by_input) != task_ids:
        raise ZBatchError("语义定点重写账与已审任务集合不一致")
    used_current_ids: set[str] = set()
    for input_event_id, prior in main_rows.items():
        ledger_row = ledger_by_input.get(input_event_id)
        if ledger_row is None:
            descendants = [
                row
                for row in repair_rows.values()
                if row["history"] == prior["history"]
            ]
            expected_retry_count = prior["retry_count"]
            if len(descendants) != 1:
                raise ZBatchError(f"未重写当前事件{input_event_id}血缘不是一对一")
        else:
            descendants = [
                row
                for row in repair_rows.values()
                if len(row["history"]) == len(prior["history"]) + 1
                and row["history"][:-1] == prior["history"]
                and row["history"][-1].get("stage") == "semantic_targeted_retry"
                and row["history"][-1].get("input_event_id") == input_event_id
            ]
            expected_retry_count = prior["retry_count"] + 1
            descendant_ids = sorted(row["current_event_id"] for row in descendants)
            if (
                not descendants
                or expected_retry_count > MAX_TARGETED_RETRIES_PER_EVENT
                or ledger_row.get("source_event_id") != prior["source_event_id"]
                or ledger_row.get("source_event_sha256") != prior["source_event_sha256"]
                or ledger_row.get("source_identity_sha256")
                != prior["source_identity_sha256"]
                or ledger_row.get("source_retry_count_before") != prior["retry_count"]
                or ledger_row.get("source_retry_count_after") != expected_retry_count
                or sorted(ledger_row.get("materialized_event_ids", []))
                != descendant_ids
            ):
                raise ZBatchError(f"语义重写当前事件{input_event_id}血缘与票据不符")
        for row in descendants:
            current_id = str(row["current_event_id"])
            if (
                current_id in used_current_ids
                or row["source_event_id"] != prior["source_event_id"]
                or row["source_event_sha256"] != prior["source_event_sha256"]
                or row["source_identity_sha256"] != prior["source_identity_sha256"]
                or row["retry_count"] != expected_retry_count
            ):
                raise ZBatchError(f"语义重写当前事件{input_event_id}稳定源接续错误")
            used_current_ids.add(current_id)
    if used_current_ids != set(repair_rows):
        raise ZBatchError("语义重写稳定血缘未覆盖全部最终事件")
    return {
        "status": "pass",
        "current_event_count": len(repair_rows),
        "semantic_retry_count": len(ledger),
        "rows": repair_rows,
    }


def _retry13_inspector_scope(
    run_dir: Path,
    *,
    lineage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not _formal_atomic_split_target(run_dir):
        raise ZBatchError("检查员原子后代范围只准用于retry13")
    validated = dict(lineage or _validate_retry13_repair_lineage(run_dir))
    event_ids = validated.get("declared_review_event_ids")
    chapter_counts = validated.get("declared_review_event_count_by_chapter")
    if (
        not isinstance(event_ids, list)
        or len(event_ids) != 32
        or len(event_ids) != len(set(event_ids))
        or chapter_counts != {"3": 7, "13": 7, "19": 18}
    ):
        raise ZBatchError("retry13检查员声明范围不等于32个物化后代")
    return {
        "schema_version": "z83-retry13-inspector-scope-v1",
        "scope": "atomic_materialized_descendants_only",
        "event_ids": list(event_ids),
        "event_count": 32,
        "event_count_by_chapter": dict(chapter_counts),
        "full_human_anchor_event_count": 175,
        "atomic_plan_sha256": validated["atomic_plan_sha256"],
        "targeted_retry_ledger_sha256": validated[
            "targeted_retry_ledger_sha256"
        ],
    }


def _current_rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    rows = data.get("current_rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ZBatchError(f"旧25判词缺 current_rows：{path}")
    result = {}
    for row in rows:
        record_id = str(row.get("record_id"))
        if not record_id or record_id in result:
            raise ZBatchError("旧25判词ID为空或重复")
        result[record_id] = dict(row)
    if len(result) != 25:
        raise ZBatchError(f"旧25判词必须25行，实际{len(result)}")
    return result


def _current_record_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    data = read_json(run_dir / "inputs/current_formal_records_122.json")
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ZBatchError("现役122条副本缺 records")
    return {
        str(row["id"]): dict(row)
        for row in records
        if isinstance(row, dict) and row.get("id")
    }


def _chapter_from_record_id(record_id: str) -> int:
    match = re.fullmatch(r"[ABCD]-C(\d{4})-\d{2}", record_id)
    if not match:
        raise ZBatchError(f"旧25记录ID格式错误：{record_id}")
    return int(match.group(1))


def build_review(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    phase: str = "main",
) -> dict[str, Any]:
    if phase not in {"main", "final"}:
        raise ZBatchError("review phase 只能是 main 或 final")
    stage_dir = run_dir / phase
    verify_event_stage(
        run_dir,
        stage_dir,
        schema_version=f"z83-{phase}-mechanical-verification-v1",
    )
    if phase == "main":
        lineage_validation = _validate_main_lineage(run_dir)
    else:
        lineage_validation = _validate_repair_lineage(run_dir)
    review_dir = run_dir / ("review" if phase == "main" else "final_review")
    if review_dir.exists():
        raise ZBatchError(f"{phase}复核目录已存在，拒绝覆盖")
    review_dir.mkdir(parents=True)
    chapters = _chapter_docs(run_dir)
    event_map = _event_map(stage_dir)
    retry13_scope = (
        _retry13_inspector_scope(run_dir, lineage=lineage_validation)
        if _formal_atomic_split_target(run_dir) and phase == "final"
        else None
    )
    inspector_scope_ids = (
        set(retry13_scope["event_ids"])
        if retry13_scope is not None
        else set(event_map)
    )
    if not inspector_scope_ids.issubset(event_map):
        raise ZBatchError("检查员声明范围引用了本轮不存在事件")
    event_set_sha = {
        str(chapter): sha256_file(_event_file(stage_dir, chapter))
        for chapter in TARGET_CHAPTERS
    }
    risk_rows = []
    forced_strong_ids: set[str] = set()
    anchor_template = []
    for chapter in TARGET_CHAPTERS:
        catalog = _catalog(run_dir, chapter)
        catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in catalog}
        batch_items = []
        event_document = read_json(_event_file(stage_dir, chapter))
        for event in event_document["events"]:
            event_id = str(event["event_id"])
            reasons, anchor_checks = validate_anchors(
                event.get("anchors"),
                chapters,
                expected_chapter=chapter,
                evidence_catalog=catalog_map,
            )
            if reasons:
                raise ZBatchError(f"{event_id}机械核锚失败：{reasons}")
            support_text = "".join(
                str(row.get("quote", "")) for row in event.get("anchors", [])
            )
            risks = _event_risks(event, support_text)
            if risks:
                risk_rows.append(
                    {
                        "risk_id": f"RISK-{event_id}",
                        "chapter": chapter,
                        "event_id": event_id,
                        "risk_codes": risks,
                        "event_sha256": canonical_sha(event),
                        "routing_only": True,
                        "final_truth": False,
                    }
                )
            if set(risks).intersection(FORCED_STRONG_RISKS):
                forced_strong_ids.add(event_id)
            declared = []
            if "multi_fact" in risks:
                declared.append("multi_fact")
            if "cross_subject" in risks:
                declared.append("cross_subject")
            if event_id in inspector_scope_ids:
                batch_items.append(
                    {
                        "item_id": event_id,
                        "check_type": "semantic_support",
                        "source_kind": "z83_candidate_event",
                        "claim": event["event"],
                        "anchors": event["anchors"],
                        "declared_risks": declared,
                        "metadata": {
                            "chapter": chapter,
                            "event_sha256": canonical_sha(event),
                            "program_risk_codes": risks,
                            "forced_strong_review": event_id in forced_strong_ids,
                        },
                    }
                )
            anchor_template.append(
                {
                    "chapter": chapter,
                    "event_id": event_id,
                    "event_sha256": canonical_sha(event),
                    "verdict": None,
                    "unsupported_claims": [],
                    "reason": "",
                }
            )
        batch = {
            "contract_version": pipeline_inspector.INPUT_CONTRACT,
            "batch_id": f"Z83-{phase.upper()}-CH{chapter:04d}",
            "decision_scope": "routing_only",
            "sampling_seed": f"z83-{phase}-ch{chapter:04d}",
            "items": batch_items,
        }
        pipeline_inspector.validate_review_batch(batch)
        if forbidden_model_hits(pipeline_inspector.build_messages(batch, batch_items)):
            raise ZBatchError("语义锚分流请求夹入判分侧材料")
        write_json(review_dir / f"inspector_batches/ch{chapter:04d}.json", batch)
    old_arm = _current_rows_by_id(run_dir / "provenance/score_only/旧臂2旧25基线.json")
    v3_rows = _current_rows_by_id(run_dir / "provenance/score_only/v3语义判词基线.json")
    records = _current_record_map(run_dir)
    current_template = []
    automatic_rows = []
    for record_id, old_row in old_arm.items():
        if record_id not in v3_rows or record_id not in records:
            raise ZBatchError(f"旧25记录无法在v3或正式记录定位：{record_id}")
        chapter = _chapter_from_record_id(record_id)
        chapter_events = [
            row
            for row in event_map.values()
            if int(str(row["event_id"])[4:8]) == chapter
        ]
        ranked = _rank_events_for_record(records[record_id], chapter_events)
        mechanical_prefilter = _old25_mechanical_prefilter(
            records[record_id], ranked, event_map
        )
        required_floor = (
            "preserved"
            if record_id in {"B-C0013-02", "B-C0019-04"}
            else str(v3_rows[record_id]["verdict"])
        )
        automatic_rows.append(
            {
                "chapter": chapter,
                "record_id": record_id,
                "old_arm_verdict": old_row["verdict"],
                "v3_verdict": v3_rows[record_id]["verdict"],
                "required_floor": required_floor,
                "formal_record_fields": {
                    key: value
                    for key, value in records[record_id].items()
                    if not key.startswith("_") and key not in {"anchors", "related_ids"}
                },
                "top_same_chapter_candidates": ranked,
                "mechanical_prefilter": mechanical_prefilter,
                "machine_decision": "semantic_review_required",
                "final_truth": False,
                "scale_note": (
                    "正式字段硬要求为不得惊动目标＋返回禀报；历史严重后果只作观察，不静默扩尺。"
                    if record_id == "B-C0019-04"
                    else None
                ),
            }
        )
        current_template.append(
            {
                "chapter": chapter,
                "record_id": record_id,
                "old_arm_verdict": old_row["verdict"],
                "v3_verdict": v3_rows[record_id]["verdict"],
                "required_floor": required_floor,
                "verdict": None,
                "candidate_event_ids": [],
                "reason": "",
                "scale_note_acknowledged": None if record_id == "B-C0019-04" else True,
            }
        )
    # 正式锚相交的候选全送人工强审；没有相交锚时只用词面首候选兜底。
    # 正式记录字段与ID不进入检查员API请求，避免把判分侧材料泄入模型。
    old25_candidate_ids: set[str] = set()
    for row in automatic_rows:
        ranked = row["top_same_chapter_candidates"]
        shared = [
            str(candidate["event_id"])
            for candidate in ranked
            if candidate["shared_anchor_count"] > 0
        ]
        if shared:
            old25_candidate_ids.update(shared)
        elif ranked and ranked[0]["lexical_overlap"] > 0:
            old25_candidate_ids.add(str(ranked[0]["event_id"]))
    forced_strong_ids.update(old25_candidate_ids)
    risks_by_event = {str(row["event_id"]): row for row in risk_rows}
    for event_id in sorted(old25_candidate_ids):
        if event_id in risks_by_event:
            codes = risks_by_event[event_id]["risk_codes"]
            if "old25_candidate" not in codes:
                codes.append("old25_candidate")
                codes.sort()
        else:
            event = event_map[event_id]
            row = {
                "risk_id": f"RISK-{event_id}",
                "chapter": int(event_id[4:8]),
                "event_id": event_id,
                "risk_codes": ["old25_candidate"],
                "event_sha256": canonical_sha(event),
                "routing_only": True,
                "final_truth": False,
            }
            risk_rows.append(row)
            risks_by_event[event_id] = row
    risk_rows.sort(key=lambda row: row["risk_id"])
    for chapter in TARGET_CHAPTERS:
        batch_path = review_dir / f"inspector_batches/ch{chapter:04d}.json"
        batch = read_json(batch_path)
        for item in batch["items"]:
            event_id = str(item["item_id"])
            if event_id in old25_candidate_ids:
                codes = list(item["metadata"].get("program_risk_codes", []))
                if "old25_candidate" not in codes:
                    codes.append("old25_candidate")
                item["metadata"]["program_risk_codes"] = sorted(codes)
                item["metadata"]["forced_strong_review"] = True
        pipeline_inspector.validate_review_batch(batch)
        if forbidden_model_hits(
            pipeline_inspector.build_messages(batch, batch["items"])
        ):
            raise ZBatchError("旧25强审路由更新后模型批次夹入判分侧材料")
        write_json(batch_path, batch)
    gold_template = [
        {
            "part_id": part_id,
            "verdict": None,
            "candidate_event_ids": [],
            "reason": "",
        }
        for part_id in _gold_parts()
    ]
    adjudication_template = {
        "schema_version": "z83-semantic-adjudication-v1",
        "run_id": run_dir.name,
        "phase": phase,
        "authority": "逐条语义强审；不是模型分流输出",
        "event_set_sha256": event_set_sha,
        "anchor_rows": anchor_template,
        "current_rows": current_template,
        "gold_rows": gold_template,
        "risk_rows": [
            {
                "risk_id": row["risk_id"],
                "event_id": row["event_id"],
                "event_sha256": row["event_sha256"],
                "verdict": None,
                "reason": "",
            }
            for row in risk_rows
        ],
        "reviewer": "",
        "reviewed_at": "",
    }
    write_json(
        review_dir / "old25_automatic_comparison.json",
        {
            "schema_version": "z83-old25-automatic-comparison-v2",
            "status": "routing_only_not_final_truth",
            "method": "formal_anchor_first_plus_per_field_bigram_coverage",
            "row_count": len(automatic_rows),
            "rows": automatic_rows,
        },
    )
    write_json(
        review_dir / "program_risks.json",
        {
            "schema_version": "z83-program-risk-prefilter-v1",
            "status": "routing_only_not_final_truth",
            "rows": risk_rows,
            "forced_strong_event_ids": sorted(forced_strong_ids),
            **(
                {
                    "inspector_forced_strong_event_ids": sorted(
                        forced_strong_ids.intersection(inspector_scope_ids)
                    )
                }
                if retry13_scope is not None
                else {}
            ),
        },
    )
    write_json(review_dir / "adjudication_template.json", adjudication_template)
    receipt = {
        "schema_version": f"z83-{phase}-review-build-v1",
        "status": "review_materials_ready_not_final_truth",
        "phase": phase,
        "event_set_sha256": event_set_sha,
        "event_count": len(event_map),
        **(
            {
                "inspector_scope": retry13_scope,
                "inspector_event_count": len(inspector_scope_ids),
                "human_anchor_event_count": len(anchor_template),
                "final_event_count": len(event_map),
                "inspector_scope_event_ids": retry13_scope["event_ids"],
                "human_anchor_row_count": len(anchor_template),
            }
            if retry13_scope is not None
            else {}
        ),
        "old25_rows": len(current_template),
        "gold_rows": len(gold_template),
        "program_risk_rows": len(risk_rows),
        "old25_forced_strong_event_ids": sorted(old25_candidate_ids),
        "old25_mechanical_review_candidate_rows": sum(
            row["mechanical_prefilter"]["decision"] == "review_candidate"
            for row in automatic_rows
        ),
        "old25_no_shared_formal_anchor_rows": sum(
            "no_shared_formal_anchor" in row["mechanical_prefilter"]["risk_codes"]
            for row in automatic_rows
        ),
        "forced_strong_event_ids": sorted(forced_strong_ids),
        "review_input_sha256": {
            "old25_automatic_comparison": sha256_file(
                review_dir / "old25_automatic_comparison.json"
            ),
            "program_risks": sha256_file(review_dir / "program_risks.json"),
            "adjudication_template": sha256_file(
                review_dir / "adjudication_template.json"
            ),
            "inspector_batches": {
                str(chapter): sha256_file(
                    review_dir / f"inspector_batches/ch{chapter:04d}.json"
                )
                for chapter in TARGET_CHAPTERS
            },
        },
        "model_visible_batches_contain_gold_or_cases": False,
        "semantic_truth_pending": True,
    }
    write_json(review_dir / "build_receipt.json", receipt)
    return receipt


def _direct_forced_routing(
    batch: Mapping[str, Any], forced_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        {
            "item_id": item["item_id"],
            "route": "strong_review",
            "source": "z83_program_gate",
            "risk_reasons": list(
                item.get("metadata", {}).get("program_risk_codes", [])
            ),
            "final_truth": False,
        }
        for item in batch["items"]
        if item["item_id"] in forced_ids
    ]


def _inspector_network_attempts(root: Path) -> int:
    return sum(
        1
        for path in root.rglob("call_attempts.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _inspector_usage_for_chapters(
    root: Path, chapters: Iterable[int]
) -> dict[str, Any]:
    return _usage_summary(
        *(root / f"ch{chapter:04d}/run/usage.jsonl" for chapter in chapters)
    )


def _inspector_request_record(
    *,
    contract_path: Path,
    case_id: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """零调用重建检查员会落盘的完整请求记录。"""

    bundle = stage_sampling.load_contract_bundle(
        contract_path,
        profile=pipeline_inspector.DEFAULT_PROFILE,
    )
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    contract = bundle.stage(pipeline_inspector.STAGE)
    body = api_transport.build_request_body(
        model=route.model,
        messages=messages,
        contract=contract,
    )
    return {
        "provider": route.provider,
        "api_base_url": route.base_url,
        "api_endpoint": route.endpoint,
        "stage": pipeline_inspector.STAGE,
        "case_id": case_id,
        "contract_status": contract.status,
        "unverified_candidate_override": contract.status == "candidate_unverified",
        "body": body,
        "_security": "no_api_key_no_authorization",
    }


def _wire_body_bytes(body: Mapping[str, Any]) -> bytes:
    """按实际 POST 规则从冻结 body 重建线上字节。"""

    return json.dumps(body, ensure_ascii=False).encode("utf-8")


class _Retry13NoRedirectHandler(api_transport.urllib.request.HTTPRedirectHandler):
    """拒绝 3xx 跟随，避免把 Authorization 带到跳转目标。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _retry13_no_redirect_open(request: Any, *, timeout: int) -> Any:
    return api_transport.urllib.request.build_opener(
        _Retry13NoRedirectHandler()
    ).open(request, timeout=timeout)


class _Retry13InspectorTransportSession:
    """只给 retry13 最终检查员使用的串行运输会话。

    它复用既有检查员消息与采样合同；唯一变化是把旧 ``ApiTransport``
    的宽重试换成续令⑪的 429-only 节流，并给每章逻辑请求落五件不可变
    检查点。历史检查员不会创建这个会话。
    """

    CONTRACT_VERSION = "semantic-inspector-retry13-transport-v1"

    def __init__(
        self,
        *,
        policy: z83_retry_transport.RetryPolicy | None = None,
        sleeper: Any = None,
        monotonic: Any = None,
        jitter: Any = None,
    ) -> None:
        self.policy = policy or z83_retry_transport.RetryPolicy()
        self.state = z83_retry_transport.RetryRunState()
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.jitter = jitter

    @staticmethod
    def _chapter(case_id: str) -> int:
        matched = re.search(r"CH([0-9]{4})", case_id)
        if matched is None:
            raise ZBatchError(f"retry13检查员 case_id 缺章号：{case_id}")
        return int(matched.group(1))

    @staticmethod
    def _strict_envelope(
        raw: bytes, *, expected_model: str
    ) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        try:
            decoded = raw.decode("utf-8")
            value = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZBatchError("retry13检查员 HTTP 200 回包不是 UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise ZBatchError("retry13检查员 HTTP 200 回包顶层不是对象")
        if value.get("model") != expected_model:
            raise ZBatchError("retry13检查员响应模型与请求不一致")
        choices = value.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ZBatchError("retry13检查员响应 choices 必须恰好一项")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        usage = value.get("usage")
        if not isinstance(content, str) or not content.strip():
            raise ZBatchError("retry13检查员响应正文为空")
        if finish_reason != "stop":
            raise ZBatchError(
                f"retry13检查员响应未正常结束：finish_reason={finish_reason or 'missing'}"
            )
        if not isinstance(usage, dict) or not usage:
            raise ZBatchError("retry13检查员响应缺真实 usage")
        return value, content, finish_reason, dict(usage)

    def __call__(
        self,
        *,
        bundle: Any,
        run_dir: Path,
        stage: str,
        case_id: str,
        messages: list[dict[str, str]],
        api_items: Sequence[Mapping[str, Any]],
        evidence_quote_policy: str,
        minimum_quote_nonspace_chars: int,
    ) -> api_transport.TransportResult:
        if stage != pipeline_inspector.STAGE:
            raise ZBatchError("retry13检查员运输只允许 semantic_route")
        key = os.environ.get(api_transport.PINNED_API_KEY_ENV)
        if not key:
            raise ZBatchError("缺少 SENSENOVA_API_KEY；retry13检查员不发网")
        route = api_transport.TransportRoute.from_mapping(bundle.route)
        request_record = _inspector_request_record(
            contract_path=Path(bundle.source_path),
            case_id=case_id,
            messages=messages,
        ) if getattr(bundle, "source_path", None) else None
        if request_record is None:
            contract = bundle.stage(stage)
            body = api_transport.build_request_body(
                model=route.model,
                messages=messages,
                contract=contract,
            )
            request_record = {
                "provider": route.provider,
                "api_base_url": route.base_url,
                "api_endpoint": route.endpoint,
                "stage": stage,
                "case_id": case_id,
                "contract_status": contract.status,
                "unverified_candidate_override": (
                    contract.status == "candidate_unverified"
                ),
                "body": body,
                "_security": "no_api_key_no_authorization",
            }
        body = request_record["body"]
        request_path = run_dir / f"requests/{stage}/{case_id}_request.json"
        if request_path.exists():
            raise ZBatchError("retry13检查员冻结请求已存在，拒绝复发")
        write_json(request_path, request_record)
        request_sha = sha256_file(request_path)
        wire = _wire_body_bytes(body)
        wire_sha = hashlib.sha256(wire).hexdigest()
        raw_path = run_dir / f"responses/{stage}/{case_id}_raw.json"
        meta_path = run_dir / f"responses/{stage}/{case_id}_meta.json"
        attempt_path = run_dir / "call_attempts.jsonl"
        chapter = self._chapter(case_id)

        def send_once(_: int) -> z83_retry_transport.AttemptOutcome:
            started_at = datetime.now().astimezone().isoformat(timespec="seconds")
            request = api_transport.urllib.request.Request(
                route.url,
                data=wire,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with _retry13_no_redirect_open(
                    request, timeout=route.timeout_seconds
                ) as response:
                    raw = response.read()
                    status = int(getattr(response, "status", 200) or 200)
                    headers = {
                        str(name): str(value)
                        for name, value in response.headers.items()
                        if str(name).lower() in api_transport.SAFE_RESPONSE_HEADERS
                    }
                if key.encode("utf-8") in raw:
                    raise ZBatchError("retry13检查员响应回显密钥，拒绝落盘")
                if raw_path.exists():
                    raise ZBatchError("retry13检查员原始响应已存在，拒绝覆盖")
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw)
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    parsed = {}
                usage = parsed.get("usage") if isinstance(parsed, dict) else None
                return z83_retry_transport.AttemptOutcome(
                    http_status=status,
                    request_sha256=request_sha,
                    raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                    usage=usage if isinstance(usage, dict) else {},
                    headers=headers,
                    payload=raw,
                    wire_body_sha256=wire_sha,
                    request_artifact_sha256=request_sha,
                    started_at=started_at,
                    finished_at=datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                )
            except api_transport.urllib.error.HTTPError as exc:
                error_body = exc.read() if hasattr(exc, "read") else b""
                return z83_retry_transport.AttemptOutcome(
                    http_status=int(exc.code),
                    request_sha256=request_sha,
                    headers={str(k): str(v) for k, v in (exc.headers or {}).items()},
                    error_code=f"http_{exc.code}",
                    error_body_sha256=hashlib.sha256(error_body).hexdigest(),
                    wire_body_sha256=wire_sha,
                    request_artifact_sha256=request_sha,
                    started_at=started_at,
                    finished_at=datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                )
            except (
                api_transport.urllib.error.URLError,
                TimeoutError,
                api_transport.http.client.IncompleteRead,
                ConnectionError,
            ) as exc:
                return z83_retry_transport.AttemptOutcome(
                    http_status=0,
                    request_sha256=request_sha,
                    error_code=f"transport_{type(exc).__name__}",
                    wire_body_sha256=wire_sha,
                    request_artifact_sha256=request_sha,
                    started_at=started_at,
                    finished_at=datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                )

        checkpoint_root = run_dir / "checkpoint"

        def write_failed_checkpoint(
            *,
            rows: Sequence[Mapping[str, Any]],
            status: int,
            raw_sha: str | None,
            error_code: str,
        ) -> None:
            raw_relative = (
                raw_path.relative_to(run_dir).as_posix() if raw_path.is_file() else ""
            )
            z83_retry_transport.write_checkpoint_bundle(
                checkpoint_root,
                request_record={
                    "schema": "z83-retry13-checkpoint-request-v1",
                    "logical_request_id": case_id,
                    "request_artifact_path": request_path.relative_to(run_dir).as_posix(),
                    "request_artifact_sha256": request_sha,
                    "wire_body_sha256": wire_sha,
                    "model": route.model,
                    "stage": "semantic_route_final_retry13",
                    "contract_version": self.CONTRACT_VERSION,
                },
                response_record={
                    "schema": "z83-retry13-checkpoint-response-v1",
                    "logical_request_id": case_id,
                    "request_artifact_sha256": request_sha,
                    "http_status": status,
                    "raw_response_path": raw_relative,
                    "raw_response_sha256": raw_sha,
                    "response_model": None,
                    "finish_reason": None,
                    "content_sha256": None,
                    "error_code": error_code,
                },
                usage_record={
                    "schema": "z83-retry13-checkpoint-usage-v1",
                    "logical_request_id": case_id,
                    "request_artifact_sha256": request_sha,
                    "raw_response_sha256": raw_sha,
                    "usage": {},
                },
                attempt_rows=rows,
                contract_version=self.CONTRACT_VERSION,
                mechanical_verdict="fail",
            )

        try:
            result = z83_retry_transport.run_logical_request(
                logical_request_id=case_id,
                chapter=chapter,
                send_once=send_once,
                attempt_ledger_path=attempt_path,
                contract_version=self.CONTRACT_VERSION,
                state=self.state,
                policy=self.policy,
                **({"sleeper": self.sleeper} if self.sleeper is not None else {}),
                **({"monotonic": self.monotonic} if self.monotonic is not None else {}),
                **({"jitter": self.jitter} if self.jitter is not None else {}),
            )
        except z83_retry_transport.RetryTransportHardStop as exc:
            rows = z68.read_jsonl(attempt_path)
            if rows:
                last = rows[-1]
                write_failed_checkpoint(
                    rows=rows,
                    status=int(last["http_status"]),
                    raw_sha=last.get("raw_response_sha256"),
                    error_code=exc.reason_code,
                )
            raise
        raw = bytes(result.outcome.payload)
        try:
            value, content, finish_reason, usage = self._strict_envelope(
                raw, expected_model=route.model
            )
            pipeline_inspector.parse_model_output(
                content,
                api_items,
                evidence_quote_policy=evidence_quote_policy,
                minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                quote_fill_audit_rows=[],
            )
        except ZBatchError as exc:
            write_failed_checkpoint(
                rows=result.attempt_rows,
                status=result.outcome.http_status,
                raw_sha=hashlib.sha256(raw).hexdigest(),
                error_code="response_envelope_invalid",
            )
            raise exc
        except pipeline_inspector.InspectorError as exc:
            write_failed_checkpoint(
                rows=result.attempt_rows,
                status=result.outcome.http_status,
                raw_sha=hashlib.sha256(raw).hexdigest(),
                error_code="inspector_output_contract_invalid",
            )
            raise exc
        raw_sha = hashlib.sha256(raw).hexdigest()
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        metadata = {
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "http_status": result.outcome.http_status,
            "provider": route.provider,
            "api_base_url": route.base_url,
            "api_endpoint": route.endpoint,
            "requested_model": route.model,
            "response_model": value["model"],
            "finish_reason": finish_reason,
            "request_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "headers": dict(result.outcome.headers),
            "sampling_n": body["n"],
            "stage_temperature": body["temperature"],
            "stage_max_tokens": body["max_tokens"],
            "contract_status": request_record["contract_status"],
            "unverified_candidate_override": request_record[
                "unverified_candidate_override"
            ],
            "retry13_transport_contract": self.CONTRACT_VERSION,
        }
        write_json(meta_path, metadata)
        append_jsonl(
            run_dir / "usage.jsonl",
            {**metadata, "stage": stage, "case_id": case_id, "usage": usage},
        )
        z83_retry_transport.write_checkpoint_bundle(
            checkpoint_root,
            request_record={
                "schema": "z83-retry13-checkpoint-request-v1",
                "logical_request_id": case_id,
                "request_artifact_path": request_path.relative_to(run_dir).as_posix(),
                "request_artifact_sha256": request_sha,
                "wire_body_sha256": wire_sha,
                "model": route.model,
                "stage": "semantic_route_final_retry13",
                "contract_version": self.CONTRACT_VERSION,
            },
            response_record={
                "schema": "z83-retry13-checkpoint-response-v1",
                "logical_request_id": case_id,
                "request_artifact_sha256": request_sha,
                "http_status": result.outcome.http_status,
                "raw_response_path": raw_path.relative_to(run_dir).as_posix(),
                "raw_response_sha256": raw_sha,
                "response_model": value["model"],
                "finish_reason": finish_reason,
                "content_sha256": content_sha,
                "error_code": None,
            },
            usage_record={
                "schema": "z83-retry13-checkpoint-usage-v1",
                "logical_request_id": case_id,
                "request_artifact_sha256": request_sha,
                "raw_response_sha256": raw_sha,
                "usage": usage,
            },
            attempt_rows=result.attempt_rows,
            contract_version=self.CONTRACT_VERSION,
            mechanical_verdict="pass",
        )
        return api_transport.TransportResult(
            request_record=request_record,
            raw_response=raw,
            response_json=value,
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            metadata=metadata,
        )


def _resolve_inspector_contract_path(run_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ZBatchError("检查员合同路径缺失")
    path = Path(value)
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [run_dir / path, ROOT / path]
    existing = [candidate.resolve() for candidate in candidates if candidate.is_file()]
    if len(existing) != 1:
        raise ZBatchError("检查员合同路径不能唯一回读")
    return existing[0]


def _inspector_api_projection(
    batch: Mapping[str, Any],
    forced_ids: set[str],
    *,
    system_prompt_suffix: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, str]]]:
    """按真实检查员规则投影最终会发给 API 的条目与消息。"""

    validated = pipeline_inspector.validate_review_batch(batch)
    outer_api_items = [
        item for item in validated["items"] if item["item_id"] not in forced_ids
    ]
    if not outer_api_items:
        return None, [], []
    api_batch = {
        **validated,
        "items": outer_api_items,
        "batch_id": validated["batch_id"] + "-API",
    }
    transport_items, _ = pipeline_inspector.split_by_rule_gate(api_batch)
    if not transport_items:
        return api_batch, [], []
    messages = pipeline_inspector.build_messages(
        api_batch,
        transport_items,
        system_prompt_suffix=system_prompt_suffix,
    )
    if forbidden_model_hits(messages):
        raise ZBatchError("检查员模型请求含判分侧材料")
    return api_batch, transport_items, messages


def _preflight_inspector_requests(
    run_dir: Path,
    *,
    phase: str,
    review_dir: Path,
    contract_path: Path,
) -> dict[str, Any]:
    """发网前证明检查员请求只含本轮获批的唯一变量。"""

    if phase not in {"main", "final"}:
        raise ZBatchError("检查员请求预验 phase 非法")
    formal_retry04 = run_dir.name == APPROVED_COMPLETED_SEED_TARGET_NAME
    formal_retry05 = run_dir.name == APPROVED_QUOTE_CONSTRAINT_TARGET_NAME
    formal_retry06 = run_dir.name == APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME
    formal_retry07 = run_dir.name == APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME
    formal_retry08 = run_dir.name == APPROVED_PUNCTUATION_UNIT_TARGET_NAME
    formal_retry13 = _formal_atomic_split_target(run_dir) and phase == "final"
    formal_punctuation_unit = formal_retry08 or formal_retry13
    formal_punctuation = formal_retry07 or formal_punctuation_unit
    formal_program_quote = formal_retry06 or formal_punctuation
    formal_completed_target = formal_retry04 or formal_retry05 or formal_program_quote
    system_prompt_suffix = _retry05_system_prompt_suffix(run_dir)
    retry04_reference = (
        _retry04_inspector_reference() if formal_retry05 and phase == "main" else None
    )
    retry05_reference = (
        _retry05_inspector_reference() if formal_retry06 and phase == "main" else None
    )
    retry06_reference = (
        _retry06_inspector_reference()
        if formal_punctuation and phase == "main"
        else None
    )
    if formal_completed_target and phase == "main":
        current_event_sha = {
            chapter: sha256_file(_event_file(run_dir / phase, chapter))
            for chapter in TARGET_CHAPTERS
        }
        if current_event_sha != APPROVED_COMPLETED_EVENT_SHA256:
            raise ZBatchError(
                "retry04／retry05／retry06／retry07／retry08三章事件SHA漂移，检查员发网前硬停"
            )

    program_risks = read_json(review_dir / "program_risks.json")
    forced_ids = set(program_risks["forced_strong_event_ids"])
    if formal_completed_target and phase == "main":
        source_risks_path = _retry03_run_dir() / "review/program_risks.json"
        if (
            not source_risks_path.is_file()
            or (review_dir / "program_risks.json").read_bytes()
            != source_risks_path.read_bytes()
        ):
            raise ZBatchError(
                "retry04／retry05／retry06／retry07／retry08程序风险路由不等于retry03冻结件"
            )
    rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        batch_path = review_dir / f"inspector_batches/ch{chapter:04d}.json"
        batch = read_json(batch_path)
        if formal_program_quote:
            _assert_batch_quotes_equal_frozen_catalog(run_dir, chapter, batch)
        if formal_completed_target and phase == "main":
            source_batch_path = (
                _retry03_run_dir() / f"review/inspector_batches/ch{chapter:04d}.json"
            )
            if (
                not source_batch_path.is_file()
                or batch_path.read_bytes() != source_batch_path.read_bytes()
            ):
                raise ZBatchError(
                    f"retry04／retry05／retry06／retry07／retry08第{chapter}章检查批不等于retry03冻结件"
                )
        baseline_api_batch, baseline_transport_items, baseline_messages = (
            _inspector_api_projection(batch, forced_ids)
        )
        api_batch, transport_items, messages = _inspector_api_projection(
            batch,
            forced_ids,
            system_prompt_suffix=system_prompt_suffix,
        )
        if (
            api_batch != baseline_api_batch
            or transport_items != baseline_transport_items
        ):
            raise ZBatchError("检查员系统消息增量改变了路由子批或条目")
        if api_batch is None or not transport_items:
            rows.append(
                {
                    "chapter": chapter,
                    "batch_path": batch_path.relative_to(run_dir).as_posix(),
                    "batch_sha256": sha256_file(batch_path),
                    "api_item_count": 0,
                    "baseline_messages_sha256": None,
                    "messages_sha256": None,
                    "baseline_request_sha256": None,
                    "candidate_request_sha256": None,
                    "differences": [],
                    "zero_call_reason": (
                        "all_forced_by_z83_program_gate"
                        if api_batch is None
                        else "all_remaining_items_escalated_by_inspector_rule_gate"
                    ),
                    "retry03_actual_request_sha256": None,
                    "retry03_actual_request_rebuilt_exactly": None,
                    "retry04_reference_request_sha256": None,
                    "retry04_request_rebuilt_exactly": None,
                    "retry05_reference_request_sha256": None,
                    "retry05_request_rebuilt_exactly": None,
                    "retry06_reference_request_sha256": None,
                    "retry06_request_rebuilt_exactly": None,
                }
            )
            continue
        case_id = str(api_batch["batch_id"])
        baseline_record = _inspector_request_record(
            contract_path=(
                contract_path
                if formal_retry05 or formal_program_quote
                else INSPECTOR_CONTRACT
            ),
            case_id=case_id,
            messages=(messages if formal_program_quote else baseline_messages),
        )
        candidate_record = _inspector_request_record(
            contract_path=contract_path,
            case_id=case_id,
            messages=messages,
        )
        differences = _json_differences(baseline_record, candidate_record)
        candidate_max_tokens = candidate_record["body"]["max_tokens"]
        if formal_program_quote:
            expected = []
        elif formal_retry05:
            expected = [
                {
                    "path": "$.body.messages[0].content",
                    "before": pipeline_inspector.SYSTEM_PROMPT,
                    "after": (
                        f"{pipeline_inspector.SYSTEM_PROMPT}\n"
                        f"{RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
                    ),
                }
            ]
        else:
            expected = (
                []
                if candidate_max_tokens == INSPECTOR_BASE_MAX_TOKENS
                else [
                    {
                        "path": "$.body.max_tokens",
                        "before": INSPECTOR_BASE_MAX_TOKENS,
                        "after": INSPECTOR_COMPAT_MAX_TOKENS,
                    }
                ]
            )
        if differences != expected:
            raise ZBatchError(f"第{chapter}章检查员请求超出本轮唯一变量")
        retry03_request_match = None
        retry03_request_sha = None
        if formal_retry04 and phase == "main" and chapter == TARGET_CHAPTERS[0]:
            source_api_batch_path = (
                _retry03_run_dir() / "review/inspector/ch0003/api_batch.json"
            )
            source_request_path = (
                _retry03_run_dir()
                / "review/inspector/ch0003/run/requests/semantic_route/"
                "Z83-MAIN-CH0003-API_request.json"
            )
            source_request = read_json(source_request_path)
            if (
                not source_api_batch_path.is_file()
                or read_json(source_api_batch_path) != api_batch
            ):
                raise ZBatchError("retry03第3章检查员API子批不能由冻结路由重建")
            retry03_request_match = source_request == baseline_record
            retry03_request_sha = sha256_file(source_request_path)
            if (
                not retry03_request_match
                or retry03_request_sha != APPROVED_RETRY03_INSPECTOR_REQUEST_SHA256
            ):
                raise ZBatchError("retry03第3章实发8k请求不能由当前冻结输入逐字重建")
        retry04_reference_sha = None
        retry04_request_match = None
        if formal_retry05 and phase == "main":
            if not isinstance(retry04_reference, dict):
                raise ZBatchError("retry05缺retry04冻结参照")
            candidate_shas = retry04_reference.get("candidate_request_sha256")
            retry04_reference_sha = (
                candidate_shas.get(str(chapter))
                if isinstance(candidate_shas, dict)
                else None
            )
            retry04_request_match = (
                isinstance(retry04_reference_sha, str)
                and canonical_sha(baseline_record) == retry04_reference_sha
            )
            if not retry04_request_match:
                raise ZBatchError(
                    f"retry05第{chapter}章基线请求不能逐字重建retry04预验件"
                )
            if chapter == TARGET_CHAPTERS[0]:
                retry04_request_path = (
                    _retry04_run_dir()
                    / "review/inspector/ch0003/run/requests/semantic_route/"
                    "Z83-MAIN-CH0003-API_request.json"
                )
                if (
                    read_json(retry04_request_path) != baseline_record
                    or sha256_file(retry04_request_path)
                    != APPROVED_RETRY04_INSPECTOR_REQUEST_SHA256
                ):
                    raise ZBatchError("retry05第3章基线请求不能逐字重建retry04实发件")
        retry05_reference_sha = None
        retry05_request_match = None
        if formal_retry06 and phase == "main":
            if not isinstance(retry05_reference, dict):
                raise ZBatchError("retry06缺retry05冻结参照")
            candidate_shas = retry05_reference.get("candidate_request_sha256")
            retry05_reference_sha = (
                candidate_shas.get(str(chapter))
                if isinstance(candidate_shas, dict)
                else None
            )
            retry05_request_match = (
                isinstance(retry05_reference_sha, str)
                and canonical_sha(candidate_record) == retry05_reference_sha
                and baseline_record == candidate_record
            )
            if not retry05_request_match:
                raise ZBatchError(f"retry06第{chapter}章请求不等于retry05冻结预验件")
            if chapter == TARGET_CHAPTERS[0]:
                retry05_request_path = (
                    _retry05_run_dir()
                    / "review/inspector/ch0003/run/requests/semantic_route/"
                    "Z83-MAIN-CH0003-API_request.json"
                )
                if (
                    read_json(retry05_request_path) != candidate_record
                    or sha256_file(retry05_request_path)
                    != APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256
                ):
                    raise ZBatchError("retry06第3章请求不能逐字重建retry05实发件")
        retry06_reference_sha = None
        retry06_request_match = None
        if formal_punctuation and phase == "main":
            if not isinstance(retry06_reference, dict):
                raise ZBatchError("retry07／retry08缺retry06冻结参照")
            candidate_shas = retry06_reference.get("candidate_request_sha256")
            retry06_reference_sha = (
                candidate_shas.get(str(chapter))
                if isinstance(candidate_shas, dict)
                else None
            )
            retry06_request_match = (
                isinstance(retry06_reference_sha, str)
                and canonical_sha(candidate_record) == retry06_reference_sha
                and baseline_record == candidate_record
            )
            if not retry06_request_match:
                raise ZBatchError(
                    f"retry07／retry08第{chapter}章请求不等于retry06冻结预验件"
                )
            if chapter == 13:
                retry06_request_path = (
                    _retry06_run_dir()
                    / "review/inspector/ch0013/run/requests/semantic_route/"
                    "Z83-MAIN-CH0013-API_request.json"
                )
                if (
                    read_json(retry06_request_path) != candidate_record
                    or sha256_file(retry06_request_path)
                    != APPROVED_RETRY06_CHAPTER13_REQUEST_SHA256
                ):
                    raise ZBatchError(
                        "retry07／retry08第13章请求不能逐字重建retry06实发件"
                    )
        rows.append(
            {
                "chapter": chapter,
                "batch_path": batch_path.relative_to(run_dir).as_posix(),
                "batch_sha256": sha256_file(batch_path),
                "api_item_count": len(transport_items),
                "baseline_messages_sha256": canonical_sha(
                    messages if formal_program_quote else baseline_messages
                ),
                "messages_sha256": canonical_sha(messages),
                "baseline_request_sha256": canonical_sha(baseline_record),
                "candidate_request_sha256": canonical_sha(candidate_record),
                "differences": differences,
                "retry03_actual_request_sha256": retry03_request_sha,
                "retry03_actual_request_rebuilt_exactly": retry03_request_match,
                "retry04_reference_request_sha256": retry04_reference_sha,
                "retry04_request_rebuilt_exactly": retry04_request_match,
                "retry05_reference_request_sha256": retry05_reference_sha,
                "retry05_request_rebuilt_exactly": retry05_request_match,
                "retry06_reference_request_sha256": retry06_reference_sha,
                "retry06_request_rebuilt_exactly": retry06_request_match,
            }
        )
    compatibility_bundle = stage_sampling.load_contract_bundle(
        contract_path,
        profile=pipeline_inspector.DEFAULT_PROFILE,
    )
    candidate_max_tokens = compatibility_bundle.stage(
        pipeline_inspector.STAGE
    ).max_tokens
    if formal_completed_target and candidate_max_tokens != INSPECTOR_COMPAT_MAX_TOKENS:
        raise ZBatchError(
            "retry04／retry05／retry06／retry07／retry08检查员实发合同不是32000"
        )
    if formal_retry04 and phase == "main" and not rows[0]["differences"]:
        raise ZBatchError("retry04第3章没有形成已拍的32k检查员实发请求")
    if formal_retry05 and phase == "main":
        if rows[0]["differences"] != [
            {
                "path": "$.body.messages[0].content",
                "before": pipeline_inspector.SYSTEM_PROMPT,
                "after": (
                    f"{pipeline_inspector.SYSTEM_PROMPT}\n"
                    f"{RETRY05_VERBATIM_QUOTE_SYSTEM_LINE}"
                ),
            }
        ]:
            raise ZBatchError("retry05第3章没有形成已拍的短引逐字唯一增量")
    if formal_retry06 and phase == "main":
        if any(row["differences"] for row in rows):
            raise ZBatchError("retry06检查员请求相对retry05存在夹带差异")
        if not all(row["retry05_request_rebuilt_exactly"] is True for row in rows):
            raise ZBatchError("retry06三章请求不能逐字重建retry05")
    if formal_retry07 and phase == "main":
        if any(row["differences"] for row in rows):
            raise ZBatchError("retry07检查员请求相对retry06存在夹带差异")
        if not all(row["retry06_request_rebuilt_exactly"] is True for row in rows):
            raise ZBatchError("retry07三章请求不能逐字重建retry06")
    if formal_retry08 and phase == "main":
        if any(row["differences"] for row in rows):
            raise ZBatchError("retry08检查员请求相对retry06存在夹带差异")
        if not all(row["retry06_request_rebuilt_exactly"] is True for row in rows):
            raise ZBatchError("retry08三章请求不能逐字重建retry06")
    candidate_contract_display = (
        contract_path.relative_to(run_dir).as_posix()
        if contract_path.is_relative_to(run_dir)
        else (
            contract_path.relative_to(ROOT).as_posix()
            if contract_path.is_relative_to(ROOT)
            else contract_path.as_posix()
        )
    )
    receipt = {
        "schema_version": f"z83-{phase}-inspector-request-preflight-v1",
        "status": (
            (
                (
                    "pass_zero_call_retry13_declared_scope32_punctuation_unit_compare_and_raw_rebuild_contract_no_prompt_or_parameter_change"
                    if formal_retry13
                    else "pass_zero_call_retry07_to_retry08_punctuation_unit_compare_and_raw_rebuild_only_no_request_change"
                    if formal_retry08 and phase == "main"
                    else "pass_zero_call_retry08_punctuation_unit_compare_and_raw_rebuild_contract_no_prompt_or_parameter_change"
                    if formal_punctuation_unit
                    else "pass_zero_call_retry06_to_retry07_punctuation_compare_only_no_request_change"
                    if phase == "main"
                    else "pass_zero_call_retry07_punctuation_compare_contract_no_prompt_or_parameter_change"
                )
            )
            if formal_punctuation
            else (
                (
                    "pass_zero_call_retry05_to_retry06_program_only_no_request_change"
                    if phase == "main"
                    else "pass_zero_call_retry06_program_contract_no_prompt_or_parameter_change"
                )
                if formal_retry06
                else (
                    "pass_zero_call_single_variable_retry04_to_retry05_verbatim_quote"
                    if formal_retry05
                    else (
                        "pass_zero_call_single_variable_8000_to_32000"
                        if candidate_max_tokens == INSPECTOR_COMPAT_MAX_TOKENS
                        else "pass_zero_call_baseline_8000"
                    )
                )
            )
        ),
        "phase": phase,
        "model_api_calls": 0,
        "network_attempts": 0,
        "baseline_contract_sha256": sha256_file(
            contract_path
            if formal_retry05 or formal_program_quote
            else INSPECTOR_CONTRACT
        ),
        "shared_8000_parent_contract_sha256": sha256_file(INSPECTOR_CONTRACT),
        "candidate_contract_path": candidate_contract_display,
        "candidate_contract_sha256": sha256_file(contract_path),
        "only_allowed_difference": (
            "none_request_identical_program_side_only"
            if formal_program_quote
            else (
                "$.body.messages[0].content: append exact verbatim-quote line"
                if formal_retry05
                else (
                    "$.body.max_tokens: 8000 -> 32000"
                    if candidate_max_tokens == INSPECTOR_COMPAT_MAX_TOKENS
                    else "none_baseline_8000"
                )
            )
        ),
        "system_prompt_suffix": system_prompt_suffix,
        "system_prompt_suffix_sha256": (
            hashlib.sha256(system_prompt_suffix.encode("utf-8")).hexdigest()
            if system_prompt_suffix is not None
            else None
        ),
        "retry04_reference_sha256": (
            canonical_sha(retry04_reference) if retry04_reference is not None else None
        ),
        "retry05_reference_sha256": (
            canonical_sha(
                retry05_reference
                if retry05_reference is not None
                else _retry05_inspector_reference()
            )
            if formal_program_quote
            else None
        ),
        "retry06_reference_sha256": (
            canonical_sha(
                retry06_reference
                if retry06_reference is not None
                else _retry06_inspector_reference()
            )
            if formal_punctuation
            else None
        ),
        "retry07_preflight_hard_stop_reference_sha256": (
            canonical_sha(_retry07_preflight_hard_stop_reference())
            if formal_punctuation_unit
            else None
        ),
        "program_side_quote_contract": (
            (
                {
                    "anchor_id_authoritative": True,
                    "formal_quote_program_filled_from_frozen_catalog": True,
                    "model_quote_role": "punctuation_normalized_substring_check_only",
                    "model_quote_must_be_contiguous_substring_after_fixed_punctuation_normalization": True,
                    "minimum_quote_nonspace_chars": RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
                    "punctuation_equivalence_sha256": (
                        pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                    ),
                    "punctuation_equivalence_path": (
                        RETRY07_PUNCTUATION_EQUIVALENCE.as_posix()
                    ),
                    "normalization_scope": "comparison_only_no_artifact_mutation",
                    "request_changed_from_retry06": False,
                    "retry06_rejected_response_imported": False,
                }
                if formal_retry07
                else {
                    "anchor_id_authoritative": True,
                    "formal_quote_program_filled_from_frozen_catalog": True,
                    "model_quote_role": "punctuation_unit_substring_check_only",
                    "model_quote_must_be_contiguous_subsequence_after_fixed_punctuation_unit_mapping": True,
                    "minimum_quote_nonspace_chars": RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
                    "punctuation_unit_equivalence_sha256": (
                        pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                    ),
                    "punctuation_unit_equivalence_path": (
                        RETRY08_PUNCTUATION_UNIT_EQUIVALENCE.as_posix()
                    ),
                    "comparison_scope": "typed_tokens_only_no_artifact_mutation",
                    "raw_response_usage_rebuild_required": True,
                    "request_changed_from_retry06": False,
                    "retry07_artifacts_imported_as_result": False,
                    "retry06_rejected_response_imported": False,
                }
                if formal_punctuation_unit
                else {
                    "anchor_id_authoritative": True,
                    "formal_quote_program_filled_from_frozen_catalog": True,
                    "model_quote_role": "consistency_check_only",
                    "model_quote_must_be_contiguous_substring": True,
                    "minimum_quote_nonspace_chars": RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
                    "request_changed_from_retry05": False,
                }
            )
            if formal_program_quote
            else None
        ),
        "inspector_source": {
            "path": Path(pipeline_inspector.__file__)
            .resolve()
            .relative_to(ROOT)
            .as_posix(),
            "sha256": sha256_file(Path(pipeline_inspector.__file__).resolve()),
        },
        "transport_source": {
            "path": Path(api_transport.__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": sha256_file(Path(api_transport.__file__).resolve()),
        },
        "rows": rows,
    }
    write_json(review_dir / "inspector_32k_preflight.json", receipt)
    return receipt


def _update_inspector_master(
    run_dir: Path,
    *,
    phase: str,
    status: str,
    receipt: Mapping[str, Any],
) -> None:
    master = read_json(run_dir / "run_manifest.json")
    slot = "review" if phase == "main" else "final"
    master["status"] = status
    master[slot] = status
    review_dir = run_dir / ("review" if phase == "main" else "final_review")
    root = review_dir / "inspector"
    root_manifest = root / "run_manifest.json"
    preflight_path = review_dir / "inspector_32k_preflight.json"
    master[f"{phase}_inspector"] = {
        "status": receipt.get("status"),
        "logical_model_calls": receipt.get(
            "logical_model_calls", receipt.get("logical_model_calls_completed")
        ),
        "network_attempts": receipt.get("network_attempts"),
        "completed_chapters": receipt.get("completed_chapters"),
        "root_manifest_path": root_manifest.relative_to(run_dir).as_posix(),
        "root_manifest_sha256": (
            sha256_file(root_manifest) if root_manifest.is_file() else None
        ),
        "request_preflight_path": preflight_path.relative_to(run_dir).as_posix(),
        "request_preflight_sha256": (
            sha256_file(preflight_path) if preflight_path.is_file() else None
        ),
        "inspector_contract_sha256": receipt.get("inspector_contract_sha256"),
    }
    write_json_atomic(run_dir / "run_manifest.json", master)


def _rebuild_review_risk_routing(
    run_dir: Path,
    *,
    phase: str,
    inspector_scope_ids: set[str] | None = None,
) -> dict[str, Any]:
    """从事件原件与旧25正式记录重建程序送审路由。

    这里故意不读 ``program_risks.json`` 或 build 票中的清单，
    避免“改清单再补 SHA”把本应发给检查员的事件变成零调用。
    """

    stage_dir = run_dir / phase
    events = _event_map(stage_dir)
    risk_rows: list[dict[str, Any]] = []
    forced_strong_ids: set[str] = set()
    for chapter in TARGET_CHAPTERS:
        event_document = read_json(_event_file(stage_dir, chapter))
        for event in event_document["events"]:
            event_id = str(event["event_id"])
            support_text = "".join(
                str(row.get("quote", "")) for row in event.get("anchors", [])
            )
            risks = _event_risks(event, support_text)
            if risks:
                risk_rows.append(
                    {
                        "risk_id": f"RISK-{event_id}",
                        "chapter": chapter,
                        "event_id": event_id,
                        "risk_codes": risks,
                        "event_sha256": canonical_sha(event),
                        "routing_only": True,
                        "final_truth": False,
                    }
                )
            if set(risks).intersection(FORCED_STRONG_RISKS):
                forced_strong_ids.add(event_id)

    old_arm = _current_rows_by_id(
        run_dir / "provenance/score_only/旧臂2旧25基线.json"
    )
    records = _current_record_map(run_dir)
    old25_candidate_ids: set[str] = set()
    for record_id in old_arm:
        if record_id not in records:
            raise ZBatchError(f"旧25记录无法在正式记录定位：{record_id}")
        chapter = _chapter_from_record_id(record_id)
        chapter_events = [
            row
            for row in events.values()
            if int(str(row["event_id"])[4:8]) == chapter
        ]
        ranked = _rank_events_for_record(records[record_id], chapter_events)
        shared = [
            str(candidate["event_id"])
            for candidate in ranked
            if candidate["shared_anchor_count"] > 0
        ]
        if shared:
            old25_candidate_ids.update(shared)
        elif ranked and ranked[0]["lexical_overlap"] > 0:
            old25_candidate_ids.add(str(ranked[0]["event_id"]))

    forced_strong_ids.update(old25_candidate_ids)
    risks_by_event = {str(row["event_id"]): row for row in risk_rows}
    for event_id in sorted(old25_candidate_ids):
        if event_id in risks_by_event:
            codes = risks_by_event[event_id]["risk_codes"]
            if "old25_candidate" not in codes:
                codes.append("old25_candidate")
                codes.sort()
        else:
            event = events[event_id]
            row = {
                "risk_id": f"RISK-{event_id}",
                "chapter": int(event_id[4:8]),
                "event_id": event_id,
                "risk_codes": ["old25_candidate"],
                "event_sha256": canonical_sha(event),
                "routing_only": True,
                "final_truth": False,
            }
            risk_rows.append(row)
            risks_by_event[event_id] = row
    risk_rows.sort(key=lambda row: row["risk_id"])
    document: dict[str, Any] = {
        "schema_version": "z83-program-risk-prefilter-v1",
        "status": "routing_only_not_final_truth",
        "rows": risk_rows,
        "forced_strong_event_ids": sorted(forced_strong_ids),
    }
    if inspector_scope_ids is not None:
        document["inspector_forced_strong_event_ids"] = sorted(
            forced_strong_ids.intersection(inspector_scope_ids)
        )
    return {
        "document": document,
        "old25_candidate_ids": sorted(old25_candidate_ids),
        "risks_by_event": risks_by_event,
    }


def _verify_review_build_inputs(run_dir: Path, *, phase: str) -> dict[str, Any]:
    review_dir = run_dir / ("review" if phase == "main" else "final_review")
    receipt = read_json(review_dir / "build_receipt.json")
    expected_event_set = {
        str(chapter): sha256_file(_event_file(run_dir / phase, chapter))
        for chapter in TARGET_CHAPTERS
    }
    expected_inputs = {
        "old25_automatic_comparison": sha256_file(
            review_dir / "old25_automatic_comparison.json"
        ),
        "program_risks": sha256_file(review_dir / "program_risks.json"),
        "adjudication_template": sha256_file(review_dir / "adjudication_template.json"),
        "inspector_batches": {
            str(chapter): sha256_file(
                review_dir / f"inspector_batches/ch{chapter:04d}.json"
            )
            for chapter in TARGET_CHAPTERS
        },
    }
    if (
        receipt.get("schema_version") != f"z83-{phase}-review-build-v1"
        or receipt.get("status") != "review_materials_ready_not_final_truth"
        or receipt.get("phase") != phase
        or receipt.get("event_set_sha256") != expected_event_set
        or receipt.get("review_input_sha256") != expected_inputs
        or receipt.get("model_visible_batches_contain_gold_or_cases") is not False
        or receipt.get("semantic_truth_pending") is not True
    ):
        raise ZBatchError(f"{phase}复核材料与build票不一致")
    if _formal_atomic_split_target(run_dir) and phase == "final":
        scope = _retry13_inspector_scope(run_dir)
        events = _event_map(run_dir / phase)
        template = read_json(review_dir / "adjudication_template.json")
        anchor_rows = template.get("anchor_rows") if isinstance(template, dict) else None
        program_risks = read_json(review_dir / "program_risks.json")
        rebuilt_routing = _rebuild_review_risk_routing(
            run_dir,
            phase=phase,
            inspector_scope_ids=set(scope["event_ids"]),
        )
        rebuilt_risks = rebuilt_routing["document"]
        risks_by_event = rebuilt_routing["risks_by_event"]
        scoped_ids: list[str] = []
        scoped_counts: Counter[int] = Counter()
        batch_metadata_valid = True
        for chapter in TARGET_CHAPTERS:
            batch = pipeline_inspector.validate_review_batch(
                read_json(review_dir / f"inspector_batches/ch{chapter:04d}.json")
            )
            chapter_ids = [str(item["item_id"]) for item in batch["items"]]
            scoped_ids.extend(chapter_ids)
            scoped_counts[chapter] += len(chapter_ids)
            for item in batch["items"]:
                event_id = str(item["item_id"])
                expected_codes = list(
                    risks_by_event.get(event_id, {}).get("risk_codes", [])
                )
                metadata = item.get("metadata")
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("program_risk_codes") != expected_codes
                    or metadata.get("forced_strong_review")
                    != (event_id in rebuilt_risks["forced_strong_event_ids"])
                ):
                    batch_metadata_valid = False
        if (
            receipt.get("inspector_scope") != scope
            or receipt.get("inspector_event_count") != 32
            or receipt.get("human_anchor_event_count") != 175
            or receipt.get("final_event_count") != 175
            or receipt.get("inspector_scope_event_ids") != scope["event_ids"]
            or receipt.get("human_anchor_row_count") != 175
            or program_risks != rebuilt_risks
            or receipt.get("program_risk_rows") != len(rebuilt_risks["rows"])
            or receipt.get("forced_strong_event_ids")
            != rebuilt_risks["forced_strong_event_ids"]
            or receipt.get("old25_forced_strong_event_ids")
            != rebuilt_routing["old25_candidate_ids"]
            or not isinstance(anchor_rows, list)
            or len(anchor_rows) != 175
            or {str(row.get("event_id") or "") for row in anchor_rows} != set(events)
            or len(scoped_ids) != len(set(scoped_ids))
            or set(scoped_ids) != set(scope["event_ids"])
            or scoped_counts != Counter({3: 7, 13: 7, 19: 18})
            or not batch_metadata_valid
        ):
            raise ZBatchError(
                "retry13复核材料没有保持人工175全量、检查员32后代或可重建强审路由"
            )
    return receipt


def _rebuild_anchor_authoritative_chapter3_reuse(
    *,
    api_batch: Mapping[str, Any],
    contract_path: Path,
    messages: list[dict[str, str]],
    retry_contract: str,
    evidence_quote_policy: str,
) -> dict[str, Any]:
    """从 retry05 原始响应重建第3章路由；不复制调用账或用量账。"""

    if retry_contract not in {"retry06", "retry07", "retry08"}:
        raise ZBatchError("第3章复用合同只接受retry06、retry07或retry08")

    reference = _retry05_inspector_reference()
    source_root = _retry05_run_dir() / "review/inspector/ch0003/run"
    source_batch_path = source_root.parent / "api_batch.json"
    source_request_path = (
        source_root / "requests/semantic_route/Z83-MAIN-CH0003-API_request.json"
    )
    source_raw_path = (
        source_root / "responses/semantic_route/Z83-MAIN-CH0003-API_raw.json"
    )
    source_routing_path = source_root / "routing_result.json"
    source_receipt_path = source_root / "run_receipt.json"
    validated_batch = pipeline_inspector.validate_review_batch(api_batch)
    if read_json(source_batch_path) != validated_batch:
        raise ZBatchError(f"{retry_contract}第3章检查批不等于retry05已通过源批")
    expected_request = _inspector_request_record(
        contract_path=contract_path,
        case_id=str(validated_batch["batch_id"]),
        messages=messages,
    )
    if (
        read_json(source_request_path) != expected_request
        or sha256_file(source_request_path) != APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256
    ):
        raise ZBatchError(f"{retry_contract}第3章待复用请求不等于retry05实发件")
    _, content = _read_response_content(source_raw_path)
    if sha256_file(source_raw_path) != APPROVED_RETRY05_CHAPTER3_RAW_SHA256:
        raise ZBatchError(f"{retry_contract}第3章待复用原始响应SHA漂移")
    transport_items, rule_escalated = pipeline_inspector.split_by_rule_gate(
        validated_batch
    )
    quote_rows: list[dict[str, Any]] = []
    model_rows = pipeline_inspector.parse_model_output(
        content,
        transport_items,
        evidence_quote_policy=evidence_quote_policy,
        minimum_quote_nonspace_chars=RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
        quote_fill_audit_rows=quote_rows,
    )
    rebuilt_routing = pipeline_inspector.build_routing_result(
        batch=validated_batch,
        model_rows=model_rows,
        rule_escalated=rule_escalated,
    )
    source_routing = read_json(source_routing_path)
    if (
        rebuilt_routing != source_routing
        or sha256_file(source_routing_path) != APPROVED_RETRY05_CHAPTER3_ROUTING_SHA256
        or sha256_file(source_receipt_path) != APPROVED_RETRY05_CHAPTER3_RECEIPT_SHA256
    ):
        raise ZBatchError(f"{retry_contract}第3章路由不能从retry05原始响应机械重建")
    quote_audit = pipeline_inspector.build_quote_fill_audit(
        batch_id=str(validated_batch["batch_id"]),
        rows=quote_rows,
        minimum_quote_nonspace_chars=RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
        evidence_quote_policy=evidence_quote_policy,
    )
    quote_audit["reuse_provenance"] = {
        "source_run_dir": reference["source_run_dir"],
        "source_request_sha256": APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256,
        "source_raw_response_sha256": APPROVED_RETRY05_CHAPTER3_RAW_SHA256,
        "source_routing_sha256": APPROVED_RETRY05_CHAPTER3_ROUTING_SHA256,
        "source_usage_imported": False,
        "source_network_attempt_imported": False,
    }
    receipt = {
        "schema_version": "z83-inspector-reused-chapter-v1",
        "status": "reused_verified_no_new_model_call",
        "chapter": 3,
        "source_run_dir": reference["source_run_dir"],
        "source_api_batch_sha256": APPROVED_RETRY05_CHAPTER3_API_BATCH_SHA256,
        "source_request_sha256": APPROVED_RETRY05_CHAPTER3_REQUEST_SHA256,
        "source_raw_response_sha256": APPROVED_RETRY05_CHAPTER3_RAW_SHA256,
        "source_routing_sha256": APPROVED_RETRY05_CHAPTER3_ROUTING_SHA256,
        "source_run_receipt_sha256": APPROVED_RETRY05_CHAPTER3_RECEIPT_SHA256,
        "request_rebuilt_exactly": True,
        f"response_reparsed_under_{retry_contract}_contract": True,
        "routing_rebuilt_exactly": True,
        "evidence_quote_policy": evidence_quote_policy,
        "minimum_quote_nonspace_chars": RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
        "model_api_calls": 0,
        "network_attempts": 0,
        "source_usage_imported": False,
        "source_network_attempt_imported": False,
        "retry05_chapter13_rejected_response_imported": False,
        "routes_sha256": canonical_sha(rebuilt_routing["routes"]),
        "quote_fill_audit_sha256": canonical_sha(quote_audit),
    }
    if retry_contract == "retry07":
        receipt.update(
            {
                "punctuation_equivalence_sha256": (
                    pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                ),
                "retry06_chapter13_rejected_response_imported": False,
            }
        )
    if retry_contract == "retry08":
        receipt.update(
            {
                "punctuation_unit_equivalence_sha256": (
                    pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                ),
                "retry07_artifacts_imported_as_result": False,
                "retry06_chapter13_rejected_response_imported": False,
            }
        )
    return {
        "routing": rebuilt_routing,
        "quote_fill_audit": quote_audit,
        "receipt": receipt,
    }


def _rebuild_retry06_chapter3_reuse(
    *,
    api_batch: Mapping[str, Any],
    contract_path: Path,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    return _rebuild_anchor_authoritative_chapter3_reuse(
        api_batch=api_batch,
        contract_path=contract_path,
        messages=messages,
        retry_contract="retry06",
        evidence_quote_policy=(
            pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
        ),
    )


def _rebuild_retry07_chapter3_reuse(
    *,
    api_batch: Mapping[str, Any],
    contract_path: Path,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    return _rebuild_anchor_authoritative_chapter3_reuse(
        api_batch=api_batch,
        contract_path=contract_path,
        messages=messages,
        retry_contract="retry07",
        evidence_quote_policy=(
            pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
        ),
    )


def _rebuild_retry08_chapter3_reuse(
    *,
    api_batch: Mapping[str, Any],
    contract_path: Path,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    return _rebuild_anchor_authoritative_chapter3_reuse(
        api_batch=api_batch,
        contract_path=contract_path,
        messages=messages,
        retry_contract="retry08",
        evidence_quote_policy=(
            pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
        ),
    )


def _rebuild_fresh_inspector_chapter_from_raw(
    *,
    nested_root: Path,
    expected_batch: Mapping[str, Any],
    contract_path: Path,
    messages: list[dict[str, str]],
    evidence_quote_policy: str,
    minimum_quote_nonspace_chars: int,
) -> dict[str, Any]:
    """只从原始请求／响应／usage 重建一次新调章，拒绝信任中间票。"""

    batch = pipeline_inspector.validate_review_batch(expected_batch)
    transport_items, rule_escalated = pipeline_inspector.split_by_rule_gate(batch)
    if not transport_items:
        raise ZBatchError("原始响应重建章没有实际 API 条目")
    case_id = str(batch["batch_id"])
    expected_request = _inspector_request_record(
        contract_path=contract_path,
        case_id=case_id,
        messages=messages,
    )
    expected_paths = _transport_paths(
        nested_root, pipeline_inspector.STAGE, case_id
    )
    path_sets = {
        "request": list(nested_root.glob("requests/semantic_route/*_request.json")),
        "raw_response": list(
            nested_root.glob("responses/semantic_route/*_raw.json")
        ),
        "response_meta": list(
            nested_root.glob("responses/semantic_route/*_meta.json")
        ),
    }
    for label, paths in path_sets.items():
        if len(paths) != 1 or paths[0] != expected_paths[label]:
            raise ZBatchError(f"{case_id}{label}落盘文件不是恰好一份")
    usage_rows = z68.read_jsonl(nested_root / "usage.jsonl")
    if (
        len(usage_rows) != 1
        or usage_rows[0].get("stage") != pipeline_inspector.STAGE
        or usage_rows[0].get("case_id") != case_id
    ):
        raise ZBatchError(f"{case_id}全章 usage 账不是恰好一条")
    attempt_rows = z68.read_jsonl(nested_root / "call_attempts.jsonl")
    retry13_checkpoint_root = nested_root / "checkpoint"
    retry13_transport = retry13_checkpoint_root.is_dir()
    if not attempt_rows or (
        retry13_transport
        and any(row.get("logical_request_id") != case_id for row in attempt_rows)
    ) or (
        not retry13_transport
        and any(
            row.get("stage") != pipeline_inspector.STAGE
            or row.get("case_id") != case_id
            for row in attempt_rows
        )
    ):
        raise ZBatchError(f"{case_id}运输尝试账混入其他章批")
    retry13_checkpoint: dict[str, Any] | None = None
    if retry13_transport:
        z83_retry_transport.validate_attempt_rows(attempt_rows)
        wait_receipts = z83_retry_transport.validate_retry_wait_sequence(
            nested_root / "call_attempts.jsonl",
            attempt_rows,
            require_all_429_completed=True,
        )
        statuses = [int(row["http_status"]) for row in attempt_rows]
        if (
            len(attempt_rows) > 3
            or statuses[-1] != 200
            or any(status != 429 for status in statuses[:-1])
            or [int(row["attempt"]) for row in attempt_rows]
            != list(range(1, len(attempt_rows) + 1))
            or len({str(row["request_sha256"]) for row in attempt_rows}) != 1
            or len({str(row["wire_body_sha256"]) for row in attempt_rows}) != 1
            or len({str(row["request_artifact_sha256"]) for row in attempt_rows})
            != 1
        ):
            raise ZBatchError(f"{case_id}retry13尝试序列不是至多2次429后唯一成功")
        for index, row in enumerate(attempt_rows[:-1]):
            required = (5.0, 10.0)[index]
            retry_after = row.get("retry_after_seconds")
            required = max(
                required,
                float(retry_after) if isinstance(retry_after, (int, float)) else 0.0,
            )
            wait_receipt = wait_receipts.get((case_id, int(row["attempt"])))
            if (
                float(row.get("retry_wait_seconds") or 0.0) < required
                or wait_receipt is None
                or wait_receipt.get("status") != "completed"
                or float(wait_receipt.get("actual_seconds") or 0.0) < required
            ):
                raise ZBatchError(f"{case_id}retry13的429退避短于冻结规则")
        retry13_checkpoint = z83_retry_transport.validate_checkpoint_bundle(
            retry13_checkpoint_root
        )
        checkpoint_request = read_json(retry13_checkpoint_root / "01_request.json")
        checkpoint_response = read_json(retry13_checkpoint_root / "02_response.json")
        checkpoint_usage = read_json(retry13_checkpoint_root / "03_usage.json")
        if (
            retry13_checkpoint.get("mechanical_verdict") != "pass"
            or retry13_checkpoint.get("contract_version")
            != _Retry13InspectorTransportSession.CONTRACT_VERSION
            or checkpoint_request.get("logical_request_id") != case_id
            or checkpoint_request.get("request_artifact_sha256")
            != sha256_file(expected_paths["request"])
            or checkpoint_request.get("wire_body_sha256")
            != hashlib.sha256(
                _wire_body_bytes(expected_request["body"])
            ).hexdigest()
            or any(
                row.get("wire_body_sha256")
                != hashlib.sha256(
                    _wire_body_bytes(expected_request["body"])
                ).hexdigest()
                for row in attempt_rows
            )
            or checkpoint_response.get("raw_response_sha256")
            != sha256_file(expected_paths["raw_response"])
            or checkpoint_usage.get("usage") != usage_rows[0].get("usage")
        ):
            raise ZBatchError(f"{case_id}retry13五件检查点不能从原件重建")
    transport_receipt = _transport_receipt_fields(
        nested_root, pipeline_inspector.STAGE, case_id
    )
    raw, content = _verify_successful_exchange(
        stage_dir=nested_root,
        stage=pipeline_inspector.STAGE,
        case_id=case_id,
        expected_body=expected_request["body"],
        receipt=transport_receipt,
    )
    nested_receipt_path = nested_root / "run_receipt.json"
    nested_routing_path = nested_root / "routing_result.json"
    quote_audit_path = nested_root / "quote_fill_audit.json"
    if (
        not nested_receipt_path.is_file()
        or not nested_routing_path.is_file()
        or not quote_audit_path.is_file()
    ):
        raise ZBatchError(f"{case_id}缺运行回执、路由或短引审计原件")
    nested_receipt = read_json(nested_receipt_path)
    response_meta = read_json(expected_paths["response_meta"])
    raw_usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    if (
        nested_receipt.get("usage") != raw_usage
        or nested_receipt.get("transport") != response_meta
    ):
        raise ZBatchError(f"{case_id}子回执 usage／运输元数据不能由原始响应重建")
    quote_rows: list[dict[str, Any]] = []
    model_rows = pipeline_inspector.parse_model_output(
        content,
        transport_items,
        evidence_quote_policy=evidence_quote_policy,
        minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
        quote_fill_audit_rows=quote_rows,
    )
    rebuilt_routing = pipeline_inspector.build_routing_result(
        batch=batch,
        model_rows=model_rows,
        rule_escalated=rule_escalated,
    )
    rebuilt_quote_audit = pipeline_inspector.build_quote_fill_audit(
        batch_id=case_id,
        rows=quote_rows,
        minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
        evidence_quote_policy=evidence_quote_policy,
    )
    if read_json(nested_routing_path) != rebuilt_routing:
        raise ZBatchError(f"{case_id}落盘路由不能从原始响应重建")
    if read_json(quote_audit_path) != rebuilt_quote_audit:
        raise ZBatchError(f"{case_id}落盘短引审计不能从原始响应重建")
    usage_path = nested_root / "usage.jsonl"
    return {
        "schema_version": "z83-inspector-raw-response-rebuild-v1",
        "status": "pass_rebuilt_from_raw_response_and_unique_usage",
        "case_id": case_id,
        "request_path": transport_receipt["request_path"],
        "request_sha256": transport_receipt["request_sha256"],
        "raw_response_path": transport_receipt["raw_response_path"],
        "raw_response_sha256": transport_receipt["raw_response_sha256"],
        "response_meta_path": transport_receipt["response_meta_path"],
        "response_meta_sha256": transport_receipt["response_meta_sha256"],
        "usage_path": "usage.jsonl",
        "usage_file_sha256": sha256_file(usage_path),
        "usage_rows": 1,
        "attempt_rows": len(attempt_rows),
        "retry13_immutable_checkpoint": (
            {
                "path": retry13_checkpoint_root.relative_to(nested_root).as_posix(),
                "checkpoint_id": retry13_checkpoint["checkpoint_id"],
                "contract_version": retry13_checkpoint["contract_version"],
                "mechanical_verdict": retry13_checkpoint["mechanical_verdict"],
            }
            if retry13_checkpoint is not None
            else None
        ),
        "usage": raw_usage,
        "routing_path": "routing_result.json",
        "routing_file_sha256": sha256_file(nested_routing_path),
        "routing_canonical_sha256": canonical_sha(rebuilt_routing),
        "quote_fill_audit_path": "quote_fill_audit.json",
        "quote_fill_audit_file_sha256": sha256_file(quote_audit_path),
        "quote_fill_audit_canonical_sha256": canonical_sha(
            rebuilt_quote_audit
        ),
        "evidence_quote_policy": evidence_quote_policy,
        "minimum_quote_nonspace_chars": minimum_quote_nonspace_chars,
        "punctuation_unit_equivalence_sha256": (
            pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
            if evidence_quote_policy
            == pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
            else None
        ),
        "routes": rebuilt_routing["routes"],
        "routes_sha256": canonical_sha(rebuilt_routing["routes"]),
        "raw_response_reparsed": True,
        "intermediate_routing_trusted_without_rebuild": False,
        "intermediate_quote_audit_trusted_without_rebuild": False,
    }


def run_inspector(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    phase: str = "main",
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """跑 Z76 低成本语义分流；结果只决定去哪里复核，不产正式真值。"""

    if _uses_retry11_request_contract(run_dir) and phase == "main":
        raise ZBatchError("retry11／retry12主阶段只准零调用复用retry09判词，禁止重跑检查员")
    if run_dir.name == APPROVED_CAPACITY_OVERRIDE_TARGET_NAME:
        raise ZBatchError(
            "retry09按续令⑦只能零调用复用retry08检查员工件，禁止新发检查员"
        )
    if phase not in {"main", "final"}:
        raise ZBatchError("inspector phase 只能是 main 或 final")
    if _formal_atomic_split_target(run_dir) and phase == "main":
        raise ZBatchError("retry13主样只用于冻结原子计划；检查员只准复查最终32个后代")
    review_dir = run_dir / ("review" if phase == "main" else "final_review")
    if not (review_dir / "build_receipt.json").is_file():
        raise ZBatchError("先生成复核材料")
    root = review_dir / "inspector"
    if (review_dir / "inspector_preflight_hard_stop.json").exists():
        raise ZBatchError("检查员发网前已有硬停票，原目录不得修复后续跑")
    if root.exists():
        raise ZBatchError("检查员阶段已有工件，拒绝复跑挑结果")
    try:
        review_build = _verify_review_build_inputs(run_dir, phase=phase)
        prepared = verify_prepared(
            run_dir,
            require_zero_call=False,
            allow_test_run_dir=allow_test_run_dir,
        )
        inspector_contract_path = Path(prepared["inspector_contract_path"])
        if not inspector_contract_path.is_absolute():
            inspector_contract_path = ROOT / inspector_contract_path
        request_preflight = _preflight_inspector_requests(
            run_dir,
            phase=phase,
            review_dir=review_dir,
            contract_path=inspector_contract_path,
        )
    except BaseException as exc:
        preflight_hard_stop = {
            "schema_version": f"z83-{phase}-inspector-preflight-hard-stop-v1",
            "status": "hard_stop_before_claim_and_network",
            "phase": phase,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "model_api_calls": 0,
            "network_attempts": 0,
            "inspector_claim_created": False,
        }
        hard_stop_path = review_dir / "inspector_preflight_hard_stop.json"
        write_json_atomic(hard_stop_path, preflight_hard_stop)
        master = read_json(run_dir / "run_manifest.json")
        slot = "review" if phase == "main" else "final"
        master["status"] = f"{phase}_inspector_preflight_hard_stop"
        master[slot] = "hard_stop_before_claim_and_network"
        master[f"{phase}_inspector_preflight"] = {
            "status": preflight_hard_stop["status"],
            "path": hard_stop_path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(hard_stop_path),
        }
        write_json_atomic(run_dir / "run_manifest.json", master)
        raise
    _require_api_key_before_claim()
    root.mkdir(parents=True)
    claim = _acquire_claim(
        root / "run_claim.json", f"z83-{phase}-inspector-run-claim-v1"
    )
    combined_routes: list[dict[str, Any]] = []
    logical_calls = 0
    batch_invocations = 0
    completed_chapters: list[int] = []
    reused_chapters: list[int] = []
    new_called_chapters: list[int] = []
    new_attempted_chapters: list[int] = []
    event_set_sha: dict[str, str] = {}
    system_prompt_suffix = _retry05_system_prompt_suffix(run_dir)
    formal_retry06 = run_dir.name == APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME
    formal_retry07 = run_dir.name == APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME
    formal_retry08 = run_dir.name == APPROVED_PUNCTUATION_UNIT_TARGET_NAME
    formal_retry13 = _formal_atomic_split_target(run_dir) and phase == "final"
    retry13_test_clock = [0.0]

    def retry13_test_monotonic() -> float:
        return retry13_test_clock[0]

    def retry13_test_sleep(seconds: float) -> None:
        retry13_test_clock[0] += seconds

    retry13_inspector_session = (
        _Retry13InspectorTransportSession(
            **(
                {
                    "sleeper": retry13_test_sleep,
                    "monotonic": retry13_test_monotonic,
                    "jitter": lambda: 0.0,
                }
                if allow_test_run_dir
                else {}
            )
        )
        if formal_retry13
        else None
    )
    formal_punctuation_unit = formal_retry08 or formal_retry13
    formal_program_quote = formal_retry06 or formal_retry07 or formal_punctuation_unit
    formal_program_quote_main = formal_program_quote and phase == "main"
    evidence_quote_policy = (
        pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
        if formal_punctuation_unit
        else (
            pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
            if formal_retry07
            else (
                pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
                if formal_retry06
                else pipeline_inspector.EVIDENCE_QUOTE_POLICY_EXACT
            )
        )
    )
    raw_rebuild_receipts: dict[str, dict[str, Any]] = {}
    minimum_quote_nonspace_chars = (
        RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS if formal_program_quote else 1
    )
    try:
        program_risks_path = review_dir / "program_risks.json"
        program_risks = read_json(program_risks_path)
        all_forced_ids = set(program_risks["forced_strong_event_ids"])
        expected_events = _event_map(run_dir / phase)
        expected_ids = (
            set(review_build["inspector_scope"]["event_ids"])
            if formal_retry13
            else set(expected_events)
        )
        if not all_forced_ids.issubset(expected_events):
            raise ZBatchError("程序强审清单引用了本轮不存在事件")
        if not expected_ids.issubset(expected_events):
            raise ZBatchError("检查员声明范围引用了本轮不存在事件")
        if formal_retry13:
            declared_forced_ids = set(
                program_risks.get("inspector_forced_strong_event_ids") or []
            )
            if declared_forced_ids != all_forced_ids.intersection(expected_ids):
                raise ZBatchError("retry13检查员强审清单不等于全量人工强审与32后代交集")
            forced_ids = declared_forced_ids
        else:
            forced_ids = all_forced_ids.intersection(expected_ids)
        event_set_sha = {
            str(chapter): sha256_file(_event_file(run_dir / phase, chapter))
            for chapter in TARGET_CHAPTERS
        }
        batch_sha = {
            str(chapter): sha256_file(
                review_dir / f"inspector_batches/ch{chapter:04d}.json"
            )
            for chapter in TARGET_CHAPTERS
        }
        running_manifest = {
            "schema_version": f"z83-{phase}-inspector-run-manifest-v1",
            "status": "running_do_not_resume",
            "phase": phase,
            "run_claim": claim,
            "event_set_sha256": event_set_sha,
            "inspector_batch_sha256": batch_sha,
            "program_risks_sha256": sha256_file(program_risks_path),
            "request_preflight_sha256": sha256_file(
                review_dir / "inspector_32k_preflight.json"
            ),
            "inspector_contract_path": request_preflight["candidate_contract_path"],
            "inspector_contract_sha256": sha256_file(inspector_contract_path),
            "global_logical_call_limit": MAX_INSPECTOR_LOGICAL_CALLS,
            "network_retry_limit_per_chapter_batch": 2 if formal_retry13 else 3,
            "reused_chapters": reused_chapters,
            "new_called_chapters": new_called_chapters,
            "new_attempted_chapters": new_attempted_chapters,
            "retry06_program_side_quote_contract": (
                {
                    "anchor_id_authoritative": True,
                    "model_quote_role": "contiguous_substring_check_only",
                    "minimum_quote_nonspace_chars": RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS,
                    "formal_quote_source": "run_dir_inputs_evidence_catalogs",
                }
                if formal_retry06
                else None
            ),
            "retry07_punctuation_normalization_contract": (
                {
                    "anchor_id_authoritative": True,
                    "model_quote_role": (
                        "punctuation_normalized_contiguous_substring_check_only"
                    ),
                    "minimum_quote_nonspace_chars": (
                        RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                    ),
                    "punctuation_equivalence_sha256": (
                        pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                    ),
                    "normalization_scope": "comparison_only_no_artifact_mutation",
                    "formal_quote_source": "run_dir_inputs_evidence_catalogs",
                    "retry06_rejected_response_imported": False,
                }
                if formal_retry07
                else None
            ),
            "retry08_punctuation_unit_and_raw_rebuild_contract": (
                {
                    "anchor_id_authoritative": True,
                    "model_quote_role": "punctuation_unit_substring_check_only",
                    "minimum_quote_nonspace_chars": (
                        RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                    ),
                    "punctuation_unit_equivalence_sha256": (
                        pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                    ),
                    "comparison_scope": "typed_tokens_only_no_artifact_mutation",
                    "fresh_chapter_raw_response_rebuild_required": True,
                    "fresh_chapter_unique_usage_required": True,
                    "formal_quote_source": "run_dir_inputs_evidence_catalogs",
                    "retry07_artifacts_imported_as_result": False,
                    "retry06_rejected_response_imported": False,
                }
                if formal_punctuation_unit
                else None
            ),
            "retry13_declared_scope": (
                review_build["inspector_scope"] if formal_retry13 else None
            ),
            "retry13_inspector_transport": (
                {
                    "contract_version": (
                        _Retry13InspectorTransportSession.CONTRACT_VERSION
                    ),
                    "retry_only_http_429": True,
                    "max_429_retries_per_request": 2,
                    "max_429_per_run": 5,
                    "retry_delays_seconds": [5, 10],
                    "retry_after_hard_stop_over_seconds": 300,
                    "same_chapter_gap_seconds": 10,
                    "cross_chapter_gap_seconds": 30,
                    "immutable_checkpoint_files_per_logical_request": 5,
                }
                if formal_retry13
                else None
            ),
        }
        write_json_atomic(root / "run_manifest.json", running_manifest)
        _update_inspector_master(
            run_dir,
            phase=phase,
            status=f"{phase}_inspector_running_do_not_resume",
            receipt=running_manifest,
        )
        for chapter in TARGET_CHAPTERS:
            batch_path = review_dir / f"inspector_batches/ch{chapter:04d}.json"
            batch = pipeline_inspector.validate_review_batch(read_json(batch_path))
            forced = _direct_forced_routing(batch, forced_ids)
            combined_routes.extend(forced)
            api_items = [
                item for item in batch["items"] if item["item_id"] not in forced_ids
            ]
            chapter_dir = root / f"ch{chapter:04d}"
            chapter_dir.mkdir(parents=True)
            if not api_items:
                write_json(
                    chapter_dir / "zero_call_all_forced.json",
                    {
                        "schema_version": "z83-inspector-all-forced-v1",
                        "chapter": chapter,
                        "model_api_calls": 0,
                        "routes": forced,
                    },
                )
                completed_chapters.append(chapter)
                continue
            if batch_invocations >= MAX_INSPECTOR_LOGICAL_CALLS:
                raise ZBatchError("检查员整轮章批次数超过3，硬停")
            api_batch = {
                **batch,
                "items": api_items,
                "batch_id": batch["batch_id"] + "-API",
            }
            if forbidden_model_hits(
                pipeline_inspector.build_messages(
                    api_batch,
                    api_items,
                    system_prompt_suffix=system_prompt_suffix,
                )
            ):
                raise ZBatchError("检查员模型请求含判分侧材料")
            api_batch_path = chapter_dir / "api_batch.json"
            write_json(api_batch_path, api_batch)
            if formal_program_quote_main and chapter == 3:
                _, transport_items, messages = _inspector_api_projection(
                    batch,
                    forced_ids,
                    system_prompt_suffix=system_prompt_suffix,
                )
                if not transport_items:
                    raise ZBatchError(
                        "retry06／retry07／retry08第3章冻结检查批意外变成零调用路由"
                    )
                rebuild = (
                    _rebuild_retry08_chapter3_reuse
                    if formal_retry08
                    else (
                        _rebuild_retry07_chapter3_reuse
                        if formal_retry07
                        else _rebuild_retry06_chapter3_reuse
                    )
                )
                reused = rebuild(
                    api_batch=api_batch,
                    contract_path=inspector_contract_path,
                    messages=messages,
                )
                write_json(
                    chapter_dir / "reused_routing_result.json", reused["routing"]
                )
                write_json(
                    chapter_dir / "quote_fill_audit.json", reused["quote_fill_audit"]
                )
                reuse_receipt = dict(reused["receipt"])
                reuse_receipt["reused_routing_path"] = "reused_routing_result.json"
                reuse_receipt["reused_routing_file_sha256"] = sha256_file(
                    chapter_dir / "reused_routing_result.json"
                )
                reuse_receipt["quote_fill_audit_path"] = "quote_fill_audit.json"
                reuse_receipt["quote_fill_audit_file_sha256"] = sha256_file(
                    chapter_dir / "quote_fill_audit.json"
                )
                write_json(chapter_dir / "reuse_receipt.json", reuse_receipt)
                combined_routes.extend(reused["routing"]["routes"])
                reused_chapters.append(chapter)
                completed_chapters.append(chapter)
                continue
            batch_invocations += 1
            if formal_program_quote:
                new_attempted_chapters.append(chapter)
            chapter_receipt = pipeline_inspector.run_inspector(
                batch_path=api_batch_path,
                run_dir=chapter_dir / "run",
                contract_path=inspector_contract_path,
                profile=pipeline_inspector.DEFAULT_PROFILE,
                max_calls=3,
                system_prompt_suffix=system_prompt_suffix,
                evidence_quote_policy=evidence_quote_policy,
                minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                call_adapter=retry13_inspector_session,
            )
            if formal_program_quote:
                new_called_chapters.append(chapter)
            logical_calls += int(chapter_receipt.get("logical_model_calls", 0))
            if logical_calls > MAX_INSPECTOR_LOGICAL_CALLS:
                raise ZBatchError("检查员整轮逻辑模型调用超过3，硬停")
            routing = read_json(chapter_dir / "run/routing_result.json")
            if formal_punctuation_unit:
                _, _, messages = _inspector_api_projection(
                    batch,
                    forced_ids,
                    system_prompt_suffix=system_prompt_suffix,
                )
                rebuilt = _rebuild_fresh_inspector_chapter_from_raw(
                    nested_root=chapter_dir / "run",
                    expected_batch=api_batch,
                    contract_path=inspector_contract_path,
                    messages=messages,
                    evidence_quote_policy=evidence_quote_policy,
                    minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                )
                raw_rebuild_path = chapter_dir / "run/raw_rebuild_receipt.json"
                write_json(raw_rebuild_path, rebuilt)
                raw_rebuild_receipts[str(chapter)] = {
                    "path": raw_rebuild_path.relative_to(root).as_posix(),
                    "sha256": sha256_file(raw_rebuild_path),
                }
            combined_routes.extend(routing["routes"])
            completed_chapters.append(chapter)
        routed_ids = [str(row["item_id"]) for row in combined_routes]
        if len(routed_ids) != len(set(routed_ids)) or set(routed_ids) != expected_ids:
            raise ZBatchError("检查员分流未逐条覆盖全部事件")
        combined_routes.sort(key=lambda row: row["item_id"])
        receipt = {
            "schema_version": f"z83-{phase}-inspector-routing-v1",
            "status": "routing_complete_not_final_truth",
            "phase": phase,
            "run_claim": claim,
            "completed_chapters": completed_chapters,
            "reused_chapters": reused_chapters,
            "new_called_chapters": new_called_chapters,
            "new_attempted_chapters": new_attempted_chapters,
            "batch_invocations": batch_invocations,
            "logical_model_calls": logical_calls,
            "global_logical_call_limit": MAX_INSPECTOR_LOGICAL_CALLS,
            "network_attempts": _inspector_network_attempts(root),
            "event_set_sha256": event_set_sha,
            "inspector_batch_sha256": batch_sha,
            "program_risks_sha256": sha256_file(program_risks_path),
            "request_preflight_sha256": sha256_file(
                review_dir / "inspector_32k_preflight.json"
            ),
            "request_preflight": request_preflight,
            "inspector_contract_path": request_preflight["candidate_contract_path"],
            "inspector_contract_sha256": sha256_file(inspector_contract_path),
            "event_count": len(expected_ids),
            **(
                {
                    "final_event_count": len(expected_events),
                    "inspector_event_count": len(expected_ids),
                    "inspector_scope_event_ids": sorted(expected_ids),
                }
                if formal_retry13
                else {}
            ),
            **(
                {"inspector_scope": review_build["inspector_scope"]}
                if formal_retry13
                else {}
            ),
            "routes": combined_routes,
            "routes_sha256": canonical_sha(combined_routes),
            "forced_strong_count": len(forced_ids),
            "evidence_quote_policy": evidence_quote_policy,
            "minimum_quote_nonspace_chars": minimum_quote_nonspace_chars,
            "punctuation_equivalence_sha256": (
                pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                if formal_retry07
                else None
            ),
            "punctuation_unit_equivalence_sha256": (
                pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                if formal_punctuation_unit
                else None
            ),
            "raw_rebuild_receipts": (
                raw_rebuild_receipts if formal_punctuation_unit else None
            ),
            "retry13_inspector_transport": (
                {
                    "contract_version": (
                        _Retry13InspectorTransportSession.CONTRACT_VERSION
                    ),
                    "retry_only_http_429": True,
                    "max_429_retries_per_request": 2,
                    "max_429_per_run": 5,
                    "retry_delays_seconds": [5, 10],
                    "retry_after_hard_stop_over_seconds": 300,
                    "same_chapter_gap_seconds": 10,
                    "cross_chapter_gap_seconds": 30,
                    "immutable_checkpoint_files_per_logical_request": 5,
                }
                if formal_retry13
                else None
            ),
            "reused_source_usage_imported": False,
            "reused_source_network_attempt_imported": False,
            "new_call_usage": (
                _inspector_usage_for_chapters(root, new_attempted_chapters)
                if formal_program_quote
                else None
            ),
            "reused_chapter3_source_usage_reference": (
                _retry05_inspector_reference()["chapter3"]["source_usage"]
                if formal_program_quote_main
                else None
            ),
            "final_truth": False,
        }
        write_json_atomic(root / "combined_routing.json", receipt)
        write_json_atomic(
            root / "run_manifest.json",
            {
                **receipt,
                "schema_version": f"z83-{phase}-inspector-run-manifest-v1",
                "status": "completed_routing_only_not_final_truth",
                "combined_routing_sha256": sha256_file(root / "combined_routing.json"),
            },
        )
        _update_inspector_master(
            run_dir,
            phase=phase,
            status=f"{phase}_inspector_completed_routing_only",
            receipt=receipt,
        )
        return receipt
    except BaseException as exc:
        hard_stop = {
            "schema_version": f"z83-{phase}-inspector-hard-stop-v1",
            "status": "hard_stop_no_resume_or_result_selection",
            "phase": phase,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "completed_chapters": completed_chapters,
            "reused_chapters": reused_chapters,
            "new_called_chapters": new_called_chapters,
            "new_attempted_chapters": new_attempted_chapters,
            "new_call_usage": (
                _inspector_usage_for_chapters(root, new_attempted_chapters)
                if formal_program_quote
                else None
            ),
            "batch_invocations": batch_invocations,
            "logical_model_calls_completed": logical_calls,
            "network_attempts": _inspector_network_attempts(root),
            "event_set_sha256": event_set_sha,
            "request_preflight_sha256": sha256_file(
                review_dir / "inspector_32k_preflight.json"
            ),
            "inspector_contract_path": request_preflight["candidate_contract_path"],
            "inspector_contract_sha256": sha256_file(inspector_contract_path),
            "run_claim": claim,
        }
        if formal_retry07 or formal_punctuation_unit:
            hard_stop["evidence_quote_policy"] = evidence_quote_policy
            hard_stop["minimum_quote_nonspace_chars"] = minimum_quote_nonspace_chars
            if formal_punctuation_unit:
                hard_stop["punctuation_unit_equivalence_sha256"] = (
                    pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                )
                hard_stop["raw_rebuild_receipts"] = raw_rebuild_receipts
            else:
                hard_stop["punctuation_equivalence_sha256"] = (
                    pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                )
        write_json_atomic(root / "hard_stop.json", hard_stop)
        write_json_atomic(root / "run_manifest.json", hard_stop)
        _update_inspector_master(
            run_dir,
            phase=phase,
            status=f"{phase}_inspector_hard_stop",
            receipt=hard_stop,
        )
        raise


def _validate_candidate_ids(
    values: Any,
    *,
    label: str,
    allowed: set[str],
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise ZBatchError(f"{label} 必须是字符串数组")
    if not allow_empty and not values:
        raise ZBatchError(f"{label} 不能为空")
    if len(values) != len(set(values)):
        raise ZBatchError(f"{label} 有重复ID")
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ZBatchError(f"{label} 引用不存在事件：{unknown}")
    return list(values)


def _nonempty_reason(row: Mapping[str, Any], label: str) -> str:
    value = row.get("reason")
    if not isinstance(value, str) or not value.strip():
        raise ZBatchError(f"{label} 缺逐条语义判词")
    return value.strip()


def validate_adjudication(
    run_dir: Path,
    path: Path,
    *,
    phase: str,
) -> dict[str, Any]:
    doc = read_json(path)
    if (
        not isinstance(doc, dict)
        or doc.get("schema_version") != "z83-semantic-adjudication-v1"
    ):
        raise ZBatchError("语义判词合同错误")
    if doc.get("run_id") != run_dir.name or doc.get("phase") != phase:
        raise ZBatchError("语义判词run_id或phase不符")
    stage_dir = run_dir / phase
    events = _event_map(stage_dir)
    allowed = set(events)
    expected_event_sha = {
        str(chapter): sha256_file(_event_file(stage_dir, chapter))
        for chapter in TARGET_CHAPTERS
    }
    if doc.get("event_set_sha256") != expected_event_sha:
        raise ZBatchError("语义判词未绑定当前最终事件文件SHA")
    reviewer = doc.get("reviewer")
    reviewed_at = doc.get("reviewed_at")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or not isinstance(reviewed_at, str)
        or not reviewed_at.strip()
    ):
        raise ZBatchError("语义判词缺reviewer或reviewed_at")

    anchor_rows = doc.get("anchor_rows")
    if not isinstance(anchor_rows, list):
        raise ZBatchError("语义判词缺anchor_rows")
    anchor_by_id = {}
    for row in anchor_rows:
        if not isinstance(row, dict):
            raise ZBatchError("anchor_rows含非对象")
        event_id = str(row.get("event_id") or "")
        if event_id in anchor_by_id or event_id not in events:
            raise ZBatchError(f"anchor_rows事件ID重复或不存在：{event_id}")
        if row.get("event_sha256") != canonical_sha(events[event_id]):
            raise ZBatchError(f"{event_id}判词未绑定事件内容SHA")
        if row.get("verdict") not in ANCHOR_VERDICTS:
            raise ZBatchError(f"{event_id}锚语义判词非法")
        unsupported = row.get("unsupported_claims")
        if not isinstance(unsupported, list) or not all(
            isinstance(value, str) for value in unsupported
        ):
            raise ZBatchError(f"{event_id} unsupported_claims格式错误")
        if row["verdict"] == "valid" and unsupported:
            raise ZBatchError(f"{event_id}判valid却登记不支撑主张")
        if row["verdict"] == "invalid" and not unsupported:
            raise ZBatchError(f"{event_id}判invalid却未列不支撑主张")
        _nonempty_reason(row, f"anchor_rows/{event_id}")
        anchor_by_id[event_id] = dict(row)
    if set(anchor_by_id) != allowed:
        raise ZBatchError(
            f"anchor_rows未全量覆盖事件：缺{sorted(allowed - set(anchor_by_id))}"
        )

    old_arm = _current_rows_by_id(run_dir / "provenance/score_only/旧臂2旧25基线.json")
    v3_rows = _current_rows_by_id(run_dir / "provenance/score_only/v3语义判词基线.json")
    current_rows = doc.get("current_rows")
    if not isinstance(current_rows, list):
        raise ZBatchError("语义判词缺current_rows")
    current_by_id = {}
    degraded = []
    for row in current_rows:
        if not isinstance(row, dict):
            raise ZBatchError("current_rows含非对象")
        record_id = str(row.get("record_id") or "")
        if (
            record_id in current_by_id
            or record_id not in old_arm
            or record_id not in v3_rows
        ):
            raise ZBatchError(f"current_rows记录ID重复或越界：{record_id}")
        chapter = _chapter_from_record_id(record_id)
        chapter_allowed = {
            event_id for event_id in allowed if int(event_id[4:8]) == chapter
        }
        candidate_ids = _validate_candidate_ids(
            row.get("candidate_event_ids"),
            label=f"current_rows/{record_id}",
            allowed=chapter_allowed,
        )
        verdict = row.get("verdict")
        if verdict not in CURRENT_RANK:
            raise ZBatchError(f"{record_id}旧25判词非法")
        if verdict != "not_observed" and not candidate_ids:
            raise ZBatchError(f"{record_id}非未观察却无候选事件")
        required_floor = (
            "preserved"
            if record_id in {"B-C0013-02", "B-C0019-04"}
            else str(v3_rows[record_id]["verdict"])
        )
        if row.get("required_floor") != required_floor:
            raise ZBatchError(f"{record_id}判词偷偷改尺")
        if record_id == "B-C0019-04" and row.get("scale_note_acknowledged") is not True:
            raise ZBatchError("B-C0019-04未确认正式字段与历史观察的口径缝")
        _nonempty_reason(row, f"current_rows/{record_id}")
        if CURRENT_RANK[str(verdict)] < CURRENT_RANK[required_floor]:
            degraded.append(record_id)
        current_by_id[record_id] = {**dict(row), "candidate_event_ids": candidate_ids}
    if set(current_by_id) != set(old_arm):
        raise ZBatchError("current_rows必须完整覆盖旧25")

    formal_parts = _gold_parts()
    gold_rows = doc.get("gold_rows")
    if not isinstance(gold_rows, list):
        raise ZBatchError("语义判词缺gold_rows")
    gold_by_id = {}
    chapter3_allowed = {event_id for event_id in allowed if int(event_id[4:8]) == 3}
    for row in gold_rows:
        if not isinstance(row, dict):
            raise ZBatchError("gold_rows含非对象")
        part_id = str(row.get("part_id") or "")
        if part_id in gold_by_id or part_id not in formal_parts:
            raise ZBatchError(f"gold_rows编号重复或越界：{part_id}")
        verdict = row.get("verdict")
        if verdict not in GOLD_VERDICTS:
            raise ZBatchError(f"{part_id}金标判词非法")
        candidate_ids = _validate_candidate_ids(
            row.get("candidate_event_ids"),
            label=f"gold_rows/{part_id}",
            allowed=chapter3_allowed,
        )
        if verdict != "miss" and not candidate_ids:
            raise ZBatchError(f"{part_id}非漏项却无候选事件")
        if verdict in {"strict_hit", "semantic_shadow"} and any(
            anchor_by_id[event_id]["verdict"] != "valid" for event_id in candidate_ids
        ):
            raise ZBatchError(f"{part_id}计入有效召回却引用语义锚无效事件")
        if verdict == "coverage_only_invalid_support" and not any(
            anchor_by_id[event_id]["verdict"] == "invalid" for event_id in candidate_ids
        ):
            raise ZBatchError(f"{part_id}判锚无效覆盖却没有无效锚事件")
        _nonempty_reason(row, f"gold_rows/{part_id}")
        gold_by_id[part_id] = {**dict(row), "candidate_event_ids": candidate_ids}
    if set(gold_by_id) != set(formal_parts):
        raise ZBatchError("gold_rows必须完整覆盖金标23条")

    risk_source = read_json(
        run_dir
        / ("review" if phase == "main" else "final_review")
        / "program_risks.json"
    )
    expected_risks = {str(row["risk_id"]): row for row in risk_source["rows"]}
    risk_rows = doc.get("risk_rows")
    if not isinstance(risk_rows, list):
        raise ZBatchError("语义判词缺risk_rows")
    risk_by_id = {}
    for row in risk_rows:
        if not isinstance(row, dict):
            raise ZBatchError("risk_rows含非对象")
        risk_id = str(row.get("risk_id") or "")
        if risk_id in risk_by_id or risk_id not in expected_risks:
            raise ZBatchError(f"risk_rows编号重复或越界：{risk_id}")
        event_id = str(row.get("event_id") or "")
        if event_id != expected_risks[risk_id]["event_id"] or row.get(
            "event_sha256"
        ) != canonical_sha(events[event_id]):
            raise ZBatchError(f"{risk_id}未绑定当前事件")
        if row.get("verdict") not in RISK_VERDICTS:
            raise ZBatchError(f"{risk_id}程序风险判词非法")
        _nonempty_reason(row, f"risk_rows/{risk_id}")
        risk_by_id[risk_id] = dict(row)
    if set(risk_by_id) != set(expected_risks):
        raise ZBatchError("risk_rows必须覆盖全部程序风险")

    return {
        "schema_version": "z83-validated-adjudication-v1",
        "phase": phase,
        "source_path": path.as_posix(),
        "source_sha256": sha256_file(path),
        "event_set_sha256": expected_event_sha,
        "events": events,
        "anchor_rows": anchor_by_id,
        "current_rows": current_by_id,
        "gold_rows": gold_by_id,
        "risk_rows": risk_by_id,
        "degraded_record_ids": sorted(degraded),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
    }


def require_inspector_complete(run_dir: Path, *, phase: str) -> dict[str, Any]:
    review_dir = run_dir / ("review" if phase == "main" else "final_review")
    review_build = _verify_review_build_inputs(run_dir, phase=phase)
    if _formal_atomic_split_target(run_dir) and phase == "main":
        raise ZBatchError("retry13主样没有检查员声明范围；只核验最终32个后代")
    if _formal_thirteen_retry_target(run_dir) and phase == "main":
        receipt_path = run_dir / RETRY09_ADJUDICATION_REUSE_RECEIPT
        adjudication_path = run_dir / "review/adjudication_reused_from_retry09.json"
        if (
            not receipt_path.is_file()
            or not adjudication_path.is_file()
            or (review_dir / "inspector").exists()
        ):
            raise ZBatchError("13条特批轮主样阶段缺零调用判词复用票或夹带检查员调用")
        receipt = read_json(receipt_path)
        master = read_json(run_dir / "run_manifest.json")
        if (
            receipt.get("status") != _retry09_reuse_status(run_dir)
            or receipt.get("source_adjudication_sha256")
            != RETRY09_ADJUDICATION_SHA256
            or receipt.get("derived_adjudication_sha256")
            != sha256_file(adjudication_path)
            or receipt.get("approved_event_ids")
            != list(_approved_thirteen_event_ids(run_dir))
            or receipt.get("semantic_pre_review_redone") is not False
            or receipt.get("model_api_calls") != 0
            or receipt.get("network_attempts") != 0
            or master.get("retry09_adjudication_reuse", {}).get("sha256")
            != sha256_file(receipt_path)
        ):
            raise ZBatchError("13条特批轮主样零调用判词复用票漂移")
        for row in receipt.get("source_artifacts", {}).values():
            path = ROOT / str(row.get("path") or "")
            if not path.is_file() or sha256_file(path) != row.get("sha256"):
                raise ZBatchError("13条特批轮引用的retry09封存来源漂移")
        validate_adjudication(run_dir, adjudication_path, phase="main")
        return receipt
    root = review_dir / "inspector"
    path = root / "combined_routing.json"
    claim_path = root / "run_claim.json"
    manifest_path = root / "run_manifest.json"
    if (
        not path.is_file()
        or not claim_path.is_file()
        or not manifest_path.is_file()
        or (root / "hard_stop.json").exists()
    ):
        raise ZBatchError(f"{phase}阶段还没有检查员全量分流票")
    receipt = read_json(path)
    claim = read_json(claim_path)
    manifest = read_json(manifest_path)
    if (
        not isinstance(claim, dict)
        or claim.get("schema_version") != f"z83-{phase}-inspector-run-claim-v1"
        or claim.get("status") != "claimed_do_not_resume"
    ):
        raise ZBatchError(f"{phase}检查员占用票错误")
    events = _event_map(run_dir / phase)
    formal_retry13 = _formal_atomic_split_target(run_dir) and phase == "final"
    expected_ids = (
        set(review_build["inspector_scope"]["event_ids"])
        if formal_retry13
        else set(events)
    )
    event_set_sha = {
        str(chapter): sha256_file(_event_file(run_dir / phase, chapter))
        for chapter in TARGET_CHAPTERS
    }
    routes = receipt.get("routes") if isinstance(receipt, dict) else None
    if (
        receipt.get("status") != "routing_complete_not_final_truth"
        or receipt.get("phase") != phase
        or receipt.get("final_truth") is not False
        or receipt.get("run_claim") != claim
        or receipt.get("event_set_sha256") != event_set_sha
        or receipt.get("routes_sha256") != canonical_sha(routes)
        or receipt.get("global_logical_call_limit") != MAX_INSPECTOR_LOGICAL_CALLS
        or receipt.get("completed_chapters") != list(TARGET_CHAPTERS)
        or (
            formal_retry13
            and receipt.get("inspector_scope") != review_build["inspector_scope"]
        )
        or (
            formal_retry13
            and (
                receipt.get("final_event_count") != len(events)
                or receipt.get("inspector_event_count") != len(expected_ids)
                or receipt.get("inspector_scope_event_ids")
                != sorted(expected_ids)
            )
        )
        or not isinstance(routes, list)
    ):
        raise ZBatchError(f"{phase}检查员分流票合同错误")
    if (
        manifest.get("schema_version") != f"z83-{phase}-inspector-run-manifest-v1"
        or manifest.get("status") != "completed_routing_only_not_final_truth"
        or manifest.get("combined_routing_sha256") != sha256_file(path)
    ):
        raise ZBatchError(f"{phase}检查员完成状态票错误")
    for key, value in receipt.items():
        if key not in {"schema_version", "status"} and manifest.get(key) != value:
            raise ZBatchError(f"{phase}检查员完成状态票与总票不一致：{key}")
    formal_retry04 = run_dir.name == APPROVED_COMPLETED_SEED_TARGET_NAME
    formal_retry05 = run_dir.name == APPROVED_QUOTE_CONSTRAINT_TARGET_NAME
    formal_retry06 = run_dir.name == APPROVED_QUOTE_PROGRAM_FILL_TARGET_NAME
    formal_retry07 = run_dir.name == APPROVED_PUNCTUATION_NORMALIZATION_TARGET_NAME
    formal_retry08 = run_dir.name == APPROVED_PUNCTUATION_UNIT_TARGET_NAME
    formal_punctuation_unit = formal_retry08 or formal_retry13
    formal_program_quote = formal_retry06 or formal_retry07 or formal_punctuation_unit
    formal_completed_target = formal_retry04 or formal_retry05 or formal_program_quote
    if formal_completed_target and (
        receipt.get("request_preflight_sha256") is None
        or receipt.get("request_preflight") is None
        or receipt.get("inspector_contract_sha256") is None
    ):
        raise ZBatchError(
            f"{phase}正式retry04／retry05检查员票缺请求预验或合同绑定（retry06／retry07／retry08同闸）"
        )
    request_preflight: dict[str, Any] | None = None
    contract_path: Path | None = None
    if receipt.get("request_preflight_sha256") is not None:
        request_preflight_path = review_dir / "inspector_32k_preflight.json"
        if not request_preflight_path.is_file() or receipt.get(
            "request_preflight_sha256"
        ) != sha256_file(request_preflight_path):
            raise ZBatchError(f"{phase}检查员请求预验票缺失或SHA漂移")
        request_preflight = read_json(request_preflight_path)
        if (
            receipt.get("request_preflight") != request_preflight
            or request_preflight.get("phase") != phase
            or request_preflight.get("model_api_calls") != 0
            or request_preflight.get("network_attempts") != 0
        ):
            raise ZBatchError(f"{phase}检查员请求预验票合同错误")
        if formal_retry05:
            expected_suffix_sha = hashlib.sha256(
                RETRY05_VERBATIM_QUOTE_SYSTEM_LINE.encode("utf-8")
            ).hexdigest()
            expected_retry04_reference_sha = canonical_sha(
                _retry04_inspector_reference()
            )
            if (
                request_preflight.get("status")
                != "pass_zero_call_single_variable_retry04_to_retry05_verbatim_quote"
                or request_preflight.get("system_prompt_suffix")
                != RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
                or request_preflight.get("system_prompt_suffix_sha256")
                != expected_suffix_sha
                or request_preflight.get("retry04_reference_sha256")
                != expected_retry04_reference_sha
            ):
                raise ZBatchError(f"{phase} retry05短引逐字唯一增量票错误")
        if formal_retry06:
            expected_retry05_reference_sha = canonical_sha(
                _retry05_inspector_reference()
            )
            program_contract = request_preflight.get("program_side_quote_contract")
            if (
                request_preflight.get("status")
                != (
                    "pass_zero_call_retry05_to_retry06_program_only_no_request_change"
                    if phase == "main"
                    else "pass_zero_call_retry06_program_contract_no_prompt_or_parameter_change"
                )
                or request_preflight.get("system_prompt_suffix")
                != RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
                or request_preflight.get("retry05_reference_sha256")
                != expected_retry05_reference_sha
                or not isinstance(program_contract, dict)
                or program_contract.get("minimum_quote_nonspace_chars")
                != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                or program_contract.get("request_changed_from_retry05") is not False
            ):
                raise ZBatchError(f"{phase} retry06程序侧唯一改动票错误")
            for row in request_preflight.get("rows", []):
                if (
                    not isinstance(row, dict)
                    or row.get("differences") != []
                    or row.get("baseline_request_sha256")
                    != row.get("candidate_request_sha256")
                ):
                    raise ZBatchError(f"{phase} retry06检查员Prompt或参数漂移")
        if formal_retry07:
            expected_retry06_reference_sha = canonical_sha(
                _retry06_inspector_reference()
            )
            program_contract = request_preflight.get("program_side_quote_contract")
            if (
                request_preflight.get("status")
                != (
                    "pass_zero_call_retry06_to_retry07_punctuation_compare_only_no_request_change"
                    if phase == "main"
                    else "pass_zero_call_retry07_punctuation_compare_contract_no_prompt_or_parameter_change"
                )
                or request_preflight.get("system_prompt_suffix")
                != RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
                or request_preflight.get("retry06_reference_sha256")
                != expected_retry06_reference_sha
                or not isinstance(program_contract, dict)
                or program_contract.get("minimum_quote_nonspace_chars")
                != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                or program_contract.get("punctuation_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                or program_contract.get("request_changed_from_retry06") is not False
                or program_contract.get("retry06_rejected_response_imported")
                is not False
            ):
                raise ZBatchError(f"{phase} retry07程序侧标点归一唯一改动票错误")
            for row in request_preflight.get("rows", []):
                if (
                    not isinstance(row, dict)
                    or row.get("differences") != []
                    or row.get("baseline_request_sha256")
                    != row.get("candidate_request_sha256")
                    or (
                        phase == "main"
                        and row.get("retry06_request_rebuilt_exactly") is not True
                    )
                ):
                    raise ZBatchError(f"{phase} retry07检查员Prompt或参数漂移")
        if formal_punctuation_unit:
            expected_retry06_reference_sha = canonical_sha(
                _retry06_inspector_reference()
            )
            expected_retry07_reference_sha = canonical_sha(
                _retry07_preflight_hard_stop_reference()
            )
            program_contract = request_preflight.get("program_side_quote_contract")
            if (
                request_preflight.get("status")
                != (
                    "pass_zero_call_retry13_declared_scope32_punctuation_unit_compare_and_raw_rebuild_contract_no_prompt_or_parameter_change"
                    if formal_retry13
                    else "pass_zero_call_retry07_to_retry08_punctuation_unit_compare_and_raw_rebuild_only_no_request_change"
                    if phase == "main"
                    else "pass_zero_call_retry08_punctuation_unit_compare_and_raw_rebuild_contract_no_prompt_or_parameter_change"
                )
                or request_preflight.get("system_prompt_suffix")
                != RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
                or request_preflight.get("retry06_reference_sha256")
                != expected_retry06_reference_sha
                or request_preflight.get(
                    "retry07_preflight_hard_stop_reference_sha256"
                )
                != expected_retry07_reference_sha
                or not isinstance(program_contract, dict)
                or program_contract.get("minimum_quote_nonspace_chars")
                != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                or program_contract.get("punctuation_unit_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                or program_contract.get("raw_response_usage_rebuild_required")
                is not True
                or program_contract.get("request_changed_from_retry06") is not False
                or program_contract.get("retry07_artifacts_imported_as_result")
                is not False
                or program_contract.get("retry06_rejected_response_imported")
                is not False
            ):
                raise ZBatchError(f"{phase} retry08程序侧双修正唯一改动票错误")
            for row in request_preflight.get("rows", []):
                if (
                    not isinstance(row, dict)
                    or row.get("differences") != []
                    or row.get("baseline_request_sha256")
                    != row.get("candidate_request_sha256")
                    or (
                        phase == "main"
                        and row.get("retry06_request_rebuilt_exactly") is not True
                    )
                ):
                    raise ZBatchError(f"{phase} retry08检查员Prompt或参数漂移")
        prepared_dependencies = read_json(run_dir / "preflight.json").get(
            "producer_dependencies"
        )
        if not isinstance(prepared_dependencies, dict) or (
            request_preflight.get("inspector_source")
            != prepared_dependencies.get("pipeline_inspector")
            or request_preflight.get("transport_source")
            != prepared_dependencies.get("api_transport")
        ):
            raise ZBatchError(f"{phase}检查员请求票未绑定准备时程序SHA")
        contract_path = _resolve_inspector_contract_path(
            run_dir,
            receipt.get("inspector_contract_path"),
        )
        if receipt.get("inspector_contract_sha256") != sha256_file(contract_path):
            raise ZBatchError(f"{phase}检查员实发合同SHA漂移")
        compatibility = read_json(run_dir / "preflight.json").get(
            "inspector_compatibility"
        )
        if (
            _verify_inspector_compatibility(run_dir, compatibility or {})
            != contract_path
        ):
            raise ZBatchError(f"{phase}检查员实发合同不等于准备阶段登记件")
        master = read_json(run_dir / "run_manifest.json")
        master_row = master.get(f"{phase}_inspector")
        if (
            not isinstance(master_row, dict)
            or master_row.get("root_manifest_sha256") != sha256_file(manifest_path)
            or master_row.get("request_preflight_sha256")
            != sha256_file(request_preflight_path)
            or master_row.get("inspector_contract_sha256") != sha256_file(contract_path)
        ):
            raise ZBatchError(f"{phase}检查员顶层机器账未绑定完成票")
    program_risks_path = review_dir / "program_risks.json"
    batches_sha = {
        str(chapter): sha256_file(
            review_dir / f"inspector_batches/ch{chapter:04d}.json"
        )
        for chapter in TARGET_CHAPTERS
    }
    if (
        receipt.get("program_risks_sha256") != sha256_file(program_risks_path)
        or receipt.get("inspector_batch_sha256") != batches_sha
    ):
        raise ZBatchError(f"{phase}检查员输入工件SHA漂移")
    program_risks = read_json(program_risks_path)
    all_forced_ids = set(program_risks["forced_strong_event_ids"])
    if not all_forced_ids.issubset(events):
        raise ZBatchError(f"{phase}程序强审清单引用了不存在事件")
    if formal_retry13:
        forced_ids = set(
            program_risks.get("inspector_forced_strong_event_ids") or []
        )
        if forced_ids != all_forced_ids.intersection(expected_ids):
            raise ZBatchError("retry13检查员强审清单不能由全量人工清单与声明范围重建")
    else:
        forced_ids = all_forced_ids.intersection(expected_ids)
    rebuilt_routes: list[dict[str, Any]] = []
    rebuilt_logical_calls = 0
    rebuilt_batch_invocations = 0
    preflight_rows = (
        {int(row["chapter"]): row for row in request_preflight.get("rows", [])}
        if request_preflight is not None
        else {}
    )
    system_prompt_suffix = _retry05_system_prompt_suffix(run_dir)
    for chapter in TARGET_CHAPTERS:
        batch = pipeline_inspector.validate_review_batch(
            read_json(review_dir / f"inspector_batches/ch{chapter:04d}.json")
        )
        forced = _direct_forced_routing(batch, forced_ids)
        rebuilt_routes.extend(forced)
        api_items = [
            item for item in batch["items"] if item["item_id"] not in forced_ids
        ]
        chapter_dir = root / f"ch{chapter:04d}"
        if api_items:
            expected_batch = {
                **batch,
                "items": api_items,
                "batch_id": batch["batch_id"] + "-API",
            }
            api_batch_path = chapter_dir / "api_batch.json"
            if formal_program_quote and phase == "main" and chapter == 3:
                _, transport_items, messages = _inspector_api_projection(
                    batch,
                    forced_ids,
                    system_prompt_suffix=system_prompt_suffix,
                )
                if not transport_items:
                    raise ZBatchError(
                        "main第3章retry06／retry07／retry08复用批意外无模型条目"
                    )
                rebuild = (
                    _rebuild_retry08_chapter3_reuse
                    if formal_retry08
                    else (
                        _rebuild_retry07_chapter3_reuse
                        if formal_retry07
                        else _rebuild_retry06_chapter3_reuse
                    )
                )
                rebuilt = rebuild(
                    api_batch=expected_batch,
                    contract_path=contract_path,
                    messages=messages,
                )
                reuse_receipt_path = chapter_dir / "reuse_receipt.json"
                reused_routing_path = chapter_dir / "reused_routing_result.json"
                quote_audit_path = chapter_dir / "quote_fill_audit.json"
                if (
                    not api_batch_path.is_file()
                    or read_json(api_batch_path) != expected_batch
                    or not reuse_receipt_path.is_file()
                    or not reused_routing_path.is_file()
                    or not quote_audit_path.is_file()
                    or read_json(reused_routing_path) != rebuilt["routing"]
                    or read_json(quote_audit_path) != rebuilt["quote_fill_audit"]
                ):
                    raise ZBatchError(
                        "main第3章retry06／retry07／retry08复用票不完整"
                    )
                expected_reuse_receipt = dict(rebuilt["receipt"])
                expected_reuse_receipt["reused_routing_path"] = (
                    "reused_routing_result.json"
                )
                expected_reuse_receipt["reused_routing_file_sha256"] = sha256_file(
                    reused_routing_path
                )
                expected_reuse_receipt["quote_fill_audit_path"] = (
                    "quote_fill_audit.json"
                )
                expected_reuse_receipt["quote_fill_audit_file_sha256"] = sha256_file(
                    quote_audit_path
                )
                if read_json(reuse_receipt_path) != expected_reuse_receipt:
                    raise ZBatchError(
                        "main第3章retry06／retry07／retry08复用血缘票漂移"
                    )
                row = preflight_rows.get(chapter)
                expected_request = _inspector_request_record(
                    contract_path=contract_path,
                    case_id=str(expected_batch["batch_id"]),
                    messages=messages,
                )
                if (
                    not isinstance(row, dict)
                    or row.get("differences") != []
                    or (
                        row.get(
                            "retry06_request_rebuilt_exactly"
                            if formal_retry07 or formal_retry08
                            else "retry05_request_rebuilt_exactly"
                        )
                        is not True
                    )
                    or row.get("candidate_request_sha256")
                    != canonical_sha(expected_request)
                    or list(chapter_dir.glob("run/requests/**/*.json"))
                    or list(chapter_dir.glob("run/responses/**/*.json"))
                    or (formal_retry08 and (chapter_dir / "run").exists())
                ):
                    raise ZBatchError(
                        "main第3章retry06／retry07／retry08复用夹带新请求或预验漂移"
                    )
                rebuilt_routes.extend(rebuilt["routing"]["routes"])
                continue
            rebuilt_batch_invocations += 1
            nested_root = chapter_dir / "run"
            nested_receipt_path = nested_root / "run_receipt.json"
            nested_routing_path = nested_root / "routing_result.json"
            if (
                not api_batch_path.is_file()
                or read_json(api_batch_path) != expected_batch
                or not nested_receipt_path.is_file()
                or not nested_routing_path.is_file()
                or (nested_root / "hard_stop.json").exists()
            ):
                raise ZBatchError(f"{phase}第{chapter}章检查员子票不完整")
            nested_receipt = read_json(nested_receipt_path)
            nested_routing = read_json(nested_routing_path)
            nested_routes = (
                nested_routing.get("routes")
                if isinstance(nested_routing, dict)
                else None
            )
            expected_api_ids = {str(item["item_id"]) for item in api_items}
            nested_network_attempts = nested_receipt.get("network_attempts")
            if (
                nested_receipt.get("status") != "complete"
                or nested_receipt.get("decision_scope") != "routing_only"
                or not isinstance(nested_routes, list)
                or {
                    str(row.get("item_id"))
                    for row in nested_routes
                    if isinstance(row, dict)
                }
                != expected_api_ids
                or isinstance(nested_network_attempts, bool)
                or not isinstance(nested_network_attempts, int)
                or nested_network_attempts != _inspector_network_attempts(nested_root)
                or not 0 <= nested_network_attempts <= 3
            ):
                raise ZBatchError(f"{phase}第{chapter}章检查员子票计数或覆盖错误")
            if (
                formal_program_quote
                and phase == "main"
                and chapter in {13, 19}
                and (
                    nested_network_attempts < 1
                    or (chapter_dir / "reuse_receipt.json").exists()
                )
            ):
                raise ZBatchError(f"main第{chapter}章必须是独立新调，不得伪装复用件")
            chapter_logical_calls = nested_receipt.get("logical_model_calls")
            if (
                isinstance(chapter_logical_calls, bool)
                or not isinstance(chapter_logical_calls, int)
                or not 0 <= chapter_logical_calls <= 1
            ):
                raise ZBatchError(f"{phase}第{chapter}章检查员逻辑调用数错误")
            if formal_program_quote:
                quote_audit_path = nested_root / "quote_fill_audit.json"
                quote_audit = (
                    read_json(quote_audit_path) if quote_audit_path.is_file() else None
                )
                outputs = nested_receipt.get("outputs")
                if (
                    not isinstance(quote_audit, dict)
                    or quote_audit.get("evidence_quote_policy")
                    != (
                        pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
                        if formal_punctuation_unit
                        else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
                        if formal_retry06
                        else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
                    )
                    or quote_audit.get("minimum_quote_nonspace_chars")
                    != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                    or not isinstance(outputs, dict)
                    or outputs.get("quote_fill_audit") != "quote_fill_audit.json"
                    or (
                        formal_retry07
                        and quote_audit.get("punctuation_equivalence_sha256")
                        != pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                    )
                    or (
                        formal_punctuation_unit
                        and quote_audit.get(
                            "punctuation_unit_equivalence_sha256"
                        )
                        != pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                    )
                ):
                    raise ZBatchError(
                        f"{phase}第{chapter}章retry06／retry07／retry08程序回填审计票缺失"
                    )
            rebuilt_logical_calls += chapter_logical_calls
            routes_for_rebuild = nested_routes
            if formal_punctuation_unit:
                if contract_path is None:
                    raise ZBatchError("retry08缺检查员冻结合同")
                _, transport_items, messages = _inspector_api_projection(
                    batch,
                    forced_ids,
                    system_prompt_suffix=system_prompt_suffix,
                )
                if not transport_items:
                    raise ZBatchError(f"{phase}第{chapter}章预期新调却无运输条目")
                rebuilt_from_raw = _rebuild_fresh_inspector_chapter_from_raw(
                    nested_root=nested_root,
                    expected_batch=expected_batch,
                    contract_path=contract_path,
                    messages=messages,
                    evidence_quote_policy=(
                        pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
                    ),
                    minimum_quote_nonspace_chars=(
                        RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
                    ),
                )
                raw_rebuild_path = nested_root / "raw_rebuild_receipt.json"
                expected_raw_rebuild_rows = receipt.get("raw_rebuild_receipts")
                expected_raw_rebuild = (
                    expected_raw_rebuild_rows.get(str(chapter))
                    if isinstance(expected_raw_rebuild_rows, dict)
                    else None
                )
                if (
                    not raw_rebuild_path.is_file()
                    or read_json(raw_rebuild_path) != rebuilt_from_raw
                    or expected_raw_rebuild
                    != {
                        "path": raw_rebuild_path.relative_to(root).as_posix(),
                        "sha256": sha256_file(raw_rebuild_path),
                    }
                ):
                    raise ZBatchError(
                        f"{phase}第{chapter}章原始响应／usage重建票漂移"
                    )
                routes_for_rebuild = rebuilt_from_raw["routes"]
            rebuilt_routes.extend(routes_for_rebuild)
            if request_preflight is not None and contract_path is not None:
                _, transport_items, messages = _inspector_api_projection(
                    batch,
                    forced_ids,
                    system_prompt_suffix=system_prompt_suffix,
                )
                row = preflight_rows.get(chapter)
                if not isinstance(row, dict):
                    raise ZBatchError(f"{phase}第{chapter}章缺请求预验行")
                if transport_items:
                    case_id = str(expected_batch["batch_id"])
                    expected_request = _inspector_request_record(
                        contract_path=contract_path,
                        case_id=case_id,
                        messages=messages,
                    )
                    actual_request_path = (
                        nested_root
                        / f"requests/{pipeline_inspector.STAGE}/{case_id}_request.json"
                    )
                    if (
                        not actual_request_path.is_file()
                        or read_json(actual_request_path) != expected_request
                        or row.get("candidate_request_sha256")
                        != canonical_sha(expected_request)
                    ):
                        raise ZBatchError(
                            f"{phase}第{chapter}章实发请求不等于32k预构造件"
                        )
                elif row.get("candidate_request_sha256") is not None or list(
                    nested_root.glob("requests/**/*.json")
                ):
                    raise ZBatchError(f"{phase}第{chapter}章零调用预验与实发账不一致")
        else:
            zero_path = chapter_dir / "zero_call_all_forced.json"
            expected_zero = {
                "schema_version": "z83-inspector-all-forced-v1",
                "chapter": chapter,
                "model_api_calls": 0,
                "routes": forced,
            }
            if not zero_path.is_file() or read_json(zero_path) != expected_zero:
                raise ZBatchError(f"{phase}第{chapter}章检查员零调用票错误")
    rebuilt_routes.sort(key=lambda row: row["item_id"])
    ids = [str(row.get("item_id")) for row in rebuilt_routes if isinstance(row, dict)]
    receipt_network_attempts = receipt.get("network_attempts")
    if formal_program_quote and phase == "main":
        if (
            receipt.get("reused_chapters") != [3]
            or receipt.get("new_called_chapters") != [13, 19]
            or receipt.get("new_attempted_chapters") != [13, 19]
            or receipt.get("evidence_quote_policy")
            != (
                pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
                if formal_retry08
                else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
                if formal_retry06
                else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
            )
            or receipt.get("minimum_quote_nonspace_chars")
            != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
            or receipt.get("reused_source_usage_imported") is not False
            or receipt.get("reused_source_network_attempt_imported") is not False
            or receipt.get("new_call_usage")
            != _inspector_usage_for_chapters(root, [13, 19])
            or (
                formal_retry07
                and receipt.get("punctuation_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
            )
            or (
                formal_retry08
                and receipt.get("punctuation_unit_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
            )
            or (
                formal_retry08
                and set((receipt.get("raw_rebuild_receipts") or {}))
                != {"13", "19"}
            )
            or rebuilt_batch_invocations != 2
            or rebuilt_logical_calls != 2
        ):
            raise ZBatchError(
                "main retry06／retry07／retry08复用章／新调章／成本分账错误"
            )
    if formal_program_quote and phase == "final":
        expected_new_chapters = [
            int(row["chapter"])
            for row in request_preflight.get("rows", [])
            if isinstance(row, dict) and int(row.get("api_item_count") or 0) > 0
        ]
        expected_policy = (
            pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
            if formal_punctuation_unit
            else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
            if formal_retry06
            else pipeline_inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
        )
        if (
            receipt.get("reused_chapters") != []
            or receipt.get("new_called_chapters") != expected_new_chapters
            or receipt.get("new_attempted_chapters") != expected_new_chapters
            or receipt.get("evidence_quote_policy") != expected_policy
            or receipt.get("minimum_quote_nonspace_chars")
            != RETRY06_MINIMUM_QUOTE_NONSPACE_CHARS
            or receipt.get("reused_source_usage_imported") is not False
            or receipt.get("reused_source_network_attempt_imported") is not False
            or receipt.get("new_call_usage")
            != _inspector_usage_for_chapters(root, expected_new_chapters)
            or rebuilt_batch_invocations != len(expected_new_chapters)
            or rebuilt_logical_calls != len(expected_new_chapters)
            or (
                formal_retry07
                and receipt.get("punctuation_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
            )
            or (
                formal_punctuation_unit
                and receipt.get("punctuation_unit_equivalence_sha256")
                != pipeline_inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
            )
            or (
                formal_punctuation_unit
                and set((receipt.get("raw_rebuild_receipts") or {}))
                != {str(chapter) for chapter in expected_new_chapters}
            )
        ):
            raise ZBatchError(
                "final retry06／retry07／retry08全新章调用／策略／成本分账错误"
            )
        if formal_retry13:
            expected_transport = {
                "contract_version": (
                    _Retry13InspectorTransportSession.CONTRACT_VERSION
                ),
                "retry_only_http_429": True,
                "max_429_retries_per_request": 2,
                "max_429_per_run": 5,
                "retry_delays_seconds": [5, 10],
                "retry_after_hard_stop_over_seconds": 300,
                "same_chapter_gap_seconds": 10,
                "cross_chapter_gap_seconds": 30,
                "immutable_checkpoint_files_per_logical_request": 5,
            }
            total_429 = 0
            for index, chapter in enumerate(expected_new_chapters):
                rows = z68.read_jsonl(
                    root / f"ch{chapter:04d}/run/call_attempts.jsonl"
                )
                total_429 += sum(
                    1 for row in rows if row.get("http_status") == 429
                )
                first = rows[0] if rows else {}
                required_gap = 0.0 if index == 0 else 30.0
                if (
                    float(first.get("pre_request_spacing_planned_seconds") or 0.0)
                    < required_gap
                    or float(first.get("pre_request_spacing_seconds") or 0.0)
                    < required_gap
                ):
                    raise ZBatchError("retry13检查员章间间隔短于冻结30秒")
            if (
                receipt.get("retry13_inspector_transport") != expected_transport
                or total_429 >= 5
            ):
                raise ZBatchError("retry13检查员运输合同或整轮429止损账错误")
    if (
        len(ids) != len(set(ids))
        or set(ids) != expected_ids
        or rebuilt_routes != routes
        or receipt.get("event_count") != len(expected_ids)
        or receipt.get("forced_strong_count") != len(forced_ids)
        or receipt.get("batch_invocations") != rebuilt_batch_invocations
        or receipt.get("logical_model_calls") != rebuilt_logical_calls
        or isinstance(receipt_network_attempts, bool)
        or not isinstance(receipt_network_attempts, int)
        or receipt_network_attempts != _inspector_network_attempts(root)
        or not 0 <= receipt_network_attempts <= MAX_INSPECTOR_LOGICAL_CALLS * 3
        or rebuilt_batch_invocations > MAX_INSPECTOR_LOGICAL_CALLS
        or rebuilt_logical_calls > MAX_INSPECTOR_LOGICAL_CALLS
    ):
        raise ZBatchError(f"{phase}检查员总票无法由逐章子票机械重建")
    return receipt


def reuse_retry08_inspector_evidence(
    run_dir: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """零调用引用 retry08 已验收检查员工件，不复制运输账或响应。"""

    if run_dir.name != APPROVED_CAPACITY_OVERRIDE_TARGET_NAME:
        raise ZBatchError("retry08检查员复用票只准写入已拍retry09目录")
    if (run_dir / RETRY08_INSPECTOR_REUSE_RECEIPT).exists():
        raise ZBatchError("retry08检查员复用票已存在，拒绝覆盖")
    verify_main(run_dir, allow_test_run_dir=allow_test_run_dir)
    _verify_review_build_inputs(run_dir, phase="main")

    source = _retry08_run_dir()
    source_paths = {
        "semantic_hard_stop": source / "review/semantic_pre_retry_hard_stop.json",
        "combined_routing": source / "review/inspector/combined_routing.json",
        "chapter13_raw_rebuild": (
            source / "review/inspector/ch0013/run/raw_rebuild_receipt.json"
        ),
        "chapter19_raw_rebuild": (
            source / "review/inspector/ch0019/run/raw_rebuild_receipt.json"
        ),
        "program_risks": source / "review/program_risks.json",
    }
    for key, path in source_paths.items():
        expected_sha = RETRY08_FROZEN_REVIEW_SHA256[key]
        if not path.is_file() or sha256_file(path) != expected_sha:
            raise ZBatchError(f"retry08已验收检查员来源漂移：{key}")
    expected_tree = {
        "files": 43,
        "bytes": 3974177,
        "sha256": "188d2f254713bbd357bc95a677c5e2fce51d219f2978bb99f50ce7f1bc80e409",
    }
    if z68.tree_fingerprint(source / "review/inspector") != expected_tree:
        raise ZBatchError("retry08检查员冻结树漂移")

    combined = read_json(source_paths["combined_routing"])
    hard_stop = read_json(source_paths["semantic_hard_stop"])
    if (
        combined.get("status") != "routing_complete_not_final_truth"
        or combined.get("event_set_sha256")
        != {str(key): value for key, value in APPROVED_COMPLETED_EVENT_SHA256.items()}
        or combined.get("routes_sha256")
        != "aa0d186444611ab25d1b968ec4f347b5cd045d021d46e8cd9006e14cbdb55809"
        or combined.get("reused_chapters") != [3]
        or combined.get("new_called_chapters") != [13, 19]
        or combined.get("logical_model_calls") != 2
        or combined.get("network_attempts") != 2
        or hard_stop.get("status")
        != "hard_stop_before_retry_plan_capacity_exceeded"
    ):
        raise ZBatchError("retry08检查员总票或权威硬停票语义漂移")
    for chapter, key in ((13, "chapter13_raw_rebuild"), (19, "chapter19_raw_rebuild")):
        raw_receipt = read_json(source_paths[key])
        if raw_receipt.get("status") != "pass_rebuilt_from_raw_response_and_unique_usage":
            raise ZBatchError(f"retry08第{chapter}章原始响应/usage重建票失效")

    target_event_sha = {
        str(chapter): sha256_file(_event_file(run_dir / "main", chapter))
        for chapter in TARGET_CHAPTERS
    }
    if target_event_sha != combined["event_set_sha256"]:
        raise ZBatchError("retry09事件集不等于retry08已验收检查员输入")
    target_risks = run_dir / "review/program_risks.json"
    if target_risks.read_bytes() != source_paths["program_risks"].read_bytes():
        raise ZBatchError("retry09程序风险表不等于retry08冻结件")
    batch_sha = {}
    for chapter in TARGET_CHAPTERS:
        target_batch = run_dir / f"review/inspector_batches/ch{chapter:04d}.json"
        source_batch = source / f"review/inspector_batches/ch{chapter:04d}.json"
        if target_batch.read_bytes() != source_batch.read_bytes():
            raise ZBatchError(f"retry09第{chapter}章检查批不等于retry08冻结件")
        batch_sha[str(chapter)] = sha256_file(target_batch)
    if (run_dir / "review/inspector").exists():
        raise ZBatchError("retry09复用前意外出现本轮检查员调用目录")

    receipt = {
        "schema_version": "z83-retry09-inspector-evidence-reuse-v1",
        "status": "pass_zero_call_reference_only_not_final_truth",
        "run_id": run_dir.name,
        "source_run_id": source.name,
        "event_set_sha256": target_event_sha,
        "inspector_batch_sha256": batch_sha,
        "source_artifacts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": RETRY08_FROZEN_REVIEW_SHA256[key],
            }
            for key, path in source_paths.items()
        },
        "source_inspector_tree": expected_tree,
        "source_routes_sha256": combined["routes_sha256"],
        "source_combined_routing_file_sha256": RETRY08_FROZEN_REVIEW_SHA256[
            "combined_routing"
        ],
        "model_api_calls": 0,
        "network_attempts": 0,
        "reused_chapters": [3, 13, 19],
        "new_called_chapters": [],
        "source_usage_imported": False,
        "source_network_attempts_imported": False,
        "source_requests_or_responses_copied": False,
        "final_truth": False,
    }
    write_json_atomic(run_dir / RETRY08_INSPECTOR_REUSE_RECEIPT, receipt)
    master = read_json(run_dir / "run_manifest.json")
    master["review"] = "retry08_inspector_evidence_reused_awaiting_full_adjudication"
    master["retry08_inspector_reuse"] = {
        "path": RETRY08_INSPECTOR_REUSE_RECEIPT.as_posix(),
        "sha256": sha256_file(run_dir / RETRY08_INSPECTOR_REUSE_RECEIPT),
        "model_api_calls": 0,
    }
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def _assert_retry_sources_available(
    event_ids: Iterable[str],
    lineage: Mapping[str, Mapping[str, Any]],
) -> None:
    requested = set(event_ids)
    unknown = sorted(requested - set(lineage))
    if unknown:
        raise ZBatchError(f"重写候选没有稳定血缘：{unknown}")
    exhausted = sorted(
        event_id
        for event_id in requested
        if lineage[event_id]["retry_count"] >= MAX_TARGETED_RETRIES_PER_EVENT
    )
    if exhausted:
        raise ZBatchError(
            f"这些当前事件所属稳定源已经重写过，达到每源事件1次上限：{exhausted}"
        )


def _collect_retry_reason_codes(
    run_dir: Path,
    validated: Mapping[str, Any],
) -> dict[str, set[str]]:
    """聚合逐条人工判词；这里只定原因，不在这里放宽或裁剪容量。"""

    reasons_by_event: dict[str, set[str]] = defaultdict(set)
    for event_id, row in validated["anchor_rows"].items():
        if row["verdict"] == "invalid":
            reasons_by_event[event_id].add("SEMANTIC_ANCHOR_UNSUPPORTED")
    for record_id in validated["degraded_record_ids"]:
        row = validated["current_rows"][record_id]
        if not row["candidate_event_ids"]:
            raise ZBatchError(f"{record_id}未观察且无现存坏条可重写，硬停")
        for event_id in row["candidate_event_ids"]:
            reasons_by_event[event_id].add("OLD25_COMPLETENESS_DEGRADED")
    risk_source = {
        row["risk_id"]: row
        for row in read_json(run_dir / "review/program_risks.json")["rows"]
    }
    risk_code_map = {
        "conclusion_compression": "CONCLUSION_COMPONENTS_COMPRESSED",
        "instruction_compression": "INSTRUCTION_COMPONENTS_COMPRESSED",
        "multi_fact": "MULTI_FACT_COMPRESSED",
        "cross_subject": "MULTI_FACT_COMPRESSED",
    }
    for risk_id, row in validated["risk_rows"].items():
        if row["verdict"] != "retry_required":
            continue
        event_id = str(row["event_id"])
        mapped = 0
        for code in risk_source[risk_id]["risk_codes"]:
            if code in risk_code_map:
                reasons_by_event[event_id].add(risk_code_map[code])
                mapped += 1
        if mapped == 0 and event_id not in reasons_by_event:
            raise ZBatchError(f"{risk_id}判定须重写但没有授权的封闭原因码")
    return reasons_by_event


def record_retry09_capacity_hard_stop(
    run_dir: Path,
    adjudication_path: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """完整判词超过本轮总额度时，只落硬停票，不生成计划或调用。"""

    if run_dir.name != APPROVED_CAPACITY_OVERRIDE_TARGET_NAME:
        raise ZBatchError("续令⑦容量硬停票只准写入已拍retry09目录")
    stop_path = run_dir / "review/semantic_pre_retry_hard_stop.json"
    if stop_path.exists():
        raise ZBatchError("retry09容量硬停票已存在，拒绝覆盖")
    if (run_dir / "repair/retry_plan.json").exists():
        raise ZBatchError("容量审计前已出现重试计划，拒绝补写硬停票")

    verify_main(run_dir, allow_test_run_dir=allow_test_run_dir)
    reuse_path = run_dir / RETRY08_INSPECTOR_REUSE_RECEIPT
    if not reuse_path.is_file():
        raise ZBatchError("retry09缺retry08检查员零调用复用票")
    reuse = read_json(reuse_path)
    master = read_json(run_dir / "run_manifest.json")
    if (
        reuse.get("status") != "pass_zero_call_reference_only_not_final_truth"
        or reuse.get("model_api_calls") != 0
        or reuse.get("network_attempts") != 0
        or reuse.get("reused_chapters") != [3, 13, 19]
        or reuse.get("new_called_chapters") != []
        or reuse.get("source_usage_imported") is not False
        or reuse.get("source_network_attempts_imported") is not False
        or master.get("retry08_inspector_reuse", {}).get("sha256")
        != sha256_file(reuse_path)
        or (run_dir / "review/inspector").exists()
    ):
        raise ZBatchError("retry08检查员零调用复用票不完整或夹带本轮调用")
    for row in reuse.get("source_artifacts", {}).values():
        source_path = ROOT / str(row.get("path") or "")
        if not source_path.is_file() or sha256_file(source_path) != row.get("sha256"):
            raise ZBatchError("retry08检查员复用来源在容量审计前漂移")

    doc = read_json(adjudication_path)
    if not isinstance(doc, dict) or sum(
        len(doc.get(key) or [])
        for key in ("anchor_rows", "current_rows", "gold_rows", "risk_rows")
    ) != 246:
        raise ZBatchError("retry09完整语义判词必须恰好覆盖246行")
    validated = validate_adjudication(run_dir, adjudication_path, phase="main")
    reasons_by_event = _collect_retry_reason_codes(run_dir, validated)
    lineage_receipt = _validate_main_lineage(run_dir)
    lineage = lineage_receipt["rows"]

    chapter3_ids = {
        event_id for event_id in reasons_by_event if int(event_id[4:8]) == 3
    }
    if chapter3_ids != set(RETRY09_CHAPTER3_OVERRIDE):
        raise ZBatchError(
            "retry09第3章只能使用已拍4条特批；第5条不得追加，也不得漏掉已拍条目"
        )
    for event_id, expected in RETRY09_CHAPTER3_OVERRIDE.items():
        if (
            canonical_sha(validated["events"][event_id])
            != expected["current_event_sha256"]
            or lineage[event_id]["source_identity_sha256"]
            != expected["source_identity_sha256"]
        ):
            raise ZBatchError(f"{event_id}不等于续令⑦点名的稳定源事件")

    other_ids = sorted(
        event_id for event_id in reasons_by_event if int(event_id[4:8]) in {13, 19}
    )
    if len(other_ids) <= 2:
        raise ZBatchError("第13／19章正式预审重写需求未超过余额2，不应登记容量硬停")
    if len(reasons_by_event) <= MAX_TARGETED_RETRIES_TOTAL:
        raise ZBatchError("整轮重写源事件未超过6，不应登记容量硬停")

    event_rows = []
    for event_id in sorted(reasons_by_event):
        event = validated["events"][event_id]
        event_rows.append(
            {
                "chapter": int(event_id[4:8]),
                "event_id": event_id,
                "current_event_sha256": canonical_sha(event),
                "source_event_id": lineage[event_id]["source_event_id"],
                "source_event_sha256": lineage[event_id]["source_event_sha256"],
                "source_identity_sha256": lineage[event_id]["source_identity_sha256"],
                "anchors": list(event.get("anchors") or []),
                "reason_codes": sorted(reasons_by_event[event_id]),
            }
        )
    by_chapter = Counter(row["chapter"] for row in event_rows)
    main_metrics = read_json(run_dir / "main/01_extract/metrics.json")
    if (
        main_metrics.get("network_attempts_this_run") != 0
        or main_metrics.get("targeted_retry_logical_calls") != 0
    ):
        raise ZBatchError("retry09容量审计前出现本轮主样或定点重写调用")

    receipt = {
        "schema_version": "z83-retry09-semantic-capacity-hard-stop-v1",
        "task_id": "Z83-retry09-chapter3-four-item-override-and-closeout",
        "status": "hard_stop_before_retry_plan_total_capacity_exceeded",
        "execution_status": "compliant_stop_no_result_selection",
        "quality_status": "not_concluded_before_targeted_rewrite_and_final_scoring",
        "run_id": run_dir.name,
        "stopped_at": z68.now_iso(),
        "authority": {
            "kind": "notion_queue_work_order",
            "step": "第83道续令⑦",
            "authority_time": "2026-07-22T12:36:00+08:00",
            "queue_url": "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc",
        },
        "completed_before_stop": {
            "full_semantic_adjudication": {
                "row_count": 246,
                "path": adjudication_path.relative_to(run_dir).as_posix(),
                "sha256": validated["source_sha256"],
                "reviewer": validated["reviewer"],
                "reviewed_at": validated["reviewed_at"],
            },
            "main_samples": {
                "source": "retry03唯一有效三章样张",
                "new_model_calls": 0,
                "event_set_sha256": validated["event_set_sha256"],
            },
            "inspector_evidence": {
                "source": "retry08已验收检查员工件，只作final_truth=false观察依据",
                "new_model_calls": 0,
                "network_attempts": 0,
                "reuse_receipt": RETRY08_INSPECTOR_REUSE_RECEIPT.as_posix(),
                "reuse_receipt_sha256": sha256_file(reuse_path),
            },
        },
        "capacity_contract": {
            "per_event": 1,
            "default_per_chapter": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "chapter3_one_time_override": 4,
            "chapter3_approved_event_ids": sorted(RETRY09_CHAPTER3_OVERRIDE),
            "total": MAX_TARGETED_RETRIES_TOTAL,
            "remaining_after_chapter3": 2,
            "chapter13_19_required": len(other_ids),
            "capacity_expression": f"4 + {len(other_ids)} = {len(reasons_by_event)} > 6",
        },
        "hard_stop_trigger": {
            "confirmed_distinct_source_events_requiring_retry": len(event_rows),
            "by_chapter": {str(chapter): by_chapter[chapter] for chapter in TARGET_CHAPTERS},
            "chapter13_19_event_ids": other_ids,
            "events": event_rows,
        },
        "stop_actions": {
            "full_semantic_adjudication_completed": True,
            "retry_plan_created": False,
            "targeted_rewrite_calls": 0,
            "final_review_started": False,
            "four_gate_scorecard_created": False,
            "api_calls_after_capacity_trigger": 0,
            "selected_subset_to_fit_budget": False,
            "retry_limit_expanded_beyond_authority": False,
            "source_artifacts_rewritten": False,
        },
        "quality_boundary": {
            "mechanical_three_gates": "passed_in_reused_retry08_artifacts",
            "old25_non_regression_gate": "not_scored_after_rewrite",
            "chapter3_gold_gate": "not_scored_after_rewrite",
            "semantic_anchor_zero_invalid_gate": "not_scored_after_rewrite",
            "overall_candidate_quality": "not_concluded",
        },
        "next_action": "等待CZ处置整轮6条额度不足；retry09不得生成计划、挑条、扩额或继续API调用。",
    }
    write_json_atomic(stop_path, receipt)
    master["status"] = receipt["status"]
    master["review"] = receipt["status"]
    master["semantic_pre_retry_hard_stop"] = {
        "path": stop_path.relative_to(run_dir).as_posix(),
        "sha256": sha256_file(stop_path),
        "retry_plan_created": False,
        "targeted_rewrite_calls": 0,
        "quality_status": receipt["quality_status"],
    }
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def reuse_retry09_adjudication_and_authorized_set(
    run_dir: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """零调用复用 retry09 的246行判词，并锁死获批的13个稳定源。"""

    if not _formal_thirteen_retry_target(run_dir):
        raise ZBatchError("13条判词复用票只准写入已拍retry10至retry12目录")
    approved_event_ids = _approved_thirteen_event_ids(run_dir)
    target_receipt = run_dir / RETRY09_ADJUDICATION_REUSE_RECEIPT
    target_adjudication = run_dir / "review/adjudication_reused_from_retry09.json"
    if target_receipt.exists() or target_adjudication.exists():
        raise ZBatchError("retry09判词复用件已存在，拒绝覆盖")
    if (run_dir / "repair/retry_plan.json").exists():
        raise ZBatchError("retry09判词复用前已出现重试计划")

    verify_main(run_dir, allow_test_run_dir=allow_test_run_dir)
    if not (run_dir / "review/build_receipt.json").is_file():
        raise ZBatchError("13条特批轮须先生成主样复核材料")
    source = _retry09_run_dir()
    source_paths = {
        "adjudication": source / "review/adjudication_completed.json",
        "capacity_hard_stop": source / "review/semantic_pre_retry_hard_stop.json",
        "inspector_reuse": source / RETRY08_INSPECTOR_REUSE_RECEIPT,
        "run_manifest": source / "run_manifest.json",
    }
    expected_sha = {
        "adjudication": RETRY09_ADJUDICATION_SHA256,
        "capacity_hard_stop": RETRY09_CAPACITY_HARD_STOP_SHA256,
        "inspector_reuse": RETRY09_INSPECTOR_REUSE_SHA256,
        "run_manifest": RETRY09_RUN_MANIFEST_SHA256,
    }
    for key, path in source_paths.items():
        if not path.is_file() or sha256_file(path) != expected_sha[key]:
            raise ZBatchError(f"retry09封存来源漂移：{key}")

    source_validated = validate_adjudication(
        source, source_paths["adjudication"], phase="main"
    )
    if sum(
        len(source_validated[key])
        for key in ("anchor_rows", "current_rows", "gold_rows", "risk_rows")
    ) != 246:
        raise ZBatchError("retry09复用判词不是246行")
    target_event_sha = {
        str(chapter): sha256_file(_event_file(run_dir / "main", chapter))
        for chapter in TARGET_CHAPTERS
    }
    if target_event_sha != source_validated["event_set_sha256"]:
        raise ZBatchError("13条特批轮主事件集不等于retry09已审事件集")

    hard_stop = read_json(source_paths["capacity_hard_stop"])
    source_rows = hard_stop.get("hard_stop_trigger", {}).get("events")
    if not isinstance(source_rows, list):
        raise ZBatchError("retry09容量硬停票缺13条权威清单")
    source_ids = tuple(str(row.get("event_id") or "") for row in source_rows)
    if (
        len(source_ids) != len(set(source_ids))
        or set(source_ids) != set(approved_event_ids)
    ):
        raise ZBatchError("retry09权威清单不等于本轮点名13条")
    if (
        run_dir.name == APPROVED_THIRTEEN_RETRY_TARGET_NAME
        and source_ids != RETRY10_APPROVED_EVENT_IDS
    ):
        raise ZBatchError("retry10权威清单顺序漂移")
    by_chapter = Counter(int(row["chapter"]) for row in source_rows)
    if dict(by_chapter) != RETRY10_EFFECTIVE_PER_CHAPTER:
        raise ZBatchError("retry09权威清单章分布不等于4／3／6")

    lineage = _validate_main_lineage(run_dir)["rows"]
    current_events = source_validated["events"]
    for row in source_rows:
        event_id = str(row["event_id"])
        if (
            canonical_sha(current_events[event_id]) != row["current_event_sha256"]
            or lineage[event_id]["source_event_id"] != row["source_event_id"]
            or lineage[event_id]["source_event_sha256"]
            != row["source_event_sha256"]
            or lineage[event_id]["source_identity_sha256"]
            != row["source_identity_sha256"]
            or sorted(_collect_retry_reason_codes(source, source_validated)[event_id])
            != row["reason_codes"]
        ):
            raise ZBatchError(f"{event_id}不等于retry09已核实稳定源")

    derived = read_json(source_paths["adjudication"])
    before = copy.deepcopy(derived)
    derived["run_id"] = run_dir.name
    differences = _json_differences(before, derived)
    if differences != [
        {
            "path": "$.run_id",
            "before": source.name,
            "after": run_dir.name,
        }
    ]:
        raise ZBatchError("retry09判词机械实例化不止替换run_id")
    write_json_atomic(target_adjudication, derived)
    validate_adjudication(run_dir, target_adjudication, phase="main")

    main_metrics = read_json(run_dir / "main/01_extract/metrics.json")
    if (
        main_metrics.get("network_attempts_this_run") != 0
        or main_metrics.get("targeted_retry_logical_calls") != 0
        or (run_dir / "review/inspector").exists()
    ):
        raise ZBatchError("13条特批轮零调用复用阶段夹带本轮调用")
    reuse_schema = {
        APPROVED_THIRTEEN_RETRY_TARGET_NAME: "z83-retry10-retry09-adjudication-reuse-v1",
        APPROVED_COUNT_CONTRACT_TARGET_NAME: "z83-retry11-retry09-adjudication-reuse-v1",
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME: "z83-retry12-retry09-adjudication-reuse-v1",
    }[run_dir.name]
    receipt = {
        "schema_version": reuse_schema,
        "status": _retry09_reuse_status(run_dir),
        "run_id": run_dir.name,
        "source_run_id": source.name,
        "source_artifacts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected_sha[key],
            }
            for key, path in source_paths.items()
        },
        "source_adjudication_row_count": 246,
        "source_adjudication_sha256": RETRY09_ADJUDICATION_SHA256,
        "derived_adjudication_path": target_adjudication.relative_to(run_dir).as_posix(),
        "derived_adjudication_sha256": sha256_file(target_adjudication),
        "mechanical_instance_differences": differences,
        "approved_event_ids": list(approved_event_ids),
        "approved_event_rows_sha256": canonical_sha(source_rows),
        "effective_one_time_capacity": {
            "per_event": 1,
            "per_chapter": {str(key): value for key, value in RETRY10_EFFECTIVE_PER_CHAPTER.items()},
            "total": RETRY10_EFFECTIVE_TOTAL,
            "fourteenth_event_allowed": False,
        },
        "long_term_default_capacity_unchanged": {
            "per_event": MAX_TARGETED_RETRIES_PER_EVENT,
            "per_chapter": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "total": MAX_TARGETED_RETRIES_TOTAL,
        },
        "semantic_pre_review_redone": False,
        "model_api_calls": 0,
        "network_attempts": 0,
        "final_truth": True,
    }
    write_json_atomic(target_receipt, receipt)
    master = read_json(run_dir / "run_manifest.json")
    master["review"] = {
        APPROVED_THIRTEEN_RETRY_TARGET_NAME: "retry09_adjudication_reused_retry10_plan_ready",
        APPROVED_COUNT_CONTRACT_TARGET_NAME: "retry09_adjudication_reused_retry11_probe_first_plan_ready",
        APPROVED_ANCHOR_FIELD_STRIP_TARGET_NAME: "retry09_adjudication_reused_retry12_probe_first_plan_ready",
    }[run_dir.name]
    master["retry09_adjudication_reuse"] = {
        "path": RETRY09_ADJUDICATION_REUSE_RECEIPT.as_posix(),
        "sha256": sha256_file(target_receipt),
        "model_api_calls": 0,
    }
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def _retry_limits(run_dir: Path, existing_retry_count: int) -> dict[str, Any]:
    if _formal_thirteen_retry_target(run_dir):
        return {
            "per_event": MAX_TARGETED_RETRIES_PER_EVENT,
            "default_per_chapter": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "default_total": MAX_TARGETED_RETRIES_TOTAL,
            "effective_one_time_per_chapter": {
                str(key): value for key, value in RETRY10_EFFECTIVE_PER_CHAPTER.items()
            },
            "effective_one_time_total": RETRY10_EFFECTIVE_TOTAL,
            "existing_mechanical_retries": existing_retry_count,
            "fourteenth_event_allowed": False,
        }
    return {
        "per_event": MAX_TARGETED_RETRIES_PER_EVENT,
        "per_chapter": MAX_TARGETED_RETRIES_PER_CHAPTER,
        "total": MAX_TARGETED_RETRIES_TOTAL,
        "existing_mechanical_retries": existing_retry_count,
    }


def _derive_retry_tasks(
    run_dir: Path,
    validated: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    reasons_by_event = _collect_retry_reason_codes(run_dir, validated)
    lineage_receipt = _validate_main_lineage(run_dir)
    main_lineage = lineage_receipt["rows"]
    previous_ledger = z68.read_jsonl(run_dir / "main/targeted_retry_ledger.jsonl")
    _assert_retry_sources_available(reasons_by_event, main_lineage)
    per_chapter: Counter[int] = Counter()
    for event_id in reasons_by_event:
        per_chapter[int(event_id[4:8])] += 1
    previous_per_chapter: Counter[int] = Counter(
        int(row["chapter"]) for row in previous_ledger
    )
    if _formal_thirteen_retry_target(run_dir):
        reuse_path = run_dir / RETRY09_ADJUDICATION_REUSE_RECEIPT
        if not reuse_path.is_file():
            raise ZBatchError("13条特批轮缺retry09判词与清单复用票")
        reuse = read_json(reuse_path)
        approved_event_ids = _approved_thirteen_event_ids(run_dir)
        if (
            reuse.get("status") != _retry09_reuse_status(run_dir)
            or reuse.get("approved_event_ids") != list(approved_event_ids)
            or reuse.get("model_api_calls") != 0
            or reuse.get("network_attempts") != 0
            or set(reasons_by_event) != set(approved_event_ids)
            or {chapter: per_chapter[chapter] for chapter in TARGET_CHAPTERS}
            != RETRY10_EFFECTIVE_PER_CHAPTER
            or previous_ledger
        ):
            raise ZBatchError("本轮重写候选不等于已拍13条封闭全集")
    else:
        if any(
            previous_per_chapter[ch] + per_chapter[ch]
            > MAX_TARGETED_RETRIES_PER_CHAPTER
            for ch in TARGET_CHAPTERS
        ):
            raise ZBatchError("候选坏条超过每章3条，发送前硬停，不挑条修")
        if len(previous_ledger) + len(reasons_by_event) > MAX_TARGETED_RETRIES_TOTAL:
            raise ZBatchError("候选坏条超过全轮6条，发送前硬停，不挑条修")
    event_map = validated["events"]
    tasks = []
    ordered_event_ids = (
        _approved_thirteen_event_ids(run_dir)
        if _formal_thirteen_retry_target(run_dir)
        else tuple(sorted(reasons_by_event))
    )
    for event_id in ordered_event_ids:
        codes = sorted(reasons_by_event[event_id])
        if any(code not in RETRY_REASON_TEXT for code in codes):
            raise ZBatchError(f"重试原因不在封闭枚举：{codes}")
        task = {
            "chapter": int(event_id[4:8]),
            "event_id": event_id,
            "event_sha256": canonical_sha(event_map[event_id]),
            "source_event_id": main_lineage[event_id]["source_event_id"],
            "source_event_sha256": main_lineage[event_id]["source_event_sha256"],
            "source_identity_sha256": main_lineage[event_id][
                "source_identity_sha256"
            ],
            "source_retry_count_before": main_lineage[event_id]["retry_count"],
            "reason_codes": codes,
            "allow_split": any(
                code
                in {
                    "CONCLUSION_COMPONENTS_COMPRESSED",
                    "INSTRUCTION_COMPONENTS_COMPRESSED",
                    "MULTI_FACT_COMPRESSED",
                }
                for code in codes
            ),
        }
        if _uses_retry11_request_contract(run_dir):
            task.update(
                {
                    "allow_split": False,
                    "replacement_count_required": 1,
                    "model_visible_permission_actions": [
                        RETRY11_VISIBLE_PERMISSION_TEXT[code] for code in codes
                    ],
                }
            )
        tasks.append(task)
    return tasks, len(previous_ledger)


def plan_retries(
    run_dir: Path,
    adjudication_path: Path,
) -> dict[str, Any]:
    if (run_dir / "repair/retry_plan.json").exists():
        raise ZBatchError("重试计划已存在，拒绝改判覆盖")
    require_inspector_complete(run_dir, phase="main")
    validated = validate_adjudication(run_dir, adjudication_path, phase="main")
    tasks, existing_retry_count = _derive_retry_tasks(run_dir, validated)
    visible_reason_text = (
        RETRY11_VISIBLE_PERMISSION_TEXT
        if _uses_retry11_request_contract(run_dir)
        else RETRY_REASON_TEXT
    )
    plan = {
        "schema_version": "z83-targeted-retry-plan-v1",
        "status": "ready" if tasks else "no_retry_needed",
        "source_adjudication": {
            "path": adjudication_path.as_posix(),
            "sha256": validated["source_sha256"],
        },
        "source_event_set_sha256": validated["event_set_sha256"],
        "limits": _retry_limits(run_dir, existing_retry_count),
        "tasks": tasks,
        "model_visible_reason_text": visible_reason_text,
        "free_text_adjudication_sent_to_model": False,
        "gold_or_case_ids_sent_to_model": False,
    }
    if _uses_retry11_request_contract(run_dir):
        plan["replacement_count_contract"] = {
            "required": 1,
            "allow_split": False,
            "allow_merge": False,
            "allow_add_event": False,
            "allow_delete_event": False,
            "model_visible_text": RETRY11_EXACT_COUNT_CONTRACT,
        }
    write_json(run_dir / "repair/retry_plan.json", plan)
    return plan


def _validate_retry_plan(run_dir: Path, plan_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    if (
        not isinstance(plan, dict)
        or plan.get("schema_version") != "z83-targeted-retry-plan-v1"
    ):
        raise ZBatchError("缺合格重试计划")
    source = plan.get("source_adjudication")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        raise ZBatchError("重试计划缺来源判词")
    source_path = Path(source["path"]).resolve()
    review_root = (run_dir / "review").resolve()
    if not source_path.is_relative_to(review_root) or not source_path.is_file():
        raise ZBatchError("重试计划来源判词不在本轮review目录")
    if sha256_file(source_path) != source.get("sha256"):
        raise ZBatchError("重试计划来源判词SHA漂移")
    require_inspector_complete(run_dir, phase="main")
    validated = validate_adjudication(run_dir, source_path, phase="main")
    expected_tasks, existing_retry_count = _derive_retry_tasks(run_dir, validated)
    expected_limits = _retry_limits(run_dir, existing_retry_count)
    expected_status = "ready" if expected_tasks else "no_retry_needed"
    expected_visible_reason_text = (
        RETRY11_VISIBLE_PERMISSION_TEXT
        if _uses_retry11_request_contract(run_dir)
        else RETRY_REASON_TEXT
    )
    expected_count_contract = (
        {
            "required": 1,
            "allow_split": False,
            "allow_merge": False,
            "allow_add_event": False,
            "allow_delete_event": False,
            "model_visible_text": RETRY11_EXACT_COUNT_CONTRACT,
        }
        if _uses_retry11_request_contract(run_dir)
        else None
    )
    if (
        plan.get("status") != expected_status
        or plan.get("source_event_set_sha256") != validated["event_set_sha256"]
        or plan.get("limits") != expected_limits
        or plan.get("tasks") != expected_tasks
        or plan.get("model_visible_reason_text") != expected_visible_reason_text
        or plan.get("replacement_count_contract") != expected_count_contract
        or plan.get("free_text_adjudication_sent_to_model") is not False
        or plan.get("gold_or_case_ids_sent_to_model") is not False
    ):
        raise ZBatchError("重试计划与绑定判词、预算或封闭原因码不一致")
    return plan


def _build_semantic_retry_messages(
    *,
    run_dir: Path,
    chapter: int,
    event: Mapping[str, Any],
    reason_codes: Sequence[str],
) -> list[dict[str, str]]:
    if any(code not in RETRY_REASON_TEXT for code in reason_codes):
        raise ZBatchError("重试原因越出封闭枚举")
    retry11_contract = _uses_retry11_request_contract(run_dir)
    violations = [
        (RETRY11_VISIBLE_PERMISSION_TEXT if retry11_contract else RETRY_REASON_TEXT)[
            code
        ]
        for code in reason_codes
    ]
    messages = z77.build_retry_messages(
        chapter=chapter,
        original_event=event,
        violations=violations,
        chapter_text=_chapter_text_path(run_dir, chapter).read_text(encoding="utf-8"),
        catalog=_catalog(run_dir, chapter),
    )
    if retry11_contract:
        split_line = "若原事件含多个可独立判真的事实，拆成多条替换项；否则保留一条。"
        system = messages[0]["content"]
        if system.count(split_line) != 1:
            raise ZBatchError("恰好1条合同轮找不到唯一的旧拆分教学句，拒绝构造请求")
        permission_block = "【本条唯一许可动作】\n" + "\n".join(
            f"- {RETRY11_VISIBLE_PERMISSION_TEXT[code]}" for code in reason_codes
        )
        messages[0]["content"] = system.replace(
            split_line,
            RETRY11_EXACT_COUNT_CONTRACT,
        ) + f"\n{permission_block}"
    hits = forbidden_model_hits(messages)
    if hits:
        raise ZBatchError(f"定点重写请求夹入判分侧材料：{hits}")
    serialized = json.dumps(messages, ensure_ascii=False)
    for code in reason_codes:
        if code in serialized:
            raise ZBatchError("内部原因码不应进入模型可见请求")
    return messages


def _audit_retry10_fifth_count_contract() -> dict[str, Any]:
    """零调用核对 retry10 第5条实发请求有没有把禁拆规则写给模型。"""

    if (
        not RETRY10_FIFTH_REQUEST.is_file()
        or sha256_file(RETRY10_FIFTH_REQUEST) != RETRY10_FIFTH_REQUEST_SHA256
        or not RETRY10_FIFTH_PREPARED_REQUEST.is_file()
        or sha256_file(RETRY10_FIFTH_PREPARED_REQUEST)
        != RETRY10_FIFTH_PREPARED_REQUEST_SHA256
    ):
        raise ZBatchError("retry10第5条请求或预构造件SHA漂移")
    request_record = read_json(RETRY10_FIFTH_REQUEST)
    prepared_body = read_json(RETRY10_FIFTH_PREPARED_REQUEST)
    body = request_record.get("body") if isinstance(request_record, dict) else None
    if body != prepared_body:
        raise ZBatchError("retry10第5条实发body不等于零调用预构造件")
    visible = json.dumps(body.get("messages"), ensure_ascii=False)
    generic_split_line = (
        "若原事件含多个可独立判真的事实，拆成多条替换项；否则保留一条。"
    )
    explicit_exact_one_markers = (
        "必须恰好返回1条",
        "必须恰好包含1条",
        "replacement_events 数组必须恰好包含1条",
    )
    explicit_no_split_markers = ("禁止拆分", "不得拆分")
    receipt = {
        "schema_version": "z83-retry10-fifth-request-count-contract-audit-v1",
        "status": "pass_zero_call_diagnostic",
        "source_request_path": RETRY10_FIFTH_REQUEST.relative_to(ROOT).as_posix(),
        "source_request_sha256": RETRY10_FIFTH_REQUEST_SHA256,
        "source_prepared_request_path": RETRY10_FIFTH_PREPARED_REQUEST.relative_to(
            ROOT
        ).as_posix(),
        "source_prepared_request_sha256": RETRY10_FIFTH_PREPARED_REQUEST_SHA256,
        "sent_body_equals_prepared_body": True,
        "explicit_exactly_one_present": any(
            marker in visible for marker in explicit_exact_one_markers
        ),
        "explicit_no_split_present": any(
            marker in visible for marker in explicit_no_split_markers
        ),
        "generic_conditional_split_guidance_present": generic_split_line in visible,
        "anchor_or_delete_permission_present": (
            "只可补挂当前冻结目录内真实支撑锚，或删去无支撑措辞。" in visible
        ),
        "conclusion": (
            "retry10第5条模型可见文本没有恰好1条或禁止拆分硬合同，"
            "反而保留按事实头条件拆分的通用教学；禁拆只存在于程序收口闸。"
        ),
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    if (
        receipt["explicit_exactly_one_present"]
        or receipt["explicit_no_split_present"]
        or not receipt["generic_conditional_split_guidance_present"]
        or not receipt["anchor_or_delete_permission_present"]
    ):
        raise ZBatchError("retry10第5条模型可见份数合同定性与封存原件不一致")
    return receipt


def _retry12_quote_observation(
    *,
    model_value: Any,
    frozen_quote: str,
) -> dict[str, Any]:
    if not isinstance(model_value, str):
        return {
            "present": True,
            "value_type": type(model_value).__name__,
            "model_quote": model_value,
            "frozen_catalog_quote": frozen_quote,
            "model_quote_sha256": canonical_sha(model_value),
            "frozen_quote_sha256": canonical_sha(frozen_quote),
            "exact_equal": False,
            "relation": "non_string_observation_only",
            "diff_direction": "frozen_to_model",
            "diff_opcodes": [],
            "used_for_validation": False,
        }
    if model_value == frozen_quote:
        relation = "exact"
    elif frozen_quote.startswith(model_value):
        relation = "model_is_prefix_of_frozen"
    elif frozen_quote.endswith(model_value):
        relation = "model_is_suffix_of_frozen"
    elif model_value in frozen_quote:
        relation = "model_is_substring_of_frozen"
    elif frozen_quote in model_value:
        relation = "frozen_is_substring_of_model"
    else:
        relation = "different"
    opcodes = []
    for tag, frozen_start, frozen_end, model_start, model_end in difflib.SequenceMatcher(
        a=frozen_quote,
        b=model_value,
        autojunk=False,
    ).get_opcodes():
        if tag == "equal":
            continue
        opcodes.append(
            {
                "op": tag,
                "frozen_span": [frozen_start, frozen_end],
                "model_span": [model_start, model_end],
                "frozen_text": frozen_quote[frozen_start:frozen_end],
                "model_text": model_value[model_start:model_end],
            }
        )
    return {
        "present": True,
        "value_type": "str",
        "model_quote": model_value,
        "frozen_catalog_quote": frozen_quote,
        "model_quote_sha256": canonical_sha(model_value),
        "frozen_quote_sha256": canonical_sha(frozen_quote),
        "exact_equal": model_value == frozen_quote,
        "relation": relation,
        "diff_direction": "frozen_to_model",
        "diff_opcodes": opcodes,
        "used_for_validation": False,
    }


def _normalize_retry12_anchor_extras(
    *,
    run_dir: Path,
    parsed: Any,
    chapter: int,
    event_id: str,
    case_id: str,
    plan_ordinal: int,
    raw_response_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """只放宽锚叶的多余字段；正式替换件仍交给 z77 严格校验。"""

    if not _formal_anchor_field_strip_target(run_dir):
        raise ZBatchError("锚字段剥离器只准在retry12运行")
    if not isinstance(parsed, dict) or set(parsed) != z77.RETRY_ROOT_KEYS:
        raise ZBatchError("retry12定点重试根字段不等于 replacement_events 合同")
    replacements = parsed.get("replacement_events")
    if not isinstance(replacements, list) or len(replacements) != 1:
        observed = len(replacements) if isinstance(replacements, list) else "non_list"
        raise ZBatchError(f"{event_id}违反常设恰好1条份数合同：observed={observed}")
    replacement = replacements[0]
    if not isinstance(replacement, dict) or set(replacement) != z77.RETRY_EVENT_KEYS:
        raise ZBatchError("retry12替换事件对象字段越权")
    anchors = replacement.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise ZBatchError("retry12替换事件没有非空锚数组")

    catalog_path = run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json"
    catalog_rows = _catalog(run_dir, chapter)
    catalog_map = {
        str(row["anchor_id"]): str(row["quote"])
        for row in catalog_rows
        if isinstance(row, dict) and row.get("anchor_id")
    }
    anchor_ids: list[str] = []
    for anchor_ordinal, anchor in enumerate(anchors, 1):
        if not isinstance(anchor, dict):
            raise ZBatchError(f"retry12替换事件锚{anchor_ordinal}不是对象")
        if "anchor_id" not in anchor:
            raise ZBatchError(f"retry12替换事件锚{anchor_ordinal}缺anchor_id")
        anchor_id = anchor.get("anchor_id")
        if (
            not isinstance(anchor_id, str)
            or z77.ANCHOR_ID_PATTERN.fullmatch(anchor_id) is None
            or anchor_id not in catalog_map
        ):
            raise ZBatchError(
                f"retry12替换事件锚{anchor_ordinal}仍含非法anchor_id：{anchor_id}"
            )
        anchor_ids.append(anchor_id)
    if len(anchor_ids) != len(set(anchor_ids)):
        raise ZBatchError("retry12替换事件anchor_id重复")
    if not raw_response_path.is_file():
        raise ZBatchError("retry12锚字段剥离缺原始响应")

    sanitized = copy.deepcopy(parsed)
    diagnostic_rows: list[dict[str, Any]] = []
    sanitized_anchors = sanitized["replacement_events"][0]["anchors"]
    for anchor_ordinal, (raw_anchor, anchor_id) in enumerate(
        zip(anchors, anchor_ids, strict=True),
        1,
    ):
        extra_names = sorted(set(raw_anchor) - {"anchor_id"})
        sanitized_anchors[anchor_ordinal - 1] = {"anchor_id": anchor_id}
        if not extra_names:
            continue
        stripped_fields = {
            name: copy.deepcopy(raw_anchor[name]) for name in extra_names
        }
        quote_observation = (
            _retry12_quote_observation(
                model_value=stripped_fields["quote"],
                frozen_quote=catalog_map[anchor_id],
            )
            if "quote" in stripped_fields
            else {
                "present": False,
                "used_for_validation": False,
            }
        )
        diagnostic_rows.append(
            {
                "schema_version": "z83-retry12-anchor-extra-field-strip-v1",
                "status": "diagnostic_observation_not_truth",
                "run_id": run_dir.name,
                "case_id": case_id,
                "plan_ordinal": plan_ordinal,
                "chapter": chapter,
                "event_id": event_id,
                "replacement_ordinal": 1,
                "anchor_ordinal": anchor_ordinal,
                "anchor_id": anchor_id,
                "raw_response_path": raw_response_path.relative_to(run_dir).as_posix(),
                "raw_response_sha256": sha256_file(raw_response_path),
                "catalog_path": catalog_path.relative_to(run_dir).as_posix(),
                "catalog_sha256": sha256_file(catalog_path),
                "extra_field_names": extra_names,
                "stripped_fields": stripped_fields,
                "stripped_fields_sha256": canonical_sha(stripped_fields),
                "formal_anchor": {"anchor_id": anchor_id},
                "formal_anchor_sha256": canonical_sha({"anchor_id": anchor_id}),
                "quote_observation": quote_observation,
                "entered_formal_record": False,
                "used_for_validation": False,
                "source_of_formal_quote": "frozen_evidence_catalog_by_anchor_id",
            }
        )
    return sanitized, diagnostic_rows


def preflight_retries(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    """只构造13条定点重写请求，不发网；供固定停点逐条核对。"""

    receipt_path = run_dir / "repair/retry_preflight.json"
    prepared_root = run_dir / "repair/prepared_requests"
    if receipt_path.exists() or prepared_root.exists():
        raise ZBatchError("定点重写预构造件已存在，拒绝覆盖")
    plan_path = run_dir / "repair/retry_plan.json"
    plan = _validate_retry_plan(run_dir, plan_path)
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        raise ZBatchError("定点重写计划tasks格式错误")
    if _formal_thirteen_retry_target(run_dir) and [
        str(row.get("event_id") or "") for row in tasks
    ] != list(_approved_thirteen_event_ids(run_dir)):
        raise ZBatchError("13条特批轮预构造请求不等于获批封闭顺序")
    if (run_dir / "repair/run_claim.json").exists() or (
        run_dir / "repair/run_manifest.json"
    ).exists():
        raise ZBatchError("定点重写预构造前已有发网痕迹")

    bundle = load_bundle(run_dir)
    stage_contract = bundle.stage("targeted_retry")
    source_events = _event_map(run_dir / "main")
    retry10_preflight: dict[str, Any] | None = None
    retry10_rows: dict[str, dict[str, Any]] = {}
    retry10_count_audit: dict[str, Any] | None = None
    retry11_preflight: dict[str, Any] | None = None
    retry11_rows: dict[str, dict[str, Any]] = {}
    if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME:
        audit_path = run_dir / "repair/retry10_fifth_request_count_contract_audit.json"
        if audit_path.exists():
            raise ZBatchError("retry11的retry10份数合同诊断票已存在，拒绝覆盖")
        retry10_count_audit = _audit_retry10_fifth_count_contract()
        write_json_atomic(audit_path, retry10_count_audit)
        if (
            not RETRY10_PREFLIGHT_RECEIPT.is_file()
            or sha256_file(RETRY10_PREFLIGHT_RECEIPT)
            != RETRY10_PREFLIGHT_RECEIPT_SHA256
        ):
            raise ZBatchError("retry10的13份请求预构造票SHA漂移")
        retry10_preflight = read_json(RETRY10_PREFLIGHT_RECEIPT)
        if retry10_preflight.get("event_ids") != list(RETRY10_APPROVED_EVENT_IDS):
            raise ZBatchError("retry10预构造票不再是续令⑧原13条")
        retry10_rows = {
            str(row["event_id"]): row for row in retry10_preflight.get("rows", [])
        }
    elif _formal_anchor_field_strip_target(run_dir):
        if (
            not RETRY11_PREFLIGHT_RECEIPT.is_file()
            or sha256_file(RETRY11_PREFLIGHT_RECEIPT)
            != RETRY11_PREFLIGHT_RECEIPT_SHA256
        ):
            raise ZBatchError("retry11的13份冻结请求预构造票SHA漂移")
        retry11_preflight = read_json(RETRY11_PREFLIGHT_RECEIPT)
        if (
            retry11_preflight.get("status") != "pass_zero_call_requests_frozen"
            or retry11_preflight.get("event_ids")
            != list(RETRY11_APPROVED_EVENT_IDS)
            or retry11_preflight.get("task_count") != RETRY10_EFFECTIVE_TOTAL
            or retry11_preflight.get("model_api_calls") != 0
            or retry11_preflight.get("network_attempts") != 0
        ):
            raise ZBatchError("retry11预构造票不再是获批13份冻结请求")
        retry11_rows = {
            str(row["event_id"]): row for row in retry11_preflight.get("rows", [])
        }
    rows = []
    for task in tasks:
        event_id = str(task["event_id"])
        chapter = int(task["chapter"])
        event = source_events[event_id]
        messages = _build_semantic_retry_messages(
            run_dir=run_dir,
            chapter=chapter,
            event=event,
            reason_codes=task["reason_codes"],
        )
        body = api_transport.build_request_body(
            model=str(bundle.route["model"]),
            messages=messages,
            contract=stage_contract,
        )
        hits = forbidden_model_hits(body)
        if hits:
            raise ZBatchError(f"{event_id}预构造请求夹入判分材料：{hits}")
        single_variable_differences: list[dict[str, Any]] | None = None
        retry11_source_path: Path | None = None
        if _uses_retry11_request_contract(run_dir):
            permissions = task.get("model_visible_permission_actions")
            visible = "\n".join(str(message.get("content") or "") for message in messages)
            old_split_line = (
                "若原事件含多个可独立判真的事实，拆成多条替换项；否则保留一条。"
            )
            if (
                task.get("replacement_count_required") != 1
                or task.get("allow_split") is not False
                or not isinstance(permissions, list)
                or not permissions
                or RETRY11_EXACT_COUNT_CONTRACT not in visible
                or any(str(permission) not in visible for permission in permissions)
                or old_split_line in visible
            ):
                raise ZBatchError(f"{event_id}没有逐字携带常设份数合同与许可动作")
            if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME:
                base_row = retry10_rows.get(event_id)
                base_path = (
                    ROOT
                    / "runs"
                    / APPROVED_THIRTEEN_RETRY_TARGET_NAME
                    / str((base_row or {}).get("prepared_request_path") or "")
                )
                if (
                    not isinstance(base_row, dict)
                    or not base_path.is_file()
                    or sha256_file(base_path)
                    != base_row.get("prepared_request_sha256")
                ):
                    raise ZBatchError(f"{event_id}找不到retry10同事件冻结请求")
                base_body = read_json(base_path)
                single_variable_differences = _json_differences(base_body, body)
                if {
                    str(row["path"]) for row in single_variable_differences
                } != {"$.messages[0].content", "$.messages[1].content"}:
                    raise ZBatchError(
                        f"{event_id}相对retry10不止份数合同与许可动作变化"
                    )
            else:
                base_row = retry11_rows.get(event_id)
                retry11_source_path = (
                    ROOT
                    / "runs"
                    / APPROVED_COUNT_CONTRACT_TARGET_NAME
                    / str((base_row or {}).get("prepared_request_path") or "")
                )
                if (
                    not isinstance(base_row, dict)
                    or not retry11_source_path.is_file()
                    or sha256_file(retry11_source_path)
                    != base_row.get("prepared_request_sha256")
                ):
                    raise ZBatchError(f"{event_id}找不到retry11同事件冻结请求")
                base_body = read_json(retry11_source_path)
                single_variable_differences = _json_differences(base_body, body)
                if single_variable_differences:
                    raise ZBatchError(f"{event_id}模型可见请求相对retry11发生变化")
        case_id = f"z83_repair_ch{chapter:04d}_{event_id.lower()}"
        path = prepared_root / f"{case_id}.json"
        if retry11_source_path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(retry11_source_path, path)
            if sha256_file(path) != sha256_file(retry11_source_path):
                raise ZBatchError(f"{event_id}复制retry11冻结请求后字节漂移")
            body = read_json(path)
        else:
            write_json(path, body)
        row = {
            "chapter": chapter,
            "event_id": event_id,
            "event_sha256": canonical_sha(event),
            "source_identity_sha256": task["source_identity_sha256"],
            "reason_codes": list(task["reason_codes"]),
            "case_id": case_id,
            "prepared_request_path": path.relative_to(run_dir).as_posix(),
            "prepared_request_sha256": sha256_file(path),
            "message_sha256": canonical_sha(messages),
            "forbidden_model_hits": [],
        }
        if _uses_retry11_request_contract(run_dir):
            row.update(
                {
                    "replacement_count_required": 1,
                    "allow_split": False,
                    "model_visible_permission_actions": list(
                        task["model_visible_permission_actions"]
                    ),
                    "count_contract_present": True,
                    "conflicting_split_guidance_present": False,
                }
            )
            if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME:
                row["retry10_single_variable_difference_paths"] = [
                    item["path"] for item in single_variable_differences or []
                ]
            else:
                if retry11_source_path is None:
                    raise ZBatchError(f"{event_id}缺retry11冻结请求来源")
                row.update(
                    {
                        "retry11_prepared_request_path": retry11_source_path.relative_to(
                            ROOT
                        ).as_posix(),
                        "retry11_prepared_request_sha256": sha256_file(
                            retry11_source_path
                        ),
                        "model_visible_body_equals_retry11": True,
                        "retry11_single_variable_difference_paths": [],
                    }
                )
        rows.append(row)
    if len(rows) != len({row["source_identity_sha256"] for row in rows}):
        raise ZBatchError("定点重写预构造出现稳定源重复")
    receipt = {
        "schema_version": "z83-targeted-retry-preflight-v1",
        "status": "pass_zero_call_requests_frozen",
        "run_id": run_dir.name,
        "source_retry_plan_sha256": sha256_file(plan_path),
        "task_count": len(rows),
        "event_ids": [row["event_id"] for row in rows],
        "rows": rows,
        "request_contract": {
            "model": body.get("model") if rows else None,
            "temperature": body.get("temperature") if rows else None,
            "n": body.get("n") if rows else None,
            "max_tokens": body.get("max_tokens") if rows else None,
            "response_format": body.get("response_format") if rows else None,
            "reasoning_effort": body.get("reasoning_effort") if rows else None,
        },
        "free_text_adjudication_sent_to_model": False,
        "gold_or_case_ids_sent_to_model": False,
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    if retry10_count_audit is not None:
        audit_path = run_dir / "repair/retry10_fifth_request_count_contract_audit.json"
        receipt["retry10_fifth_request_count_contract_audit"] = {
            "path": audit_path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(audit_path),
            "explicit_exactly_one_present": False,
            "explicit_no_split_present": False,
            "generic_conditional_split_guidance_present": True,
        }
        receipt["single_variable_against_retry10"] = {
            "only_message_contract_and_permission_text_changed": True,
            "request_parameters_unchanged": True,
            "event_order_change": {
                "moved_event_id": "EV-C0013-06",
                "before_ordinal": 5,
                "after_ordinal": 1,
                "other_twelve_relative_order_unchanged": True,
            },
        }
    if retry11_preflight is not None:
        receipt["source_retry11_preflight"] = {
            "path": RETRY11_PREFLIGHT_RECEIPT.relative_to(ROOT).as_posix(),
            "sha256": RETRY11_PREFLIGHT_RECEIPT_SHA256,
        }
        receipt["single_variable_against_retry11"] = {
            "model_visible_bodies_identical": True,
            "identical_body_count": len(rows),
            "request_parameters_unchanged": True,
            "only_program_anchor_leaf_acceptance_changed": True,
            "retry11_responses_or_transport_rows_reused": False,
        }
    write_json_atomic(receipt_path, receipt)
    master = read_json(run_dir / "run_manifest.json")
    master["repair_preflight"] = {
        "status": receipt["status"],
        "path": receipt_path.relative_to(run_dir).as_posix(),
        "sha256": sha256_file(receipt_path),
        "model_api_calls": 0,
    }
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def run_retries(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    plan_path = run_dir / "repair/retry_plan.json"
    plan = _validate_retry_plan(run_dir, plan_path)
    main_stage = run_dir / "main"
    verify_event_stage(
        run_dir, main_stage, schema_version="z83-main-mechanical-verification-v1"
    )
    main_event_sha = {
        str(chapter): sha256_file(_event_file(main_stage, chapter))
        for chapter in TARGET_CHAPTERS
    }
    if plan.get("source_event_set_sha256") != main_event_sha:
        raise ZBatchError("重试计划未绑定当前主样张")
    repair_dir = run_dir / "repair"
    if (repair_dir / "run_claim.json").exists() or (
        repair_dir / "run_manifest.json"
    ).exists():
        raise ZBatchError("定点重写阶段已有运行痕迹，拒绝复跑")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        raise ZBatchError("重试计划tasks格式错误")
    retry_preflight: dict[str, Any] | None = None
    if _formal_thirteen_retry_target(run_dir):
        retry_preflight_path = run_dir / "repair/retry_preflight.json"
        if not retry_preflight_path.is_file():
            raise ZBatchError("13条特批轮缺零调用定点重写请求预构造票")
        retry_preflight = read_json(retry_preflight_path)
        if (
            retry_preflight.get("status") != "pass_zero_call_requests_frozen"
            or retry_preflight.get("source_retry_plan_sha256")
            != sha256_file(plan_path)
            or retry_preflight.get("event_ids")
            != list(_approved_thirteen_event_ids(run_dir))
            or retry_preflight.get("task_count") != RETRY10_EFFECTIVE_TOTAL
            or retry_preflight.get("model_api_calls") != 0
            or retry_preflight.get("network_attempts") != 0
        ):
            raise ZBatchError("13条特批轮定点重写请求预构造票漂移")
        if _uses_retry11_request_contract(run_dir):
            if any(
                row.get("replacement_count_required") != 1
                or row.get("allow_split") is not False
                or row.get("count_contract_present") is not True
                or row.get("conflicting_split_guidance_present") is not False
                for row in retry_preflight.get("rows", [])
            ):
                raise ZBatchError("预构造票没有钉死常设恰好1条份数合同")
            if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME and (
                retry_preflight.get("single_variable_against_retry10", {}).get(
                    "only_message_contract_and_permission_text_changed"
                )
                is not True
            ):
                raise ZBatchError("retry11预构造票没有钉死相对retry10的单变量")
            if _formal_anchor_field_strip_target(run_dir):
                retry12_single = retry_preflight.get(
                    "single_variable_against_retry11", {}
                )
                if (
                    retry_preflight.get("source_retry11_preflight", {}).get(
                        "sha256"
                    )
                    != RETRY11_PREFLIGHT_RECEIPT_SHA256
                    or retry12_single.get("model_visible_bodies_identical") is not True
                    or retry12_single.get("identical_body_count")
                    != RETRY10_EFFECTIVE_TOTAL
                    or retry12_single.get(
                        "only_program_anchor_leaf_acceptance_changed"
                    )
                    is not True
                    or retry12_single.get("retry11_responses_or_transport_rows_reused")
                    is not False
                    or any(
                        row.get("model_visible_body_equals_retry11") is not True
                        or row.get("retry11_single_variable_difference_paths") != []
                        for row in retry_preflight.get("rows", [])
                    )
                ):
                    raise ZBatchError("retry12预构造票没有钉死模型可见请求零改动")
    if _formal_anchor_field_strip_target(run_dir) and (
        run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
    ).exists():
        raise ZBatchError("retry12发网前已出现锚字段剥离旁账，拒绝复跑")
    if tasks:
        _require_api_key_before_claim()
    claim = _acquire_claim(repair_dir / "run_claim.json", "z83-repair-run-claim-v1")
    source_events = _event_map(main_stage)
    main_lineage = _validate_main_lineage(run_dir)["rows"]
    replacements_by_chapter: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(
        dict
    )
    receipt_by_chapter_index: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    completed_retry_receipts: list[dict[str, Any]] = []
    ledgers: list[dict[str, Any]] = []
    active_event_id: str | None = None
    active_plan_ordinal = 0
    try:
        transport = api_transport.ApiTransport.from_bundle(
            load_bundle(run_dir), run_dir=repair_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for active_plan_ordinal, task in enumerate(tasks, 1):
            if not isinstance(task, dict):
                raise ZBatchError("重试任务不是对象")
            event_id = str(task.get("event_id") or "")
            active_event_id = event_id
            chapter = int(task.get("chapter"))
            if event_id not in source_events or int(event_id[4:8]) != chapter:
                raise ZBatchError(f"重试任务引用不存在事件：{event_id}")
            event = source_events[event_id]
            if task.get("event_sha256") != canonical_sha(event):
                raise ZBatchError(f"{event_id}重试任务未绑定原事件")
            lineage_row = main_lineage[event_id]
            if (
                task.get("source_event_id") != lineage_row["source_event_id"]
                or task.get("source_event_sha256") != lineage_row["source_event_sha256"]
                or task.get("source_identity_sha256")
                != lineage_row["source_identity_sha256"]
                or task.get("source_retry_count_before") != lineage_row["retry_count"]
                or lineage_row["retry_count"] >= MAX_TARGETED_RETRIES_PER_EVENT
            ):
                raise ZBatchError(f"{event_id}重试任务未绑定可重写的稳定源身份")
            codes = task.get("reason_codes")
            if (
                not isinstance(codes, list)
                or not codes
                or any(code not in RETRY_REASON_TEXT for code in codes)
            ):
                raise ZBatchError(f"{event_id}重试原因越权")
            messages = _build_semantic_retry_messages(
                run_dir=run_dir, chapter=chapter, event=event, reason_codes=codes
            )
            case_id = f"z83_repair_ch{chapter:04d}_{event_id.lower()}"
            expected_body = api_transport.build_request_body(
                model=str(load_bundle(run_dir).route["model"]),
                messages=messages,
                contract=load_bundle(run_dir).stage("targeted_retry"),
            )
            if retry_preflight is not None:
                preflight_row = next(
                    (
                        row
                        for row in retry_preflight["rows"]
                        if row.get("event_id") == event_id
                    ),
                    None,
                )
                prepared_path = run_dir / str(
                    (preflight_row or {}).get("prepared_request_path") or ""
                )
                if (
                    not isinstance(preflight_row, dict)
                    or not prepared_path.is_file()
                    or sha256_file(prepared_path)
                    != preflight_row.get("prepared_request_sha256")
                    or read_json(prepared_path) != expected_body
                ):
                    raise ZBatchError(f"{event_id}实发前请求不等于零调用预构造件")
                if _formal_anchor_field_strip_target(run_dir):
                    retry11_path = ROOT / str(
                        preflight_row.get("retry11_prepared_request_path") or ""
                    )
                    if (
                        not retry11_path.is_file()
                        or sha256_file(retry11_path)
                        != preflight_row.get("retry11_prepared_request_sha256")
                        or sha256_file(prepared_path) != sha256_file(retry11_path)
                        or read_json(retry11_path) != expected_body
                    ):
                        raise ZBatchError(
                            f"{event_id}实发前模型可见请求不再等于retry11冻结件"
                        )
            result = transport.call(
                stage="targeted_retry", case_id=case_id, messages=messages
            )
            if result.request_record.get("body") != expected_body:
                raise ZBatchError(f"{event_id}实际请求不等于冻结预构造件")
            parsed = candidate_envelope.parse_json_content(result.content)
            if _uses_retry11_request_contract(run_dir):
                raw_replacements = (
                    parsed.get("replacement_events")
                    if isinstance(parsed, dict)
                    else None
                )
                if not isinstance(raw_replacements, list) or len(raw_replacements) != 1:
                    observed = (
                        len(raw_replacements)
                        if isinstance(raw_replacements, list)
                        else "non_list"
                    )
                    contract_label = (
                        "retry11"
                        if run_dir.name == APPROVED_COUNT_CONTRACT_TARGET_NAME
                        else "常设"
                    )
                    raise ZBatchError(
                        f"{event_id}违反{contract_label}恰好1条份数合同："
                        f"observed={observed}"
                    )
            parsed_for_validation = parsed
            strip_rows: list[dict[str, Any]] = []
            if _formal_anchor_field_strip_target(run_dir):
                raw_response_path = _transport_paths(
                    repair_dir,
                    "targeted_retry",
                    case_id,
                )["raw_response"]
                parsed_for_validation, strip_rows = _normalize_retry12_anchor_extras(
                    run_dir=run_dir,
                    parsed=parsed,
                    chapter=chapter,
                    event_id=event_id,
                    case_id=case_id,
                    plan_ordinal=active_plan_ordinal,
                    raw_response_path=raw_response_path,
                )
            replacements = z77.validate_replacements(
                parsed_for_validation,
                catalog=_catalog(run_dir, chapter),
                allow_multiple=bool(task.get("allow_split")),
            )
            for strip_row in strip_rows:
                append_jsonl(
                    run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER,
                    strip_row,
                )
            index = int(event_id.rsplit("-", 1)[1]) - 1
            replacements_by_chapter[chapter][index] = replacements
            ledger = {
                "chapter": chapter,
                "plan_ordinal": active_plan_ordinal,
                **_transport_receipt_fields(repair_dir, "targeted_retry", case_id),
                "original_event_id": event_id,
                "original_event_sha256": canonical_sha(event),
                "source_event_id": lineage_row["source_event_id"],
                "source_event_sha256": lineage_row["source_event_sha256"],
                "source_identity_sha256": lineage_row["source_identity_sha256"],
                "source_retry_count_before": lineage_row["retry_count"],
                "reason_codes": list(codes),
                "free_text_adjudication_sent_to_model": False,
                "replacement_count": len(replacements),
                "replacement_sha256": canonical_sha(replacements),
            }
            if _formal_anchor_field_strip_target(run_dir):
                ledger["anchor_extra_field_strip"] = {
                    "diagnostic_only": True,
                    "ledger_path": RETRY12_ANCHOR_EXTRA_FIELD_LEDGER.relative_to(
                        Path("repair")
                    ).as_posix(),
                    "row_count": len(strip_rows),
                    "rows_canonical_sha256": canonical_sha(strip_rows),
                    "formal_replacement_uses_sanitized_copy": True,
                    "formal_quote_source": "frozen_evidence_catalog_by_anchor_id",
                }
            receipt_by_chapter_index[chapter][index] = ledger
            completed_retry_receipts.append(ledger)
        for chapter in TARGET_CHAPTERS:
            original = read_json(_model_file(main_stage, chapter))
            lineage_original = read_json(_event_file(main_stage, chapter))
            final_json = z77.apply_replacements(
                original,
                chapter=chapter,
                replacements=replacements_by_chapter.get(chapter, {}),
            )
            materialized, audit = neutral_extract.process_model_data(
                final_json, chapter=chapter, catalog=_catalog(run_dir, chapter)
            )
            prior_rows = {
                event_id: row
                for event_id, row in main_lineage.items()
                if int(event_id[4:8]) == chapter
            }
            lineage, descendants = _build_event_lineage(
                chapter=chapter,
                original=lineage_original,
                final=materialized,
                replacements=replacements_by_chapter.get(chapter, {}),
                retry_receipts=receipt_by_chapter_index.get(chapter, {}),
                stage="semantic_targeted_retry",
                prior_rows=prior_rows,
            )
            for index, ledger in sorted(
                receipt_by_chapter_index.get(chapter, {}).items()
            ):
                input_event_id = str(original["events"][index]["event_id"])
                ledger["materialized_event_ids"] = descendants[input_event_id]
                ledger["source_retry_count_after"] = 1
                ledgers.append(ledger)
                append_jsonl(repair_dir / "targeted_retry_ledger.jsonl", ledger)
            write_json(
                repair_dir / f"01_extract/model_json/ch{chapter:04d}.json", final_json
            )
            write_json(
                repair_dir / f"01_extract/events/ch{chapter:04d}.json", materialized
            )
            write_json(
                repair_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit
            )
            write_json(
                repair_dir / f"01_extract/event_lineage/ch{chapter:04d}.json", lineage
            )
    except BaseException as exc:
        hard_stop = {
            "schema_version": "z83-repair-hard-stop-v1",
            "status": "hard_stop_no_unapproved_repair",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "completed_retries": len(completed_retry_receipts),
            "network_attempts": len(z68.read_jsonl(repair_dir / "call_attempts.jsonl")),
            "failed_event_id": active_event_id,
            "failed_plan_ordinal": active_plan_ordinal,
            "required_replacement_count": (
                1 if _uses_retry11_request_contract(run_dir) else None
            ),
        }
        diagnostic_path = run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
        if _formal_anchor_field_strip_target(run_dir):
            diagnostic_rows = (
                z68.read_jsonl(diagnostic_path) if diagnostic_path.is_file() else []
            )
            hard_stop["anchor_extra_field_strip_diagnostics"] = {
                "status": "diagnostic_observation_not_truth",
                "path": (
                    diagnostic_path.relative_to(run_dir).as_posix()
                    if diagnostic_path.is_file()
                    else None
                ),
                "sha256": (
                    sha256_file(diagnostic_path)
                    if diagnostic_path.is_file()
                    else None
                ),
                "row_count": len(diagnostic_rows),
                "entered_formal_record": False,
            }
        write_json(repair_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            repair_dir / "run_manifest.json", {**hard_stop, "run_claim": claim}
        )
        raise
    usage = _usage_summary(repair_dir / "usage.jsonl")
    metrics = {
        "schema_version": "z83-repair-metrics-v1",
        "status": "completed_candidate_silver_only",
        "targeted_retry_logical_calls": len(tasks),
        "network_attempts": len(z68.read_jsonl(repair_dir / "call_attempts.jsonl")),
        **usage,
        "targeted_retry_ledger": ledgers,
        "zero_retry_copy": not tasks,
    }
    if _formal_anchor_field_strip_target(run_dir):
        diagnostic_path = run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
        diagnostic_rows = (
            z68.read_jsonl(diagnostic_path) if diagnostic_path.is_file() else []
        )
        metrics["anchor_extra_field_strip_diagnostics"] = {
            "status": "diagnostic_observation_not_truth",
            "path": (
                diagnostic_path.relative_to(run_dir).as_posix()
                if diagnostic_path.is_file()
                else None
            ),
            "sha256": (
                sha256_file(diagnostic_path) if diagnostic_path.is_file() else None
            ),
            "row_count": len(diagnostic_rows),
            "formal_quote_source": "frozen_evidence_catalog_by_anchor_id",
            "entered_formal_record": False,
        }
    write_json(repair_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        repair_dir / "run_manifest.json",
        {
            "schema_version": "z83-repair-run-manifest-v1",
            "status": "completed_candidate_silver_only",
            "run_claim": claim,
            "targeted_retry_count": len(tasks),
            "network_attempts": metrics["network_attempts"],
            "anchor_extra_field_strip_diagnostics": metrics.get(
                "anchor_extra_field_strip_diagnostics"
            ),
        },
    )
    verify_event_stage(
        run_dir, repair_dir, schema_version="z83-repair-mechanical-verification-v1"
    )
    final_dir = run_dir / "final"
    if final_dir.exists():
        raise ZBatchError("最终事件目录已存在，拒绝覆盖")
    shutil.copytree(repair_dir / "01_extract", final_dir / "01_extract")
    write_json(
        final_dir / "run_manifest.json",
        {
            "schema_version": "z83-final-event-manifest-v1",
            "status": "awaiting_final_semantic_review",
            "source_retry_plan_sha256": sha256_file(plan_path),
            "targeted_retry_count": len(tasks),
        },
    )
    verify_event_stage(
        run_dir, final_dir, schema_version="z83-final-mechanical-verification-v1"
    )
    master = read_json(run_dir / "run_manifest.json")
    master["status"] = "repair_completed"
    master["repair"] = "completed_candidate_silver_only"
    master["final"] = "awaiting_final_semantic_review"
    write_json_atomic(run_dir / "run_manifest.json", master)
    return metrics


def _summary_current(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(rows)
    counts = Counter(str(row["verdict"]) for row in values)
    degraded = [
        str(row["record_id"])
        for row in values
        if CURRENT_RANK[str(row["verdict"])] < CURRENT_RANK[str(row["required_floor"])]
    ]
    return {
        "total": len(values),
        "preserved": counts["preserved"],
        "partially_preserved": counts["partially_preserved"],
        "not_observed": counts["not_observed"],
        "degradation_count": len(degraded),
        "degraded_record_ids": sorted(degraded),
        "gate_pass": not degraded,
    }


def _assert_exchange_inventory(
    stage_dir: Path,
    *,
    stage: str,
    expected_case_ids: set[str],
) -> None:
    actual_requests = {
        path.name.removesuffix("_request.json")
        for path in (stage_dir / f"requests/{stage}").glob("*_request.json")
    }
    actual_raw = {
        path.name.removesuffix("_raw.json")
        for path in (stage_dir / f"responses/{stage}").glob("*_raw.json")
    }
    actual_meta = {
        path.name.removesuffix("_meta.json")
        for path in (stage_dir / f"responses/{stage}").glob("*_meta.json")
    }
    if (
        actual_requests != expected_case_ids
        or actual_raw != expected_case_ids
        or actual_meta != expected_case_ids
    ):
        raise ZBatchError(f"{stage}调用工件集合与调用账不一致")


def _validate_attempt_inventory(
    *,
    run_dir: Path,
    stage_dir: Path,
    expected_calls: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """全量核对调用尝试；不允许白名单外 stage/case 混入计数。"""

    rows = z68.read_jsonl(stage_dir / "call_attempts.jsonl")
    route = api_transport.TransportRoute.from_mapping(load_bundle(run_dir).route)
    if len(rows) > len(expected_calls) * route.network_attempts:
        raise ZBatchError("调用尝试总数超过逻辑调用数乘运输重试上限")
    observed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for call_number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ZBatchError("调用尝试账含非对象")
        key = (str(row.get("stage") or ""), str(row.get("case_id") or ""))
        if key not in expected_calls:
            raise ZBatchError(f"调用尝试账混入未授权 stage/case：{key}")
        if (
            row.get("call_number") != call_number
            or row.get("max_calls") != MAX_NETWORK_ATTEMPTS
        ):
            raise ZBatchError("调用尝试账全局序号或总上限不连续")
        observed[key].append(row)
    if set(observed) != expected_calls:
        raise ZBatchError("调用尝试账没有逐次覆盖全部预期逻辑调用")
    for key, attempts in observed.items():
        numbers = [row.get("attempt") for row in attempts]
        if (
            numbers != list(range(1, len(attempts) + 1))
            or len(attempts) > route.network_attempts
        ):
            raise ZBatchError(f"{key}运输重试序号不连续或超过合同上限")
    usage_rows = z68.read_jsonl(stage_dir / "usage.jsonl")
    if any(not isinstance(row, dict) for row in usage_rows):
        raise ZBatchError("usage 成功账含非对象")
    usage_keys = [
        (str(row.get("stage") or ""), str(row.get("case_id") or ""))
        for row in usage_rows
    ]
    if len(usage_keys) != len(expected_calls) or set(usage_keys) != expected_calls:
        raise ZBatchError("usage 成功账没有与预期逻辑调用一一对应")
    return rows


def _validate_main_sample_exchanges(run_dir: Path) -> dict[int, dict[str, Any]]:
    stage_dir = run_dir / "main"
    rows = z68.read_jsonl(stage_dir / "main_sample_ledger.jsonl")
    if len(rows) != len(TARGET_CHAPTERS):
        raise ZBatchError("主采样请求－响应账不是三章各一条")
    by_chapter: dict[int, dict[str, Any]] = {}
    for row in rows:
        chapter = row.get("chapter")
        if (
            isinstance(chapter, bool)
            or not isinstance(chapter, int)
            or chapter in by_chapter
        ):
            raise ZBatchError("主采样请求－响应账章号为空或重复")
        by_chapter[chapter] = dict(row)
    if set(by_chapter) != set(TARGET_CHAPTERS):
        raise ZBatchError("主采样请求－响应账章集合错误")
    for chapter in TARGET_CHAPTERS:
        receipt = by_chapter[chapter]
        case_id = f"z83_main_ch{chapter:04d}"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        model_path = stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        if (
            receipt.get("schema_version") != "z83-main-sample-exchange-v1"
            or receipt.get("case_id") != case_id
            or receipt.get("prepared_request_path")
            != f"prepared_requests/ch{chapter:04d}.json"
            or receipt.get("prepared_request_sha256") != sha256_file(prepared_path)
            or receipt.get("parsed_model_path")
            != _stage_relative(stage_dir, model_path)
            or not model_path.is_file()
            or receipt.get("parsed_model_file_sha256") != sha256_file(model_path)
        ):
            raise ZBatchError(f"第{chapter}章主采样账未绑定冻结请求或解析件")
        _, content = _verify_successful_exchange(
            stage_dir=stage_dir,
            stage="neutral_extract",
            case_id=case_id,
            expected_body=read_json(prepared_path),
            receipt=receipt,
        )
        parsed = candidate_envelope.parse_json_content(content)
        if receipt.get("parsed_model_canonical_sha256") != canonical_sha(
            parsed
        ) or parsed != read_json(model_path):
            raise ZBatchError(f"第{chapter}章主样张不能从原始响应重建")
    _assert_exchange_inventory(
        stage_dir,
        stage="neutral_extract",
        expected_case_ids={f"z83_main_ch{chapter:04d}" for chapter in TARGET_CHAPTERS},
    )
    return by_chapter


def _validate_main_retry_exchanges(
    run_dir: Path,
    ledger: Sequence[Mapping[str, Any]],
) -> None:
    stage_dir = run_dir / "main"
    replacements_by_chapter: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(
        dict
    )
    case_ids: set[str] = set()
    expected_by_chapter: dict[int, dict[str, dict[str, Any]]] = {}
    ledger_by_chapter: dict[int, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for receipt in ledger:
        chapter_raw = receipt.get("chapter")
        if isinstance(chapter_raw, bool) or not isinstance(chapter_raw, int):
            raise ZBatchError("机械重写账章号错误")
        event_id = str(receipt.get("original_event_id") or "")
        if not event_id or event_id in ledger_by_chapter[chapter_raw]:
            raise ZBatchError("机械重写账原事件为空或重复")
        ledger_by_chapter[chapter_raw][event_id] = receipt
    total_eligible = 0
    for chapter in TARGET_CHAPTERS:
        original = read_json(
            stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        )
        original_events = original.get("events") if isinstance(original, dict) else None
        if not isinstance(original_events, list):
            raise ZBatchError(f"第{chapter}章主采样原始事件格式错误")
        analysis = z77.analyze_main_response(
            original,
            chapter=chapter,
            catalog=_catalog(run_dir, chapter),
        )
        if analysis.get("hard_reasons"):
            raise ZBatchError(f"第{chapter}章原始主响应含未授权失败面")
        eligible_rows = analysis.get("eligible")
        if not isinstance(eligible_rows, list):
            raise ZBatchError(f"第{chapter}章机械违规分析格式错误")
        if len(eligible_rows) > MAX_TARGETED_RETRIES_PER_CHAPTER:
            raise ZBatchError(f"第{chapter}章真实机械坏条超过章预算")
        expected: dict[str, dict[str, Any]] = {}
        for row in eligible_rows:
            if not isinstance(row, dict):
                raise ZBatchError(f"第{chapter}章机械违规项不是对象")
            event_id = str(row.get("event_id") or "")
            index = row.get("index")
            if (
                not event_id
                or event_id in expected
                or isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < len(original_events)
                or row.get("original_event") != original_events[index]
            ):
                raise ZBatchError(f"第{chapter}章机械违规项不能绑定原事件")
            expected[event_id] = row
        expected_by_chapter[chapter] = expected
        total_eligible += len(expected)
        if set(ledger_by_chapter.get(chapter, {})) != set(expected):
            raise ZBatchError(f"第{chapter}章机械重写账与主响应真实违规集合不一致")
    if (
        set(ledger_by_chapter) - set(TARGET_CHAPTERS)
        or total_eligible > MAX_TARGETED_RETRIES_TOTAL
    ):
        raise ZBatchError("机械重写账章集合或全轮真实违规预算错误")
    for chapter in TARGET_CHAPTERS:
        original = read_json(
            stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        )
        for event_id, expected_row in expected_by_chapter[chapter].items():
            receipt = ledger_by_chapter[chapter][event_id]
            index = int(expected_row["index"])
            event = original["events"][index]
            raw_violations = receipt.get("raw_violations_local_only")
            if not isinstance(raw_violations, list):
                raise ZBatchError(f"{event_id}机械重写账缺本地原始违规列表")
            reason_codes, visible_reasons = _closed_mechanical_retry_reasons(
                raw_violations
            )
            if (
                receipt.get("kind") != "existing_mechanical_retry"
                or receipt.get("case_id")
                != f"z83_main_ch{chapter:04d}_{event_id.lower()}"
                or receipt.get("original_event_index") != index
                or raw_violations != expected_row.get("violations")
                or receipt.get("reason_codes") != reason_codes
                or receipt.get("raw_violations_sent_to_model") is not False
                or receipt.get("original_event_sha256") != canonical_sha(event)
            ):
                raise ZBatchError(f"{event_id}机械重写账与原始事件／封闭原因码不一致")
            messages = z77.build_retry_messages(
                chapter=chapter,
                original_event=event,
                violations=visible_reasons,
                chapter_text=_chapter_text_path(run_dir, chapter).read_text(
                    encoding="utf-8"
                ),
                catalog=_catalog(run_dir, chapter),
            )
            if forbidden_model_hits(messages):
                raise ZBatchError(f"{event_id}机械重写请求含判分侧材料")
            replacements, strip_rows = _verify_retry_exchange(
                run_dir=run_dir,
                stage_dir=stage_dir,
                receipt=receipt,
                expected_messages=messages,
                allow_multiple="EVENT_TOO_LONG" in reason_codes,
            )
            if strip_rows:
                raise ZBatchError(f"{event_id}主采样机械重写不应出现retry12旁账")
            if index in replacements_by_chapter[chapter]:
                raise ZBatchError(f"{event_id}机械重写事件重复")
            replacements_by_chapter[chapter][index] = replacements
            case_ids.add(str(receipt["case_id"]))
    _assert_exchange_inventory(
        stage_dir, stage="targeted_retry", expected_case_ids=case_ids
    )
    for chapter in TARGET_CHAPTERS:
        original = read_json(
            stage_dir / f"01_extract/model_json_original/ch{chapter:04d}.json"
        )
        rebuilt = z77.apply_replacements(
            original,
            chapter=chapter,
            replacements=replacements_by_chapter.get(chapter, {}),
        )
        if rebuilt != read_json(_model_file(stage_dir, chapter)):
            raise ZBatchError(f"第{chapter}章机械重写产物不能由原始响应重建")


def _validate_semantic_retry_exchanges(
    run_dir: Path,
    *,
    tasks: Sequence[Mapping[str, Any]],
    ledger: Sequence[Mapping[str, Any]],
) -> None:
    stage_dir = run_dir / "repair"
    task_by_event = {str(task.get("event_id") or ""): task for task in tasks}
    plan_ordinal_by_event = {
        str(task.get("event_id") or ""): ordinal
        for ordinal, task in enumerate(tasks, 1)
    }
    ledger_by_event = {str(row.get("original_event_id") or ""): row for row in ledger}
    if set(task_by_event) != set(ledger_by_event) or "" in task_by_event:
        raise ZBatchError("语义重写调用账与已审任务集合不一致")
    source_events = _event_map(run_dir / "main")
    replacements_by_chapter: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(
        dict
    )
    case_ids: set[str] = set()
    expected_strip_rows: list[dict[str, Any]] = []
    for event_id, task in task_by_event.items():
        receipt = ledger_by_event[event_id]
        chapter = int(task["chapter"])
        event = source_events.get(event_id)
        codes = task.get("reason_codes")
        if (
            not isinstance(event, dict)
            or not isinstance(codes, list)
            or receipt.get("chapter") != chapter
            or receipt.get("plan_ordinal") != plan_ordinal_by_event[event_id]
            or receipt.get("case_id")
            != f"z83_repair_ch{chapter:04d}_{event_id.lower()}"
            or receipt.get("reason_codes") != codes
            or receipt.get("original_event_sha256") != canonical_sha(event)
            or receipt.get("free_text_adjudication_sent_to_model") is not False
        ):
            raise ZBatchError(f"{event_id}语义重写账未绑定任务与当前事件")
        messages = _build_semantic_retry_messages(
            run_dir=run_dir,
            chapter=chapter,
            event=event,
            reason_codes=codes,
        )
        replacements, strip_rows = _verify_retry_exchange(
            run_dir=run_dir,
            stage_dir=stage_dir,
            receipt=receipt,
            expected_messages=messages,
            allow_multiple=bool(task.get("allow_split")),
            retry12_event_id=(
                event_id if _formal_anchor_field_strip_target(run_dir) else None
            ),
            retry12_plan_ordinal=(
                plan_ordinal_by_event[event_id]
                if _formal_anchor_field_strip_target(run_dir)
                else None
            ),
        )
        expected_strip_rows.extend(strip_rows)
        index = int(event_id.rsplit("-", 1)[1]) - 1
        if index in replacements_by_chapter[chapter]:
            raise ZBatchError(f"{event_id}语义重写任务重复")
        replacements_by_chapter[chapter][index] = replacements
        case_ids.add(str(receipt["case_id"]))
    _assert_exchange_inventory(
        stage_dir, stage="targeted_retry", expected_case_ids=case_ids
    )
    strip_path = run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
    if _formal_anchor_field_strip_target(run_dir):
        actual_strip_rows = z68.read_jsonl(strip_path) if strip_path.is_file() else []
        if actual_strip_rows != expected_strip_rows:
            raise ZBatchError("retry12锚字段剥离旁账不能从原始响应与冻结目录重建")
    elif strip_path.exists():
        raise ZBatchError("非retry12运行夹入锚字段剥离旁账")
    for chapter in TARGET_CHAPTERS:
        original = read_json(_model_file(run_dir / "main", chapter))
        rebuilt = z77.apply_replacements(
            original,
            chapter=chapter,
            replacements=replacements_by_chapter.get(chapter, {}),
        )
        if rebuilt != read_json(_model_file(stage_dir, chapter)):
            raise ZBatchError(f"第{chapter}章语义重写产物不能由原始响应重建")


def _verify_retry13_call_lineage(
    run_dir: Path,
    *,
    main_attempts: int,
    main_retry_count: int,
    seed_receipt: Mapping[str, Any] | None,
    imported_attempts: int,
    main_lineage: Mapping[str, Any],
    main_mechanical: Mapping[str, Any],
) -> dict[str, Any]:
    """核验 retry13 的32份单对象检查点与13次父源物化。"""

    # 延迟导入，避免主模块加载时与 retry13 专用执行器形成循环导入。
    import z83_retry13_atomic_repair as retry13_atomic

    # 专用执行器里这两道校验会从代码闭集重建父子任务、
    # 事实目标、许可动作、完整锚集和32份冻结请求。不只信运行目录内部自洽。
    # 第94道只替换供料切片，因此用自己的冻结校验器；后续单对象合同、
    # 运输、检查点与物化仍沿用同一套 retry13 合同。
    atomic_runner: Any = retry13_atomic
    if run_dir.name in {
        APPROVED_Z94_LOCAL_SEMANTIC_SUPPLY_TARGET_NAME,
        APPROVED_Z94_TENCENT_FLASH_TARGET_NAME,
    }:
        import z94_local_semantic_live as z94_atomic

        atomic_runner = z94_atomic
    approved_plan = atomic_runner._validate_plan(run_dir)
    preflight_verification = atomic_runner.verify_preflight(run_dir)
    atomic = _validate_retry13_atomic_plan_identity(run_dir)
    plan = atomic["plan"]
    if plan != approved_plan:
        raise ZBatchError("retry13原子计划不等于专用执行器从获批闭集重建的计划")
    task_by_id = atomic["tasks"]
    repair_dir = run_dir / "repair"
    final_dir = run_dir / "final"
    preflight_path = repair_dir / "atomic_preflight.json"
    claim_path = repair_dir / "retry13_run_claim.json"
    manifest_path = repair_dir / "retry13_run_manifest.json"
    metrics_path = repair_dir / "01_extract/metrics.json"
    if not claim_path.is_file() or not manifest_path.is_file() or not metrics_path.is_file():
        raise ZBatchError("retry13缺专用占用票、完成票或指标账")
    claim = read_json(claim_path)
    manifest = read_json(manifest_path)
    metrics = read_json(metrics_path)
    if (repair_dir / "hard_stop.json").exists():
        raise ZBatchError("retry13完成态不得同时存在硬停票")
    expected_transport_policy = {
        "max_429_retries_per_request": 2,
        "retry_delays_seconds": [5, 10],
        "same_chapter_gap_seconds": 10,
        "cross_chapter_gap_seconds": 30,
        "fifth_429_hard_stop": True,
        "retry_after_over_300_hard_stop": True,
        "http_401_403_5xx_or_network_error_auto_retry": False,
    }
    plan_receipt = read_json(run_dir / "review/retry13_plan_receipt.json")
    preflight = read_json(preflight_path)
    if (
        plan.get("transport_policy") != expected_transport_policy
        or plan.get("model_visible_contract_version")
        != retry13_atomic.CONTRACT_VERSION
        or plan.get("gold_or_score_material_sent_to_model") is not False
        or plan.get("model_api_calls") != 0
        or plan.get("network_attempts") != 0
        or plan_receipt.get("schema_version")
        != "z83-retry13-plan-receipt-v1"
        or plan_receipt.get("status")
        != "pass_zero_call_parent13_child32_frozen"
        or preflight.get("schema_version") != retry13_atomic.PREFLIGHT_SCHEMA
        or preflight.get("status") != "pass_zero_call_requests_frozen"
        or preflight.get("run_id") != run_dir.name
        or preflight.get("plan_path") != "repair/atomic_plan.json"
        or preflight.get("plan_sha256") != atomic["sha256"]
        or preflight.get("contract_version") != retry13_atomic.CONTRACT_VERSION
        or preflight.get("contract_text_sha256")
        != canonical_sha(retry13_atomic._extract_single_object_system_contract())
        or preflight.get("parent_count") != 13
        or preflight.get("task_count") != 32
        or preflight.get("atomic_split_counts") != plan.get("atomic_split_counts")
        or preflight.get("atomic_split_total") != 25
        or preflight.get("pending_parent_ids") != []
        or preflight.get("model_api_calls") != 0
        or preflight.get("network_attempts") != 0
    ):
        raise ZBatchError("retry13获批计划、运输规则或预构造总票漂移")
    preflight_rows = preflight.get("rows")
    if not isinstance(preflight_rows, list) or len(preflight_rows) != 32:
        raise ZBatchError("retry13预构造票不是32行")
    preflight_by_task = {
        str(row.get("task_id") or ""): row
        for row in preflight_rows
        if isinstance(row, dict)
    }
    if len(preflight_by_task) != 32 or set(preflight_by_task) != set(task_by_id):
        raise ZBatchError("retry13预构造票任务集合漂移")
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        row = preflight_by_task[task_id]
        prepared_path = run_dir / str(row.get("prepared_request_path") or "")
        prepared_body = read_json(prepared_path)
        recomputed_wire_sha = hashlib.sha256(
            json.dumps(prepared_body, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        case_id = f"z83r13-{task_id}"
        if (
            row.get("parent_event_id") != task.get("parent_event_id")
            or row.get("chapter") != task.get("chapter")
            or row.get("fact_ordinal") != task.get("fact_ordinal")
            or row.get("fact_count") != task.get("fact_count")
            or row.get("fact_target_sha256") != task.get("fact_target_sha256")
            or row.get("case_id") != case_id
            or row.get("prepared_request_path")
            != f"repair/prepared_single_object_requests/{case_id}.json"
            or row.get("prepared_request_sha256") != sha256_file(prepared_path)
            or row.get("body_canonical_sha256") != canonical_sha(prepared_body)
            or row.get("messages_sha256")
            != canonical_sha(prepared_body.get("messages"))
            or row.get("single_object_contract_present") is not True
            or row.get("output_array_contract_present") is not False
            or row.get("gold_or_score_hits") != []
        ):
            raise ZBatchError(f"retry13预构造行不能逐字绑定任务：{task_id}")
    attempts = z68.read_jsonl(repair_dir / "call_attempts.jsonl")
    reservations = z68.read_jsonl(repair_dir / "attempt_reservations.jsonl")
    usage_rows = z68.read_jsonl(repair_dir / "usage.jsonl")
    z83_retry_transport.validate_attempt_rows(attempts)
    retry_wait_receipts = z83_retry_transport.validate_retry_wait_sequence(
        repair_dir / "call_attempts.jsonl",
        attempts,
        require_all_429_completed=True,
    )
    http_429_count = sum(row.get("http_status") == 429 for row in attempts)
    if (
        set(claim)
        != {
            "schema_version",
            "status",
            "run_id",
            "plan_sha256",
            "preflight_sha256",
            "preflight_verification_sha256",
            "logical_request_count",
            "claimed_at",
        }
        or claim.get("schema_version") != "z83-retry13-run-claim-v1"
        or claim.get("status") != "running_do_not_resume_or_cherry_pick"
        or claim.get("run_id") != run_dir.name
        or claim.get("plan_sha256") != atomic["sha256"]
        or claim.get("preflight_sha256") != sha256_file(preflight_path)
        or claim.get("preflight_verification_sha256")
        != canonical_sha(preflight_verification)
        or not isinstance(claim.get("claimed_at"), str)
        or not str(claim.get("claimed_at") or "").strip()
        or claim.get("logical_request_count") != 32
        or manifest.get("schema_version") != "z83-retry13-run-manifest-v1"
        or manifest.get("status")
        != "completed_candidate_silver_only_awaiting_targeted_semantic_review"
        or manifest.get("run_claim") != claim
        or manifest.get("logical_request_count") != 32
        or manifest.get("network_attempts") != len(attempts)
        or manifest.get("http_429_count") != http_429_count
        or manifest.get("rewritten_descendant_count") != 32
        or manifest.get("final_event_count") != 175
        or manifest.get("prefix_cherry_picked") is not False
        or manifest.get("candidate_silver_only") is not True
        or metrics.get("schema_version") != "z83-retry13-repair-metrics-v1"
        or metrics.get("status")
        != "completed_candidate_silver_only_awaiting_targeted_semantic_review"
        or metrics.get("parent_rewrite_count") != 13
        or metrics.get("logical_request_count") != 32
        or metrics.get("network_attempts") != len(attempts)
        or metrics.get("http_429_count") != http_429_count
        or metrics.get("usage_row_count") != 32
        or metrics.get("main_event_count") != 156
        or metrics.get("final_event_count") != 175
        or metrics.get("rewritten_descendant_count") != 32
        or metrics.get("main_event_count_by_chapter")
        != {"3": 58, "13": 46, "19": 52}
        or metrics.get("final_event_count_by_chapter")
        != {"3": 61, "13": 50, "19": 64}
        or metrics.get("rewritten_descendant_count_by_chapter")
        != {"3": 7, "13": 7, "19": 18}
        or metrics.get("candidate_silver_only") is not True
        or not 32 <= len(attempts) <= int(plan["network_attempt_budget"])
        or http_429_count > 4
    ):
        raise ZBatchError("retry13专用调用状态、32子请求计数或429预算错误")

    reservation_keys: list[tuple[Any, ...]] = []
    for row in reservations:
        preimage = {key: value for key, value in row.items() if key != "row_sha256"}
        task = task_by_id.get(str(row.get("logical_request_id") or ""))
        if (
            set(row)
            != {
                "schema",
                "logical_request_id",
                "parent_event_id",
                "chapter",
                "attempt",
                "request_artifact_sha256",
                "wire_body_sha256",
                "reserved_at",
                "state",
                "row_sha256",
            }
            or task is None
            or row.get("schema") != "z83-retry13-attempt-reservation-v1"
            or row.get("parent_event_id") != task.get("parent_event_id")
            or row.get("chapter") != task.get("chapter")
            or isinstance(row.get("attempt"), bool)
            or not isinstance(row.get("attempt"), int)
            or int(row["attempt"]) < 1
            or not isinstance(row.get("reserved_at"), str)
            or not str(row.get("reserved_at") or "").strip()
            or row.get("state") != "reserved_before_network_do_not_resend_if_unmatched"
            or row.get("row_sha256") != canonical_sha(preimage)
        ):
            raise ZBatchError("retry13发网前占用票不能重建")
        reservation_keys.append(
            (
                row.get("logical_request_id"),
                row.get("attempt"),
                row.get("request_artifact_sha256"),
                row.get("wire_body_sha256"),
            )
        )
    attempt_keys = [
        (
            row.get("logical_request_id"),
            row.get("attempt"),
            row.get("request_artifact_sha256"),
            row.get("wire_body_sha256"),
        )
        for row in attempts
    ]
    if (
        len(reservations) != len(attempts)
        or reservation_keys != attempt_keys
        or len(reservation_keys) != len(set(reservation_keys))
    ):
        raise ZBatchError("retry13发网前占用票与终态attempt不是逐次一一对应")

    attempts_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempts:
        attempts_by_task[str(row.get("logical_request_id") or "")].append(row)
    if set(attempts_by_task) != set(task_by_id):
        raise ZBatchError("retry13尝试账没有逐项覆盖32个子请求")
    expected_attempt_task_order = [
        str(task["task_id"])
        for task in plan["tasks"]
        for _ in attempts_by_task[str(task["task_id"])]
    ]
    if [str(row.get("logical_request_id") or "") for row in attempts] != (
        expected_attempt_task_order
    ):
        raise ZBatchError("retry13尝试账不等于冻结32任务的串行顺序")
    retry_policy = z83_retry_transport.RetryPolicy()
    retry_policy.validate()

    def timing_value(row: Mapping[str, Any], field: str) -> float | None:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if number >= 0 else None

    def retry_after_matches(
        raw_value: Any,
        parsed_value: Any,
        *,
        reference_time: datetime,
    ) -> bool:
        if raw_value is None:
            return parsed_value is None
        try:
            expected = max(0.0, float(str(raw_value).strip()))
        except ValueError:
            expected = z83_retry_transport.parse_retry_after_seconds(
                str(raw_value), now=lambda: reference_time
            )
            if expected is None:
                return parsed_value is None
            return (
                not isinstance(parsed_value, bool)
                and isinstance(parsed_value, (int, float))
                and abs(float(parsed_value) - expected)
                <= timestamp_resolution_tolerance_seconds
            )
        return (
            not isinstance(parsed_value, bool)
            and isinstance(parsed_value, (int, float))
            and float(parsed_value) == expected
        )

    def parsed_attempt_time(value: Any, *, task_id: str, field: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ZBatchError(f"retry13{task_id}尝试账缺{field}时间")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ZBatchError(f"retry13{task_id}尝试账{field}时间不可解析") from exc
        if parsed.tzinfo is None:
            raise ZBatchError(f"retry13{task_id}尝试账{field}时间缺时区")
        return parsed

    timestamp_resolution_tolerance_seconds = 1.0
    timing_tolerance_seconds = 0.05
    previous_task: Mapping[str, Any] | None = None
    previous_finished: datetime | None = None
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        first_row = attempts_by_task[task_id][0]
        spacing_planned = timing_value(
            first_row, "pre_request_spacing_planned_seconds"
        )
        spacing_actual = timing_value(first_row, "pre_request_spacing_seconds")
        started = parsed_attempt_time(
            first_row.get("started_at"), task_id=task_id, field="开始"
        )
        if previous_task is None:
            if spacing_planned != 0.0 or spacing_actual != 0.0:
                raise ZBatchError("retry13首个子请求不应有前置间隔")
        else:
            assert previous_finished is not None
            required_gap = (
                retry_policy.same_chapter_gap_seconds
                if previous_task["chapter"] == task["chapter"]
                else retry_policy.cross_chapter_gap_seconds
            )
            observed_gap = (started - previous_finished).total_seconds()
            if (
                spacing_planned is None
                or spacing_actual is None
                or spacing_actual + timing_tolerance_seconds < spacing_planned
                or observed_gap + timestamp_resolution_tolerance_seconds
                < required_gap
            ):
                raise ZBatchError(f"retry13子请求首发间隔未满足冻结运输规则：{task_id}")
        last_row = attempts_by_task[task_id][-1]
        previous_finished = parsed_attempt_time(
            last_row.get("finished_at"), task_id=task_id, field="结束"
        )
        if previous_finished < started:
            raise ZBatchError(f"retry13子请求结束时间早于开始：{task_id}")
        previous_task = task

    for task_id, rows in attempts_by_task.items():
        task = task_by_id[task_id]
        sequence_valid = (
            [row.get("attempt") for row in rows] == list(range(1, len(rows) + 1))
            and 1 <= len(rows) <= 1 + retry_policy.max_429_retries_per_request
            and all(row.get("chapter") == task.get("chapter") for row in rows)
        )
        timing_valid = True
        for ordinal, row in enumerate(rows, 1):
            row_started = parsed_attempt_time(
                row.get("started_at"), task_id=task_id, field=f"第{ordinal}次开始"
            )
            row_finished = parsed_attempt_time(
                row.get("finished_at"), task_id=task_id, field=f"第{ordinal}次结束"
            )
            spacing_planned = timing_value(
                row, "pre_request_spacing_planned_seconds"
            )
            spacing_actual = timing_value(row, "pre_request_spacing_seconds")
            retry_wait = timing_value(row, "retry_wait_seconds")
            retry_wait_actual = (
                retry_wait_receipts.get((task_id, ordinal), {}).get(
                    "actual_seconds"
                )
                if row.get("http_status") == 429
                else timing_value(row, "retry_wait_actual_seconds")
            )
            if None in (
                spacing_planned,
                spacing_actual,
                retry_wait,
                retry_wait_actual,
            ):
                timing_valid = False
            if row_finished < row_started:
                timing_valid = False
            if row.get("previous_attempt") != (ordinal - 1 if ordinal > 1 else None):
                timing_valid = False
            if ordinal > 1 and (
                spacing_planned != 0.0 or spacing_actual != 0.0
            ):
                timing_valid = False
        prior_rows = rows[:-1]
        for retry_ordinal, row in enumerate(prior_rows, 1):
            retry_after = row.get("retry_after_seconds")
            base_wait = retry_policy.retry_delays_seconds[retry_ordinal - 1]
            retry_wait = timing_value(row, "retry_wait_seconds")
            retry_wait_actual = retry_wait_receipts.get(
                (task_id, retry_ordinal), {}
            ).get("actual_seconds")
            current_finished = parsed_attempt_time(
                row.get("finished_at"), task_id=task_id, field="结束"
            )
            next_started = parsed_attempt_time(
                rows[retry_ordinal].get("started_at"),
                task_id=task_id,
                field="下次开始",
            )
            observed_retry_gap = (next_started - current_finished).total_seconds()
            if (
                row.get("http_status") != 429
                or row.get("outcome") != "http_error"
                or row.get("usage") != z83_retry_transport.UNKNOWN_USAGE
                or row.get("usage_status") != "unknown"
                or not retry_after_matches(
                    row.get("retry_after_raw"),
                    retry_after,
                    reference_time=current_finished,
                )
                or isinstance(retry_after, bool)
                or (
                    retry_after is not None
                    and (
                        not isinstance(retry_after, (int, float))
                        or float(retry_after) < 0
                        or float(retry_after)
                        > retry_policy.max_retry_after_seconds
                    )
                )
                or retry_wait is None
                or retry_wait_actual is None
                or retry_wait < base_wait
                or retry_wait_actual + timing_tolerance_seconds < retry_wait
                or observed_retry_gap + timestamp_resolution_tolerance_seconds
                < retry_wait
                or (
                    retry_after is not None
                    and isinstance(retry_after, (int, float))
                    and not isinstance(retry_after, bool)
                    and retry_wait is not None
                    and retry_wait < float(retry_after)
                )
            ):
                sequence_valid = False
        final_row = rows[-1]
        final_retry_wait = timing_value(final_row, "retry_wait_seconds")
        final_retry_wait_actual = timing_value(
            final_row, "retry_wait_actual_seconds"
        )
        if (
            final_row.get("http_status") != 200
            or final_row.get("outcome") != "success"
            or final_row.get("usage_status") != "returned"
            or not isinstance(final_row.get("usage"), dict)
            or not final_row.get("usage")
            or final_retry_wait != 0.0
            or final_retry_wait_actual != 0.0
        ):
            sequence_valid = False
        if not sequence_valid or not timing_valid:
            raise ZBatchError(f"retry13子请求尝试序列或成功终态错误：{task_id}")

    usage_by_task: dict[str, dict[str, Any]] = {}
    for row in usage_rows:
        task_id = str(row.get("logical_request_id") or "")
        preimage = {key: value for key, value in row.items() if key != "row_sha256"}
        task = task_by_id.get(task_id)
        if (
            task is None
            or task_id in usage_by_task
            or row.get("schema_version") != "z83-retry13-usage-v1"
            or row.get("parent_event_id") != task.get("parent_event_id")
            or row.get("chapter") != task.get("chapter")
            or not isinstance(row.get("usage"), dict)
            or not row.get("usage")
            or row.get("row_sha256") != canonical_sha(preimage)
        ):
            raise ZBatchError(f"retry13子请求usage账错误：{task_id or '<empty>'}")
        last = attempts_by_task[task_id][-1]
        if (
            row.get("request_artifact_sha256")
            != last.get("request_artifact_sha256")
            or row.get("raw_response_sha256") != last.get("raw_response_sha256")
        ):
            raise ZBatchError(f"retry13子请求usage没有绑定成功attempt：{task_id}")
        usage_by_task[task_id] = dict(row)
    if set(usage_by_task) != set(task_by_id):
        raise ZBatchError("retry13usage账没有逐项覆盖32个子请求")

    result_paths = sorted((repair_dir / "results").glob("*.json"))
    checkpoint_roots = sorted(
        path for path in (repair_dir / "checkpoints").iterdir() if path.is_dir()
    )
    if (
        {path.stem for path in result_paths} != set(task_by_id)
        or {path.name for path in checkpoint_roots} != set(task_by_id)
        or len(result_paths) != 32
        or len(checkpoint_roots) != 32
    ):
        raise ZBatchError("retry13结果或不可变检查点不是32份唯一工件")

    run_root = run_dir.resolve()

    def bound_artifact(relative: Any, *, label: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ZBatchError(f"retry13{label}路径为空")
        path = (run_dir / relative).resolve()
        if not path.is_relative_to(run_root) or not path.is_file():
            raise ZBatchError(f"retry13{label}路径越界或不存在")
        return path

    results_by_task: dict[str, dict[str, Any]] = {}
    for task_id, task in task_by_id.items():
        result = read_json(repair_dir / f"results/{task_id}.json")
        normalized = result.get("normalized_replacement")
        if (
            result.get("schema_version") != "z83-retry13-task-result-v1"
            or result.get("status") != "contract_pass_semantic_review_pending"
            or result.get("task_id") != task_id
            or result.get("parent_event_id") != task.get("parent_event_id")
            or result.get("fact_ordinal") != task.get("fact_ordinal")
            or result.get("fact_count") != task.get("fact_count")
            or result.get("fact_target_sha256") != task.get("fact_target_sha256")
            or not isinstance(normalized, dict)
            or result.get("normalized_replacement_sha256") != canonical_sha(normalized)
            or result.get("candidate_silver_only") is not True
            or result.get("semantic_truth") is not False
        ):
            raise ZBatchError(f"retry13子请求结果不能由原子计划重建：{task_id}")
        checkpoint_root = repair_dir / f"checkpoints/{task_id}"
        seal = z83_retry_transport.validate_checkpoint_bundle(checkpoint_root)
        if (
            seal.get("mechanical_verdict") != "pass"
            or seal.get("contract_version")
            != "z83-one-to-one-single-object-repair-v1"
        ):
            raise ZBatchError(f"retry13子请求检查点不是合同PASS：{task_id}")
        checkpoint_request = read_json(checkpoint_root / "01_request.json")
        checkpoint_response = read_json(checkpoint_root / "02_response.json")
        checkpoint_usage = read_json(checkpoint_root / "03_usage.json")
        checkpoint_attempts = read_json(checkpoint_root / "04_attempts.json")["rows"]
        request_path = bound_artifact(
            checkpoint_request.get("request_artifact_path"), label="请求工件"
        )
        raw_path = bound_artifact(
            checkpoint_response.get("raw_response_path"), label="原始响应"
        )
        actual_request = read_json(request_path)
        prepared_path = bound_artifact(
            actual_request.get("prepared_request_path"), label="冻结单对象请求"
        )
        prepared_body = read_json(prepared_path)
        recomputed_wire_sha = hashlib.sha256(
            json.dumps(prepared_body, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        raw_response, content, finish_reason, raw_usage = (
            retry13_atomic._parse_sensenova_envelope(
                raw_path.read_bytes(),
                expected_model=str(checkpoint_request.get("model") or ""),
            )
        )
        rebuilt_normalized, rebuilt_diagnostics = (
            retry13_atomic.parse_single_object_result(
                content,
                catalog=_catalog(run_dir, int(task["chapter"])),
                required_anchor_ids=list(task["required_anchor_ids"]),
            )
        )
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if (
            actual_request.get("schema_version")
            != "z83-retry13-actual-request-v1"
            or actual_request.get("run_id") != run_dir.name
            or actual_request.get("logical_request_id") != task_id
            or actual_request.get("parent_event_id") != task.get("parent_event_id")
            or actual_request.get("fact_ordinal") != task.get("fact_ordinal")
            or actual_request.get("fact_count") != task.get("fact_count")
            or actual_request.get("stage") != "targeted_retry_single_object"
            or actual_request.get("contract_version")
            != "z83-one-to-one-single-object-repair-v1"
            or actual_request.get("plan_sha256") != atomic["sha256"]
            or actual_request.get("prepared_request_sha256")
            != sha256_file(prepared_path)
            or actual_request.get("body") != prepared_body
            or actual_request.get("_security") != "no_api_key_no_authorization"
            or checkpoint_request.get("logical_request_id") != task_id
            or checkpoint_response.get("logical_request_id") != task_id
            or checkpoint_usage.get("logical_request_id") != task_id
            or checkpoint_request.get("request_artifact_sha256")
            != sha256_file(request_path)
            or checkpoint_request.get("wire_body_sha256")
            != recomputed_wire_sha
            or checkpoint_request.get("model") != prepared_body.get("model")
            or raw_response.get("model") != checkpoint_request.get("model")
            or checkpoint_response.get("raw_response_sha256") != sha256_file(raw_path)
            or checkpoint_response.get("response_model")
            != raw_response.get("model")
            or checkpoint_response.get("finish_reason") != finish_reason
            or checkpoint_response.get("content_sha256") != content_sha
            or checkpoint_attempts != attempts_by_task[task_id]
            or any(
                row.get("request_sha256") != sha256_file(request_path)
                or row.get("request_artifact_sha256") != sha256_file(request_path)
                or row.get("wire_body_sha256") != recomputed_wire_sha
                for row in attempts_by_task[task_id]
            )
            or checkpoint_usage.get("usage") != raw_usage
            or usage_by_task[task_id]["usage"] != raw_usage
            or attempts_by_task[task_id][-1].get("usage") != raw_usage
            or normalized != rebuilt_normalized
            or result.get("anchor_leaf_extra_diagnostics")
            != rebuilt_diagnostics
            or result.get("request_artifact_sha256") != sha256_file(request_path)
            or result.get("wire_body_sha256") != recomputed_wire_sha
            or result.get("raw_response_sha256") != sha256_file(raw_path)
            or result.get("content_sha256") != content_sha
            or result.get("checkpoint_path")
            != checkpoint_root.relative_to(run_dir).as_posix()
            or result.get("checkpoint_id") != seal.get("checkpoint_id")
        ):
            raise ZBatchError(f"retry13子请求检查点与请求／响应／usage断链：{task_id}")
        results_by_task[task_id] = result

    replacements, rebuilt_parent_ledgers = retry13_atomic.aggregate_parent_results(
        plan, results_by_task
    )
    if metrics.get("parent_ledgers") != rebuilt_parent_ledgers:
        raise ZBatchError("retry13指标内13条父源聚合账不能从32份结果重建")
    parent_ledger_by_id = {
        str(row["parent_event_id"]): row for row in rebuilt_parent_ledgers
    }
    rebuilt_targeted_ledger: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        original = read_json(_model_file(run_dir / "main", chapter))
        lineage_original = read_json(_event_file(run_dir / "main", chapter))
        rebuilt_model = z77.apply_replacements(
            original,
            chapter=chapter,
            replacements=replacements.get(chapter, {}),
        )
        rebuilt_events, rebuilt_audit = neutral_extract.process_model_data(
            rebuilt_model,
            chapter=chapter,
            catalog=_catalog(run_dir, chapter),
        )
        receipts_by_index: dict[int, dict[str, Any]] = {}
        chapter_parents: dict[int, dict[str, Any]] = {}
        for parent in plan["parents"]:
            if int(parent["chapter"]) != chapter:
                continue
            event_id = str(parent["event_id"])
            index = int(event_id.rsplit("-", 1)[1]) - 1
            chapter_parents[index] = parent
            receipts_by_index[index] = {
                "reason_codes": list(parent["reason_codes"]),
                **parent_ledger_by_id[event_id],
            }
        prior_rows = {
            event_id: row
            for event_id, row in main_lineage["rows"].items()
            if int(event_id[4:8]) == chapter
        }
        rebuilt_lineage, descendants = _build_event_lineage(
            chapter=chapter,
            original=lineage_original,
            final=rebuilt_events,
            replacements=replacements.get(chapter, {}),
            retry_receipts=receipts_by_index,
            stage="semantic_targeted_retry_atomic_program_split",
            prior_rows=prior_rows,
        )
        if (
            rebuilt_model != read_json(_model_file(repair_dir, chapter))
            or rebuilt_events != read_json(_event_file(repair_dir, chapter))
            or rebuilt_audit
            != read_json(
                repair_dir / f"01_extract/program_audits/ch{chapter:04d}.json"
            )
            or rebuilt_lineage != read_json(_lineage_file(repair_dir, chapter))
        ):
            raise ZBatchError(
                f"retry13第{chapter}章修复产物不能从32份原子结果反向重建"
            )
        for index, receipt in sorted(receipts_by_index.items()):
            input_event_id = str(original["events"][index]["event_id"])
            parent = chapter_parents[index]
            if input_event_id != parent["event_id"]:
                raise ZBatchError(
                    f"retry13父源位置与原始事件错位：{input_event_id}"
                )
            row = {
                "schema_version": "z83-retry13-parent-rewrite-ledger-v1",
                "chapter": chapter,
                "original_event_id": input_event_id,
                "original_event_sha256": parent["event_sha256"],
                "source_event_id": parent["source_event_id"],
                "source_event_sha256": parent["source_event_sha256"],
                "source_identity_sha256": parent["source_identity_sha256"],
                "source_retry_count_before": prior_rows[input_event_id][
                    "retry_count"
                ],
                "source_retry_count_after": prior_rows[input_event_id]["retry_count"]
                + 1,
                "reason_codes": list(parent["reason_codes"]),
                "materialized_event_ids": descendants[input_event_id],
                "replacement_count": receipt["replacement_count"],
                "child_results": receipt["child_results"],
                "fact_closed_set_semantic_review": "pending_not_inferred_from_sha",
            }
            row["row_sha256"] = canonical_sha(row)
            rebuilt_targeted_ledger.append(row)
    if z68.read_jsonl(repair_dir / "targeted_retry_ledger.jsonl") != (
        rebuilt_targeted_ledger
    ):
        raise ZBatchError(
            "retry13的13条父源物化账不能从32份结果逐行重建"
        )

    parent_metrics = metrics.get("parent_ledgers")
    if not isinstance(parent_metrics, list) or len(parent_metrics) != 13:
        raise ZBatchError("retry13指标账缺13条父源聚合账")
    parent_metric_by_id = {
        str(row.get("parent_event_id") or ""): row
        for row in parent_metrics
        if isinstance(row, dict)
    }
    if len(parent_metric_by_id) != 13 or set(parent_metric_by_id) != set(atomic["parents"]):
        raise ZBatchError("retry13指标内父源聚合账身份错误")
    ledger = z68.read_jsonl(repair_dir / "targeted_retry_ledger.jsonl")
    for row in ledger:
        parent_id = str(row.get("original_event_id") or "")
        metric_row = parent_metric_by_id.get(parent_id)
        if (
            metric_row is None
            or metric_row.get("status") != "complete_parent_aggregated_once"
            or metric_row.get("replacement_count") != row.get("replacement_count")
            or metric_row.get("child_results") != row.get("child_results")
            or metric_row.get("fact_closed_set_semantic_review")
            != "pending_not_inferred_from_sha"
        ):
            raise ZBatchError(f"retry13父源指标账与物化账断链：{parent_id}")
        for child in row["child_results"]:
            task_id = str(child["task_id"])
            normalized = results_by_task[task_id]["normalized_replacement"]
            if child.get("replacement_sha256") != canonical_sha(normalized):
                raise ZBatchError(f"retry13父源账不能追到子请求结果：{task_id}")

    repair_lineage = _validate_retry13_repair_lineage(run_dir)
    repair_mechanical = verify_event_stage(
        run_dir,
        repair_dir,
        schema_version="z83-retry13-repair-mechanical-verification-v1",
    )
    if metrics.get(
        "mechanical_verification_sha256"
    ) != retry13_atomic._stable_mechanical_verification_sha256(repair_mechanical):
        raise ZBatchError("retry13指标账没有绑定机械复验票")
    final_manifest = read_json(final_dir / "run_manifest.json")
    if (
        final_manifest.get("schema_version")
        != "z83-retry13-final-event-manifest-v1"
        or final_manifest.get("status") != "awaiting_targeted_semantic_review"
        or final_manifest.get("source_atomic_plan_sha256") != atomic["sha256"]
        or final_manifest.get("parent_rewrite_count") != 13
        or final_manifest.get("logical_request_count") != 32
        or final_manifest.get("candidate_silver_only") is not True
        or z68.tree_fingerprint(final_dir / "01_extract")
        != z68.tree_fingerprint(repair_dir / "01_extract")
    ):
        raise ZBatchError("retry13最终事件不能逐字追溯到原子化修复产物")
    final_lineage = _load_stage_lineage(final_dir)
    if final_lineage != repair_lineage["rows"]:
        raise ZBatchError("retry13最终稳定血缘账不等于修复血缘账")
    final_mechanical = verify_event_stage(
        run_dir,
        final_dir,
        schema_version="z83-final-mechanical-verification-v1",
    )
    receipt = {
        "schema_version": "z83-call-lineage-verification-v1",
        "status": "pass",
        "repair_contract": "retry13_atomic_single_object",
        "main_network_attempts": main_attempts,
        "main_targeted_retry_calls": main_retry_count,
        "main_seeded_chapters": seed_receipt["chapters"] if seed_receipt else [],
        "main_imported_network_attempts": imported_attempts,
        "repair_network_attempts": len(attempts),
        "repair_parent_rewrite_count": 13,
        "repair_logical_request_count": 32,
        "repair_declared_review_event_count": 32,
        "repair_materialized_event_count": 175,
        "stable_source_count": main_lineage["stable_source_count"],
        "main_retried_source_count": main_lineage["retried_source_count"],
        "repair_semantic_retry_count": repair_lineage["semantic_retry_count"],
        "main_mechanical_sha256": canonical_sha(main_mechanical),
        "repair_mechanical_sha256": canonical_sha(repair_mechanical),
        "final_mechanical_sha256": canonical_sha(final_mechanical),
        "atomic_plan_sha256": atomic["sha256"],
        "targeted_retry_ledger_sha256": repair_lineage[
            "targeted_retry_ledger_sha256"
        ],
        "final_tree_equals_repair_tree": True,
        "prompt_v3_unchanged": True,
    }
    write_json(final_dir / "call_lineage_verification.json", receipt)
    return receipt


def verify_call_lineage(
    run_dir: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """把最终事件追到唯一主采样、已审计划和定点重写，不接受手拼final。"""

    verify_prepared(
        run_dir,
        require_zero_call=False,
        allow_test_run_dir=allow_test_run_dir,
    )
    main_dir = run_dir / "main"
    repair_dir = run_dir / "repair"
    final_dir = run_dir / "final"
    for label, path in (
        ("主采样", main_dir),
        ("定点重写", repair_dir),
        ("最终事件", final_dir),
    ):
        if (path / "hard_stop.json").exists():
            raise ZBatchError(f"{label}阶段已有硬停票，不能进入最终判分")
    main_claim = read_json(main_dir / "run_claim.json")
    main_manifest = read_json(main_dir / "run_manifest.json")
    main_metrics = read_json(main_dir / "01_extract/metrics.json")
    main_attempts = len(z68.read_jsonl(main_dir / "call_attempts.jsonl"))
    main_retry_count = main_manifest.get("targeted_retry_count")
    seed_receipt = (
        verify_main_seed(run_dir, allow_test_run_dir=allow_test_run_dir)
        if (run_dir / MAIN_SEED_MANIFEST).is_file()
        else None
    )
    imported_attempts = (
        int(seed_receipt["imported_network_attempts"])
        if seed_receipt is not None
        else 0
    )
    expected_seeded = list(seed_receipt["chapters"]) if seed_receipt is not None else []
    expected_new = [
        chapter for chapter in TARGET_CHAPTERS if chapter not in expected_seeded
    ]
    if (
        main_manifest.get("status") != "completed_candidate_silver_only"
        or main_manifest.get("run_claim") != main_claim
        or main_manifest.get("chapters_completed") != list(TARGET_CHAPTERS)
        or isinstance(main_retry_count, bool)
        or not isinstance(main_retry_count, int)
        or not 0 <= main_retry_count <= MAX_TARGETED_RETRIES_TOTAL
        or main_manifest.get("network_attempts") != main_attempts
        or not 3 <= main_attempts <= MAX_NETWORK_ATTEMPTS
        or main_metrics.get("main_logical_calls") != len(TARGET_CHAPTERS)
        or main_metrics.get("targeted_retry_logical_calls") != main_retry_count
        or main_metrics.get("network_attempts") != main_attempts
        or main_metrics.get("successful_responses")
        != len(TARGET_CHAPTERS) + main_retry_count
    ):
        raise ZBatchError("主采样调用血缘、计数或占用票错误")
    if seed_receipt is not None and (
        main_manifest.get("seeded_chapters") != expected_seeded
        or main_manifest.get("newly_sampled_chapters") != expected_new
        or main_manifest.get("network_attempts_imported") != imported_attempts
        or main_manifest.get("source_incomplete_attempts_not_imported")
        != seed_receipt["source_incomplete_attempts_not_imported"]
        or main_manifest.get("main_seed") != seed_receipt
        or main_metrics.get("seeded_chapters") != expected_seeded
        or main_metrics.get("newly_sampled_chapters") != expected_new
        or main_metrics.get("main_live_logical_calls") != len(expected_new)
        or main_metrics.get("main_reused_logical_samples") != len(expected_seeded)
        or main_metrics.get("network_attempts_imported") != imported_attempts
        or main_metrics.get("network_attempts_this_run")
        != main_attempts - imported_attempts
        or main_metrics.get("source_incomplete_attempts_not_imported")
        != seed_receipt["source_incomplete_attempts_not_imported"]
        or main_metrics.get("main_seed") != seed_receipt
    ):
        raise ZBatchError("主采样复用血缘没有贯穿状态票与指标账")
    formal_completed_target = _formal_completed_seed_target(run_dir)
    formal_completed_seed = bool(
        seed_receipt is not None
        and seed_receipt.get("source_kind") == "completed_main_retry03"
    )
    if formal_completed_target and not formal_completed_seed:
        raise ZBatchError(
            "retry04至retry12没有复用已拍续令批准的retry03完整三章"
        )
    if formal_completed_seed:
        event_sha = {
            str(chapter): sha256_file(_event_file(main_dir, chapter))
            for chapter in TARGET_CHAPTERS
        }
        expected_event_sha = {
            str(chapter): value
            for chapter, value in APPROVED_COMPLETED_EVENT_SHA256.items()
        }
        if (
            expected_seeded != list(TARGET_CHAPTERS)
            or expected_new
            or main_retry_count != 0
            or main_attempts != 3
            or imported_attempts != 3
            or main_metrics.get("network_attempts_this_run") != 0
            or main_metrics.get("main_live_logical_calls") != 0
            or main_metrics.get("targeted_retry_logical_calls") != 0
            or main_metrics.get("usage_totals")
            != {
                "prompt_tokens": 33438,
                "completion_tokens": 49859,
                "total_tokens": 83297,
            }
            or event_sha != expected_event_sha
        ):
            raise ZBatchError("完整复用主样张零新调用、成本账或事件SHA钢线不成立")
    if seed_receipt is None and (
        (main_dir / "seed_provenance").exists()
        or main_manifest.get("seeded_chapters") != []
        or main_manifest.get("newly_sampled_chapters") != list(TARGET_CHAPTERS)
        or main_manifest.get("network_attempts_imported") != 0
        or main_manifest.get("source_incomplete_attempts_not_imported") != 0
        or main_manifest.get("main_seed") is not None
        or main_metrics.get("seeded_chapters") != []
        or main_metrics.get("newly_sampled_chapters") != list(TARGET_CHAPTERS)
        or main_metrics.get("main_live_logical_calls") != len(TARGET_CHAPTERS)
        or main_metrics.get("main_reused_logical_samples") != 0
        or main_metrics.get("network_attempts_imported") != 0
        or main_metrics.get("network_attempts_this_run") != main_attempts
        or main_metrics.get("source_incomplete_attempts_not_imported") != 0
        or main_metrics.get("main_seed") is not None
    ):
        raise ZBatchError("主采样复用标记与复用清单双向不一致")
    main_samples = _validate_main_sample_exchanges(run_dir)
    if main_metrics.get("main_sample_ledger") != [
        main_samples[chapter] for chapter in TARGET_CHAPTERS
    ]:
        raise ZBatchError("主采样指标内的请求－响应账与独立账不一致")
    main_mechanical = verify_event_stage(
        run_dir, main_dir, schema_version="z83-main-mechanical-verification-v1"
    )
    main_lineage = _validate_main_lineage(run_dir)
    main_retry_ledger = z68.read_jsonl(main_dir / "targeted_retry_ledger.jsonl")
    if main_lineage["retried_source_count"] != main_retry_count:
        raise ZBatchError("主采样机械重写次数与稳定源血缘账不一致")
    if main_metrics.get("targeted_retry_ledger") != main_retry_ledger:
        raise ZBatchError("主采样指标内的机械重写账与独立账不一致")
    _validate_main_retry_exchanges(run_dir, main_retry_ledger)
    main_expected_calls = {
        ("neutral_extract", f"z83_main_ch{chapter:04d}") for chapter in TARGET_CHAPTERS
    } | {("targeted_retry", str(row.get("case_id") or "")) for row in main_retry_ledger}
    if (
        len(
            _validate_attempt_inventory(
                run_dir=run_dir,
                stage_dir=main_dir,
                expected_calls=main_expected_calls,
            )
        )
        != main_attempts
    ):
        raise ZBatchError("主采样尝试账总数与全量清点不一致")

    if _formal_atomic_split_target(run_dir):
        return _verify_retry13_call_lineage(
            run_dir,
            main_attempts=main_attempts,
            main_retry_count=main_retry_count,
            seed_receipt=seed_receipt,
            imported_attempts=imported_attempts,
            main_lineage=main_lineage,
            main_mechanical=main_mechanical,
        )

    plan_path = repair_dir / "retry_plan.json"
    plan = _validate_retry_plan(run_dir, plan_path)
    tasks = plan["tasks"]
    repair_claim = read_json(repair_dir / "run_claim.json")
    repair_manifest = read_json(repair_dir / "run_manifest.json")
    repair_metrics = read_json(repair_dir / "01_extract/metrics.json")
    repair_attempts = len(z68.read_jsonl(repair_dir / "call_attempts.jsonl"))
    repair_ledger = z68.read_jsonl(repair_dir / "targeted_retry_ledger.jsonl")
    if (
        repair_manifest.get("status") != "completed_candidate_silver_only"
        or repair_manifest.get("run_claim") != repair_claim
        or repair_manifest.get("targeted_retry_count") != len(tasks)
        or repair_manifest.get("network_attempts") != repair_attempts
        or repair_metrics.get("targeted_retry_logical_calls") != len(tasks)
        or repair_metrics.get("network_attempts") != repair_attempts
        or repair_metrics.get("successful_responses") != len(tasks)
        or len(repair_ledger) != len(tasks)
        or len({str(row.get("original_event_id")) for row in repair_ledger})
        != len(repair_ledger)
        or not 0 <= repair_attempts <= MAX_NETWORK_ATTEMPTS
    ):
        raise ZBatchError("定点重写调用血缘、计数或占用票错误")
    repair_mechanical = verify_event_stage(
        run_dir, repair_dir, schema_version="z83-repair-mechanical-verification-v1"
    )
    if repair_metrics.get("targeted_retry_ledger") != repair_ledger:
        raise ZBatchError("定点重写指标内调用账与独立账不一致")
    _validate_semantic_retry_exchanges(run_dir, tasks=tasks, ledger=repair_ledger)
    if _formal_anchor_field_strip_target(run_dir):
        diagnostic_path = run_dir / RETRY12_ANCHOR_EXTRA_FIELD_LEDGER
        diagnostic_rows = (
            z68.read_jsonl(diagnostic_path) if diagnostic_path.is_file() else []
        )
        expected_diagnostic_summary = {
            "status": "diagnostic_observation_not_truth",
            "path": (
                diagnostic_path.relative_to(run_dir).as_posix()
                if diagnostic_path.is_file()
                else None
            ),
            "sha256": (
                sha256_file(diagnostic_path) if diagnostic_path.is_file() else None
            ),
            "row_count": len(diagnostic_rows),
            "formal_quote_source": "frozen_evidence_catalog_by_anchor_id",
            "entered_formal_record": False,
        }
        if (
            repair_metrics.get("anchor_extra_field_strip_diagnostics")
            != expected_diagnostic_summary
            or repair_manifest.get("anchor_extra_field_strip_diagnostics")
            != expected_diagnostic_summary
        ):
            raise ZBatchError("retry12锚字段剥离旁账摘要与运行票不能重建")
    repair_expected_calls = {
        ("targeted_retry", str(row.get("case_id") or "")) for row in repair_ledger
    }
    if (
        len(
            _validate_attempt_inventory(
                run_dir=run_dir,
                stage_dir=repair_dir,
                expected_calls=repair_expected_calls,
            )
        )
        != repair_attempts
    ):
        raise ZBatchError("定点重写尝试账总数与全量清点不一致")
    repair_lineage = _validate_repair_lineage(run_dir)
    final_manifest = read_json(final_dir / "run_manifest.json")
    if (
        final_manifest.get("status") != "awaiting_final_semantic_review"
        or final_manifest.get("source_retry_plan_sha256") != sha256_file(plan_path)
        or final_manifest.get("targeted_retry_count") != len(tasks)
        or z68.tree_fingerprint(final_dir / "01_extract")
        != z68.tree_fingerprint(repair_dir / "01_extract")
    ):
        raise ZBatchError("最终事件不能逐字追溯到已审定点重写产物")
    final_lineage = _load_stage_lineage(final_dir)
    if final_lineage != repair_lineage["rows"]:
        raise ZBatchError("最终稳定血缘账不等于定点重写血缘账")
    final_mechanical = verify_event_stage(
        run_dir, final_dir, schema_version="z83-final-mechanical-verification-v1"
    )
    receipt = {
        "schema_version": "z83-call-lineage-verification-v1",
        "status": "pass",
        "main_network_attempts": main_attempts,
        "main_targeted_retry_calls": main_retry_count,
        "main_seeded_chapters": seed_receipt["chapters"] if seed_receipt else [],
        "main_imported_network_attempts": imported_attempts,
        "repair_network_attempts": repair_attempts,
        "repair_targeted_retry_calls": len(tasks),
        "stable_source_count": main_lineage["stable_source_count"],
        "main_retried_source_count": main_lineage["retried_source_count"],
        "repair_semantic_retry_count": repair_lineage["semantic_retry_count"],
        "main_mechanical_sha256": canonical_sha(main_mechanical),
        "repair_mechanical_sha256": canonical_sha(repair_mechanical),
        "final_mechanical_sha256": canonical_sha(final_mechanical),
        "retry_plan_sha256": sha256_file(plan_path),
        "final_tree_equals_repair_tree": True,
        "prompt_v3_unchanged": True,
    }
    write_json(final_dir / "call_lineage_verification.json", receipt)
    return receipt


def finalize(
    run_dir: Path,
    adjudication_path: Path,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    if (run_dir / "final/scorecard.json").exists():
        raise ZBatchError("最终成绩单已存在，拒绝改判覆盖或挑结果")
    require_inspector_complete(run_dir, phase="final")
    validated = validate_adjudication(run_dir, adjudication_path, phase="final")
    call_lineage = verify_call_lineage(
        run_dir,
        allow_test_run_dir=allow_test_run_dir,
    )
    mechanical = verify_event_stage(
        run_dir,
        run_dir / "final",
        schema_version="z83-final-mechanical-verification-v1",
    )
    gold_rows = list(validated["gold_rows"].values())
    gold_summary = z75_score.score_summary(gold_rows, 23)
    current_summary = _summary_current(validated["current_rows"].values())
    invalid_event_ids = sorted(
        event_id
        for event_id, row in validated["anchor_rows"].items()
        if row["verdict"] == "invalid"
    )
    blocking_program_risk_ids = sorted(
        risk_id
        for risk_id, row in validated["risk_rows"].items()
        if row["verdict"] == "retry_required"
    )
    gates = {
        "mechanical_three_gates": mechanical["status"] == "pass"
        and all(mechanical["gates"].values()),
        "old25_zero_regression": current_summary["gate_pass"],
        "chapter3_gold_floor": gold_summary["strict_hit"] >= 10
        and gold_summary["effective_recall"] >= 19,
        "semantic_anchor_invalid_zero": not invalid_event_ids,
    }
    all_pass = all(gates.values()) and not blocking_program_risk_ids
    usage_paths = [run_dir / "main/usage.jsonl", run_dir / "repair/usage.jsonl"]
    for phase_name in ("review", "final_review"):
        inspector_root = run_dir / phase_name / "inspector"
        if inspector_root.is_dir():
            usage_paths.extend(inspector_root.rglob("usage.jsonl"))
    usage = _usage_summary(*usage_paths)
    receipt = {
        "schema_version": "z83-final-scorecard-v1",
        "status": "pass_candidate_ready_for_cz"
        if all_pass
        else "hard_stop_candidate_failed",
        "all_pass": all_pass,
        "four_gates": gates,
        "gold_chapter_3": gold_summary,
        "current_record_subset_25": current_summary,
        "semantic_anchor_gate": {
            "invalid_count": len(invalid_event_ids),
            "invalid_event_ids": invalid_event_ids,
            "required": 0,
            "gate_pass": not invalid_event_ids,
        },
        "program_risk_precondition": {
            "blocking_count": len(blocking_program_risk_ids),
            "blocking_risk_ids": blocking_program_risk_ids,
            "required": 0,
            "passed": not blocking_program_risk_ids,
        },
        "transport": usage,
        "call_lineage": call_lineage,
        "prompt_v3_unchanged": True,
        "source_adjudication": {
            "path": adjudication_path.as_posix(),
            "sha256": validated["source_sha256"],
        },
        "event_set_sha256": validated["event_set_sha256"],
        "protected_unchanged": protected_snapshot()
        == read_json(run_dir / "preflight.json")["protected_before"],
        "formal_artifacts_mutated": 0,
        "decision": (
            "四闸全过，只登记首个可上桌银标候选；固化与跨书复验另拍。"
            if all_pass
            else "任一闸未过，按令硬停留档，不缝补。"
        ),
    }
    if not receipt["protected_unchanged"]:
        raise ZBatchError("最终验收发现保护件漂移")
    write_json(run_dir / "final/scorecard.json", receipt)
    master = read_json(run_dir / "run_manifest.json")
    master["status"] = receipt["status"]
    master["final"] = receipt["status"]
    write_json_atomic(run_dir / "run_manifest.json", master)
    return receipt


def record_pre_send_block(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_test_run_dir: bool = False,
) -> dict[str, Any]:
    """把缺密钥记成可续跑的发网前停点，不创建运行占用票。"""

    verify_prepared(
        run_dir,
        require_zero_call=True,
        allow_test_run_dir=allow_test_run_dir,
    )
    if os.environ.get("SENSENOVA_API_KEY"):
        raise ZBatchError("密钥已存在，不应登记缺密钥停点")
    receipt = {
        "schema_version": "z83-pre-send-block-v1",
        "status": "blocked_before_network_missing_api_key",
        "reason": "当前Codex进程未载入SENSENOVA_API_KEY",
        "model_api_calls": 0,
        "network_attempts": 0,
        "run_claim_created": False,
        "prepared_run_reusable_after_key_loaded": True,
        "prompt_v3_unchanged": True,
        "protected_unchanged": True,
    }
    write_json(run_dir / "pre_send_block.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "verify-prepared",
            "seed-main",
            "run-main",
            "verify-main",
            "build-review",
            "run-inspector",
            "reuse-retry08-inspector",
            "audit-retry-capacity",
            "reuse-retry09-adjudication",
            "plan-retries",
            "preflight-retries",
            "run-retries",
            "build-final-review",
            "run-final-inspector",
            "finalize",
            "record-pre-send-block",
        ),
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--seed-run-dir", type=Path)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument(
        "--inspector-max-tokens",
        type=int,
        choices=(INSPECTOR_BASE_MAX_TOKENS, INSPECTOR_COMPAT_MAX_TOKENS),
        default=INSPECTOR_BASE_MAX_TOKENS,
    )
    parser.add_argument("--allow-test-run-dir", action="store_true")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    assert_safe_run_dir(run_dir, allow_test_run_dir=args.allow_test_run_dir)
    if args.action == "prepare":
        result = prepare(
            run_dir,
            inspector_max_tokens=args.inspector_max_tokens,
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "verify-prepared":
        result = verify_prepared(
            run_dir,
            require_zero_call=not bool(call_artifacts_present(run_dir)),
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "seed-main":
        if args.seed_run_dir is None:
            parser.error("seed-main必须提供--seed-run-dir")
        result = seed_main_samples(
            run_dir,
            args.seed_run_dir.resolve(),
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "run-main":
        result = run_main(run_dir, allow_test_run_dir=args.allow_test_run_dir)
    elif args.action == "verify-main":
        result = verify_main(
            run_dir,
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "build-review":
        result = build_review(run_dir, phase="main")
    elif args.action == "run-inspector":
        result = run_inspector(
            run_dir,
            phase="main",
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "reuse-retry08-inspector":
        result = reuse_retry08_inspector_evidence(
            run_dir,
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "audit-retry-capacity":
        if args.adjudication is None:
            parser.error("audit-retry-capacity必须提供--adjudication")
        result = record_retry09_capacity_hard_stop(
            run_dir,
            args.adjudication.resolve(),
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "reuse-retry09-adjudication":
        result = reuse_retry09_adjudication_and_authorized_set(
            run_dir,
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "plan-retries":
        if args.adjudication is None:
            parser.error("plan-retries必须提供--adjudication")
        result = plan_retries(run_dir, args.adjudication.resolve())
    elif args.action == "preflight-retries":
        result = preflight_retries(run_dir)
    elif args.action == "run-retries":
        result = run_retries(run_dir)
    elif args.action == "build-final-review":
        result = build_review(run_dir, phase="final")
    elif args.action == "run-final-inspector":
        result = run_inspector(
            run_dir,
            phase="final",
            allow_test_run_dir=args.allow_test_run_dir,
        )
    elif args.action == "finalize":
        if args.adjudication is None:
            parser.error("finalize必须提供--adjudication")
        result = finalize(
            run_dir,
            args.adjudication.resolve(),
            allow_test_run_dir=args.allow_test_run_dir,
        )
    else:
        result = record_pre_send_block(
            run_dir, allow_test_run_dir=args.allow_test_run_dir
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
