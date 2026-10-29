/* 小说创作智能 Agent — 前端逻辑（原生 JS，无构建步骤） */
'use strict';

const state = {
  sessionId: null,
  mode: 'create',        // create | kb
  sessions: [],
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};

async function api(path, body) {
  const opts = { method: 'GET', headers: { 'Content-Type': 'application/json' } };
  if (body) { opts.method = 'POST'; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`;
    try { const j = await res.json(); if (j.detail) msg = j.detail; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

/* ---------- 会话 ---------- */
async function loadSessions() {
  const data = await api('/api/sessions');
  state.sessions = data.sessions;
  renderSessions();
}

function renderSessions() {
  const box = $('#sessionList');
  box.innerHTML = '';
  for (const s of state.sessions) {
    const item = el('div', 'session-item' + (s.id === state.sessionId ? ' active' : ''));
    const left = el('div');
    left.appendChild(el('div', 'title', escapeHtml(s.title)));
    const modeLabel = s.mode === 'kb' ? '知识库' : '创作';
    left.appendChild(el('div', 'sub', `${modeLabel} · ${s.num_messages} 条`));
    const del = el('button', 'del', '🗑');
    del.title = '删除会话';
    del.onclick = async (e) => { e.stopPropagation(); await deleteSession(s.id); };
    item.appendChild(left);
    item.appendChild(del);
    item.onclick = () => selectSession(s.id);
    box.appendChild(item);
  }
}

async function newSession() {
  const s = await api('/api/sessions', { title: '新会话 ' + new Date().toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' }) });
  state.sessionId = s.id;
  await loadSessions();
  await loadSession(s.id);
}

async function deleteSession(id) {
  if (!confirm('确认删除该会话？')) return;
  await api('/api/sessions/' + id, null).catch(() => {});
  await fetch('/api/sessions/' + id, { method: 'DELETE' });
  if (state.sessionId === id) state.sessionId = null;
  await loadSessions();
  $('#messages').innerHTML = '<div class="empty">从左侧新建会话开始。</div>';
}

async function selectSession(id) {
  state.sessionId = id;
  renderSessions();
  await loadSession(id);
}

async function loadSession(id) {
  const s = await api('/api/sessions/' + id);
  state.mode = s.mode || 'create';
  syncModeUI();
  renderMessages(s.messages || []);
  renderStoryTags(s.story || {});
}

/* ---------- 渲染消息 ---------- */
function renderMessages(messages) {
  const box = $('#messages');
  box.innerHTML = '';
  if (!messages.length) {
    box.appendChild(el('div', 'empty', '开始对话吧。创作模式可与 Agent 讨论情节/人物；知识库模式提问将逐条标注依据。'));
    return;
  }
  for (const m of messages) {
    if (m.role !== 'user' && m.role !== 'assistant') continue;
    box.appendChild(renderMsg(m));
  }
  box.scrollTop = box.scrollHeight;
}

function renderMsg(m) {
  const wrap = el('div', 'msg ' + m.role);
  wrap.appendChild(el('div', 'avatar', m.role === 'user' ? '我' : 'AI'));
  const bubble = el('div', 'bubble');
  bubble.appendChild(el('pre', null, escapeHtml(m.content)));
  if (m.citations && m.citations.length) {
    bubble.appendChild(renderCitations(m.citations));
  }
  wrap.appendChild(bubble);
  return wrap;
}

function renderCitations(cites) {
  const box = el('div', 'cite');
  box.appendChild(el('div', 'cite-title', '📚 引用依据'));
  const ul = el('ul');
  for (const c of cites) {
    const li = el('li');
    li.innerHTML = `<span class="loc">[${c.index}] ${escapeHtml(c.doc)}（第 ${c.line_start}–${c.line_end} 行）</span><br>${escapeHtml(c.snippet)}`;
    ul.appendChild(li);
  }
  box.appendChild(ul);
  return box;
}

function renderStoryTags(story) {
  // 仅做轻量展示：把关键设定回填入设定面板（若存在）
  if (story.theme) $('#f-theme').value = story.theme;
  if (story.genre) $('#f-genre').value = story.genre;
  if (story.style) $('#f-style').value = story.style;
  if (story.characters) $('#f-chars').value = story.characters;
  if (story.plot_direction) $('#f-plot').value = story.plot_direction;
}

/* ---------- 模式 ---------- */
function syncModeUI() {
  document.querySelectorAll('#modeToggle button').forEach((b) => {
    b.classList.toggle('active', b.dataset.mode === state.mode);
  });
  const isKb = state.mode === 'kb';
  $('#setupPanel').classList.toggle('hidden', isKb);
  $('#toolbar').querySelectorAll('[data-act]').forEach((b) => b.classList.toggle('hidden', isKb));
  $('#toggleSetupBtn').classList.toggle('hidden', isKb);
  $('#input').placeholder = isKb
    ? '向知识库提问，答案将逐条标注文档与行号依据…'
    : '输入消息…（创作模式可与 Agent 多轮讨论情节/人物）';
}

document.querySelectorAll('#modeToggle button').forEach((b) => {
  b.onclick = async () => {
    state.mode = b.dataset.mode;
    syncModeUI();
    if (state.sessionId) {
      await api(`/api/sessions/${state.sessionId}/mode`, { mode: state.mode });
      renderSessions();
    }
  };
});

/* ---------- 发送 / 对话 ---------- */
async function send() {
  const input = $('#input');
  const text = input.value.trim();
  if (!text) return;
  if (!state.sessionId) { alert('请先新建会话'); return; }
  input.value = '';
  try {
    const data = await api('/api/chat', { session_id: state.sessionId, message: text, mode: state.mode });
    await loadSession(state.sessionId);
  } catch (e) {
    alert(e.message);
  }
}

$('#sendBtn').onclick = send;
$('#input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});

/* ---------- 设定面板 ---------- */
$('#toggleSetupBtn').onclick = () => $('#setupPanel').classList.toggle('hidden');

$('#saveSetupBtn').onclick = async () => {
  if (!state.sessionId) { alert('请先新建会话'); return; }
  const body = {
    session_id: state.sessionId,
    theme: $('#f-theme').value.trim(),
    genre: $('#f-genre').value.trim(),
    style: $('#f-style').value.trim(),
    characters: $('#f-chars').value.trim(),
    plot_direction: $('#f-plot').value.trim(),
  };
  for (const k of ['theme', 'genre', 'style', 'characters', 'plot_direction']) {
    if (!body[k]) delete body[k];
  }
  try {
    await api('/api/settings', body);
    alert('设定已保存');
  } catch (e) { alert(e.message); }
};

$('#genOutlineBtn').onclick = async () => {
  if (!state.sessionId) { alert('请先新建会话'); return; }
  const theme = $('#f-theme').value.trim();
  const genre = $('#f-genre').value.trim();
  const style = $('#f-style').value.trim();
  const characters = $('#f-chars').value.trim();
  if (!theme || !genre) { alert('至少填写「主题」与「题材」'); return; }
  try {
    const data = await api('/api/novel/outline', { session_id: state.sessionId, theme, genre, style, characters });
    await loadSession(state.sessionId);
  } catch (e) { alert(e.message); }
};

/* ---------- 创作工具按钮 ---------- */
document.querySelectorAll('#toolbar [data-act]').forEach((b) => {
  b.onclick = async () => {
    if (!state.sessionId) { alert('请先新建会话'); return; }
    const act = b.dataset.act;
    try {
      if (act === 'rewrite') {
        const instruction = prompt('改写约束（如：加快节奏 / 更口语化 / 缩减到 200 字）：');
        if (!instruction) return;
        await api('/api/novel/rewrite', { session_id: state.sessionId, instruction });
      } else if (act === 'style') {
        const ns = prompt('目标风格（如：冷硬写实 / 轻松吐槽 / 史诗庄重）：');
        if (!ns) return;
        await api('/api/novel/style', { session_id: state.sessionId, new_style: ns });
      } else if (act === 'chapter') {
        await api('/api/novel/chapter', { session_id: state.sessionId });
      } else if (act === 'continue') {
        await api('/api/novel/continue', { session_id: state.sessionId });
      }
      await loadSession(state.sessionId);
    } catch (e) { alert(e.message); }
  };
});

/* ---------- 知识库状态 ---------- */
async function refreshKbStatus() {
  try {
    const s = await api('/api/kb/status');
    const dot = $('#kbStatus').querySelector('.dot');
    dot.classList.toggle('ok', !!s.ready);
    const embed = s.use_embed ? '· 稠密向量' : '· BM25';
    $('#kbStatus').lastChild.textContent = ` 知识库：${s.ready ? s.num_chunks + ' 片段' : '未构建'}${embed}`;
  } catch (_) {
    $('#kbStatus').lastChild.textContent = ' 知识库：不可用';
  }
}

/* ---------- 工具 ---------- */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- 启动 ---------- */
(async function init() {
  syncModeUI();
  await loadSessions();
  await refreshKbStatus();
  if (state.sessions.length) {
    await selectSession(state.sessions[0].id);
  } else {
    await newSession();
  }
})();
