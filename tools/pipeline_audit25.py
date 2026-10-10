# 执行身份：Codex
"""Static closure and full-text corpus-specific string checks."""
import ast
import hashlib
import json
import re
from pathlib import Path
from pipeline_source25 import read_sources, read_json, write_json

WEB_RESIDUE = ('加入书架', '上一章', '下一章', '返回目录', '点击收藏', '推荐票', '月票')
DYNAMIC = {'importlib', 'runpy', '__import__'}
LOCATION_NAMES = {'chapter', 'ch', 'para', 'paragraph_number', 'start', 'end', 'local_key'}


def local_closure(entry, prompt_files=(), config_files=()):
    root = Path(entry).resolve().parent
    todo, found, errors = [Path(entry).resolve()], set(), []
    while todo:
        file = todo.pop()
        if file in found:
            continue
        found.add(file)
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or '']
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '__import__':
                errors.append({'file': str(file), 'line': node.lineno, 'error': 'dynamic_import'})
            for module in modules:
                if module.split('.')[0] in DYNAMIC:
                    errors.append({'file': str(file), 'line': node.lineno, 'error': 'dynamic_import'})
                target = root / (module.replace('.', '/') + '.py')
                package = root / module.replace('.', '/') / '__init__.py'
                if target.is_file():
                    todo.append(target)
                elif package.is_file():
                    todo.append(package)
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('eval', 'exec') for n in ast.walk(tree)):
            errors.append({'file': str(file), 'error': 'runtime_code_loading'})
    found.update(Path(p).resolve() for p in (*prompt_files, *config_files))
    return sorted(found), errors


def structural_checks(files):
    errors, examples, format_exceptions = [], [], []
    for file in files:
        if file.suffix != '.py':
            continue
        text = file.read_text()
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                restricted = names & LOCATION_NAMES
                if restricted and any(isinstance(n, ast.Constant) and isinstance(n.value, (int, str)) for n in node.comparators):
                    errors.append({'file': str(file), 'line': node.lineno, 'error': 'chapter_paragraph_literal_branch'})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method = node.func.attr
                if method == 'replace' and len(node.args) >= 2 and all(isinstance(n, ast.Constant) and isinstance(n.value, str) and re.search(r'[\u4e00-\u9fff]', n.value) for n in node.args[:2]):
                    errors.append({'file': str(file), 'line': node.lineno, 'error': 'literal_typo_replace'})
                if method in ('startswith', 'endswith'):
                    restricted = {n.id for n in ast.walk(node.func.value) if isinstance(n, ast.Name)} & LOCATION_NAMES
                    if restricted and any(isinstance(n, ast.Constant) for n in node.args):
                        errors.append({'file': str(file), 'line': node.lineno, 'error': 'chapter_paragraph_literal_branch'})
                if method == 'startswith' and any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == 0 for n in ast.walk(node)):
                    errors.append({'file': str(file), 'line': node.lineno, 'error': 'entity_initial_matching'})
                if method == 'zfill':
                    format_exceptions.append({'file': str(file), 'line': node.lineno, 'reason': '通用编号补零，不按编号选择故事规则'})
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and isinstance(value, ast.Constant) and isinstance(key.value, str) and isinstance(value.value, str):
                        a, b = key.value, value.value
                        if a != b and len(a) == len(b) and re.fullmatch(r'[\u4e00-\u9fff]+', a) and re.fullmatch(r'[\u4e00-\u9fff]+', b) and sum(x != y for x, y in zip(a, b)) <= 2:
                            errors.append({'file': str(file), 'line': node.lineno, 'error': 'literal_typo_map'})
        if re.search(r':ch\d{2}:p\d{3}', text):
            errors.append({'file': str(file), 'error': 'literal_full_paragraph_id'})
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r'正例|反例|比如|如：|虚构名', line):
                examples.append({'file': str(file), 'line': number, 'text': line})
    return {'passed': not errors, 'errors': errors, 'example_lines': examples, 'format_exceptions': format_exceptions}


def cleaned(text):
    for word in WEB_RESIDUE:
        text = text.replace(word, '')
    return text


def long_grams(text, minimum=4):
    result = set()
    for span in re.findall(r'[\u4e00-\u9fff]+', cleaned(text)):
        for size in range(minimum, 9):
            result.update(span[n:n + size] for n in range(len(span) - size + 1))
    return result


def collect_entities(value):
    result = set()
    def walk(obj):
        if isinstance(obj, dict):
            for name, val in obj.items():
                if name in ('entity', 'subject_text', 'subject', 'alias', 'name', 'location', 'object_name') and isinstance(val, str):
                    pieces = re.findall(r'[\u4e00-\u9fff]{2,}', val)
                    result.update(pieces)
                if name in ('mentions', 'aliases') and isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            result.update(re.findall(r'[\u4e00-\u9fff]{2,}', item))
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(value)
    return result


