# 执行身份：Codex
"""旧全文报告与公开书目白名单计数模式；计数模式不保存命中串或实体。"""
import argparse
import os
import hashlib
import json
import pathlib
import sys
import zipfile
sys.dont_write_bytecode = True
import pipeline_audit25 as audit
from pipeline_source25 import read_json, write_json, digest


def counts_only(background, allowed_book_ids, files, terms, release_table=None):
    """只打开显式准许的书目；其余记录在任何正文/实体文件读取前排除。"""
    records = read_json(background)['books']
    allowed = set(allowed_book_ids)
    ids = [r['book_id'] for r in records]
    if not allowed or len(ids) != len(set(ids)) or not allowed <= set(ids):
        raise ValueError('invalid_public_book_allowlist')
    codes = [r['code'] for r in records]
    if len(codes) != len(set(codes)):
        raise ValueError('duplicate_book_code')
    corpora, entities, receipts, excluded = {}, {}, [], []
    for record in records:
        ident = hashlib.sha256(record['book_id'].encode()).hexdigest()
        if record['book_id'] not in allowed:
            excluded.append({'book_id_sha256': ident, 'reason': 'not_in_approved_public_allowlist'})
            continue
        blocks, used, missing = [], [], 0
        # ZIP只打开白名单记录；混合包只读取该编号的指定成员，不遍历其他书。
        with zipfile.ZipFile(record['archive']) as package:
            for n in range(1, record['chapter_count'] + 1):
                member = 'books/' + record['book_id'] + '/sources/' + str(n).zfill(2) + '_paragraphs.json'
                try:
                    raw = package.read(member)
                except KeyError:
                    missing += 1
                    continue
                data = json.loads(raw)
                rows = data.get('paragraphs') if isinstance(data, dict) else data
                blocks.extend(r['text'] for r in rows)
                used.append({'sha256': hashlib.sha256(raw).hexdigest(), 'paragraph_count': len(rows)})
        code = record['code']
        corpora[code] = '\n'.join(blocks)
        entities[code] = set()
        for item in record.get('entity_records', []):
            obj = read_json(item['path'])
            if item.get('views'):
                obj = {key: obj['views'].get(key, []) for key in item['views']}
            if item.get('chapter_book'):
                obj = [row for row in obj['chapters'] if row.get('book') == item['chapter_book']]
            entities[code].update(audit.collect_entities(obj))
        receipts.append({'book_id_sha256': ident, 'chapter_count': len(used),
                         'missing_chapter_count': missing, 'text_length': len(corpora[code]), 'members': used})
    scans = audit.string_scan(files, corpora, entities, read_json(terms)['words'])
    if release_table is not None:
        scans = audit.apply_background_releases(scans, files, release_table)
    reports = []
    for record in records:
        if record['book_id'] not in allowed:
            continue
        scan = scans[record['code']]
        reports.append({'book_id_sha256': hashlib.sha256(record['book_id'].encode()).hexdigest(),
                        'candidate_count': scan['candidate_count'], 'entity_count': scan['entity_count'],
                        'raw_hit_count': scan.get('raw_hit_count', scan['hit_count']),
                        'hit_count': scan['hit_count'],
                        'released_hit_count': sum(r['count'] for r in scan.get('released_hits', [])),
                        'six_plus_verbatim_hit_count': sum(len(v) for v in scan['six_plus_verbatim_hits'].values())})
    # 仅组装允许输出的数字、布尔值、固定状态及SHA，不转存scans或entities。
    return {'execution_identity': 'Codex', 'schema': 'detector_counts_v63', 'performed': True,
            'counts_only': True, 'scope': 'approved_public_books_only',
            'effective': not any(r['missing_chapter_count'] for r in receipts),
            'ineffective_reasons': ['missing_chapters'] if any(r['missing_chapter_count'] for r in receipts) else [],
            'missing_chapter_count': sum(r['missing_chapter_count'] for r in receipts),
            'book_count': len(reports), 'excluded_book_count': len(excluded),
            'excluded_books': excluded, 'corpus_receipts': receipts, 'reports': reports,
            'all_scanned_hit_counts_zero': all(r['hit_count'] == 0 for r in reports),
            'excluded_book_hit_counts': None, 'background_sha256': digest(background),
            'terms_sha256': digest(terms), 'release_table_sha256': digest(release_table) if release_table else None,
            'file_count': len(files), 'file_sha256': [digest(p) for p in files]}


