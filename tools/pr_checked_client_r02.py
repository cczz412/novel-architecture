# 执行身份：Codex
"""分步输出的格式检查；最多一次具体错误回传，不拼接残缺正文。"""
import json
import uuid

from pr_ark_client_r02 import Client as ArkClient, OUT
from pr_shape_guard_r02 import decode, BC_FIELDS, A_FIELDS


class Client(ArkClient):
    def call(self, model, messages, parameters, max_tokens=12000):
        fields = BC_FIELDS if '本步仅处理分组的事实与原文材料' in messages[1]['content'] else A_FIELDS
        folder = OUT / 'format_attempts' / self.job / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        current_messages = messages
        summary = dict(execution_identity='Codex', model=model, format_retry_limit=1, attempts=[], conversions=[])
        last_error = None
        for retry in range(2):
            response = super().call(model, current_messages, parameters, max_tokens=max_tokens)
            (folder / ('attempt_' + str(retry) + '_response.json')).write_text(
                json.dumps(response, ensure_ascii=False, indent=2) + '\n')
            try:
                obj, conversions = decode(response, fields)
                summary['attempts'].append(dict(retry=retry, valid=True))
                summary['conversions'].extend(conversions)
                (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
                # 只转换数组外壳，其他字段内容原样传给下游。
                response['choices'][0]['message']['content'] = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
                return response
            except (ValueError, KeyError, TypeError) as exc:
                last_error = str(exc)
                summary['attempts'].append(dict(retry=retry, valid=False, error=last_error))
                summary['no_progress'] = retry == 1 and summary['attempts'][0].get('error') == last_error
                (folder / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
                if retry == 1:
                    break
                content = response.get('choices', [{}])[0].get('message', {}).get('content') or ''
                current_messages = messages + ([dict(role='assistant', content=content)] if content else []) + [
                    dict(role='user', content='上次输出的具体格式错误：' + last_error +
                         '。只重新输出本步骤完整对象，保留所有已有正确内容。顶层数组必须是' + ','.join(fields) +
                         '。不要输出其他步骤字段。JSON完整结束，不用省略号代替内容。每条短理由，逐字短引，不复制整段。')]
        raise ValueError('一次格式重写后仍失败，停止该组：' + str(last_error))