def string_scan(files, corpora, entities, whitelist):
    allowed = {r['word'] for r in whitelist}
    if len(allowed) > 50 or any(not r.get('reason') or not r.get('registered_by') for r in whitelist):
        raise ValueError('通用词白名单无效')
    all_entities = set().union(*entities.values()) if entities else set()
    if allowed & all_entities:
        raise ValueError('通用词白名单混入实体')
    texts = {str(p): p.read_text() for p in files}
    reports = {}
    for book, corpus in corpora.items():
        background_grams = set().union(*(long_grams(text) for code, text in corpora.items() if code != book))
        candidates = (long_grams(corpus) - background_grams) | entities.get(book, set())
        by_file = {}
        strict_long = {}
        for file, text in texts.items():
            hits = [{'word': word, 'count': text.count(word), 'entity': word in entities.get(book, set())}
                    for word in sorted((candidates - allowed) & (long_grams(text) | {e for e in entities.get(book, set()) if e in text}))]
            by_file[file] = {'count': sum(r['count'] for r in hits), 'hits': hits}
            long_hits = sorted(long_grams(text, 6) & long_grams(corpus, 6))
            if long_hits:
                strict_long[file] = long_hits
        reports[book] = {'candidate_count': len(candidates), 'entity_count': len(entities.get(book, set())),
                         'hit_count': sum(v['count'] for v in by_file.values()),
                         'by_file': by_file, 'six_plus_verbatim_hits': strict_long,
                         'six_plus_passed': not strict_long}
    return reports


def apply_background_releases(reports, files, release_table):
    """原始检测完成后逐处核对审读签名；原候选串、实体和长串判法不变。"""
    table_path=Path(release_table)
    table=read_json(table_path)
    signer=table.get('signer','')
    if table.get('schema')!='background_string_release_v1' or not signer or signer=='Codex' or not table.get('signed_at'):
        raise ValueError('背景串放行表缺独立审读签名')
    for key in ('source_report','judgement_report','basis_decision'):
        source=table[key]
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('背景串放行表出处指纹改变：'+key)
    entries=table['entries']
    if table['released_count']!=len(entries):raise ValueError('放行条数不等于清单')
    paths={str(p):Path(p) for p in files}
    seen=set();release_rows=[]
    for entry in entries:
        literal,relative=entry['literal'],entry['file']
        if not literal or Path(relative).is_absolute() or '..' in Path(relative).parts:raise ValueError('放行路径或字面无效')
        construct=entry['location']['construct']
        key=(relative,literal,construct)
        if key in seen:raise ValueError('放行条目重复')
        seen.add(key)
        matches=[p for p in paths.values() if p.as_posix().endswith('/'+relative)]
        if len(matches)!=1:raise ValueError('放行文件不在唯一检测闭包内')
        path=matches[0];text=path.read_text();lines=text.splitlines();tree=ast.parse(text)
        label=re.match(r'(模块常量|函数)\s+(\w+)',construct)
        if not label:raise ValueError('放行结构无法重核')
        kind,name=label.groups()
        nodes=[n for n in (tree.body if kind=='模块常量' else ast.walk(tree))
               if (kind=='函数' and isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
               or (kind=='模块常量' and isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))]
        if len(nodes)!=1:raise ValueError('放行结构不存在或不唯一')
        node=nodes[0]
        positions=[{'line':i+1,'column':m.start()+1} for i in range(node.lineno-1,node.end_lineno)
                   for m in re.finditer(re.escape(literal),lines[i])]
        # 每条签名只批准原有一处；新增的同词不能连带放行。
        release_rows.append({'literal':literal,'file':str(path),'construct':construct,'reason':entry['reason'],
            'signed_location':entry['location'],'current_positions':positions,'released_max_count':min(1,len(positions)),
            'status':'结构内仍存在' if positions else '字面已由通用规则取代','signer':signer})
    for book,report in reports.items():
        report['raw_hit_count']=report['hit_count'];released=[]
        for file,group in report['by_file'].items():
            group['raw_count']=group['count'];group['raw_hits']=[dict(h) for h in group['hits']]
            remaining=[]
            for hit in group['hits']:
                approved=[r for r in release_rows if r['file']==file and r['literal']==hit['word']]
                count=min(hit['count'],sum(r['released_max_count'] for r in approved))
                if count:released.append({'book':book,'file':file,'literal':hit['word'],'count':count,
                    'entity':hit['entity'],'signed_entries':approved})
                if hit['count']>count:remaining.append({**hit,'count':hit['count']-count})
            group['hits']=remaining;group['count']=sum(h['count'] for h in remaining)
        report['hit_count']=sum(g['count'] for g in report['by_file'].values())
        report['released_hits']=released
        report['release_table']={'path':str(table_path),'sha256':hashlib.sha256(table_path.read_bytes()).hexdigest(),
            'signer':signer,'signed_at':table['signed_at'],'entries':release_rows,'not_released':table.get('not_released',[])}
    return reports
