'use strict';
let languagePreference = localStorage.getItem('todo-list-language') || 'auto';
let locale = languagePreference === 'auto' ? (navigator.language.toLowerCase().startsWith('ko') ? 'ko' : 'en') : languagePreference;
if (!['ko','en'].includes(locale)) locale = 'en';
let translations = {}, readyLocale = false;
function tr(text) { return translations[locale]?.[text] ?? text; }
async function boot() {
  try {
    const response = await fetch('/locales.json');
    if (!response.ok) throw Error('Translation load failed');
    translations = await response.json();
    document.documentElement.lang = locale;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => { const text = node.textContent.trim(); if (text && translations[locale]?.[text]) node.textContent = node.textContent.replace(text,tr(text)); });
    document.querySelectorAll('[title],[placeholder],[aria-label]').forEach(node => {
      for (const attr of ['title','placeholder','aria-label']) if (node.hasAttribute(attr)) node.setAttribute(attr,tr(node.getAttribute(attr)));
    });
    readyLocale = true;
    await refresh();
  } catch (error) { $('sync').textContent = 'Unable to load language resources. Reload to retry.'; }
}

const $ = id => document.getElementById(id);
let token = document.querySelector('meta[name="board-token"]').content;
const getLabels = () => ({todo:tr('할 일'),doing:tr('작업 중'),done:tr('작업 완료'),pending:tr('미검수'),queued:tr('검수 대기'),running:tr('검수 중'),complete:tr('검수 완료'),changes:tr('수정 필요'),blocked:tr('확인 불가'),error:tr('실행 오류'),stale:tr('재검수 필요')});
const getFilterNames = () => ({all:tr('전체'),ready:tr('검수 대기'),attention:tr('확인 필요'),complete:tr('검수 완료'),notes:tr('아이디어')});
const requestedReviews=new Set();
let environmentTask=null;
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
async function api(route, data, refreshed=false) {
  let response;
  try { response = await fetch('/api/' + route, {
    method:data === undefined ? 'GET' : 'POST',
    headers:{'X-Board-Token':token,'Content-Type':'application/json','X-Board-Language':locale},
    body:data === undefined ? undefined : JSON.stringify(data),
    signal:AbortSignal.timeout(route==='environment'?25000:15000)
  });
  } catch(error) { throw Error(tr('서버 연결이 끊겼습니다. 입력 내용은 유지됩니다. 서버가 연결되면 저장을 다시 눌러주세요.')); }
  if(response.status===403&&!refreshed){
    const page=await fetch('/',{cache:'no-store'});
    if(page.ok){const html=new DOMParser().parseFromString(await page.text(),'text/html');const next=html.querySelector('meta[name=board-token]')?.content;if(next){token=next;return api(route,data,true);}}
  }
  const result = await response.json();
  if (!response.ok) throw Error(result.error || tr('요청에 실패했습니다.'));
  return result;
}
async function refresh() {
  try {
    const next = await api('state');
    state = next;
    for(const task of state.tasks){if(requestedReviews.has(task.id)&&!active(task)){requestedReviews.delete(task.id);if(['blocked','error'].includes(task.review)&&!document.querySelector('dialog[open]'))openEnvironment(task);}}
    $('board-name').textContent = state.name;
    document.title = state.name + ' · Todo List';
    $('project').textContent = state.project.split('/').filter(Boolean).pop();
    $('project').title = state.project + tr(' · 프로젝트 설정');
    const nextSignature = JSON.stringify(state) + filter;
    if (signature !== nextSignature) { signature = nextSignature; render(); }
    $('sync').textContent = state.runnerAvailable ? tr('연결됨 · 상태 자동 갱신') : tr('Codex CLI가 필요합니다 · 설치 후 다시 실행하세요');
  } catch (error) {
    $('sync').textContent = tr('연결 끊김 · 보드를 다시 열어주세요');
  }
}
async function action(route, data) {
  if (pending.has(data.id)) return;
  pending.add(data.id);
  $('error').textContent = '';
  render();
  try { await api(route, data); if(route==='review')requestedReviews.add(data.id); await refresh(); }
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
    const label = {pass:tr('통과'),fail:tr('실패'),blocked:tr('확인 불가')}[check.status];
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
  const tasks=state.tasks.filter(task=>!task.deletedAt&&task.kind!=='note');
  const counts = {all:tasks.length,ready:tasks.filter(ready).length,attention:tasks.filter(attention).length,complete:tasks.filter(task => task.review === 'complete').length,notes:state.tasks.filter(task=>!task.deletedAt&&task.kind==='note').length};
  document.querySelectorAll('[data-filter]').forEach(button => {
    button.replaceChildren(el('span', getFilterNames()[button.dataset.filter]), el('span', String(counts[button.dataset.filter]), 'tab-count'));
    button.setAttribute('aria-pressed', String(button.dataset.filter === filter));
  });
  root.replaceChildren();
  $('trash').textContent=tr('휴지통')+' '+state.tasks.filter(task=>task.deletedAt).length;
  const visible = state.tasks.filter(task => task.deletedAt ? filter==='trash' : filter==='trash' ? false : task.kind==='note' ? filter==='notes' : filter === 'all' || filter === 'ready' && ready(task) || filter === 'attention' && attention(task) || filter === 'complete' && task.review === 'complete');
  if (!visible.length) root.append(el('p', state.tasks.length ? tr('이 상태의 항목이 없습니다.') : tr('+ 버튼으로 첫 할 일을 추가하세요.'), 'empty'));
  for (const task of visible) {
    const card = el('article', undefined, 'task');
    if(task.deletedAt){const row=el('div',undefined,'trash-row');const restore=el('button',tr('복원'));restore.onclick=()=>action('archive',{id:task.id,deleted:false});row.append(el('span',task.title),restore);card.append(row);root.append(card);continue;}
    if(task.kind==='note'){
      const fold=detail(task.id+':note',task.title,openKeys);fold.querySelector('summary').className='task-heading';
      const body=el('div',undefined,'task-body');body.append(el('p',task.note||'', 'note-body'));
      const convert=el('button',tr('할 일로 전환'));convert.onclick=()=>openTask({...task,kind:'task'});const remove=el('button',tr('삭제'),'danger-button');remove.onclick=()=>action('archive',{id:task.id,deleted:true});body.append(convert,remove);fold.append(body);
      const row=el('div',undefined,'task-row');const edit=el('button',tr('수정'),'review-button');edit.onclick=()=>openTask(task);row.append(fold,edit);card.append(row);root.append(card);continue;
    }
    const badges = el('div', undefined, 'badges');
    badges.append(el('span', getLabels()[task.work], 'badge ' + task.work), el('span', getLabels()[task.review], 'badge ' + task.review));
    (task.platforms || ['android','ios']).forEach(platform => badges.append(el('span', {web:'Web',android:'Android',ios:'iOS'}[platform], 'badge platform')));
    const row = el('div', undefined, 'task-row');
    const fold = detail(task.id + ':task', task.title, openKeys);
    fold.querySelector('summary').className = 'task-heading';
    const body = el('div', undefined, 'task-body');
    const info = detail(task.id + ':info', tr('검수 상세 · 조건 ') + task.criteria.length + tr('개'), openKeys, 'task-details');
    const content = el('div', undefined, 'detail-content');
    if(task.note)content.append(el('p',task.note,'note-body'));
    content.append(el('h3', tr('대상 파일')));
    if (task.paths.length) task.paths.forEach(path => content.append(el('p', path, 'paths')));
    else content.append(el('p', tr('검수 요청 시 프로젝트에서 자동으로 찾습니다.'), 'help'));
    content.append(el('h3', tr('검수 조건')));
    const criteria = el('ul');
    task.criteria.forEach(text => criteria.append(el('li', text)));
    content.append(criteria);
    if (task.result) {
      content.append(el('h3', task.mode==='live'?tr('실제 화면 검수'):tr('로컬 결과물 검수')), resultNode(task.result));
      if (task.finished) content.append(el('p', new Date(task.finished).toLocaleString(locale), 'timestamp'));
    }
    for (const platform of task.result?.platforms || []) {
      content.append(el('h3',platform.platform+' · '+({pass:tr('통과'),fail:tr('실패'),blocked:tr('확인 불가')}[platform.status])));
      const steps=el('ol');platform.steps.forEach(step=>steps.append(el('li',step)));content.append(steps);
    }
    (task.evidence || []).forEach((item,index)=>{const button=el('button',item.platform+' · '+tr('스크린샷'));button.onclick=async()=>{try{const response=await fetch('/api/evidence/'+task.id+'/'+index,{headers:{'X-Board-Token':token}});if(!response.ok)throw Error(tr('화면 증거를 불러오지 못했습니다.'));const blob=await response.blob();if(evidenceUrl)URL.revokeObjectURL(evidenceUrl);evidenceUrl=URL.createObjectURL(blob);$('evidence-image').src=evidenceUrl;$('evidence-dialog').showModal();}catch(error){$('error').textContent=error.message;}};content.append(button);});
    info.append(content); body.append(info);
    if (task.message) body.append(el('p', task.message, 'notice'));
    if (task.history?.length) {
      const history = detail(task.id + ':history', tr('이전 검수 ') + task.history.length + tr('회'), openKeys, 'history');
      task.history.slice().reverse().forEach(item => {
        history.append(el('p', item.finished || '', 'timestamp'));
        if (item.result) history.append(resultNode(item.result));
      });
      body.append(history);
    }
    const actions = el('div', undefined, 'actions');
    const work = el('button', task.work === 'todo' ? tr('작업 시작') : task.work === 'doing' ? tr('작업 완료') : tr('다시 열기'));
    work.disabled = active(task) || pending.has(task.id);
    work.onclick = () => action('status', {id:task.id,work:task.work === 'todo' ? 'doing' : task.work === 'doing' ? 'done' : 'doing'});
    const edit = el('button', tr('수정'));
    edit.disabled = active(task) || pending.has(task.id);
    edit.onclick = () => openTask(task);
    const remove=el('button',tr('삭제'),'danger-button');remove.disabled=active(task)||pending.has(task.id);remove.onclick=()=>action('archive',{id:task.id,deleted:true});actions.append(work, edit,remove); body.append(actions); fold.append(body);
    const review = el('button', task.review === 'queued' ? tr('대기 중') : task.review === 'running' ? tr('검수 중…') : tr('검수 요청'), 'primary review-button');
    review.disabled = active(task) || pending.has(task.id);
    if(['blocked','error'].includes(task.review))review.textContent=tr('검수 준비');
    review.setAttribute('aria-label', task.title + ' ' + review.textContent);
    review.onclick = () => ['blocked','error'].includes(task.review)?openEnvironment(task):action('review', {id:task.id,language:locale});
    row.append(fold, review); card.append(badges, row);
    if (['blocked','error','changes'].includes(task.review)) {
      const reason = task.message || task.result?.summary;
      if (reason) card.append(el('p', reason, 'list-reason'));
    }
    root.append(card);
  }
}
async function checkEnvironment(){
  $('environment-devices').textContent=tr('기기 연결 확인 중…');$('environment-retry').disabled=true;
  try { const {result}=await api('environment',{});const root=$('environment-devices');root.replaceChildren();
    let missingTool=false;
    for(const platform of environmentTask.platforms || ['android','ios']){
      const entry=result[platform];let message;
      if(platform==='web')message=tr('테스트 웹 주소와 브라우저 화면 접근을 준비하세요.');
      else if(entry?.status==='found')message=entry.devices.map(d=>d.name+' · '+(d.status==='unauthorized'?tr('기기에서 USB 디버깅을 승인하세요.'):d.status)).join(', ')+ ' — '+tr('연결 확인됨. 화면 제어 도구의 접근은 검수 시 확인합니다.');
      else if(entry?.status==='missing')message=platform==='ios'?tr('iOS Simulator를 실행하거나 지원되는 테스트 기기를 연결하세요.'):tr('테스트폰을 USB로 연결하거나 Android 에뮬레이터를 실행하세요.');
      else message=tr('기기 목록에 접근하지 못했습니다. SDK 설치와 도구 접근 권한을 확인하세요.');
      root.append(el('p',platform.toUpperCase()+' · '+message));
      if(platform!=='web'&&!result.tools?.[platform]){missingTool=true;root.append(el('p',platform.toUpperCase()+' · '+tr('화면 제어 도구가 없습니다. Codex에서 Mobile MCP 연결을 요청하세요. 연결 전에는 재검수할 수 없습니다.'),'errorbox'));}
    }
    $('environment-retry').disabled=missingTool;
  }catch(error){$('environment-devices').textContent=error.message;}
}
function openEnvironment(task){environmentTask=task;$('environment-reason').textContent=task.message||task.result?.summary||'';$('environment-context').value=task.reviewContext||'';$('environment-error').textContent='';$('environment-dialog').showModal();checkEnvironment();}
$('environment-check').onclick=checkEnvironment;
$('environment-edit').onclick=()=>{$('environment-dialog').close();openTask(environmentTask);};
$('environment-retry').onclick=async()=>{const task=environmentTask;const context=$('environment-context').value.trim();$('environment-dialog').close();await action('review',{id:task.id,language:locale,context});};
let evidenceUrl=null;
function syncPlatforms(){const note=document.querySelector('[name=item-kind]:checked').value==='note';$('task-form-title').textContent=note?(editing?tr('아이디어 수정'):tr('아이디어 추가')):(editing?tr('할 일 수정'):tr('할 일 추가'));$('note-fields').hidden=!note;$('platform-fields').hidden=note;$('advanced').hidden=note;$('web-target').hidden=note||!document.querySelector('[name=platform][value=web]').checked;}
document.querySelectorAll('[name=item-kind]').forEach(input=>input.onchange=syncPlatforms);
document.querySelectorAll('[name=platform]').forEach(input=>input.onchange=syncPlatforms);
function openTask(task = null) {
  editing = task?.id || null;
  $('task-form').reset(); $('advanced').open = false; $('task-error').textContent = '';
  $('task-form-title').textContent = task ? tr('할 일 수정') : tr('할 일 추가');
  if (task) { $('title').value = task.title; $('paths').value = task.paths.join('\n'); $('criteria').value = task.criteria.join('\n'); }
  document.querySelectorAll('[name=item-kind]').forEach(input=>input.checked=input.value===(task?.kind || (filter==='notes'?'note':'task')));$('note-body').value=task?.note || '';
  const platforms=task?.platforms || ['android','ios'];
  document.querySelectorAll('[name=platform]').forEach(input=>input.checked=platforms.includes(input.value));
  $('web-url').value=task?.webUrl || '';syncPlatforms();
  $('task-dialog').showModal();
}
function openSettings() {
  $('language').value = languagePreference;
  $('name-input').value = state.name;
  $('project-input').value = state.project;
  $('settings-error').textContent = '';
  $('settings-dialog').showModal();
}
$('trash').onclick=()=>{filter='trash';render();};
$('add').onclick = () => openTask();
$('board-name').onclick = openSettings;
$('project').onclick = openSettings;
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => $(button.dataset.close).close());
document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {filter = button.dataset.filter; render();});
$('task-form').onsubmit = async event => {
  event.preventDefault(); const submit = event.submitter; submit.disabled = true;
  try {
    const lines = id => $(id).value.split('\n').map(text => text.trim()).filter(Boolean);
    const platforms=[...document.querySelectorAll('[name=platform]:checked')].map(input=>input.value);
    const kind=document.querySelector('[name=item-kind]:checked').value;
    if(kind==='note'&&!platforms.length)platforms.push('web');
    if(!platforms.length)throw Error(tr('플랫폼을 하나 이상 선택하세요.'));
    await api(editing ? 'edit' : 'add', {kind,note:$('note-body').value,platforms,webUrl:platforms.includes('web')?$('web-url').value.trim():'',language:locale,id:editing,title:$('title').value.trim(),paths:lines('paths'),criteria:lines('criteria')});
    filter=kind==='note'?'notes':'all';$('task-dialog').close(); await refresh();
  } catch (error) { $('task-error').textContent = error.message; }
  finally { submit.disabled = false; }
};
$('settings-form').onsubmit = async event => {
  event.preventDefault(); const submit = event.submitter; submit.disabled = true;
  try {
    const project = $('project-input').value.trim();
    if (project !== state.project) await api('configure', {project});
    await api('rename', {name:$('name-input').value.trim()});
    localStorage.setItem('todo-list-language',$('language').value);
    location.reload();
  } catch (error) { $('settings-error').textContent = error.message; }
  finally { submit.disabled = false; }
};
boot();
setInterval(() => {if (readyLocale && !document.hidden) refresh();}, 3000);
document.addEventListener('visibilitychange', () => {if (readyLocale && !document.hidden) refresh();});