def legacy(args):
    R=pathlib.Path(args.output_dir);R.mkdir(parents=True,exist_ok=True)
    W=pathlib.Path(__file__).resolve().parents[1]
    import pipeline_audit25 as audit
    from pipeline_source25 import read_json,write_json,digest
    p=pathlib.Path(args.background)
    terms=W/'tools/pipeline_terms25.json'
    records=read_json(p)['books']; corpora={}; receipts=[]
    for record in records:
     blocks=[];used=[];missing=0
     with zipfile.ZipFile(record['archive']) as package:
      for n in range(1,record['chapter_count']+1):
       chapter=str(n).zfill(2);member='books/'+record['book_id']+'/sources/'+chapter+'_paragraphs.json'
       try:raw=package.read(member)
       except KeyError:
        missing+=1
        continue
       data=json.loads(raw); rows=data.get('paragraphs') if isinstance(data,dict) else data
       blocks.extend(r['text'] for r in rows)
       used.append(dict(member=member,sha256=hashlib.sha256(raw).hexdigest(),paragraph_count=len(rows)))
     corpora[record['code']]='\n'.join(blocks)
     receipts.append(dict(**record,members=used,text_length=len(corpora[record['code']]),pipeline_steps=0))
    entities={code:set() for code in corpora}
    for record in records:
     for item in record.get('entity_records', []):
      obj=read_json(item['path'])
      if item.get('views'):
       obj={key:obj['views'].get(key,[]) for key in item['views']}
      if item.get('chapter_book'):
       obj=[row for row in obj['chapters'] if row.get('book')==item['chapter_book']]
      entities[record['code']].update(audit.collect_entities(obj))
    configs=[terms,p]
    files,errors=audit.local_closure(W/'tools/run_pipeline.py',[],configs)
    struct=audit.structural_checks(files);scans=audit.string_scan(files,corpora,entities,read_json(terms)['words'])
    if pathlib.Path(args.release_table).exists():scans=audit.apply_background_releases(scans,files,args.release_table)
    write_json(R/'closure_candidate_v25.json',dict(execution_identity='Codex',files=[dict(path=str(p),sha256=digest(p)) for p in files],dynamic_errors=errors))
    write_json(R/'string_detection_v25.json',dict(execution_identity='Codex',reports=scans,whitelist_sha256=digest(terms),background_sha256=digest(p),corpus_receipts=receipts,entities={k:sorted(v) for k,v in entities.items()},known_exposure={'provider':'审读侧持表代跑','words_read':False,'self_populated':False},hard_passed=not any(r['missing_chapter_count'] for r in receipts) and all(scans[k]['hit_count']==0 for k in ['qishi','dixian']),effective=not any(r['missing_chapter_count'] for r in receipts),ineffective_reasons=['missing_chapters'] if any(r['missing_chapter_count'] for r in receipts) else []))
    write_json(R/'structural_checks_v25.json',dict(execution_identity='Codex',**struct))
    if any(r['missing_chapter_count'] for r in receipts):
     print('coverage_incomplete: missing_chapters',sum(r['missing_chapter_count'] for r in receipts))
    print('closure',len(files),'dynamic errors',errors,'structural',struct['passed'])
    for code,scan in scans.items():
     print(code,'chars',len(corpora[code]),'entities',scan['entity_count'],'candidates',scan['candidate_count'],'hits',scan['hit_count'],'six+',scan['six_plus_passed'])
     for file,rows in scan['by_file'].items():
      if rows['count']:print(pathlib.Path(file).name,rows['hits'][:35])
    if struct['errors']:print(struct['errors'])


def main():
    parser = argparse.ArgumentParser(description='登记语料检测；--counts-only只输出公开白名单书目的计数')
    parser.add_argument('output_dir', nargs='?')
    parser.add_argument('--counts-only', action='store_true')
    parser.add_argument('--allow-book-id', action='append', default=[])
    parser.add_argument('--counts-out')
    root = pathlib.Path(__file__).resolve().parents[1]
    parser.add_argument('--background', default=os.environ.get('PIPELINE_BACKGROUND_CONFIG'))
    parser.add_argument('--terms', default=str(root / 'tools/pipeline_terms25.json'))
    parser.add_argument('--release-table', default=os.environ.get('PIPELINE_RELEASE_TABLE'))
    args = parser.parse_args()
    if not args.background:
        parser.error('请用 --background 或 PIPELINE_BACKGROUND_CONFIG 提供外部背景配置')
    if not args.release_table:
        parser.error('请用 --release-table 或 PIPELINE_RELEASE_TABLE 提供外部放行表')
    if not args.counts_only:
        if not args.output_dir:
            parser.error('output_dir required for legacy mode')
        legacy(args)
        return 0
    # 输出位置在打开任何正文前核定。正式回执不能写进job目录，也不能覆盖已有文件。
    if args.output_dir or not args.counts_out or not args.allow_book_id:
        parser.error('counts mode requires --counts-out and --allow-book-id; no output_dir')
    output = pathlib.Path(args.counts_out).resolve()
    if any(part.startswith('job_R04_') for part in output.parts) or output.exists():
        print(json.dumps({'execution_identity': 'Codex', 'performed': False, 'error': 'invalid_counts_output'}))
        return 2
    try:
        files, errors = audit.local_closure(root / 'tools/run_pipeline.py', [], [args.terms, args.background])
        structure = audit.structural_checks(files)
        report = counts_only(args.background, args.allow_book_id, files, args.terms, args.release_table)
        report.update(dynamic_error_count=len(errors), structural_error_count=len(structure['errors']))
        with output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False))
    except Exception:
        # 异常也不能把命中串、实体或输入路径带进stderr/日志。
        print(json.dumps({'execution_identity': 'Codex', 'performed': False, 'error': 'counts_scan_failed', 'counts': None}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
