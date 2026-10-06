#!/usr/bin/env python3
# 执行身份：Codex
"""Zero-call question replay without view or search-term parameters."""
import argparse
from pathlib import Path
from pipeline_source25 import read_json, write_json
from pipeline_author25 import query


def main():
    parser = argparse.ArgumentParser(description='只给自然问句，回放当前作者资料')
    parser.add_argument('output_dir')
    parser.add_argument('question_file')
    args = parser.parse_args()
    root = Path(args.output_dir)
    questions = read_json(args.question_file)
    if isinstance(questions, dict):
        questions = questions.get('questions')
    if not isinstance(questions, list):
        raise ValueError('问句文件须提供questions数组')
    store = read_json(root / 'author_store.json')
    rows = []
    for index, item in enumerate(questions, 1):
        if isinstance(item, str):
            ident, question = str(index), item
        elif isinstance(item, dict) and set(item) <= {'id', 'question'} and isinstance(item.get('question'), str):
            ident, question = str(item.get('id', index)), item['question']
        else:
            raise ValueError('每题只能给编号和自然问句，不能预填表或搜索词')
        rows.append({'id': ident, 'result': query(store, question)})
    write_json(root / 'query_replay.json', {'results': rows, 'model_calls': 0})
    print('执行身份：Codex；问句回放完成：' + str(len(rows)))


if __name__ == '__main__':
    main()
