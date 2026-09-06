"""单文件页面的画面与交互；所有候选文案都先转义。"""

from __future__ import annotations

import html
import json
from typing import Any

STYLE = r"""
:root{color-scheme:light;--paper:#f5f5f2;--card:#fff;--ink:#25302e;--muted:#72807a;--line:#e3e8e3;--accent:#326a59;--soft:#edf5ef;--gold:#987141;--goldsoft:#faf4e9}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;font-size:14px;line-height:1.6}
button{font:inherit;cursor:pointer}button:disabled{cursor:wait;opacity:.65}button:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.top{padding:24px 30px 18px;background:#fafbf8;border-bottom:1px solid var(--line)}.topline{display:flex;align-items:center;justify-content:space-between;gap:16px}.eyebrow{font-size:12px;font-weight:650;letter-spacing:.13em;color:var(--accent)}.chip{display:inline-block;padding:2px 9px;border:1px solid #d5dfd8;border-radius:20px;font-size:11px;letter-spacing:0;margin-left:10px;color:#607469}
h1{font-size:22px;font-weight:660;letter-spacing:-.03em;margin:12px 0 6px}.subtitle{color:var(--muted);margin:0;font-size:13px}.permission-button{border:1px solid #b8cdc0;border-radius:8px;background:#fff;color:var(--accent);padding:8px 13px;font-size:12px;white-space:nowrap}.permission-button:hover{background:var(--soft)}
.meta-strip{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:12px 30px}.metrics{display:flex;gap:22px;color:var(--muted);font-size:12px}.metrics strong{color:var(--ink);font-weight:650;font-size:15px;margin-right:4px}.legend{font-size:11px;color:var(--muted)}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#78a68d;margin-right:6px}.dot.pale{background:#c6cdc4;margin-left:12px}
.canvas{overflow-x:auto;padding:0 24px 16px}.board{position:relative;display:grid;grid-template-columns:minmax(230px,.96fr) minmax(365px,1.48fr) minmax(305px,1.2fr) minmax(150px,.58fr);gap:14px;min-width:1100px;max-width:1820px;margin:0 auto;height:calc(100vh - 245px);min-height:590px}.panel{position:relative;background:var(--card);border:1px solid var(--line);border-radius:12px;min-width:0;overflow:hidden;display:flex;flex-direction:column}.panel-head{height:77px;flex-shrink:0;border-bottom:1px solid var(--line);padding:15px 16px 10px}.panel-head h2{margin:0;font-size:15px;font-weight:650;display:flex;gap:9px;align-items:center}.step{font-size:11px;color:#8b9b90;font-weight:500;letter-spacing:.07em}.panel-head p{font-size:11px;color:var(--muted);margin:4px 0 0}.panel-scroll{overflow-y:auto;min-height:0;flex:1;padding:13px 12px 18px;scrollbar-width:thin;scrollbar-color:#d4ddd5 transparent}
.source-unit{position:relative;border:1px solid transparent;border-radius:8px;padding:12px 12px 34px;margin-bottom:12px;min-height:95px}.sentence-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px}.number{font-size:10px;color:#91a098;letter-spacing:.08em}.sentence-text{display:block;font-size:17px;line-height:1.9;white-space:pre-wrap;font-family:'Songti SC',STSong,'Noto Serif CJK SC',serif}.source-unit.possibly-missing{background:#f5f5f1;border:1px dashed #dfe2d8;color:#7a8279}.missing-label{font-size:10px;color:#93998b;background:#eaede5;padding:1px 6px;border-radius:4px}.source-note{font-size:11px;color:var(--muted);margin:18px 10px 8px;line-height:1.8}.marker-badge{display:inline-block;font-size:10px;color:var(--gold);background:var(--goldsoft);padding:1px 6px;border-radius:4px;margin-left:5px}.toolbar{position:absolute;right:8px;bottom:6px;visibility:hidden;pointer-events:none;z-index:5}.toolbar button{padding:3px 9px;border:1px solid #b9ccbd;background:white;border-radius:5px;color:var(--accent);font-size:11px;box-shadow:0 2px 5px #243b2210}.source-unit:hover .toolbar,.source-unit:focus-within .toolbar,.fact-unit:hover .toolbar,.fact-unit:focus-within .toolbar{visibility:visible;pointer-events:auto}
.fact-unit{position:relative;border:1px solid #e5eae5;border-radius:9px;padding:11px 12px 32px;margin-bottom:10px;background:#fff;min-height:130px}.fact-heading{display:flex;align-items:flex-start;gap:8px;margin-bottom:6px}.fact-heading strong{font-size:14px;font-weight:620;line-height:1.65;flex:1}.fact-number{font-size:10px;line-height:2;color:#9ba69f}.fact-meta{display:flex;flex-wrap:wrap;gap:5px;align-items:center;margin-bottom:7px}.status{border-radius:4px;background:#eff3ef;color:#617d69;font-size:10px;padding:1px 6px}.status.uncertain{background:#f5f1ea;color:#8b775e}.route{font-size:10px;color:#839587}.evidence{font-size:12px;color:#586962;line-height:1.75}.evidence em{font-style:normal;color:#9aa59f;font-size:10px;margin-right:5px}.source-location{font-size:10px;color:#8d9a92;margin-top:3px;overflow-wrap:anywhere}.source-unmatched{color:#97794f;font-size:11px;margin-top:4px}.fact-unit.new-candidate{border:1px dashed #bbad91;background:#fffcf6}.blank-fact{min-height:17px;border-bottom:1px dashed #d8ccba;flex:1;margin:7px 0 4px}.pending-label{font-size:10px;color:#a78651}.new-note{font-size:11px;color:#928269}
.source-unit.is-linked,.fact-unit.is-linked{background:#edf6ee;border-color:#80a994;box-shadow:inset 3px 0 0 #6f9b81}.source-unit.is-active,.fact-unit.is-active{border-color:#6a9b80}.source-unit.is-added-linked,.fact-unit.is-added-linked{border-color:#b29562;background:#fbf6e9;border-style:dashed}.source-unit.possibly-missing.is-added-linked{box-shadow:none}.ledger-group{border:1px solid #e5e9e3;border-radius:7px;margin-bottom:8px;overflow:hidden}.ledger-title{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:#f8faf6}.ledger-title h3{font-size:12px;font-weight:620;margin:0}.ledger-count{font-size:10px;color:#919d93}.ledger-row{border-top:1px solid #eef0e9;padding:7px 10px}.ledger-row.is-linked{background:#edf6ee;box-shadow:inset 3px 0 0 #75a085}.ledger-key{font-size:12px;font-weight:570;display:block;overflow-wrap:anywhere}.field-name{font-size:9px;color:#94a095;font-weight:400;margin-right:6px}.ledger-tags{display:flex;flex-wrap:wrap;gap:3px 8px;color:#78877b;font-size:10px;margin-top:3px}.tag-groups{font-size:10px;color:#78897b;margin-top:3px}.group-pill{display:inline-block;border:1px solid #dfe6db;color:#839078;border-radius:3px;font-size:9px;line-height:1.5;padding:0 5px}.empty-ledger{font-size:10px;color:#a1aa9f;margin:5px 10px 7px}.ledger-note{font-size:10px;color:#91a08e;margin:9px 4px 0}.storyboard{background:#f9faf7}.storyboard .panel-scroll{display:flex;align-items:center;justify-content:center;padding:15px;text-align:center}.placeholder-box{color:#97a194;font-size:12px;border:1px dashed #d7dfd1;min-height:165px;width:100%;display:flex;align-items:center;justify-content:center;padding:18px;line-height:2.2;border-radius:8px}
.connection-lines{position:absolute;inset:0;pointer-events:none;z-index:6;width:100%;height:100%;overflow:visible}.connection-lines path{fill:none;stroke:#a88d60;stroke-width:1.5;stroke-dasharray:5 5}.marks-bar{margin:0 30px 20px;border-top:1px solid #dde5dc;padding-top:11px;display:grid;grid-template-columns:auto 1fr;gap:14px;font-size:11px;color:#8a968c}.marks-bar strong{font-weight:580;color:#6b7e6e}.marks-text{min-width:0}.marks-log{display:flex;gap:6px 15px;flex-wrap:wrap;margin-top:4px;font-size:10px;color:#8b967f}.marks-log span{overflow-wrap:anywhere}.marks-error{color:#947240}.footer-note{margin-top:2px;color:#9ba494;font-size:10px}.noscript{margin:16px;padding:12px;background:#fff5e8;color:#8d6f42;font-size:12px}
@media(max-width:800px){.top{padding:17px 18px}.topline{align-items:flex-start}h1{font-size:18px;max-width:85%}.meta-strip{padding:10px 18px}.legend{display:none}.canvas{padding:0 12px 14px}.marks-bar{margin-left:18px;margin-right:18px}.board{height:660px}.permission-button{white-space:normal;max-width:135px}.metrics{gap:13px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

SCRIPT = r"""
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('door1-data').textContent);
  const byId = id => document.getElementById(id);
  const sources = new Map(data.sentences.map(s => [s.id, s]));
  const originals = new Map(data.candidates.map(c => [c.id, c]));
  const statusNode = byId('marks-status');
  const connectButton = byId('connect-marks');
  const maxMarks = 4096, maxBytes = 1048576;
  let directory = null;
  let diskMarks = data.marks.document.marks.slice();
  let pending = [];
  let saving = false;
  let restoring = true;
  let active = null;
  let pointerActive = null;
  let rememberedHandle = null;

  function message(text, error = false) {
    statusNode.textContent = text;
    statusNode.classList.toggle('marks-error', error);
  }
  function addElement(parent, tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (cls) node.className = cls;
    parent.append(node);
    return node;
  }
  function emptyDocument() { return {schema_version: 1, view_id: data.view_id, marks: []}; }
  function sameKeys(object, expected) {
    return object && typeof object === 'object' && !Array.isArray(object)
      && Object.keys(object).sort().join('|') === expected.slice().sort().join('|');
  }
  function validTime(stamp) {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(stamp)) return false;
    const ms = Date.parse(stamp);
    if (!Number.isFinite(ms)) return false;
    return new Date(ms).toISOString().slice(0, 19) === stamp.slice(0, 19);
  }
  function validate(value) {
    if (!sameKeys(value, ['schema_version', 'view_id', 'marks']) || value.schema_version !== 1
        || value.view_id !== data.view_id || !Array.isArray(value.marks) || value.marks.length > maxMarks) {
      throw new Error('GAP_MARKS_SCOPE');
    }
    const seen = new Set(), candidates = new Set(originals.keys());
    for (const m of value.marks) {
      if (!sameKeys(m, ['mark_id', 'mark_type', 'target_type', 'target_id', 'created_at'])
          || !Object.values(m).every(v => typeof v === 'string')
          || !/^m_[0-9a-f]{32}$/.test(m.mark_id) || seen.has(m.mark_id) || !validTime(m.created_at)) {
        throw new Error('GAP_MARKS_SHAPE');
      }
      seen.add(m.mark_id);
      if (m.mark_type === '漏抽' && m.target_type === 'sentence' && sources.has(m.target_id)) {
        candidates.add('new_' + m.mark_id);
      } else if (!(m.mark_type === '重新抽' && m.target_type === 'candidate' && candidates.has(m.target_id))) {
        throw new Error('GAP_MARKS_TARGET');
      }
    }
    return value;
  }
  function mergedMarks() {
    const map = new Map(diskMarks.map(m => [m.mark_id, m]));
    for (const m of pending) map.set(m.mark_id, m);
    return [...map.values()];
  }
  function newCandidate(mark, isPending) {
    const article = document.createElement('article');
    article.id = 'new_' + mark.mark_id;
    article.className = 'fact-unit new-candidate';
    article.dataset.kind = 'candidate';
    article.tabIndex = 0;
    article.setAttribute('aria-label', '空白候选，新生成，待抽');
    const head = addElement(article, 'div', null, 'fact-heading');
    addElement(head, 'span', '＋', 'fact-number');
    const blank = addElement(head, 'div', null, 'blank-fact');
    blank.setAttribute('aria-label', '空白事实');
    const meta = addElement(article, 'div', null, 'fact-meta');
    addElement(meta, 'span', '新生成，待抽', 'status uncertain');
    if (isPending) addElement(meta, 'span', '尚未落盘', 'pending-label');
    addElement(article, 'div', `来自原文第 ${sources.get(mark.target_id).number} 句；尚无抽取内容，不分账。`, 'new-note');
    addElement(article, 'span', null, 'reextract-slot');
    const toolbar = addElement(article, 'div', null, 'toolbar');
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', '这条候选的标记');
    const button = addElement(toolbar, 'button', '重新抽');
    button.type = 'button'; button.dataset.action = 'reextract'; button.dataset.target = article.id;
    return article;
  }
  function renderMarks() {
    const all = mergedMarks(), unsaved = new Set(pending.map(m => m.mark_id));
    const additions = new Map(all.filter(m => m.mark_type === '漏抽').map(m => ['new_' + m.mark_id, m]));
    // 不重建现有候选，避免鼠标、键盘焦点随着保存跳走。
    for (const [id, mark] of additions) {
      if (!byId(id)) byId('fact-list').append(newCandidate(mark, unsaved.has(mark.mark_id)));
      const node = byId(id);
      node.dataset.sourceId = mark.target_id;
      const label = node.querySelector('.pending-label');
      if (label && !unsaved.has(mark.mark_id)) label.remove();
    }
    for (const node of document.querySelectorAll('.new-candidate')) {
      // 这里只清理未核对快照中的旧画面，不存在任何用户可点的撤回操作。
      if (!additions.has(node.id)) node.remove();
    }
    for (const s of sources.values()) {
      const slot = byId('mark_' + s.id); slot.replaceChildren();
      const count = all.filter(m => m.mark_type === '漏抽' && m.target_id === s.id).length;
      if (count) addElement(slot, 'span', `已标补漏 ${count}`, 'marker-badge');
    }
    document.querySelectorAll('.reextract-slot').forEach(slot => slot.replaceChildren());
    for (const m of all.filter(m => m.mark_type === '重新抽')) {
      const node = byId(m.target_id); if (!node) continue;
      const slot = node.querySelector('.reextract-slot');
      if (slot && !slot.childElementCount) addElement(slot, 'span', '标记：重新抽', 'marker-badge');
      if (slot && unsaved.has(m.mark_id)) addElement(slot, 'span', '尚未落盘', 'pending-label');
    }
    byId('mark-count').textContent = String(all.length);
    const log = byId('marks-log'); log.replaceChildren();
    for (const m of all.slice(-5)) {
      const source = sources.get(m.target_id), candidate = originals.get(m.target_id);
      const target = source ? `原文 ${source.number}` : candidate ? `候选 ${candidate.number}` : '新候选';
      const line = addElement(log, 'span', `${m.mark_type} · ${target} · ${new Date(m.created_at).toLocaleTimeString('zh-CN')}${unsaved.has(m.mark_id) ? ' · 未落盘' : ''}`);
      line.title = m.created_at;
    }
    if (active) highlight(active.kind, active.id);
    queueLines();
  }
  function clearHighlight() {
    document.querySelectorAll('.is-linked,.is-active,.is-added-linked').forEach(node => {
      node.classList.remove('is-linked', 'is-active', 'is-added-linked');
    });
  }
  function revealInPanel(id) {
    const node = byId(id), panel = node?.closest('.panel-scroll');
    if (!node || !panel) return;
    const box = node.getBoundingClientRect(), frame = panel.getBoundingClientRect();
    if (box.top < frame.top + 5) panel.scrollTop += box.top - frame.top - 5;
    else if (box.bottom > frame.bottom - 5) panel.scrollTop += box.bottom - frame.bottom + 5;
  }
  function highlight(kind, id) {
    const changed = !active || active.kind !== kind || active.id !== id;
    clearHighlight(); active = {kind, id};
    const all = mergedMarks();
    const node = byId(id); if (node) node.classList.add('is-active');
    let factIds = [], sentenceIds = [];
    if (kind === 'sentence' && sources.has(id)) {
      sentenceIds = [id]; factIds = sources.get(id).candidate_ids.slice();
    } else if (originals.has(id)) {
      factIds = [id]; sentenceIds = originals.get(id).source_ids.slice();
    }
    factIds.forEach(fid => {
      byId(fid)?.classList.add('is-linked');
      byId('ledger_' + fid)?.classList.add('is-linked');
    });
    sentenceIds.forEach(sid => byId(sid)?.classList.add('is-linked'));
    // 只挪另一栏的内部滚动条；不让作者悬停的那条从鼠标下跑开，不做平滑动画。
    if (changed) {
      if (kind === 'sentence' && factIds.length) revealInPanel(factIds[0]);
      if (kind === 'candidate' && sentenceIds.length) revealInPanel(sentenceIds[0]);
      if (factIds.length) revealInPanel('ledger_' + factIds[0]);
    }
    for (const m of all.filter(m => m.mark_type === '漏抽')) {
      const fresh = 'new_' + m.mark_id;
      if ((kind === 'sentence' && m.target_id === id) || fresh === id) {
        byId(m.target_id)?.classList.add('is-added-linked');
        byId(fresh)?.classList.add('is-added-linked');
      }
    }
  }
  function hoverable(target) { return target.closest?.('[data-kind]'); }
  document.addEventListener('pointerover', event => {
    const node = hoverable(event.target); if (!node) return;
    pointerActive = node; highlight(node.dataset.kind, node.id);
  });
  document.addEventListener('pointerout', event => {
    const node = hoverable(event.target); if (!node || node.contains(event.relatedTarget)) return;
    pointerActive = null;
    const focused = hoverable(document.activeElement);
    if (focused) highlight(focused.dataset.kind, focused.id); else { active = null; clearHighlight(); }
  });
  document.addEventListener('focusin', event => {
    const node = hoverable(event.target); if (node) highlight(node.dataset.kind, node.id);
  });
  document.addEventListener('focusout', () => {
    queueMicrotask(() => {
      const node = hoverable(document.activeElement) || pointerActive;
      if (node) highlight(node.dataset.kind, node.id); else { active = null; clearHighlight(); }
    });
  });
  let linesQueued = false;
  function queueLines() {
    if (linesQueued) return;
    linesQueued = true;
    requestAnimationFrame(() => { linesQueued = false; drawLines(); });
  }
  function drawLines() {
    const svg = byId('connection-lines'), board = byId('board').getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${board.width} ${board.height}`);
    svg.replaceChildren();
    for (const m of mergedMarks().filter(mark => mark.mark_type === '漏抽')) {
      const startNode = byId(m.target_id), endNode = byId('new_' + m.mark_id);
      if (!startNode || !endNode) continue;
      const a = startNode.getBoundingClientRect(), b = endNode.getBoundingClientRect();
      const pa = startNode.closest('.panel-scroll').getBoundingClientRect();
      const pb = endNode.closest('.panel-scroll').getBoundingClientRect();
      if (a.bottom <= pa.top || a.top >= pa.bottom || b.bottom <= pb.top || b.top >= pb.bottom) continue;
      const x1 = a.right - board.left, x2 = b.left - board.left;
      const y1 = Math.min(pa.bottom - 6, Math.max(pa.top + 6, a.top + a.height / 2)) - board.top;
      const y2 = Math.min(pb.bottom - 6, Math.max(pb.top + 6, b.top + b.height / 2)) - board.top;
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.dataset.markId = m.mark_id;
      path.setAttribute('d', `M ${x1} ${y1} C ${x1+26} ${y1}, ${x2-26} ${y2}, ${x2} ${y2}`);
      svg.append(path);
    }
  }
  document.querySelectorAll('.panel-scroll,.canvas').forEach(node => node.addEventListener('scroll', queueLines, {passive:true}));
  window.addEventListener('resize', queueLines, {passive:true});

  // 浏览器记住的只有授权句柄；标记正文从来不放进 IndexedDB 或 localStorage。
  async function handleMemory(write, value) {
    if (!window.indexedDB) return null;
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('door1-directory-permission-r01', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('handles');
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('GAP_HANDLE_MEMORY_BUSY'));
      request.onsuccess = () => {
        const db = request.result;
        try {
        const tx = db.transaction('handles', write ? 'readwrite' : 'readonly');
        const store = tx.objectStore('handles');
        const op = write ? store.put(value, location.href) : store.get(location.href);
        let result = null;
        op.onsuccess = () => { result = op.result; };
        tx.oncomplete = () => { db.close(); resolve(result); };
        tx.onerror = () => { db.close(); reject(tx.error); };
        tx.onabort = () => { db.close(); reject(tx.error); };
        } catch (error) { db.close(); reject(error); }
      };
    });
  }
  async function verifyDirectory(handle) {
    // 不列目录、不读任意正文；只核对同名 HTML 的页头标记。
    const pageHandle = await handle.getFileHandle(data.output_name);
    const file = await pageHandle.getFile();
    const head = await file.slice(0, 2048).text();
    if (!head.includes(`<meta name="door1-document" content="${data.document_token}">`)) {
      throw new Error('GAP_DIRECTORY_MISMATCH');
    }
  }
  async function readDisk(handle = directory) {
    const fileHandle = await handle.getFileHandle('door1.marks.json');
    const file = await fileHandle.getFile();
    if (file.size > maxBytes) throw new Error('GAP_MARKS_TOO_LARGE');
    const text = await file.text();
    const value = validate(JSON.parse(text));
    return {fileHandle, text, value};
  }
  async function loadDisk() {
    try {
      const current = await readDisk();
      diskMarks = current.value.marks;
      renderMarks();
      message(`已读回 ${diskMarks.length} 条标记；只写同目录的 door1.marks.json。`);
      return true;
    } catch (error) {
      message('标记没读到；边车原样保留，当前画面不是最新标记。', true);
      return false;
    }
  }
  async function chooseDirectory() {
    if (typeof window.showDirectoryPicker !== 'function') throw new Error('GAP_BROWSER_UNSUPPORTED');
    // 直接从按钮点击进入，不能放到后台任务里再请求授权。
    const handle = await window.showDirectoryPicker({id: 'door1-marks', mode: 'readwrite'});
    await verifyDirectory(handle);
    const permission = await handle.queryPermission({mode:'readwrite'});
    if (permission !== 'granted') throw new Error('GAP_MARKS_PERMISSION');
    directory = handle; rememberedHandle = handle;
    try { await handleMemory(true, handle); } catch (_) { /* 不记句柄也能保存，重开时再选目录。 */ }
    connectButton.textContent = '重读标记 / 连接目录';
    return handle;
  }
  async function ensureDirectoryFromClick() {
    if (directory) {
      if (await directory.queryPermission({mode:'readwrite'}) === 'granted') return directory;
      if (await directory.requestPermission({mode:'readwrite'}) === 'granted') return directory;
      throw new Error('GAP_MARKS_PERMISSION');
    }
    // 初次调用会立即展示目录选择器；不先等待其他异步存储操作。
    return chooseDirectory();
  }
  function explainSaveError(error) {
    if (error?.name === 'AbortError') return '本次没有授权，标记尚未落盘；连接目录后可继续保存。';
    if (error?.message === 'GAP_DIRECTORY_MISMATCH') return '选的不是这张页面所在目录；标记尚未落盘。';
    if (error?.message === 'GAP_BROWSER_UNSUPPORTED') return '这个浏览器不能写同目录边车；请用支持目录授权的桌面浏览器。标记尚未落盘。';
    if (error?.message === 'GAP_MARKS_PERMISSION' || error?.name === 'NotAllowedError') return '文件权限没有获准，标记尚未落盘；点连接目录重试。';
    if (error?.message === 'GAP_MARKS_CHANGED') return '边车正被别处改动，本次标记未落盘；请先停下另一处编辑再重试。';
    return '标记没读到，或本次写入失败；边车未主动清空，新标记尚未核对落盘。';
  }
  async function commitPending() {
    if (!pending.length) return;
    const submitted = pending.slice();
    const work = async () => {
      await verifyDirectory(directory);
      const old = await readDisk();
      const value = old.value;
      const existing = new Map(value.marks.map(m => [m.mark_id, m]));
      for (const m of submitted) {
        if (existing.has(m.mark_id)) {
          if (JSON.stringify(existing.get(m.mark_id)) !== JSON.stringify(m)) throw new Error('GAP_MARKS_CONFLICT');
        } else { value.marks.push(m); existing.set(m.mark_id, m); }
      }
      validate(value);
      const text = JSON.stringify(value, null, 2) + '\n';
      if (new TextEncoder().encode(text).length > maxBytes) throw new Error('GAP_MARKS_TOO_LARGE');
      let writable;
      try {
        writable = await old.fileHandle.createWritable({mode:'exclusive'});
        const recheck = await old.fileHandle.getFile();
        if (await recheck.text() !== old.text) throw new Error('GAP_MARKS_CHANGED');
        await writable.write(text);
        await writable.close();
        writable = null;
      } catch (error) {
        if (writable) { try { await writable.abort(); } catch (_) {} }
        throw error;
      }
      const readback = await readDisk();
      const readIds = new Set(readback.value.marks.map(m => m.mark_id));
      if (!submitted.every(m => readIds.has(m.mark_id))) throw new Error('GAP_MARKS_CHANGED');
      diskMarks = readback.value.marks;
      const committed = new Set(submitted.map(m => m.mark_id));
      pending = pending.filter(m => !committed.has(m.mark_id));
      renderMarks();
      message(`已落盘 ${diskMarks.length} 条标记，刷新后从边车读回。候选库没有改动。`);
    };
    if (navigator.locks) await navigator.locks.request('door1-marks-' + data.view_id, {mode:'exclusive'}, work);
    else await work();
  }
  function markRecord(type, id) {
    const bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
    return {mark_id: 'm_' + [...bytes].map(b => b.toString(16).padStart(2,'0')).join(''),
      mark_type: type, target_type: type === '漏抽' ? 'sentence' : 'candidate', target_id: id,
      created_at: new Date().toISOString()};
  }
  async function addMarkFromClick(button) {
    if (saving || restoring) return;
    const type = button.dataset.action === 'missing' ? '漏抽' : '重新抽';
    const mark = markRecord(type, button.dataset.target);
    if (mergedMarks().length >= maxMarks) { message('标记数量已到本刀上限；本次没有添加。', true); return; }
    pending.push(mark); renderMarks();
    saving = true; button.disabled = true;
    try {
      await ensureDirectoryFromClick();
      await commitPending();
      if (type === '漏抽') {
        byId('new_' + mark.mark_id)?.scrollIntoView({block:'nearest', inline:'nearest', behavior:'instant'});
        queueLines();
      }
    } catch (error) { message(explainSaveError(error), true); }
    finally { saving = false; button.disabled = false; }
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('button[data-action]');
    if (button) void addMarkFromClick(button);
  });
  connectButton.addEventListener('click', async () => {
    if (saving || restoring) return;
    saving = true; connectButton.disabled = true;
    try {
      if (directory || rememberedHandle) {
        directory = directory || rememberedHandle;
        if (await directory.queryPermission({mode:'readwrite'}) !== 'granted'
            && await directory.requestPermission({mode:'readwrite'}) !== 'granted') {
          directory = null; throw new Error('GAP_MARKS_PERMISSION');
        }
        await verifyDirectory(directory);
      } else { await chooseDirectory(); }
      if (pending.length) await commitPending(); else await loadDisk();
    } catch (error) {
      message(explainSaveError(error), true);
      if (error?.message === 'GAP_DIRECTORY_MISMATCH' || error?.name === 'NotFoundError') {
        directory = null; rememberedHandle = null;
      }
    } finally { saving = false; connectButton.disabled = false; }
  });
  window.addEventListener('beforeunload', event => {
    if (pending.length || saving) { event.preventDefault(); event.returnValue = ''; }
  });
  async function restoreOnOpen() {
    renderMarks();
    if (data.marks.status === 'ERROR') message('标记没读到；生成页面时边车就有问题，文件原样保留。', true);
    else message(`构建时读到 ${diskMarks.length} 条标记；正在核对边车授权。`);
    try {
      const handle = await handleMemory(false);
      rememberedHandle = handle || null;
      if (handle && await handle.queryPermission({mode:'read'}) === 'granted') {
        directory = handle;
        await verifyDirectory(handle);
        await loadDisk();
      } else if (data.marks.status !== 'ERROR') {
        message(`构建时读到 ${diskMarks.length} 条标记；重开后尚未核对，请连接页面所在目录。`);
      }
    } catch (_) {
      directory = null;
      if (data.marks.status !== 'ERROR') message('尚未核对边车；请连接页面所在目录，不把构建时快照当成最新标记。', true);
    }
    restoring = false;
    document.querySelectorAll('button').forEach(button => { button.disabled = false; });
    document.documentElement.dataset.ready = 'true';
  }
  // 初次核对授权时不接写操作，避免晚到的旧快照盖过刚添加的标记。
  document.querySelectorAll('button').forEach(button => { button.disabled = true; });
  void restoreOnOpen();
})();
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def safe_json(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _sentences(model: dict[str, Any]) -> str:
    lines = []
    for sentence in model["sentences"]:
        sid = esc(sentence["id"])
        missing = sentence["possibly_missing"]
        lines.append(
            f'<section id="{sid}" class="source-unit{" possibly-missing" if missing else ""}" data-kind="sentence" tabindex="0" aria-label="原文第 {sentence["number"]} 句">'
            f'<div class="sentence-top"><span class="number">{sentence["number"]:02d}</span>'
            + ('<span class="missing-label">可能漏抽</span>' if missing else "")
            + f'</div><span class="sentence-text">{esc(sentence["text"])}</span><span id="mark_{sid}"></span>'
            f'<div class="toolbar" role="toolbar" aria-label="这句原文的标记"><button type="button" data-action="missing" data-target="{sid}">＋ 补一条</button></div></section>'
        )
    lines.append(
        '<p class="source-note">浅灰的句子还没连上当前候选。<br>这只是“可能漏抽”提示，不是整章抽全结论。补漏标记也不等于已经抽到。</p>'
    )
    return "\n".join(lines)


def _facts(model: dict[str, Any]) -> str:
    lines = []
    for item in model["candidates"]:
        cid = esc(item["id"])
        uncertain = item["status"] not in {"已发生", "正在发生"}
        lines.append(
            f'<article id="{cid}" class="fact-unit" data-kind="candidate" tabindex="0" aria-label="候选第 {item["number"]} 条">'
            f'<div class="fact-heading"><span class="fact-number">{item["number"]:02d}</span><strong>{esc(item["fact"])}</strong></div>'
            f'<div class="fact-meta"><span class="status{" uncertain" if uncertain else ""}">{esc(item["status"])}</span>'
            f'<span class="route">→ {esc(item["ledger"])}候选</span></div>'
            f'<div class="evidence"><em>证据</em>{esc(item["evidence"])}</div>'
            + (
                f'<div class="source-location">{esc(item["source_location"])}</div>'
                if item["source_matched"]
                else '<div class="source-unmatched">来源没对上</div>'
            )
            + f'<span class="reextract-slot"></span><div class="toolbar" role="toolbar" aria-label="这条候选的标记"><button type="button" data-action="reextract" data-target="{cid}">重新抽</button></div></article>'
        )
    return "\n".join(lines)


def _ledgers(model: dict[str, Any]) -> str:
    lines = []
    for ledger in model["ledgers"]:
        rows = []
        for row in ledger["entries"]:
            tags = "".join(
                f"<span>{esc(key)}={esc(value)}</span>"
                for key, value in row["tags"].items()
            )
            groups = " ".join(
                f'<span class="group-pill">{esc(name)}</span>'
                for name in row["tag_groups"]
            )
            rows.append(
                f'<div id="{esc(row["id"])}" class="ledger-row"><strong class="ledger-key" title="{esc(row["candidate_id"] or row["id"])}"><span class="field-name">主键</span>{esc(row["primary_key"])}</strong>'
                f'<div class="ledger-tags"><span class="field-name">标签</span>{tags}</div><div class="tag-groups"><span class="field-name">标签组</span>{groups}</div></div>'
            )
        if not rows:
            rows.append('<p class="empty-ledger">暂时没有分到这里的条目</p>')
        lines.append(
            f'<section class="ledger-group" data-ledger="{esc(ledger["name"])}"><header class="ledger-title"><h3>{esc(ledger["name"])}</h3><span class="ledger-count">{len(ledger["entries"])} 条</span></header>'
            + "".join(rows)
            + "</section>"
        )
    lines.append(
        '<p class="ledger-note">这里只展示候选归类，不是正式事实。标签组只显示名字，本刀不执行权限规则。</p>'
    )
    return "\n".join(lines)


def render_page(
    model: dict[str, Any],
    marks: dict[str, Any],
    *,
    output_name: str,
    document_token: str,
) -> str:
    payload = {
        **model,
        "marks": marks,
        "output_name": output_name,
        "document_token": document_token,
    }
    initial = (
        "标记没读到"
        if marks["status"] == "ERROR"
        else "构建时标记快照；重开后须核对同目录边车。"
    )
    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
        f'<meta name="door1-document" content="{esc(document_token)}">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'; frame-src 'none'\">\n"
        "<title>北塔夹具 · 门 1 作者认库</title>\n<style>"
        + STYLE
        + "</style></head><body>\n"
        '<header class="top"><div class="topline"><div class="eyebrow">作者认库 <span class="chip">门 1 · 第一刀</span></div>'
        '<button id="connect-marks" class="permission-button" type="button">连接页面目录，保存标记</button></div>'
        f'<h1>{esc(model["identity"])}</h1><p class="subtitle">悬停一句，看看它从哪来、往哪本账去。标记保留下来，候选库保持原样。</p></header>'
        '<div class="meta-strip"><div class="metrics">'
        f"<span><strong>{len(model['sentences'])}</strong>句原文</span><span><strong>{len(model['candidates'])}</strong>条候选</span>"
        f'<span><strong>{model["missing_count"]}</strong>句可能漏抽</span><span><strong id="mark-count">{len(marks["document"]["marks"])}</strong>条标记</span></div>'
        '<div class="legend"><span class="dot"></span>原文与候选对应<span class="dot pale"></span>还没有对应</div></div>'
        '<main class="canvas"><div id="board" class="board">'
        '<section class="panel" aria-labelledby="source-title"><header class="panel-head"><h2 id="source-title"><span class="step">01</span>正文大卡</h2><p>北塔夹具 · 第 1 章</p></header>'
        '<div class="panel-scroll" id="source-list">'
        + _sentences(model)
        + "</div></section>"
        '<section class="panel" aria-labelledby="fact-title"><header class="panel-head"><h2 id="fact-title"><span class="step">02</span>事实句子大卡</h2><p>只读当前候选 · 状态照原样保留</p></header>'
        '<div class="panel-scroll" id="fact-list">' + _facts(model) + "</div></section>"
        '<section class="panel" aria-labelledby="ledger-title"><header class="panel-head"><h2 id="ledger-title"><span class="step">03</span>10 本账 · 简装</h2><p>主键 + 标签 + 标签组 · 仅展示归类</p></header>'
        '<div class="panel-scroll" id="ledger-list">'
        + _ledgers(model)
        + "</div></section>"
        '<section class="panel storyboard" aria-labelledby="storyboard-title"><header class="panel-head"><h2 id="storyboard-title"><span class="step">04</span>分镜</h2></header>'
        '<div class="panel-scroll"><div class="placeholder-box">分镜（占位，本刀不接）</div></div></section>'
        '<svg id="connection-lines" class="connection-lines" aria-hidden="true"></svg></div></main>'
        '<section class="marks-bar" aria-label="标记读写状态"><strong>本地标记</strong><div class="marks-text">'
        f'<div id="marks-status" role="status" aria-live="polite">{esc(initial)}</div><div id="marks-log" class="marks-log"></div>'
        '<div class="footer-note">边车：door1.marks.json · 只保留标记类型、指向和时间等定位字段，不改正式事实。</div></div></section>'
        '<noscript><p class="noscript">JavaScript 没有启用。原文、候选和账本仍可看；悬停对应和标记保存暂不可用。</p></noscript>'
        '<script id="door1-data" type="application/json">'
        + safe_json(payload)
        + "</script>\n<script>"
        + SCRIPT
        + "</script></body></html>\n"
    )
