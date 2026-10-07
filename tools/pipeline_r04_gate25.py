# 执行身份：Codex
"""R04-only authorization wrapper, outside the portable pipeline."""
import os
from pathlib import Path
from pipeline_budget25 import Budget, Halt, before, now, check_limits, runtime_guard_errors
from pipeline_source25 import read_json, write_json, digest

class R04Budget(Budget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_path = Path(self.config['authorization_file'])

    def close(self, reason):
        super().close(reason)
        auth = read_json(self.auth_path)
        auth.update(allowed=False, closed_at=now(), closed_reason=reason)
        write_json(self.auth_path, auth)

    def guard(self):
        self.guard_r04()
        return super().guard()

    def guard_r04(self):
        check_limits(self.config)
        auth = read_json(self.auth_path)
        if not auth.get('allowed') or not before(auth['stop_new_calls_at']) or not before(auth['deadline']):
            raise Halt('授权未开启或已停新请求')
        fixed = read_json(self.config['authorization_fixed_file'])['preset']
        mutable = {'allowed', 'execution_identity', 'responded_reviews', 'stop_new_calls_at', 'deadline',
                   'closed_at', 'closed_reason', 'gate_proof', 'updated_at', 'opened_at', 'opened_by', 'open_reason'}
        if any(auth.get(k) != v for k, v in fixed.items() if k not in mutable):
            raise Halt('授权固定字段改变')
        additions = read_json(self.config['authorization_additions_file'])
        approved_additions = additions['additions']
        if any(auth.get(k) != v for k, v in approved_additions.items()):
            raise Halt('调度新增封存登记不一致')
        if set(auth) - set(fixed) - mutable - set(approved_additions):
            raise Halt('授权出现未登记的新字段')
        if digest(additions['approved_source']) != additions['source_sha256']:
            raise Halt('新增授权出处改变')
        if not str(os.environ.get('PR_JOB_ID', '')).startswith(auth['prefix']):
            raise Halt('作业前缀不符')
        freeze = read_json(self.config['freeze_file'])
        if freeze.get('overall_sha256') != self.config['code_freeze_sha']:
            raise Halt('预算未绑定冻结版本')
        if not freeze.get('freeze_effective') or not freeze.get('effective'):
            raise Halt('冻结候选尚未生效')
        for row in freeze['files']:
            if digest(row['path']) != row['sha256']:
                raise Halt('冻结文件发生变化')
        independent = read_json(self.config['independent_freeze_receipt'])
        if not independent.get('effective') or independent.get('overall_sha256') != freeze['overall_sha256'] or not independent.get('overall_sha_recomputed') or independent.get('reviewer') == 'Codex':
            raise Halt('独立冻结回执未生效')
        if independent.get('git_commit') != freeze.get('git_commit'):
            raise Halt('独立冻结回执未绑定候选提交')
        if independent.get('detector_counts') != {'qishi': 0, 'dixian': 0} or independent.get('blind_terms_sha256') != freeze['blind_terms_sha256']:
            raise Halt('独立串检测或词表SHA回执不符')
        blind = read_json(self.config['blind_scan_receipt'])
        scanned = {row['path']: row['sha256'] for row in blind['scanned_files']}
        if blind['hits']['new'] != 0 or any(scanned.get(row['path']) != row['sha256'] for row in freeze['files']):
            raise Halt('盲测词表回执未覆盖当前闭包或有新命中')
        if blind['word_list_sha256']['main'] != freeze['blind_terms_sha256']:
            raise Halt('审读持表扫描SHA不同')
        if independent.get('blind_terms_new_hits', independent.get('blind_terms_hit_count')) != 0:
            raise Halt('独立盲测词表新命中不为零')
        proof = read_json(self.config['reservation_proof'])
        if self.config.get('runtime_guard'):
            errors = runtime_guard_errors(self.config)
            if errors: raise Halt('运行期守门配置不完整：' + ','.join(errors))
        elif not proof['passed'] or not proof.get('full_ABC_reservation'):
            raise Halt('整线A/B/C预留证明未齐')
        window = auth['windows'].get(proof['authorization_window'])
        if not window or window['book'] != proof['book_code'] or window['chapters'] != ['ch' + c for c in self.config['chapters']]:
            raise Halt('书目或章范围与授权窗口不同')
        if proof['book_id'] != self.config['book_id'] or proof['input_pkg_sha'] != self.identity['input_sha']:
            raise Halt('整流程证明未绑定本次输入')
        if auth.get('gate_proof', {}).get(str(self.path)) != digest(self.path):
            raise Halt('预算文件未在调用授权中登记SHA')
        receipt = read_json(self.config['review_receipt'])
        bodies = {}
        for file, expected in receipt['response_documents'].items():
            if digest(file) != expected:
                raise Halt('逐条回应文件改变')
            bodies[file] = Path(file).read_text()
        sources = {}
        for file, expected in receipt['responded_reviews'].items():
            if digest(file) != expected:
                raise Halt('已回应意见改变')
            sources[file] = Path(file).read_text()
        for entry in receipt['entries']:
            rendered = '| ' + ' | '.join(str(entry[k]).replace('|', '／') for k in
                                        ('id', 'source_text', 'decision', 'reason', 'action', 'acceptance')) + ' |'
            if entry['source_text'] not in sources[entry['source_document']] or not any(rendered in b for b in bodies.values()):
                raise Halt('原条目逐项回应缺失')
        snapshot = read_json(self.config['published_baseline'])['published_snapshot']
        owned = self.config.get('owned_documents', {})
        acknowledged = read_json(self.config['published_changes_ack'])['acknowledged']
        forbidden = {Path(p.rstrip('/')).name for p in fixed.get('forbidden_paths', [])}
        for folder, previous in snapshot.items():
            for directory in {str(Path(p).parent) for p in previous}:
                for path in Path(directory).iterdir():
                    if path.name.startswith(('_封存', '_试算')) or path.name in forbidden or path.suffix != '.md':
                        continue
                    expected = receipt['responded_reviews'].get(str(path), owned.get(str(path), acknowledged.get(str(path), previous.get(str(path)))))
                    if expected != digest(path):
                        raise Halt('新发布意见尚未逐条回应：' + path.name)
        evidence = read_json(self.config['implementation_evidence'])
        mapped = {row['id']:row for row in evidence['entries']}
        if not evidence['all_items_have_evidence'] or set(mapped) != {row['id'] for row in receipt['entries']}:
            raise Halt('逐条回应缺修后文件行号和验收证据')
        for row in mapped.values():
            if not row['diff_summary'] or not row['acceptance_status'] or not row['locations']:
                raise Halt('逐条回应只有接受，没有实际改法/验收')
            if any(digest(cell['file']) != cell['sha256'] for cell in row['locations']):
                raise Halt('逐条回应改动位置SHA过期')
        if auth.get('responded_reviews') != receipt['responded_reviews']:
            raise Halt('授权逐条回应登记不同步')
        return auth
