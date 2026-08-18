#!/usr/bin/env python3
"""novel-mvp 命令行入口（M0 编排器）。用法见 README.md。

只做参数解析、模块调用和打印；业务逻辑在 mvp/ 各模块，
跨模块数据格式见 contracts/（C1–C4、C6、C7）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mvp import admission
from mvp import ask as qa
from mvp import check as hc
from mvp import extract as ex
from mvp import ingest, plan as pl
from mvp import refine, segment, store


def cmd_init(args):
    d = store.init_project(args.project)
    print(f"项目已建：{d}")


def cmd_ingest(args):
    kind = "outline" if args.outline else "draft"
    declaration_manifest = None
    declarations_path = getattr(args, "declarations", None)
    material_role = getattr(args, "material_role", None)
    if args.outline and (declarations_path is not None or material_role is not None):
        raise SystemExit("--outline 不能与 --material-role／--declarations 同时使用")
    if declarations_path is not None:
        try:
            declaration_manifest = json.loads(Path(declarations_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"读不了 declarations JSON：{exc}") from exc
    report = ingest.ingest_files(
        args.project,
        args.files,
        kind=kind,
        title=args.title,
        on_imported=lambda ch, n: print(f"已导入 {ch['id']}［{kind}］{ch['title']}（{n} 字）"),
        material_role=material_role,
        declaration_manifest=declaration_manifest,
    )
    material_count = len(report.get("material_units", []))
    if kind == "draft":
        print(f"C10 material units：{material_count}；Chapter C1：{report['count']}")
    for w in report["warnings"]:
        print(f"⚠️ {w}")


def prepare_m3_segments(chapter: dict, cfg: dict) -> tuple[list[dict], dict]:
    """让现役抽取路径只消费 Pre-M3 准入门放行的精确原文片段。"""
    receipt = admission.apply_pre_m3_admission(chapter)
    if receipt["status"] != "READY":
        return [], receipt

    segments: list[dict] = []
    for target in receipt["m3_eligible_targets"]:
        built = segment.segment_chapter(
            target["text"], cfg["seg_min_chars"], cfg["seg_max_chars"], cfg["halo_chars"]
        )
        for item in built:
            segments.append({**item, "seg": len(segments) + 1})
    return segments, receipt


def cmd_extract(args):
    chs = store.chapters(args.project)
    targets = [c for c in chs if c["kind"] == "draft"]
    if args.chapter:
        targets = [c for c in targets if c["id"] == args.chapter]
    if not targets:
        raise SystemExit("没有可抽取的正文章节（大纲章不走抽取）")
    cfg = ex.load_config()
    print(f"模型：{cfg['model_id']}（改 config.json 可换）")
    for ch in targets:
        done = {f.get("seg") for f in store.facts(args.project) if f["chapter_id"] == ch["id"]}
        if done and not args.redo:
            print(f"{ch['id']} 已有抽取结果，跳过（--redo 强制重抽）")
            continue
        print(f"\n抽取 {ch['id']}《{ch['title']}》…")
        segs, admission_receipt = prepare_m3_segments(ch, cfg)
        if admission_receipt["status"] != "READY":
            print(f"  ⚠️ Pre-M3 准入未放行（{admission_receipt['status']}），本章未调用模型")
            continue
        isolated_count = len(admission_receipt["isolated_author_note_segments"])
        if isolated_count:
            print(f"  已隔离作者提示 {isolated_count} 段，不进入 M3")
        cands, errors, ok = [], [], 0
        for seg in segs:
            print(f"  段 {seg['seg']}/{len(segs)}（{len(seg['text'])} 字）调用中…", flush=True)
            try:
                cands.extend(ex.extract_segment(seg, cfg))
                ok += 1
            except RuntimeError as e:
                errors.append(f"段{seg['seg']}: {e}")
        n = store.add_fact_candidates(args.project, ch["id"], cands, source=cfg["model_id"])
        print(f"  完成：{len(segs)} 段，成功 {ok} 次，入库候选 {n} 条")
        for e in errors:
            print(f"  ⚠️ {e}")


def cmd_refine(args):
    import json as _json

    chs = [c for c in store.chapters(args.project) if c["id"] == args.chapter]
    if not chs:
        raise SystemExit(f"章节不存在：{args.chapter}")
    ch = chs[0]
    cfg = ex.load_config()
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    bad = [s for s in stages if s not in refine.ALL_STAGES]
    if bad:
        raise SystemExit(f"未知管线段：{bad}（可选：{','.join(refine.ALL_STAGES)}）")
    segs, admission_receipt = prepare_m3_segments(ch, cfg)
    if admission_receipt["status"] != "READY":
        raise SystemExit(
            f"Pre-M3 准入未放行（{admission_receipt['status']}），未调用主抽或质检模型"
        )

    if args.fresh:
        print(f"主抽 {ch['id']}《{ch['title']}》（{cfg['model_id']}）…")
        main_cands = []
        for seg in segs:
            print(f"  段 {seg['seg']}/{len(segs)} 调用中…", flush=True)
            main_cands.extend(ex.extract_segment(seg, cfg))
    else:
        main_cands = [
            {"text": f["text"], "quote": f.get("quote", ""), "seg": f.get("seg")}
            for f in store.facts(args.project)
            if f["chapter_id"] == ch["id"] and f["status"] != store.STATUS_REJECTED
        ]
        if not main_cands:
            raise SystemExit(f"{ch['id']} 库里没有候选；先 extract，或加 --fresh 现场主抽")
        print(f"复用库里 {ch['id']} 的 {len(main_cands)} 条候选当主抽结果")

    print(f"质检模型：{cfg.get('checker_model_id', cfg['model_id'])}（管线段：{','.join(stages)}）")
    report = refine.run_pipeline(
        segs, main_cands, cfg, stages,
        on_call=lambda r: print(f"  [{r['stage']}·段{r['seg']}] {r['model']}：{r['seconds']}s", flush=True))
    print("\n" + refine.format_receipt(report))
    out = store.project_dir(args.project) / f"refine_{ch['id']}.json"
    out.write_text(_json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完整报告已存：{out}")


def cmd_candidates(args):
    chapters = [item for item in store.chapters(args.project) if item["id"] == args.chapter]
    if len(chapters) != 1:
        raise SystemExit(f"章节不存在：{args.chapter}")
    admission_receipt = admission.apply_pre_m3_admission(chapters[0])
    if admission_receipt["status"] != "READY":
        raise SystemExit(
            f"Pre-M3 准入未放行（{admission_receipt['status']}），未载入外部候选"
        )
    items = ex.load_candidates_file(args.json_file)
    n = store.add_fact_candidates(args.project, args.chapter, items, source=Path(args.json_file).name)
    print(f"已载入候选 {n} 条")


def cmd_confirm(args):
    pend = [
        f for f in store.facts(args.project)
        if isinstance(f, dict) and f.get("status") == store.STATUS_EXTRACTED
    ]
    if args.chapter:
        pend = [f for f in pend if f["chapter_id"] == args.chapter]
    if not pend:
        print("没有待确认的候选")
        return
    print(f"待确认 {len(pend)} 条。y=采纳 n=拒绝 s=跳过 e=改写后采纳 q=退出\n")
    for f in pend:
        print(f"[{f['id']}·{f['chapter_id']}] {f['text']}")
        if f.get("quote"):
            print(f"    依据：…{f['quote'][:80]}…")
        try:
            ans = input("  > ").strip().lower()
        except EOFError:
            print("\n输入结束，确认中止。")
            break
        if ans == "q":
            break
        elif ans == "y":
            store.set_status(args.project, f["id"], store.STATUS_CONFIRMED)
        elif ans == "n":
            store.set_status(args.project, f["id"], store.STATUS_REJECTED)
        elif ans == "e":
            try:
                new = input("  改写为：").strip()
            except EOFError:
                print("\n输入结束，确认中止。")
                break
            if new:
                store.review_fact(
                    args.project,
                    f["id"],
                    decision="edit_and_confirm",
                    replacement_text=new,
                )
        # s 或其他输入 = 跳过
    print("\n确认结束。")


def cmd_ask(args):
    hits = qa.search_confirmed(args.project, args.keywords)
    if not hits:
        print(f"已确认事实里没有同时含 {args.keywords} 的条目")
        return
    print(f"命中 {len(hits)} 条：\n")
    for f in hits:
        print(f"[{f['chapter_id']}《{f['chapter_title']}》] {f['text']}")
        if f.get("quote"):
            print(f"    原文：…{f['quote'][:100]}…")
        print()


def cmd_check(args):
    if args.plan:
        print(hc.format_plan(args.project))
        return
    cfg = ex.load_config()
    print(f"模型：{cfg['model_id']}（一组事实一次调用）")
    report = hc.run_check(
        args.project, cfg,
        on_group=lambda name, i, n, size: print(f"  [{i}/{n}] 组「{name}」（{size} 条）调用中…", flush=True),
    )
    print(hc.format_report(report))
    path = hc.save_report(args.project, report)
    print(f"\n报告已存：{path}")


def cmd_plan(args):
    report = pl.run_plan(
        args.project, args.purpose,
        purpose_note=args.note or "",
        reverse=args.reverse,
        stub=args.stub,
        chapter_intent=args.intent or "",
    )
    print(pl.format_plan(report))
    path = pl.save_plan(args.project, report)
    print(f"\n计划已存：{path}（计划，不入事实账）")


def cmd_repair_ids(args):
    report = store.repair_ids(args.project)
    if not report["remap"]:
        print(f"账本干净：{report['total']} 条事实号全部唯一，无需修账")
        return
    print(f"修账完成：{report['total']} 条里 {len(report['remap'])} 条撞号后到者已迁新号")
    for r in report["remap"]:
        seg = f"·段{r['seg']}" if r.get("seg") else ""
        print(f"  {r['old']} → {r['new']}  [{r['chapter_id']}{seg}] {r['text']}")
    print(f"报告已存：{store.project_dir(args.project) / 'repair_ids_report.json'}")
    print("👉 旧体检报告里的事实号已过期，重跑 check 才算数")


def cmd_status(args):
    chs = store.chapters(args.project)
    fs = store.facts(args.project)
    by = lambda s: sum(1 for f in fs if f["status"] == s)  # noqa: E731
    print(f"项目：{args.project}")
    print(f"章节：{len(chs)} 篇（正文 {sum(1 for c in chs if c['kind'] == 'draft')}，大纲 {sum(1 for c in chs if c['kind'] == 'outline')}）")
    for c in chs:
        nf = sum(1 for f in fs if f["chapter_id"] == c["id"])
        print(f"  {c['id']}［{c['kind']}］{c['title']}（{len(c['text'])} 字，事实 {nf} 条）")
    print(f"事实账：候选 {by('extracted')} / 已确认 {by('confirmed')} / 已拒绝 {by('rejected')}")


def main():
    ap = argparse.ArgumentParser(prog="novel-mvp", description="故事真源引擎 MVP")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="新建项目")
    p.add_argument("project")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("ingest", help="C10-first 导入明确材料或兼容导入大纲")
    p.add_argument("project")
    p.add_argument("files", nargs="+")
    p.add_argument("--outline", action="store_true", help="按大纲导入（不走抽取）")
    p.add_argument("--title", help="章节标题（默认取文件名）")
    identity = p.add_mutually_exclusive_group()
    identity.add_argument(
        "--material-role",
        choices=["chapter", "intro", "setting", "title", "tags", "unknown"],
        help="用户明确声明整份／整批材料身份；不填时按 Unknown 保存，0 C1",
    )
    identity.add_argument(
        "--declarations",
        help="精确 C10 declarations JSON；单 source 用数组，多 source 用 source_name→数组对象",
    )
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("extract", help="调用模型抽取事实句候选")
    p.add_argument("project")
    p.add_argument("--chapter", help="只抽某一章，如 c01")
    p.add_argument("--redo", action="store_true", help="已有结果也重抽")
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser("refine", help="抽取质检管线：引文回填→补漏→验真→去噪→去重（质检用另一家 API）")
    p.add_argument("project")
    p.add_argument("--chapter", required=True, help="要精修的章，如 c01")
    p.add_argument("--fresh", action="store_true", help="现场重新主抽（默认复用库里该章候选）")
    p.add_argument("--stages", default=",".join(refine.ALL_STAGES),
                   help=f"要跑的管线段，逗号分隔（默认全跑：{','.join(refine.ALL_STAGES)}）")
    p.set_defaults(fn=cmd_refine)

    p = sub.add_parser("candidates", help="从 JSON 文件载入外部候选")
    p.add_argument("project")
    p.add_argument("chapter")
    p.add_argument("json_file")
    p.set_defaults(fn=cmd_candidates)

    p = sub.add_parser("confirm", help="逐条确认候选")
    p.add_argument("project")
    p.add_argument("--chapter")
    p.set_defaults(fn=cmd_confirm)

    p = sub.add_parser("ask", help="按关键词查已确认事实（带原文依据）")
    p.add_argument("project")
    p.add_argument("keywords", nargs="+")
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("check", help="一致性体检：全书扫矛盾（人名/时间线/设定）")
    p.add_argument("project")
    p.add_argument("--plan", action="store_true", help="只看分组预演，不调用模型")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("plan", help="M8 出题：目的挂卡 → 选项／前置卡 → 冲突爆出（不代写）")
    p.add_argument("project")
    p.add_argument("--purpose", required=True, help="要达成的目的（挂到卡上）")
    p.add_argument("--note", default="", help="卡上注解／额外限制，影响选项，不改事实账")
    p.add_argument("--intent", default="", help="本章原意图，用来对拍冲突")
    p.add_argument("--reverse", action="store_true", help="先拆前置卡：前面得先达成什么")
    p.add_argument("--stub", action="store_true", help="离线占位出题，不调模型")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("repair-ids", help="修账：重复事实号的后到者迁移到新号（I-014）")
    p.add_argument("project")
    p.set_defaults(fn=cmd_repair_ids)

    p = sub.add_parser("status", help="项目概览")
    p.add_argument("project")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
