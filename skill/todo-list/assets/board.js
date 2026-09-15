'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="board-token"]').content;
const labels = {todo:'할 일',doing:'작업 중',done:'작업 완료',pending:'미검수',queued:'검수 대기',running:'검수 중',complete:'검수 완료',changes:'수정 필요',blocked:'확인 불가',error:'실행 오류',stale:'재검수 필요'};
const filterNames = {all:'전체',ready:'검수 대기',attention:'확인 필요',complete:'검수 완료'};
let state = {tasks:[]}, filter = 'all', signature = '', editing = null;
const pending = new Set();
const active = task => ['running','queued'].includes(task.review);
const attention = task => ['changes','blocked','error','stale'].includes(task.review);
const ready = task => task.review === 'queued' || (task.work === 'done' && task.review === 'pending');
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
async function api(route, data) {
  const response = await fetch('/api/' + route, {
    method:data === undefined ? 'GET' : 'POST',
    headers:{'X-Board-Token':token,'Content-Type':'application/json'},
    body:data === undefined ? undefined : JSON.stringify(data),
    signal:AbortSignal.timeout(15000)
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || '요청에 실패했습니다.');
  return result;
}
async function refresh() {
  try {
    const next = await api('state');
    state = next;
    $('board-name').textContent = state.name;
    document.title = state.name + ' · Todo List';
    $('project').textContent = state.project.split('/').filter(Boolean).pop();
    $('project').title = state.project + ' · 프로젝트 설정';
    const nextSignature = JSON.stringify(state) + filter;
    if (signature !== nextSignature) { signature = nextSignature; render(); }
    $('sync').textContent = state.runnerAvailable ? '연결됨 · 상태 자동 갱신' : 'Codex CLI가 필요합니다 · 설치 후 다시 실행하세요';
  } catch (error) {
    $('sync').textContent = '연결 끊김 · 보드를 다시 열어주세요';
  }
}
async function action(route, data) {
  if (pending.has(data.id)) return;
  pending.add(data.id);
  $('error').textContent = '';
  render();
  try { await api(route, data); await refresh(); }
  catch (error) { $('error').textContent = error.message; }
  finally { pending.delete(data.id); render(); }
}
function detail(key, title, openKeys, cls) {
  const node = el('details', undefined, cls);
  node.dataset.key = key;
  node.open = openKeys.has(key);
  node.append(el('summary', title));
  return node;
}
function resultNode(result) {
  const node = el('div', undefined, 'result');
  node.append(el('p', result.summary));
  for (const check of result.checks || []) {
    const row = el('div', undefined, 'check');
    const label = {pass:'통과',fail:'실패',blocked:'확인 불가'}[check.status];
    row.append(el('strong', label + ' · ' + check.criterion), el('p', check.evidence));
    node.append(row);
  }
  if (result.findings?.length) {
    const list = el('ul');
    result.findings.forEach(text => list.append(el('li', text)));
    node.append(list);
  }
  return node;
}
function render() {
  const root = $('tasks');
  const openKeys = new Set([...root.querySelectorAll('details[open]')].map(node => node.dataset.key));
  const counts = {all:state.tasks.length,ready:state.tasks.filter(ready).length,attention:state.tasks.filter(attention).length,complete:state.tasks.filter(task => task.review === 'complete').length};
  document.querySelectorAll('[data-filter]').forEach(button => {
    button.replaceChildren(el('span', filterNames[button.dataset.filter]), el('span', String(counts[button.dataset.filter]), 'tab-count'));
    button.setAttribute('aria-pressed', String(button.dataset.filter === filter));
  });
  root.replaceChildren();
  const visible = state.tasks.filter(task => filter === 'all' || filter === 'ready' && ready(task) || filter === 'attention' && attention(task) || filter === 'complete' && task.review === 'complete');
  if (!visible.length) root.append(el('p', state.tasks.length ? '이 상태의 항목이 없습니다.' : '+ 버튼으로 첫 할 일을 추가하세요.', 'empty'));
  for (const task of visible) {
    const card = el('article', undefined, 'task');
    const badges = el('div', undefined, 'badges');
    badges.append(el('span', labels[task.work], 'badge ' + task.work), el('span', labels[task.review], 'badge ' + task.review));
    const row = el('div', undefined, 'task-row');
    const fold = detail(task.id + ':task', task.title, openKeys);
    fold.querySelector('summary').className = 'task-heading';
    const body = el('div', undefined, 'task-body');
    const info = detail(task.id + ':info', '검수 상세 · 조건 ' + task.criteria.length + '개', openKeys, 'task-details');
    const content = el('div', undefined, 'detail-content');
    content.append(el('h3', '대상 파일'));
    if (task.paths.length) task.paths.forEach(path => content.append(el('p', path, 'paths')));
    else content.append(el('p', '검수 요청 시 프로젝트에서 자동으로 찾습니다.', 'help'));
    content.append(el('h3', '검수 조건'));
    const criteria = el('ul');
    task.criteria.forEach(text => criteria.append(el('li', text)));
    content.append(criteria);
    if (task.result) {
      content.append(el('h3', '로컬 결과물 검수'), resultNode(task.result));
      if (task.finished) content.append(el('p', new Date(task.finished).toLocaleString('ko-KR'), 'timestamp'));
    }
    info.append(content); body.append(info);
    if (task.message) body.append(el('p', task.message, 'notice'));
    if (task.history?.length) {
      const history = detail(task.id + ':history', '이전 검수 ' + task.history.length + '회', openKeys, 'history');
      task.history.slice().reverse().forEach(item => {
        history.append(el('p', item.finished || '', 'timestamp'));
        if (item.result) history.append(resultNode(item.result));
      });
      body.append(history);
    }
    const actions = el('div', undefined, 'actions');
    const work = el('button', task.work === 'todo' ? '작업 시작' : task.work === 'doing' ? '작업 완료' : '다시 열기');
    work.disabled = active(task) || pending.has(task.id);
    work.onclick = () => action('status', {id:task.id,work:task.work === 'todo' ? 'doing' : task.work === 'doing' ? 'done' : 'doing'});
    const edit = el('button', '수정');
    edit.disabled = active(task) || pending.has(task.id);
    edit.onclick = () => openTask(task);
    actions.append(work, edit); body.append(actions); fold.append(body);
    const review = el('button', task.review === 'queued' ? '대기 중' : task.review === 'running' ? '검수 중…' : '검수 요청', 'primary review-button');
    review.disabled = active(task) || pending.has(task.id);
    review.setAttribute('aria-label', task.title + ' ' + review.textContent);
    review.onclick = () => action('review', {id:task.id});
    row.append(fold, review); card.append(badges, row);
    if (['blocked','error','changes'].includes(task.review)) {
      const reason = task.message || task.result?.summary;
      if (reason) card.append(el('p', reason, 'list-reason'));
    }
    root.append(card);
  }
}
function openTask(task = null) {
  editing = task?.id || null;
  $('task-form').reset(); $('advanced').open = false; $('task-error').textContent = '';
  $('task-form-title').textContent = task ? '할 일 수정' : '할 일 추가';
  if (task) { $('title').value = task.title; $('paths').value = task.paths.join('\n'); $('criteria').value = task.criteria.join('\n'); }
  $('task-dialog').showModal();
}
function openSettings() {
  $('name-input').value = state.name;
  $('project-input').value = state.project;
  $('settings-error').textContent = '';
  $('settings-dialog').showModal();
}
$('add').onclick = () => openTask();
$('board-name').onclick = openSettings;
$('project').onclick = openSettings;
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => $(button.dataset.close).close());
document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {filter = button.dataset.filter; render();});
$('task-form').onsubmit = async event => {
  event.preventDefault(); const submit = event.submitter; submit.disabled = true;
  try {
    const lines = id => $(id).value.split('\n').map(text => text.trim()).filter(Boolean);
    await api(editing ? 'edit' : 'add', {id:editing,title:$('title').value.trim(),paths:lines('paths'),criteria:lines('criteria')});
    $('task-dialog').close(); await refresh();
  } catch (error) { $('task-error').textContent = error.message; }
  finally { submit.disabled = false; }
};
$('settings-form').onsubmit = async event => {
  event.preventDefault(); const submit = event.submitter; submit.disabled = true;
  try {
    const project = $('project-input').value.trim();
    if (project !== state.project) await api('configure', {project});
    await api('rename', {name:$('name-input').value.trim()});
    $('settings-dialog').close(); await refresh();
  } catch (error) { $('settings-error').textContent = error.message; }
  finally { submit.disabled = false; }
};
refresh();
setInterval(() => {if (!document.hidden) refresh();}, 3000);
document.addEventListener('visibilitychange', () => {if (!document.hidden) refresh();});
