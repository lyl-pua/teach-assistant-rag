/* ============================================================
 * 教学助手 · 国风教研工作台 - app.js
 * 兼容旧环境：禁止使用 ?? / ?. / ||= / 等新语法
 * ============================================================ */

/* ========== 1. API_BASE 自动推导 ========== */
var API_BASE = (function () {
  var host = window.location.hostname || '';
  var port = window.location.port ? parseInt(window.location.port, 10) : 80;
  var lhost = (host === 'localhost' || host === '127.0.0.1');
  if (lhost && port !== 8777) {
    var proto = (window.location.protocol === 'https:') ? 'https' : 'http';
    return proto + '://127.0.0.1:8777/api';
  }
  var p = window.location.pathname;
  var parts = p.split('/').filter(function (x) { return x !== ''; });
  if (parts.length > 0 && parts[0] !== 'static') {
    return '/' + parts[0] + '/api';
  }
  return '/api';
})();

/* ========== 2. 全局状态 ========== */
var STATE = {
  currentPage: 'home',
  userName: '刘老师',
  settings: {},
  calendar: { year: 2026, month: 8, selected: null },
  chat: { currentSessionId: null, streaming: false },
  inbox: { currentType: 'all', q: '' },
  reading: { currentCat: '' },
  tools: { currentTool: 'lesson_plan' }
};

var CAL_MAP = { teach: '教学', research: '教研', meeting: '会议', life: '生活', student: '学生' };
var TYPE_ICON = { note: '📝', idea: '💡', todo: '✅', student: '👧' };

/* ========== 3. 通用工具函数 ========== */
function _def(a, b) { return (a === null || a === undefined || a === '') ? b : a; }
function _len(a) { return (a === null || a === undefined) ? 0 : a.length; }
function _has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

/* 安全赋值：找不到元素也不抛错（避免 .value on null 崩溃整个 JS） */
function setVal(id, v) {
  var el = document.getElementById(id);
  if (el) el.value = (v === null || v === undefined) ? '' : v;
}
/* 安全取值 */
function getVal(id) {
  var el = document.getElementById(id);
  return el ? (el.value == null ? '' : el.value) : '';
}

/* ===================== 国风 SVG 图标系统 ===================== */
/* 7 个侧栏 + 入口图标，统一卷轴风格，不用 emoji */
var GUO_ICONS = {
  home:     '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="14" height="14" rx="1"/><line x1="10" y1="3" x2="10" y2="17"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="6.5" y1="6.5" x2="13.5" y2="13.5" stroke-width="1"/><line x1="13.5" y1="6.5" x2="6.5" y2="13.5" stroke-width="1"/></svg>',
  inbox:    '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8 Q5 5 10 5 Q15 5 15 8 L15 16 Q15 17 14 17 L6 17 Q5 17 5 16 Z"/><path d="M7 5 Q8 3 10 3 Q12 3 13 5"/><line x1="7.5" y1="9" x2="12.5" y2="9" stroke-dasharray="1.5 1" stroke-width="1"/></svg>',
  reading:  '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="3" height="12" rx="0.5"/><rect x="8.5" y="4" width="3" height="12" rx="0.5"/><rect x="13" y="4" width="3" height="12" rx="0.5"/><line x1="4" y1="8" x2="7" y2="8" stroke-width="1"/><line x1="8.5" y1="8" x2="11.5" y2="8" stroke-width="1"/><line x1="13" y1="8" x2="16" y2="8" stroke-width="1"/></svg>',
  schedule: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="6"/><line x1="10" y1="10" x2="13" y2="6.5" stroke-width="1.8"/><circle cx="10" cy="10" r="1" fill="currentColor"/><line x1="10" y1="3" x2="10" y2="4.5" stroke-width="1"/><line x1="10" y1="15.5" x2="10" y2="17" stroke-width="1"/></svg>',
  ai:       '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="2.5" height="10" rx="1" fill="currentColor" opacity="0.25"/><rect x="13.5" y="5" width="2.5" height="10" rx="1" fill="currentColor" opacity="0.25"/><rect x="6" y="6" width="8" height="8" rx="0.5"/><line x1="8" y1="8.5" x2="12" y2="8.5" stroke-width="1"/><line x1="8" y1="10.5" x2="12" y2="10.5" stroke-width="1"/><line x1="8" y1="12.5" x2="10.5" y2="12.5" stroke-width="1"/></svg>',
  tools:    '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="10" cy="12" rx="7" ry="3"/><ellipse cx="10" cy="11" rx="5" ry="2" fill="currentColor" opacity="0.2"/><path d="M5 10 Q5 7 8 7 Q10 5 12 7 Q15 7 15 10"/></svg>',
  settings: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="8" height="5" rx="0.5"/><rect x="5" y="9" width="10" height="3" rx="0.5" fill="currentColor" opacity="0.25"/><line x1="7" y1="12" x2="7" y2="16"/><line x1="13" y1="12" x2="13" y2="16"/><line x1="5" y1="16" x2="15" y2="16"/></svg>',
  note:     '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3 L13 3 L15 5 L15 17 L5 17 Z"/><line x1="7" y1="8" x2="13" y2="8" stroke-width="1"/><line x1="7" y1="11" x2="13" y2="11" stroke-width="1"/><line x1="7" y1="14" x2="11" y2="14" stroke-width="1"/></svg>',
  idea:     '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 Q6 3 6 7 Q6 9 8 11 L8 13 L12 13 L12 11 Q14 9 14 7 Q14 3 10 3 Z"/><line x1="8" y1="15" x2="12" y2="15"/><line x1="9" y1="17" x2="11" y2="17"/></svg>',
  todo:     '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="12" height="12" rx="1"/><path d="M7 10 L9 12 L13 8" stroke-width="1.8"/></svg>',
  student:  '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="7" r="3"/><path d="M4 17 Q4 12 10 12 Q16 12 16 17"/></svg>',
  refresh:  '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10 Q4 5 9 4"/><path d="M16 10 Q16 15 11 16"/><path d="M4 4 L4 7 L7 7" stroke-width="1.2"/><path d="M16 16 L16 13 L13 13" stroke-width="1.2"/></svg>',
};
var EMOJI_TO_ICON = {
  '🏠':'home','📥':'inbox','📖':'reading','📅':'schedule',
  '🤖':'ai','🛠️':'tools','🛠':'tools','⚙️':'settings','⚙':'settings',
  '📝':'note','💡':'idea','✅':'todo','👧':'student',
  '🔄':'refresh',
};
function _giSVG(key) {
  var svg = GUO_ICONS[key];
  if (!svg) return '';
  return '<span class="gi-svg">' + svg + '</span>';
}
function applyGuoIcons(root) {
  if (!root) root = document;
  // 1) Nav items: replace .ico emoji text with SVG
  var navIcos = root.querySelectorAll('.nav-item .ico');
  for (var i = 0; i < navIcos.length; i++) {
    var emoji = (navIcos[i].textContent || '').trim();
    if (EMOJI_TO_ICON[emoji]) {
      navIcos[i].innerHTML = GUO_ICONS[EMOJI_TO_ICON[emoji]];
    }
  }
  // 2) Entry cards, page titles, inbox tabs, buttons: replace inline emojis
  var selectors = '.entry .t, .p-title, .inbox-tab, .btn, .section-title span, .tool-card .tc-head, .modal-title';
  var els = root.querySelectorAll(selectors);
  for (var j = 0; j < els.length; j++) {
    var html = els[j].innerHTML;
    var changed = false;
    for (var em in EMOJI_TO_ICON) {
      if (html.indexOf(em) !== -1) {
        html = html.split(em).join(_giSVG(EMOJI_TO_ICON[em]));
        changed = true;
      }
    }
    if (changed) els[j].innerHTML = html;
  }
}

/* ===================== Token 用量追踪 ===================== */
function refreshTokenBadge() {
  fetch(API_BASE + '/stats/tokens').then(function (r) { return r.json(); }).then(function (data) {
    var total = data.total || {};
    var el = document.getElementById('tokenCount');
    if (el) {
      var n = total.total_tokens || 0;
      el.textContent = n >= 10000 ? (n / 1000).toFixed(1) + 'k' : n;
    }
    window.__tokenStats = data;
  }).catch(function () {});
}
function showTokenDetail() {
  var data = window.__tokenStats;
  if (!data) { toast('暂无 Token 记录', 'info'); return; }
  var total = data.total || {};
  var byModel = data.by_model || [];
  var recent = data.recent || [];
  // 构建弹窗
  var existing = document.getElementById('tokenDetailModal');
  if (existing) existing.remove();
  var modal = document.createElement('div');
  modal.className = 'token-detail-modal active';
  modal.id = 'tokenDetailModal';
  modal.onclick = function (e) { if (e.target === modal) modal.remove(); };
  var html = '<div class="token-detail-box">';
  html += '<span class="td-close" onclick="this.closest(\'.token-detail-modal\').remove()">&times;</span>';
  html += '<h3>Token 消耗统计</h3>';
  html += '<div class="td-row"><span>总调用次数</span><span>' + (total.calls || 0) + '</span></div>';
  html += '<div class="td-row"><span>总消耗 Token</span><span>' + (total.total_tokens || 0) + '</span></div>';
  html += '<div class="td-row"><span>输入 Token (prompt)</span><span>' + (total.prompt_tokens || 0) + '</span></div>';
  html += '<div class="td-row"><span>输出 Token (completion)</span><span>' + (total.completion_tokens || 0) + '</span></div>';
  if (byModel.length > 0) {
    html += '<div class="td-section"><div class="td-section-title">按模型分组</div>';
    for (var i = 0; i < byModel.length; i++) {
      var m = byModel[i];
      html += '<div class="td-row"><span>' + (m.model || '?') + ' (' + (m.calls || 0) + '次)</span><span>' + (m.total_tokens || 0) + ' tokens</span></div>';
    }
    html += '</div>';
  }
  if (recent.length > 0) {
    html += '<div class="td-section"><div class="td-section-title">最近调用</div>';
    for (var j = 0; j < recent.length; j++) {
      var r = recent[j];
      html += '<div class="td-row"><span>' + (r.ts || '') + ' ' + (r.model || '') + '</span><span>' + (r.total_tokens || 0) + ' tokens / ' + (r.latency_ms || 0) + 'ms</span></div>';
    }
    html += '</div>';
  }
  html += '</div>';
  modal.innerHTML = html;
  document.body.appendChild(modal);
}
window.showTokenDetail = showTokenDetail;

function toast(msg, type) {
  if (type === null || type === undefined) type = 'info';
  var t = document.getElementById('toast');
  if (!t) return;
  t.className = 'toast show ' + type;
  var iconMap = { info: 'ℹ️', success: '✅', error: '❌', warn: '⚠️' };
  var ico = iconMap[type] ? iconMap[type] : 'ℹ️';
  t.innerHTML = '<span>' + ico + '</span><span>' + escapeHtml(msg) + '</span>';
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(function () {
    t.className = t.className.replace(' show', '');
  }, 2500);
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  s = String(s);
  var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return s.replace(/[&<>"']/g, function (c) { return map[c] || c; });
}

function api(url, opts) {
  if (opts === null || opts === undefined) opts = {};
  if (!opts.headers) opts.headers = {};
  if (!opts.headers['Content-Type'] && !(opts.body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
  }
  var fullUrl = API_BASE + url;

  return fetch(fullUrl, opts).then(function (resp) {
    var ct = resp.headers.get('content-type') || '';
    var isJson = ct.indexOf('application/json') >= 0;
    if (resp.status >= 200 && resp.status < 300) {
      if (isJson) return resp.json();
      return resp.text();
    }
    // 非 2xx：尝试解析错误
    return (isJson ? resp.json() : resp.text()).then(function (err) {
      var msg = '请求失败';
      if (typeof err === 'object') {
        msg = err.detail || err.message || err.error || JSON.stringify(err);
      } else if (typeof err === 'string') {
        msg = err.length > 300 ? err.substring(0, 300) + '…' : err;
      }
      msg = '[' + resp.status + '] ' + msg;
      var e = new Error(msg);
      e.status = resp.status;
      throw e;
    });
  }).catch(function (err) {
    console.error('[API ERR]', fullUrl, err);
    toast(err.message || '网络请求失败', 'error');
    throw err;
  });
}

/* ========== 4. 页面导航 ========== */
var CRUMB_MAP = {
  home: '首页 / 工作台',
  inbox: '📥 收集箱',
  reading: '📖 阅读 · 知识库',
  schedule: '📅 日程',
  assistant: '🤖 AI 教研助手',
  tools: '🛠️ 教学工具',
  settings: '⚙️ 设置与数据'
};

function navigateTo(page) {
  if (!CRUMB_MAP[page]) page = 'home';
  STATE.currentPage = page;
  // 切换 .nav-item
  var navItems = document.querySelectorAll('.nav-item');
  for (var i = 0; i < navItems.length; i++) {
    var ni = navItems[i];
    var dp = ni.getAttribute('data-page');
    if (dp === page) ni.classList.add('active');
    else ni.classList.remove('active');
  }
  // 切换 .page
  var pages = document.querySelectorAll('.page');
  for (var j = 0; j < pages.length; j++) {
    var pg = pages[j];
    if (pg.id === 'page-' + page) pg.classList.add('active');
    else pg.classList.remove('active');
  }
  var cr = document.getElementById('crumb');
  if (cr) cr.textContent = CRUMB_MAP[page];

  // 触发对应 load
  try {
    if (page === 'home') loadHome();
    else if (page === 'inbox') loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
    else if (page === 'reading') loadDocuments();
    else if (page === 'schedule') loadSchedule(STATE.calendar.year, STATE.calendar.month);
    else if (page === 'assistant') loadChatSessions();
    else if (page === 'tools') loadTools();
    else if (page === 'settings') loadSettings();
  } catch (err) {
    console.error('[navigateTo]', err);
  }
  // 页面切换后应用国风图标
  try { applyGuoIcons(); } catch (e) {}
}

/* ========== 5. Modal 控制 ========== */
function openModal(id) {
  var m = document.getElementById(id);
  if (m) m.classList.add('active');
}
function closeModal(id) {
  var m = document.getElementById(id);
  if (m) m.classList.remove('active');
}
function bindModalMaskClose() {
  var modals = document.querySelectorAll('.modal');
  for (var i = 0; i < modals.length; i++) {
    (function (m) {
      m.addEventListener('click', function (ev) {
        if (ev.target === m) m.classList.remove('active');
      });
    })(modals[i]);
  }
  var closeBtns = document.querySelectorAll('[data-close]');
  for (var j = 0; j < closeBtns.length; j++) {
    closeBtns[j].addEventListener('click', function () {
      var id = this.getAttribute('data-close');
      closeModal(id);
    });
  }
}

/* ========== 6. 农历/诗词简易表（内置 700+ 首诗轮换）========== */
var _LAST_GREET_SEG = -1;   // 上次问候分段：0=早 1=中 2=午 3=晚 4=深夜
function _greetSeg(h) {
  // 5-12 早 / 12-14 中 / 14-18 下午 / 18-23 晚 / 23-5 深夜
  if (h >= 5  && h < 12) return 0;
  if (h >= 12 && h < 14) return 1;
  if (h >= 14 && h < 18) return 2;
  if (h >= 18 && h < 23) return 3;
  return 4;
}
function greetByHour(name) {
  var h = new Date().getHours();
  var seg = _greetSeg(h);
  var s = ({0:'早上好',1:'中午好',2:'下午好',3:'晚上好',4:'夜深了'})[seg];
  var realName = name || '刘老师';
  return s + '，' + realName;
}
/* 刷新问候语（跨时段自动切换 早上好→中午好→下午好→晚上好→夜深了） */
function refreshGreetingIfNeeded(force) {
  try {
    var now = new Date();
    var seg = _greetSeg(now.getHours());
    if (force || seg !== _LAST_GREET_SEG) {
      _LAST_GREET_SEG = seg;
      var greetEl = document.getElementById('greetTitle');
      if (greetEl) greetEl.textContent = greetByHour(STATE.userName);
      // 跨时段顺带换一句诗（每天至少能看到几次变化）
      if (!force) showRandomPoem(false);
    }
  } catch (e) { /* 静默 */ }
}

// 兼容：如果 poems.js 未加载，则用此小表保底
var _POEM_FALLBACK = [
  { t: '空山新雨后，天气晚来秋。\n明月松间照，清泉石上流。', a: '——王维《山居秋暝》' },
  { t: '沾衣欲湿杏花雨，吹面不寒杨柳风。\n等闲识得东风面，万紫千红总是春。', a: '——志南《绝句》/朱熹《春日》' },
  { t: '小荷才露尖尖角，早有蜻蜓立上头。\n接天莲叶无穷碧，映日荷花别样红。', a: '——杨万里《小池》/《晓出净慈寺送林子方》' },
  { t: '停车坐爱枫林晚，霜叶红于二月花。\n一年好景君须记，最是橙黄橘绿时。', a: '——杜牧《山行》/苏轼《赠刘景文》' },
  { t: '墙角数枝梅，凌寒独自开。\n遥知不是雪，为有暗香来。', a: '——王安石《梅花》' },
  { t: '海上生明月，天涯共此时。\n情人怨遥夜，竟夕起相思。', a: '——张九龄《望月怀远》' }
];

// 简易字符串哈希（用于每日稳定取一首）
function _poemHash(str) {
  var h = 2166136261;
  for (var i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul ? Math.imul(h, 16777619) : ((h << 1) + h);
  }
  return ((h >>> 0) % 2147483647);
}
function _todayKey() {
  var d = new Date();
  return d.getFullYear() + '-' + (d.getMonth()+1) + '-' + d.getDate();
}
function _getPoemLibrary() {
  var L = (typeof window !== 'undefined' && window.POEM_LIBRARY) ? window.POEM_LIBRARY : null;
  if (L && L.length) return L;
  // 兜底：兼容 POEMS 数组
  if (typeof POEMS !== 'undefined' && POEMS && POEMS.length) return POEMS;
  return _POEM_FALLBACK;
}
// mode: 'daily'(每日稳定) | 'random'(完全随机)
function pickPoem(mode) {
  var lib = _getPoemLibrary();
  if (!lib || !lib.length) return _POEM_FALLBACK[0];
  if (mode === 'random') {
    var idx = Math.floor(Math.random() * lib.length);
    return _normalizePoem(lib[idx]);
  }
  // 默认 daily：按日期+用户名稳定
  var key = _todayKey() + '|' + (STATE.userName || 'liu') + '|' + lib.length;
  var idx = _poemHash(key) % lib.length;
  return _normalizePoem(lib[idx]);
}
function _normalizePoem(p) {
  // 兼容两种格式：{t:诗,a:作者/出处} 或 {t:标题,a:正文,u:作者}
  if (!p) return { t: '', a: '' };
  if (p.u && p.a && /选|吟|第.*日/.test(p.t || '')) {
    // poems.js 新格式：t=标题 / a=正文（含句号分隔） / u=作者
    var title = p.t || '';
    var body = (p.a || '').replace(/。/g, '。\n').replace(/\n+/g, '\n').replace(/^\n|\n$/g, '');
    var author = '——' + (p.u || '佚名') + (title ? '《' + title + '》' : '');
    return { t: body, a: author };
  }
  return { t: p.t || '', a: p.a || '' };
}

// 渲染诗到 .poem
function renderPoem(mode) {
  var poem = pickPoem(mode);
  var poemBox = document.querySelector('.poem');
  if (poemBox && poem) {
    var text = poem.t || '';
    var lines = text.split(/\n|。/).map(function (x) { return (x || '').replace(/^\s+|\s+$/g, ''); }).filter(function (x) { return x.length > 0; });
    var html = '';
    for (var k = 0; k < lines.length; k++) {
      var line = lines[k];
      if (line.charAt(line.length - 1) !== '。' && line.charAt(line.length - 1) !== '？' && line.charAt(line.length - 1) !== '！' && line.charAt(line.length - 1) !== '，') {
        line += '。';
      }
      html += '<p>' + escapeHtml(line) + '</p>';
    }
    if (poem.a) html += '<small>' + escapeHtml(poem.a) + '</small>';
    poemBox.innerHTML = html;
    // 可点击刷新：点一次换一首
    poemBox.style.cursor = 'pointer';
    poemBox.title = '点击换一首诗句';
    if (!poemBox.dataset.boundRefresh) {
      poemBox.addEventListener('click', function () { renderPoem('random'); });
      poemBox.dataset.boundRefresh = '1';
    }
  }
}

// 旧函数兼容
var POEMS = _POEM_FALLBACK;
function pickPoemByMonth() { return pickPoem('daily'); }

var SOLAR_TERMS = [
  '小寒','大寒','立春','雨水','惊蛰','春分','清明','谷雨','立夏','小满','芒种','夏至',
  '小暑','大暑','立秋','处暑','白露','秋分','寒露','霜降','立冬','小雪','大雪','冬至'
];
var SOLAR_TERM_DATES = [
  [1,6],[1,20],[2,4],[2,19],[3,6],[3,21],[4,5],[4,20],[5,6],[5,21],[6,6],[6,21],
  [7,7],[7,23],[8,8],[8,23],[9,8],[9,23],[10,8],[10,23],[11,7],[11,22],[12,7],[12,22]
];
function getSolarTermInfo(d) {
  var m = d.getMonth();
  var day = d.getDate();
  var t1 = SOLAR_TERM_DATES[m * 2];
  var t2 = SOLAR_TERM_DATES[m * 2 + 1];
  var s1 = SOLAR_TERMS[m * 2];
  var s2 = SOLAR_TERMS[m * 2 + 1];
  if (day < t1[1]) {
    // 上一个节气后
    var prevIdx = (m * 2 - 1 + 24) % 24;
    return '（' + SOLAR_TERMS[prevIdx] + '→' + s1 + '之间）';
  } else if (day < t2[1]) {
    return '（' + s1 + '→' + s2 + '之间）';
  } else {
    return '（' + s2 + '前后）';
  }
}

// 农历简化近似表（仅给大致描述，不精确）
function lunarApproxStr(d) {
  var y = d.getFullYear();
  var m = d.getMonth();
  var day = d.getDate();
  // 用儒略日差近似（不准确，仅做显示）
  var offset = ((y - 2000) % 19 + 19) % 19;
  var arr = ['初一','初二','初三','初四','初五','初六','初七','初八','初九','初十',
             '十一','十二','十三','十四','十五','十六','十七','十八','十九','二十',
             '廿一','廿二','廿三','廿四','廿五','廿六','廿七','廿八','廿九','三十'];
  var dIdx = (((day + offset * 3 + m * 11) % 30) + 30) % 30;
  var lunarMonthNames = ['正月','二月','三月','四月','五月','六月','七月','八月','九月','十月','冬月','腊月'];
  var lm = lunarMonthNames[((m + offset) % 12 + 12) % 12];
  return '农历' + lm + arr[dIdx] + ' · ' + getSolarTermInfo(d);
}

function formatTopDate() {
  var d = new Date();
  var weekNames = ['日','一','二','三','四','五','六'];
  return d.getFullYear() + '年' + (d.getMonth()+1) + '月' + d.getDate() + '日 · 周' + weekNames[d.getDay()];
}

/* ============================================================
 * 7. 首页 loadHome()
 * ============================================================ */
function loadHome() {
  var td = document.getElementById('topDate');
  if (td) td.textContent = formatTopDate();

  // 问候语（优先 /health 取后端 greeting）
  api('/health').then(function (h) {
    if (h && h.user_name) {
      STATE.userName = h.user_name;
      var sbn = document.getElementById('sidebar-teacher-name');
      if (sbn) sbn.textContent = h.user_name;
    }
    var greetEl = document.getElementById('greetTitle');
    if (greetEl) {
      if (h && h.greeting) greetEl.textContent = h.greeting;
      else greetEl.textContent = greetByHour(STATE.userName);
    }
    return h;
  }).catch(function () {
    var greetEl = document.getElementById('greetTitle');
    if (greetEl) greetEl.textContent = greetByHour(STATE.userName);
  });

  // 副标题：日期 + 农历
  var subEl = document.getElementById('greetSub');
  if (subEl) {
    var d = new Date();
    subEl.textContent = '今天是 ' + d.getFullYear() + ' 年 ' + (d.getMonth()+1) + ' 月 ' + d.getDate() + ' 日 · ' + lunarApproxStr(d);
  }

  // 诗词：每日稳定+天气刷新时随机换一首+诗词块可点击换
  renderPoem('daily');

  // 天气（天气刷新结束后顺带再随机换一首）
  refreshWeather().then(function () {
    try { renderPoem('random'); } catch (e) {}
  });

  // 统计
  renderDefaultStats();
  api('/stats').then(function (st) {
    renderStats(st);
  }).catch(function () { /* 已 toast */ });
}

function renderDefaultStats() {
  var grid = document.getElementById('statGrid');
  if (!grid) return;
  grid.innerHTML = renderStatCards([
    { ico: '📥', label: '收集箱条目', num: '--', sub: '笔记/灵感/待办/学生' },
    { ico: '📅', label: '日程总数', num: '--', sub: '今日已安排 0 项' },
    { ico: '📖', label: '知识库文档', num: '--', sub: '已就绪 0 份 / 待处理 0 份' },
    { ico: '🤖', label: 'AI 会话数', num: '--', sub: 'RAG 问答 · 智谱向量' }
  ]);
}
function renderStatCards(arr) {
  var html = '';
  for (var i = 0; i < arr.length; i++) {
    var s = arr[i];
    html += '<div class="stat-card">' +
      '<div class="stat-ico">' + s.ico + '</div>' +
      '<div class="stat-label">' + escapeHtml(s.label) + '</div>' +
      '<div class="stat-num">' + escapeHtml(String(s.num)) + '</div>' +
      '<div class="stat-sub">' + escapeHtml(s.sub) + '</div>' +
    '</div>';
  }
  return html;
}
function renderStats(st) {
  var grid = document.getElementById('statGrid');
  if (!grid) return;
  var inboxC = _def(st.inbox_count, 0);
  var schC = _def(st.schedule_count, 0);
  var schDone = _def(st.schedule_done, 0);
  var docReady = _def(st.doc_ready, 0);
  var docTotal = _def(st.doc_count, 0);
  var chatS = _def(st.chat_sessions, 0);
  var chatM = _def(st.chat_messages, 0);
  grid.innerHTML = renderStatCards([
    { ico: '📥', label: '收集箱条目', num: inboxC, sub: '置顶 ' + _def(st.inbox_pinned, 0) + ' 条 · 含笔记/灵感/待办/学生' },
    { ico: '📅', label: '日程总数', num: schC, sub: '已完成 ' + schDone + ' 项 · 待办 ' + (Math.max(schC - schDone,0)) + ' 项' },
    { ico: '📖', label: '知识库文档', num: docReady, sub: '就绪 ' + docReady + ' 份 / 共 ' + docTotal + ' 份 · Chunk ' + _def(st.kb_chunks, 0) + ' 块' },
    { ico: '🤖', label: 'AI 会话', num: chatS, sub: chatM + ' 条消息 · 生成 ' + _def(st.tool_runs, 0) + ' 次' }
  ]);
}

/* 天气渲染 */
var _weatherIconMap = {
  '晴': '☀️', '多云': '⛅', '阴': '☁️', '小雨': '🌦️', '中雨': '🌧️', '大雨': '🌧️',
  '雷阵雨': '⛈️', '雨夹雪': '🌨️', '小雪': '🌨️', '中雪': '❄️', '大雪': '❄️',
  '雾': '🌫️', '霾': '🌫️'
};
function weatherIcon(text) {
  if (!text) return '🌡️';
  for (var k in _weatherIconMap) {
    if (Object.prototype.hasOwnProperty.call(_weatherIconMap, k) && text.indexOf(k) >= 0) {
      return _weatherIconMap[k];
    }
  }
  return '🌤️';
}

function refreshWeather() {
  // 先尝试取 settings 里的城市/经纬度
  var q = '/weather?days=3';
  var city = STATE.settings['default_city'];
  var lat = STATE.settings['city_lat'];
  var lon = STATE.settings['city_lon'];
  if (lat && lon && !isNaN(parseFloat(lat))) {
    q += '&lat=' + encodeURIComponent(lat) + '&lon=' + encodeURIComponent(lon);
  } else if (city) {
    q += '&city=' + encodeURIComponent(city);
  }
  var titleEl = document.querySelector('.w-title');
  if (titleEl && city) {
    titleEl.textContent = '📍' + city + ' · 今日天气';
  }
  return api(q).then(function (w) {
    renderWeather(w);
    return w;
  }).catch(function (err) {
    console.warn('weather error', err);
    // 不弹 toast，仅在卡片显示加载失败
    var ww = document.getElementById('w-weather');
    if (ww) ww.textContent = '数据暂不可用';
    var wd = document.getElementById('w-daily');
    if (wd) wd.innerHTML = '';
    throw err;
  });
}
window.refreshWeather = refreshWeather;

function renderWeather(w) {
  if (!w) return;
  // 兼容各种天气返回格式
  var cur = w.current || w.realtime || w.now || w;
  var city = w.city || w.location || (STATE.settings['default_city'] ? STATE.settings['default_city'] : '本地');
  var titleEl = document.querySelector('.w-title');
  if (titleEl) titleEl.textContent = '📍' + city + ' · 今日天气';

  var text = cur.text || cur.weather || cur.condition || cur.summary || '--';
  var temp = cur.temp != null ? cur.temp : (cur.temperature != null ? cur.temperature : '--');
  var tempUnit = (temp === '--') ? '' : '°';
  var humidity = cur.humidity != null ? cur.humidity : (cur.rh != null ? cur.rh : '--');
  var wind = cur.windSpeed != null ? cur.windSpeed : (cur.wind_speed != null ? cur.wind_speed : (cur.wind != null ? cur.wind : '--'));
  var maxT = (cur.tempMax != null) ? cur.tempMax : ((w.today && w.today.tempMax != null) ? w.today.tempMax : '--');
  var minT = (cur.tempMin != null) ? cur.tempMin : ((w.today && w.today.tempMin != null) ? w.today.tempMin : '--');
  var pop = (cur.precipProb != null) ? cur.precipProb : (cur.pop != null ? cur.pop : (w.today && w.today.pop != null ? w.today.pop : '--'));

  var ic = document.getElementById('w-icon');
  if (ic) ic.textContent = weatherIcon(text);
  var tTemp = document.getElementById('w-temp');
  if (tTemp) tTemp.textContent = temp + tempUnit;
  var tWeather = document.getElementById('w-weather');
  if (tWeather) tWeather.textContent = text;
  var tHum = document.getElementById('w-humidity');
  if (tHum) tHum.textContent = humidity;
  var tWind = document.getElementById('w-wind');
  if (tWind) tWind.textContent = wind;
  var tMax = document.getElementById('w-max');
  if (tMax) tMax.textContent = maxT;
  var tMin = document.getElementById('w-min');
  if (tMin) tMin.textContent = minT;
  var tPop = document.getElementById('w-pop');
  if (tPop) tPop.textContent = pop;

  // daily
  var daily = w.daily || w.forecast || w.days || [];
  var wd = document.getElementById('w-daily');
  if (!wd) return;
  wd.innerHTML = '';
  if (daily.length === 0) return;
  var maxShow = Math.min(3, daily.length);
  for (var i = 0; i < maxShow; i++) {
    var d = daily[i];
    var dd = d.date || d.day || ('Day ' + (i+1));
    if (dd && typeof dd === 'string' && dd.length > 10) dd = dd.substring(5); // YYYY-MM-DD → MM-DD
    var tt = d.text || d.weather || d.condition || '';
    var tmx = d.tempMax != null ? d.tempMax : (d.high != null ? d.high : '--');
    var tmn = d.tempMin != null ? d.tempMin : (d.low != null ? d.low : '--');
    var div = document.createElement('div');
    div.className = 'w-daily-item';
    div.innerHTML = '<div class="d">' + escapeHtml(String(dd)) + '</div>' +
      '<div class="i">' + weatherIcon(tt) + '</div>' +
      '<div class="t">' + escapeHtml(String(tmn)) + '° ~ ' + escapeHtml(String(tmx)) + '°</div>';
    wd.appendChild(div);
  }
}

/* ============================================================
 * 8. 收集箱 inbox
 * ============================================================ */
function bindInboxTabs() {
  var tabs = document.querySelectorAll('#inboxTabs .inbox-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var self = this;
      document.querySelectorAll('#inboxTabs .inbox-tab').forEach(function (x) { x.classList.remove('active'); });
      self.classList.add('active');
      STATE.inbox.currentType = self.getAttribute('data-type') || 'all';
      loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
    });
  }
  var search = document.getElementById('inboxSearch');
  if (search) {
    search.addEventListener('input', function () {
      STATE.inbox.q = search.value;
      loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
    });
  }
  var addBtn = document.getElementById('inboxAddBtn');
  if (addBtn) addBtn.addEventListener('click', function () {
    // reset form
    var t = document.getElementById('ib-title'); if (t) t.value = '';
    var c = document.getElementById('ib-content'); if (c) c.value = '';
    var tags = document.getElementById('ib-tags'); if (tags) tags.value = '';
    var p = document.getElementById('ib-pinned'); if (p) p.checked = false;
    openModal('inbox-modal');
  });
  var save = document.getElementById('ib-save');
  if (save) save.addEventListener('click', saveInboxItem);
}

function loadInboxItems(type, q) {
  if (type === null || type === undefined || type === '') type = 'all';
  STATE.inbox.currentType = type;
  var url = '/inbox';
  var qs = [];
  if (type !== 'all') qs.push('item_type=' + encodeURIComponent(type));
  if (q) qs.push('q=' + encodeURIComponent(q));
  if (qs.length) url += '?' + qs.join('&');

  var listEl = document.getElementById('inboxList');
  if (!listEl) return;
  listEl.innerHTML = '<li class="empty-state small">加载中…</li>';

  api(url).then(function (items) {
    renderInboxList(items);
  }).catch(function () {
    listEl.innerHTML = '<li class="empty-state small">加载失败，请稍后重试。</li>';
  });
}

function renderInboxList(items) {
  var listEl = document.getElementById('inboxList');
  if (!listEl) return;
  if (!items || items.length === 0) {
    listEl.innerHTML = '<li class="inbox-empty">暂无可显示的条目，点击右上「新建条目」添加。</li>';
    return;
  }
  var html = '';
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    var id = it.id || '';
    var type = it.type || 'note';
    var ico = TYPE_ICON[type] || '📝';
    var title = it.title || '';
    var content = it.content || '';
    var tagsStr = it.tags || '';
    var pinned = it.pinned ? true : false;
    var date = it.updated_at || it.created_at || '';
    if (date && date.length > 16) date = date.substring(0, 16).replace('T', ' ');
    var tagHtml = '';
    if (tagsStr) {
      var arr = tagsStr.split(/[,，]/);
      for (var k = 0; k < arr.length; k++) {
        var t = (arr[k] || '').trim();
        if (!t) continue;
        tagHtml += '<span class="tag-chip">' + escapeHtml(t) + '</span>';
      }
    }
    var pinFlag = pinned ? '<span class="pin-tag">📌 置顶</span>' : '';
    var cls = 'inbox-item' + (pinned ? ' pinned' : '');
    html += '<li class="' + cls + '" data-id="' + escapeHtml(String(id)) + '">' +
      '<div class="inbox-ico ' + escapeHtml(type) + '">' + ico + '</div>' +
      '<div class="inbox-body">' +
        '<div class="inbox-title">' + escapeHtml(title) + pinFlag + '</div>' +
        (content ? ('<div class="inbox-content">' + escapeHtml(content) + '</div>') : '') +
        '<div class="inbox-meta">' +
          '<span>📂 ' + escapeHtml(_def(CAL_MAP_FOR_TYPE[type], type)) + '</span>' +
          '<span>🕓 ' + escapeHtml(date) + '</span>' +
          (tagHtml ? '<span>' + tagHtml + '</span>' : '') +
        '</div>' +
      '</div>' +
      '<div class="inbox-actions">' +
        '<button class="icon-btn pin' + (pinned ? ' pinned' : '') + '" data-id="' + escapeHtml(String(id)) + '" title="置顶">📌</button>' +
        '<button class="icon-btn danger" data-id="' + escapeHtml(String(id)) + '" title="删除">🗑️</button>' +
      '</div>' +
    '</li>';
  }
  listEl.innerHTML = html;

  // 绑定操作
  var pins = listEl.querySelectorAll('.icon-btn.pin');
  for (var p = 0; p < pins.length; p++) {
    pins[p].addEventListener('click', function () {
      var iid = this.getAttribute('data-id');
      api('/inbox/' + iid + '/pin', { method: 'POST' }).then(function () {
        toast('置顶状态已更新', 'success');
        loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
      });
    });
  }
  var dels = listEl.querySelectorAll('.icon-btn.danger');
  for (var d = 0; d < dels.length; d++) {
    dels[d].addEventListener('click', function () {
      if (!confirm('确定删除该条目？此操作不可恢复。')) return;
      var iid = this.getAttribute('data-id');
      api('/inbox/' + iid, { method: 'DELETE' }).then(function () {
        toast('已删除', 'success');
        loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
      });
    });
  }
}
var CAL_MAP_FOR_TYPE = { note: '笔记', idea: '灵感', todo: '待办', student: '学生情况' };

function saveInboxItem() {
  var titleEl = document.getElementById('ib-title');
  var title = titleEl ? titleEl.value.trim() : '';
  if (!title) {
    toast('标题不能为空', 'warn');
    if (titleEl) titleEl.focus();
    return;
  }
  var typeEl = document.getElementById('ib-type');
  var contentEl = document.getElementById('ib-content');
  var tagsEl = document.getElementById('ib-tags');
  var pinEl = document.getElementById('ib-pinned');
  var payload = {
    title: title,
    content: contentEl ? (contentEl.value || '') : '',
    type: typeEl ? (typeEl.value || 'note') : 'note',
    tags: tagsEl ? (tagsEl.value || '') : '',
    pinned: pinEl && pinEl.checked ? 1 : 0
  };
  api('/inbox', { method: 'POST', body: JSON.stringify(payload) }).then(function () {
    toast('已保存', 'success');
    closeModal('inbox-modal');
    loadInboxItems(STATE.inbox.currentType, STATE.inbox.q);
  });
}

/* ============================================================
 * 9. 阅读 / 文档 documents
 * ============================================================ */
function bindReadingUI() {
  var tabs = document.querySelectorAll('#readingTabs .reading-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var self = this;
      document.querySelectorAll('#readingTabs .reading-tab').forEach(function (x) { x.classList.remove('active'); });
      self.classList.add('active');
      STATE.reading.currentCat = self.getAttribute('data-cat') || '';
      loadDocuments();
    });
  }
  var upBtn = document.getElementById('readingUploadBtn');
  if (upBtn) upBtn.addEventListener('click', function () {
    setVal('up-category', STATE.reading.currentCat || '教材');
    var f = document.getElementById('up-file');
    if (f) f.value = '';
    var fn = document.getElementById('up-file-name');
    if (fn) fn.textContent = '未选择文件';
    var pg = document.getElementById('uploadProgress');
    if (pg) pg.classList.add('hidden');
    openModal('upload-modal');
  });
  var fileInput = document.getElementById('up-file');
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var fn = document.getElementById('up-file-name');
      if (!fn) return;
      var fs = fileInput.files;
      if (!fs || fs.length === 0) { fn.textContent = '未选择文件'; return; }
      var names = [];
      var total = 0;
      for (var k = 0; k < fs.length; k++) {
        names.push(fs[k].name);
        total += fs[k].size;
      }
      fn.textContent = names.join('、') + '  (' + humanSize(total) + ')';
    });
  }
  var saveBtn = document.getElementById('up-save');
  if (saveBtn) saveBtn.addEventListener('click', uploadDocument);

  // 拖拽区
  var drop = document.getElementById('readingDrop');
  if (drop) {
    var fileIn = document.createElement('input');
    fileIn.type = 'file';
    fileIn.accept = '.pdf,.docx,.md,.txt';
    fileIn.multiple = true;
    fileIn.style.display = 'none';
    drop.appendChild(fileIn);
    drop.addEventListener('click', function () { fileIn.click(); });
    fileIn.addEventListener('change', function () {
      if (fileIn.files && fileIn.files.length) dropFilesToUpload(fileIn.files);
    });
    drop.addEventListener('dragover', function (ev) {
      ev.preventDefault();
      drop.classList.add('hover');
    });
    drop.addEventListener('dragleave', function () { drop.classList.remove('hover'); });
    drop.addEventListener('drop', function (ev) {
      ev.preventDefault();
      drop.classList.remove('hover');
      if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
        dropFilesToUpload(ev.dataTransfer.files);
      }
    });
  }
}

function humanSize(b) {
  if (b == null) return '';
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1024 / 1024).toFixed(2) + ' MB';
}

function dropFilesToUpload(fileList) {
  // 依次在 upload-modal 里上传
  STATE._uploadQueue = [];
  for (var i = 0; i < fileList.length; i++) STATE._uploadQueue.push(fileList[i]);
  STATE._uploadCategory = STATE.reading.currentCat || '其他';
  runUploadQueue();
}
function runUploadQueue() {
  if (!STATE._uploadQueue || STATE._uploadQueue.length === 0) return;
  var f = STATE._uploadQueue.shift();
  doUploadFile(f, STATE._uploadCategory, function (err) {
    if (STATE._uploadQueue.length > 0) {
      setTimeout(runUploadQueue, 100);
    } else {
      loadDocuments();
    }
  });
}

function uploadDocument() {
  var fileInput = document.getElementById('up-file');
  var cat = document.getElementById('up-category');
  var files = fileInput ? fileInput.files : null;
  if (!files || files.length === 0) {
    toast('请先选择文件', 'warn');
    return;
  }
  var catVal = cat ? (cat.value || '其他') : '其他';
  STATE._uploadCategory = catVal;
  STATE._uploadQueue = [];
  for (var i = 0; i < files.length; i++) STATE._uploadQueue.push(files[i]);
  closeModal('upload-modal');
  runUploadQueue();
}

function doUploadFile(file, category, cb) {
  var form = new FormData();
  form.append('file', file);
  form.append('category', category || '其他');

  var progWrap = document.getElementById('uploadProgress');
  var progBar = document.getElementById('uploadProgressBar');
  var progText = document.getElementById('uploadProgressText');
  // 如果 modal 打开着，则使用 modal 里进度，否则 toast 提示
  toast('开始上传：' + file.name, 'info');

  // 使用 XMLHttpRequest 以便显示进度
  var xhr = new XMLHttpRequest();
  xhr.open('POST', API_BASE + '/documents/upload');
  xhr.upload.onprogress = function (ev) {
    if (ev.lengthComputable) {
      var pct = Math.round(ev.loaded / ev.total * 100);
      if (progWrap && progBar && progText) {
        progWrap.classList.remove('hidden');
        progBar.style.width = pct + '%';
        progText.textContent = '上传中：' + file.name + ' (' + pct + '%)';
      }
    }
  };
  xhr.onload = function () {
    try {
      if (xhr.status >= 200 && xhr.status < 300) {
        var data = JSON.parse(xhr.responseText);
        toast('✅ ' + file.name + ' 上传成功（' + (data.chunks_count || 0) + ' 块）', 'success');
        if (progWrap) progWrap.classList.add('hidden');
        loadDocuments();
        if (cb) cb(null, data);
      } else {
        var msg = '上传失败 [' + xhr.status + ']';
        try {
          var er = JSON.parse(xhr.responseText);
          msg += '：' + (er.detail || er.error || er.message || xhr.responseText);
        } catch (_) { msg += '：' + xhr.responseText; }
        toast(msg, 'error');
        if (cb) cb(new Error(msg));
      }
    } catch (e) {
      toast('上传失败：响应解析异常', 'error');
      if (cb) cb(e);
    }
  };
  xhr.onerror = function () {
    toast('上传失败：网络错误', 'error');
    if (cb) cb(new Error('network'));
  };
  xhr.send(form);
}

function loadDocuments() {
  var cat = STATE.reading.currentCat;
  var url = '/documents';
  if (cat) url += '?category=' + encodeURIComponent(cat);
  var listEl = document.getElementById('docList');
  if (listEl) listEl.innerHTML = '<div class="empty-state small">加载中…</div>';

  Promise.all([
    api(url),
    api('/stats').catch(function () { return {}; })
  ]).then(function (r) {
    var list = r[0];
    var stats = r[1] || {};
    renderDocList(list);
    // 顶部统计
    var dt = document.getElementById('docTotal');
    var dr = document.getElementById('docReady');
    var dc = document.getElementById('docChunks');
    if (dt) dt.textContent = _def(stats.doc_count, (list == null ? 0 : list.length));
    if (dr) dr.textContent = _def(stats.doc_ready, countByStatus(list, 'ready'));
    if (dc) dc.textContent = _def(stats.kb_chunks, countChunks(list));
  }).catch(function () {
    if (listEl) listEl.innerHTML = '<div class="empty-state small">加载失败，请稍后重试。</div>';
  });

  // 设置页面的知识库文档一览（若存在）
  loadKbDocListIfVisible();
}
function countByStatus(list, s) {
  if (!list) return 0;
  var n = 0;
  for (var i = 0; i < list.length; i++) if (list[i].status === s) n++;
  return n;
}
function countChunks(list) {
  if (!list) return 0;
  var n = 0;
  for (var i = 0; i < list.length; i++) n += (parseInt(list[i].chunks_count, 10) || 0);
  return n;
}

function renderDocList(list) {
  var el = document.getElementById('docList');
  if (!el) return;
  if (!list || list.length === 0) {
    el.innerHTML = '<div class="empty-state">知识库暂无文档。点击右上角「上传文档」添加课件/教材。</div>';
    return;
  }
  var exts = { pdf: '📕', docx: '📘', doc: '📘', md: '📗', txt: '📙', pptx: '📙' };
  var html = '';
  for (var i = 0; i < list.length; i++) {
    var d = list[i];
    var fn = d.filename || '未命名';
    var ext = (fn.split('.').pop() || '').toLowerCase();
    var ico = exts[ext] || '📄';
    var statusCls = 'status-tag ' + (d.status || 'processing');
    var statusText = d.status === 'ready' ? '✅ 就绪' : (d.status === 'error' ? '❌ 解析失败' : '⏳ 处理中');
    var size = humanSize(d.file_size);
    var date = d.created_at || '';
    if (date && date.length > 16) date = date.substring(0,16).replace('T',' ');
    var cat = d.category || '未分类';
    var chunks = parseInt(d.chunks_count || 0, 10);
    html += '<div class="doc-item" data-id="' + escapeHtml(String(d.id)) + '">' +
      '<div class="doc-ico">' + ico + '</div>' +
      '<div class="doc-main">' +
        '<div class="doc-name">' + escapeHtml(fn) + '</div>' +
        '<div class="doc-meta">' +
          '<span class="cat-tag">' + escapeHtml(cat) + '</span>' +
          '<span class="' + statusCls + '">' + statusText + '</span>' +
          '<span>🧩 ' + chunks + ' 块</span>' +
          '<span>📦 ' + size + '</span>' +
          '<span>🕓 ' + escapeHtml(date) + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="doc-actions">' +
        '<button class="icon-btn" data-act="rebuild" data-id="' + escapeHtml(String(d.id)) + '" title="重建分块 & 向量">🔧</button>' +
        '<button class="icon-btn danger" data-act="del" data-id="' + escapeHtml(String(d.id)) + '" title="删除">🗑️</button>' +
      '</div>' +
    '</div>';
  }
  el.innerHTML = html;
  var rbts = el.querySelectorAll('button[data-act="rebuild"]');
  for (var r = 0; r < rbts.length; r++) {
    rbts[r].addEventListener('click', function () {
      var id = this.getAttribute('data-id');
      if (!confirm('重新构建该文档分块并全量重建向量库？（可能较慢）')) return;
      toast('开始重建…', 'info');
      api('/documents/' + id + '/rebuild', { method: 'POST' }).then(function (res) {
        toast('✅ 重建完成：总 ' + (res ? res.kb_total_chunks || 0 : 0) + ' chunks', 'success');
        loadDocuments();
      });
    });
  }
  var dbts = el.querySelectorAll('button[data-act="del"]');
  for (var d = 0; d < dbts.length; d++) {
    dbts[d].addEventListener('click', function () {
      if (!confirm('确定删除该文档？删除后建议去设置「重建向量库」。')) return;
      var id = this.getAttribute('data-id');
      api('/documents/' + id, { method: 'DELETE' }).then(function () {
        toast('已删除', 'success');
        loadDocuments();
      });
    });
  }
}

function loadKbDocListIfVisible() {
  var el = document.getElementById('kbDocList');
  if (!el) return;
  api('/documents').then(function (list) {
    if (!list || list.length === 0) {
      el.innerHTML = '<p class="empty-state small">暂无文档</p>';
      return;
    }
    var html = '';
    for (var i = 0; i < list.length; i++) {
      var d = list[i];
      html += '<div class="doc-item" style="padding:10px 14px;">' +
        '<div class="doc-main">' +
          '<div class="doc-name" style="font-size:13.5px;">' + escapeHtml(d.filename || '') + '</div>' +
          '<div class="doc-meta">' +
            '<span class="cat-tag">' + escapeHtml(d.category || '未分类') + '</span>' +
            '<span>🧩 ' + escapeHtml(String(d.chunks_count || 0)) + ' 块</span>' +
            '<span>' + escapeHtml(String(d.status || '')) + '</span>' +
          '</div>' +
        '</div>' +
      '</div>';
    }
    el.innerHTML = html;
  }).catch(function () {});
}

/* ============================================================
 * 10. 日程 schedule
 * ============================================================ */
function bindScheduleUI() {
  var prev = document.getElementById('schPrev');
  var next = document.getElementById('schNext');
  var addBtn = document.getElementById('schAddBtn');
  if (prev) prev.addEventListener('click', function () {
    STATE.calendar.month -= 1;
    if (STATE.calendar.month < 1) { STATE.calendar.month = 12; STATE.calendar.year -= 1; }
    loadSchedule(STATE.calendar.year, STATE.calendar.month);
  });
  if (next) next.addEventListener('click', function () {
    STATE.calendar.month += 1;
    if (STATE.calendar.month > 12) { STATE.calendar.month = 1; STATE.calendar.year += 1; }
    loadSchedule(STATE.calendar.year, STATE.calendar.month);
  });
  if (addBtn) addBtn.addEventListener('click', function () {
    var today = new Date();
    if (STATE.calendar.selected) today = parseISODate(STATE.calendar.selected);
    setVal('sc-date', fmtISODate(today));
    setVal('sc-title', '');
    setVal('sc-content', '');
    openModal('schedule-modal');
  });
  var scSave = document.getElementById('sc-save');
  if (scSave) scSave.addEventListener('click', saveSchedule);
}

function fmtISODate(d) {
  var m = d.getMonth() + 1;
  var day = d.getDate();
  return d.getFullYear() + '-' + (m < 10 ? '0':'') + m + '-' + (day < 10 ? '0':'') + day;
}
function parseISODate(s) {
  var parts = s.split('-');
  if (parts.length < 3) return new Date();
  return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
}

function loadSchedule(year, month) {
  if (!year || !month) {
    var now = new Date();
    year = now.getFullYear();
    month = now.getMonth() + 1;
  }
  STATE.calendar.year = year;
  STATE.calendar.month = month;
  var t = document.getElementById('calTitle');
  if (t) t.textContent = year + ' 年 ' + month + ' 月';
  if (!STATE.calendar.selected) {
    var tod = new Date();
    if (tod.getFullYear() === year && (tod.getMonth()+1) === month) {
      STATE.calendar.selected = fmtISODate(tod);
    } else {
      STATE.calendar.selected = fmtISODate(new Date(year, month - 1, 1));
    }
  }
  // 选中日期若不在当前月 → 重置为 1 号
  var selParts = STATE.calendar.selected.split('-');
  if (selParts.length >= 2 && (parseInt(selParts[0], 10) !== year || parseInt(selParts[1], 10) !== month)) {
    STATE.calendar.selected = fmtISODate(new Date(year, month - 1, 1));
  }

  // 月范围
  var fromD = fmtISODate(new Date(year, month - 1, 1));
  var toD = fmtISODate(new Date(year, month, 0));
  renderCalendarGrid(year, month, []);
  updateDayDetail([]);

  // 取日程
  api('/schedules?from_date=' + encodeURIComponent(fromD) + '&to=' + encodeURIComponent(toD)).then(function (list) {
    renderCalendarGrid(year, month, list || []);
    var todayS = STATE.calendar.selected;
    var dayList = filterSchedulesForDate(list, todayS);
    updateDayDetail(dayList);
  }).catch(function () {
    // 已 toast
  });
}

function filterSchedulesForDate(list, s) {
  var out = [];
  if (!list) return out;
  for (var i = 0; i < list.length; i++) if (list[i].date === s) out.push(list[i]);
  // 排序
  out.sort(function (a, b) {
    var ta = a.time_start || ''; var tb = b.time_start || '';
    if (ta < tb) return -1; if (ta > tb) return 1;
    return (a.id || 0) - (b.id || 0);
  });
  return out;
}

function renderCalendarGrid(year, month, events) {
  var grid = document.getElementById('calGrid');
  if (!grid) return;
  var first = new Date(year, month - 1, 1);
  var startWeekDay = first.getDay(); // 0=Sun
  var daysInMonth = new Date(year, month, 0).getDate();
  var prevMonthLast = new Date(year, month - 1, 0).getDate();
  var today = new Date();
  var todayStr = fmtISODate(today);

  var cells = [];
  // 上月尾部
  for (var i = startWeekDay - 1; i >= 0; i--) {
    var pDay = prevMonthLast - i;
    var pMonth = month - 1; var pYear = year;
    if (pMonth < 1) { pMonth = 12; pYear -= 1; }
    cells.push({ date: fmtISODate(new Date(pYear, pMonth - 1, pDay)), day: pDay, other: true });
  }
  // 本月
  for (var d = 1; d <= daysInMonth; d++) {
    cells.push({ date: fmtISODate(new Date(year, month - 1, d)), day: d, other: false });
  }
  // 下月补足至 42 格（6 行）
  var need = 42 - cells.length;
  for (var k = 1; k <= need; k++) {
    var nMonth = month + 1; var nYear = year;
    if (nMonth > 12) { nMonth = 1; nYear += 1; }
    cells.push({ date: fmtISODate(new Date(nYear, nMonth - 1, k)), day: k, other: true });
  }

  // 按日期聚合事件
  var evMap = {};
  for (var e = 0; e < events.length; e++) {
    var ev = events[e];
    if (!ev.date) continue;
    if (!evMap[ev.date]) evMap[ev.date] = [];
    evMap[ev.date].push(ev);
  }

  var html = '';
  for (var c = 0; c < cells.length; c++) {
    var cell = cells[c];
    var cls = 'cal-cell' + (cell.other ? ' other' : '');
    if (cell.date === todayStr) cls += ' today';
    if (cell.date === STATE.calendar.selected) cls += ' selected';
    html += '<div class="' + cls + '" data-date="' + escapeHtml(cell.date) + '">';
    html += '<div class="cal-date">' + cell.day + '</div>';
    html += '<div class="cal-events">';
    var evList = evMap[cell.date] || [];
    var maxShow = 2;
    for (var ei = 0; ei < Math.min(evList.length, maxShow); ei++) {
      var e1 = evList[ei];
      var cat = e1.category || 'teach';
      var title = (e1.time_start ? (e1.time_start + ' ') : '') + (e1.title || '未命名');
      html += '<div class="cal-ev ' + escapeHtml(cat) + '">' + escapeHtml(title) + '</div>';
    }
    if (evList.length > maxShow) {
      html += '<div class="cal-ev-more">⋯ 还有 ' + (evList.length - maxShow) + ' 项</div>';
    }
    html += '</div></div>';
  }
  grid.innerHTML = html;

  var cellsEls = grid.querySelectorAll('.cal-cell');
  for (var ci = 0; ci < cellsEls.length; ci++) {
    cellsEls[ci].addEventListener('click', function () {
      var dt = this.getAttribute('data-date');
      STATE.calendar.selected = dt;
      var arr = Object.keys(evMap).length > 0 ? [] : null;
      // 从 events 变量筛选
      var selList = filterSchedulesForDate(events, dt);
      updateDayDetail(selList);
      renderCalendarGrid(year, month, events);
    });
  }
}

function updateDayDetail(dayList) {
  var h = document.getElementById('dayTitle');
  if (h) {
    var sel = STATE.calendar.selected;
    var tod = fmtISODate(new Date());
    var prefix = (sel === tod) ? '今日' : sel;
    h.textContent = prefix + ' 日程（共 ' + (dayList ? dayList.length : 0) + ' 项）';
  }
  var ul = document.getElementById('dayList');
  if (!ul) return;
  if (!dayList || dayList.length === 0) {
    ul.innerHTML = '<li class="empty-state small">该日暂无日程安排。</li>';
    return;
  }
  var html = '';
  for (var i = 0; i < dayList.length; i++) {
    var ev = dayList[i];
    var cat = ev.category || 'teach';
    var done = ev.done ? true : false;
    var t = ev.time_start || '';
    var e = ev.time_end || '';
    var timeS = (t || e) ? (t + (e ? (' - ' + e) : '')) : '全天';
    var title = ev.title || '未命名日程';
    var content = ev.content || '';
    html += '<li class="day-ev ' + escapeHtml(cat) + (done ? ' done' : '') + '" data-id="' + escapeHtml(String(ev.id)) + '">' +
      '<div class="de-head">' +
        '<div class="de-title">' + escapeHtml(title) + '</div>' +
        '<div class="de-time">' + escapeHtml(timeS) + '</div>' +
      '</div>' +
      (content ? ('<div class="de-content">' + escapeHtml(content) + '</div>') : '') +
      '<div class="de-actions">' +
        '<button class="icon-btn" data-act="done" data-id="' + escapeHtml(String(ev.id)) + '" title="完成/取消">' + (done ? '↩️' : '✅') + '</button>' +
        '<button class="icon-btn danger" data-act="del" data-id="' + escapeHtml(String(ev.id)) + '" title="删除">🗑️</button>' +
      '</div>' +
    '</li>';
  }
  ul.innerHTML = html;

  var dbtns = ul.querySelectorAll('button[data-act="done"]');
  for (var di = 0; di < dbtns.length; di++) {
    dbtns[di].addEventListener('click', function () {
      var id = this.getAttribute('data-id');
      api('/schedules/' + id + '/done', { method: 'POST' }).then(function () {
        toast('状态已更新', 'success');
        loadSchedule(STATE.calendar.year, STATE.calendar.month);
      });
    });
  }
  var xbtns = ul.querySelectorAll('button[data-act="del"]');
  for (var xi = 0; xi < xbtns.length; xi++) {
    xbtns[xi].addEventListener('click', function () {
      if (!confirm('确定删除该日程？')) return;
      var id = this.getAttribute('data-id');
      api('/schedules/' + id, { method: 'DELETE' }).then(function () {
        toast('已删除', 'success');
        loadSchedule(STATE.calendar.year, STATE.calendar.month);
      });
    });
  }
}

function saveSchedule() {
  var titleEl = document.getElementById('sc-title');
  var title = titleEl ? titleEl.value.trim() : '';
  if (!title) { toast('请填写日程标题', 'warn'); return; }
  var date = document.getElementById('sc-date').value;
  if (!date) { toast('请选择日期', 'warn'); return; }
  var payload = {
    title: title,
    content: document.getElementById('sc-content') ? (document.getElementById('sc-content').value || '') : '',
    date: date,
    time_start: document.getElementById('sc-start') ? (document.getElementById('sc-start').value || '') : '',
    time_end: document.getElementById('sc-end') ? (document.getElementById('sc-end').value || '') : '',
    category: document.getElementById('sc-category') ? (document.getElementById('sc-category').value || 'teach') : 'teach',
    done: 0
  };
  api('/schedules', { method: 'POST', body: JSON.stringify(payload) }).then(function () {
    toast('已保存日程', 'success');
    closeModal('schedule-modal');
    loadSchedule(STATE.calendar.year, STATE.calendar.month);
  });
}

/* ============================================================
 * 11. AI 教研助手
 * ============================================================ */
function bindAssistantUI() {
  var btn = document.getElementById('newSessionBtn');
  if (btn) btn.addEventListener('click', newSession);

  var send = document.getElementById('sendBtn');
  if (send) send.addEventListener('click', sendChat);
  var ta = document.getElementById('chatInput');
  if (ta) {
    ta.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        sendChat();
      }
    });
    ta.addEventListener('input', function () {
      ta.style.height = 'auto';
      var maxH = 160;
      ta.style.height = Math.min(ta.scrollHeight, maxH) + 'px';
    });
  }
  // quickPrompts 在 placeholder 中
  var qpEl = document.getElementById('quickPrompts');
  if (qpEl) {
    qpEl.addEventListener('click', function (ev) {
      var t = ev.target;
      if (t && t.tagName === 'SPAN') {
        var q = t.textContent || '';
        var chatIn = document.getElementById('chatInput');
        if (chatIn) { chatIn.value = q; chatIn.focus(); }
      }
    });
  }

  // AI 助手多模态三 Tab 切换
  var aTabs = document.querySelectorAll('#assistantTabs .assistant-tab');
  for (var at = 0; at < aTabs.length; at++) {
    aTabs[at].addEventListener('click', function () {
      var self = this;
      var key = self.getAttribute('data-atab') || 'text';
      document.querySelectorAll('#assistantTabs .assistant-tab').forEach(function (x) { x.classList.remove('active'); });
      self.classList.add('active');
      document.querySelectorAll('.assistant-pane').forEach(function (p) {
        p.classList.toggle('active', p.getAttribute('data-apane') === key);
      });
    });
  }

  // 图片理解：快捷模板
  var vqEl = document.getElementById('visionQuickPrompts');
  if (vqEl) {
    vqEl.addEventListener('click', function (ev) {
      var t = ev.target;
      if (t && t.tagName === 'SPAN' && t.getAttribute('data-vp')) {
        var pp = document.getElementById('visionPrompt');
        if (pp) { pp.value = t.getAttribute('data-vp'); pp.focus(); }
      }
    });
  }
  // 文生图：快捷模板
  var tqEl = document.getElementById('ttiQuickPrompts');
  if (tqEl) {
    tqEl.addEventListener('click', function (ev) {
      var t = ev.target;
      if (t && t.tagName === 'SPAN' && t.getAttribute('data-tp')) {
        var pp = document.getElementById('ttiPrompt');
        if (pp) { pp.value = t.getAttribute('data-tp'); pp.focus(); }
      }
    });
  }

  // 图片理解分析
  var vBtn = document.getElementById('visionAnalyzeBtn');
  if (vBtn) {
    vBtn.addEventListener('click', function () {
      var urlsEl = document.getElementById('visionUrls');
      var promptEl = document.getElementById('visionPrompt');
      var urlsRaw = urlsEl ? (urlsEl.value || '') : '';
      var urls = urlsRaw.split(/\s+/).map(function (s) { return s.trim(); }).filter(function (s) { return s && /^https?:\/\//i.test(s); });
      var prompt = promptEl ? (promptEl.value || '').trim() : '';
      if (!urls.length) { toast('请先填写至少 1 张图片的 URL（https:// 开头）', 'warn'); return; }
      if (!prompt) { toast('请先填写分析指令（可点击上方快捷模板）', 'warn'); return; }
      var his = document.getElementById('visionHistory');
      if (his) {
        var userMsg = document.createElement('div');
        userMsg.className = 'msg user';
        var thumbs = '';
        for (var ui = 0; ui < urls.length; ui++) {
          thumbs += '<img src="' + escapeHtml(urls[ui]) + '" class="mm-thumb" alt="图' + (ui+1) + '" />';
        }
        userMsg.innerHTML = '<div class="msg-bubble">' +
          (thumbs ? '<div class="mm-thumbs">' + thumbs + '</div>' : '') +
          '<div class="mm-question">' + escapeHtml(prompt) + '</div>' +
        '</div>';
        his.appendChild(userMsg);
        var placeholder = his.querySelector('.chat-placeholder');
        if (placeholder) placeholder.remove();
        var bot = document.createElement('div');
        bot.className = 'msg ai mm-loading';
        bot.innerHTML = '<div class="msg-bubble">🖼️ 千问 qwen-vl-plus 正在读图中…（通常 5-15 秒）</div>';
        his.appendChild(bot);
        his.scrollTop = his.scrollHeight;
      }
      vBtn.disabled = true; vBtn.classList.add('disabled');
      var origText = vBtn.textContent;
      vBtn.textContent = '分析中…';
      api('/ai/vision_chat', {
        method: 'POST',
        body: JSON.stringify({ image_urls: urls, prompt: prompt })
      }).then(function (r) {
        var reply = (r && r.answer) || (r && r.message) || '（无返回内容）';
        var usage = r && r.usage ? r.usage : null;
        var model = r && r.model ? r.model : 'qwen-vl-plus';
        var html = '<div class="mm-answer">' + renderMiniMd(reply) + '</div>';
        html += '<div class="mm-foot-meta">模型：' + escapeHtml(model) + (usage ? ('　图像输入：' + (usage.image_count || urls.length) + ' 张　输入 tokens：' + (usage.input_tokens || '-') + '　输出 tokens：' + (usage.output_tokens || '-')) : '') + '</div>';
        if (bot) {
          bot.classList.remove('mm-loading');
          bot.querySelector('.msg-bubble').innerHTML = html;
        } else if (his) {
          var x = document.createElement('div'); x.className = 'msg ai';
          x.innerHTML = '<div class="msg-bubble">' + html + '</div>';
          his.appendChild(x);
        }
        if (his) his.scrollTop = his.scrollHeight;
        toast('图片分析完成', 'success');
      }).catch(function (e) {
        var errMsg = e && e.message ? e.message : '网络错误或未配置千问 Key（请先到「设置 - AI 配置」填写）';
        if (bot) {
          bot.classList.remove('mm-loading');
          bot.querySelector('.msg-bubble').innerHTML = '❌ 分析失败：' + escapeHtml(errMsg);
        }
        toast('分析失败', 'error');
      }).then(function () {
        vBtn.disabled = false; vBtn.classList.remove('disabled');
        vBtn.textContent = origText;
      });
    });
  }

  // 文生图
  var tBtn = document.getElementById('ttiGenBtn');
  if (tBtn) {
    tBtn.addEventListener('click', function () {
      var pEl = document.getElementById('ttiPrompt');
      var sEl = document.getElementById('ttiSize');
      var cEl = document.getElementById('ttiCount');
      var prompt = pEl ? (pEl.value || '').trim() : '';
      var size = sEl ? (sEl.value || '1024*1024') : '1024*1024';
      var count = cEl ? (parseInt(cEl.value, 10) || 1) : 1;
      if (!prompt) { toast('请先输入画面描述（可点击上方快捷模板）', 'warn'); return; }
      var his = document.getElementById('ttiHistory');
      if (his) {
        var userMsg = document.createElement('div');
        userMsg.className = 'msg user';
        userMsg.innerHTML = '<div class="msg-bubble"><div class="mm-question">' + escapeHtml(prompt) + '</div>' +
          '<div class="mm-foot-meta">尺寸：' + escapeHtml(size) + '　数量：' + count + ' 张</div>' +
        '</div>';
        his.appendChild(userMsg);
        var placeholder = his.querySelector('.chat-placeholder');
        if (placeholder) placeholder.remove();
        var bot = document.createElement('div');
        bot.className = 'msg ai mm-loading';
        bot.innerHTML = '<div class="msg-bubble">🎨 通义万相 wanx-v1 正在生成…（通常 3-10 秒 / 张）</div>';
        his.appendChild(bot);
        his.scrollTop = his.scrollHeight;
      }
      tBtn.disabled = true; tBtn.classList.add('disabled');
      var origText = tBtn.textContent;
      tBtn.textContent = '生成中…';
      api('/ai/text_to_image', {
        method: 'POST',
        body: JSON.stringify({ prompt: prompt, size: size, n: count })
      }).then(function (r) {
        var urls = (r && r.images && r.images.length) ? r.images : [];
        var model = (r && r.model) ? r.model : 'wanx-v1';
        if (!urls.length) {
          if (bot) bot.querySelector('.msg-bubble').innerHTML = '❌ 未生成到图片：' + escapeHtml((r && r.error) || '未知错误');
          toast('生成失败', 'error');
          return;
        }
        var imgsHtml = '';
        for (var ui = 0; ui < urls.length; ui++) {
          imgsHtml += '<a href="' + escapeHtml(urls[ui]) + '" target="_blank" rel="noopener" class="mm-img-link">' +
            '<img src="' + escapeHtml(urls[ui]) + '" alt="生成图' + (ui+1) + '" class="mm-gen-img" /></a>';
        }
        var tips = '<div class="mm-foot-meta">模型：' + escapeHtml(model) + '　数量：' + urls.length + ' 张　尺寸：' + escapeHtml(size) + '　（点击图片可放大，右键另存）</div>';
        if (bot) {
          bot.classList.remove('mm-loading');
          bot.querySelector('.msg-bubble').innerHTML = '<div class="mm-imgs-grid">' + imgsHtml + '</div>' + tips;
        }
        if (his) his.scrollTop = his.scrollHeight;
        toast('图片生成成功', 'success');
      }).catch(function (e) {
        var errMsg = e && e.message ? e.message : '网络错误或未配置千问 Key（请先到「设置 - AI 配置」填写）';
        if (bot) {
          bot.classList.remove('mm-loading');
          bot.querySelector('.msg-bubble').innerHTML = '❌ 生成失败：' + escapeHtml(errMsg);
        }
        toast('生成失败', 'error');
      }).then(function () {
        tBtn.disabled = false; tBtn.classList.remove('disabled');
        tBtn.textContent = origText;
      });
    });
  }
}

function loadChatSessions() {
  var ul = document.getElementById('sessionList');
  if (!ul) return;
  ul.innerHTML = '<li class="empty-state small">加载中…</li>';
  api('/sessions').then(function (list) {
    var arr = list || [];
    var selId = STATE.chat.currentSessionId;
    if (selId == null && arr.length > 0) selId = arr[0].id;
    // 渲染列表
    if (arr.length === 0) {
      ul.innerHTML = '<li class="empty-state small">暂无会话 · 点击「新会话」或直接在右侧提问即可创建</li>';
    } else {
      var html = '';
      for (var i = 0; i < arr.length; i++) {
        var s = arr[i];
        var active = (s.id === selId) ? ' active' : '';
        var title = s.title || '新会话';
        var updated = s.updated_at || s.created_at || '';
        if (updated && updated.length > 16) updated = updated.substring(5, 16).replace('T',' ');
        html += '<li class="session-item' + active + '" data-id="' + escapeHtml(String(s.id)) + '">' +
          '<span class="s-title">' + escapeHtml(title) + '</span>' +
          '<span style="font-size:10.5px;color:rgba(247,242,227,0.35);">' + escapeHtml(updated) + '</span>' +
          '<button class="s-del" data-id="' + escapeHtml(String(s.id)) + '" title="删除">🗑</button>' +
        '</li>';
      }
      ul.innerHTML = html;

      var lis = ul.querySelectorAll('.session-item');
      for (var li = 0; li < lis.length; li++) {
        lis[li].addEventListener('click', function (ev) {
          // 如果点的是删除按钮
          if (ev.target && ev.target.classList && ev.target.classList.contains('s-del')) return;
          var id = this.getAttribute('data-id');
          STATE.chat.currentSessionId = parseInt(id, 10);
          loadChatSessions(); // 重新标记 active + 加载消息
        });
      }
      var dels = ul.querySelectorAll('.s-del');
      for (var dd = 0; dd < dels.length; dd++) {
        dels[dd].addEventListener('click', function (ev) {
          ev.stopPropagation();
          if (!confirm('确定删除该会话？')) return;
          var id = this.getAttribute('data-id');
          api('/sessions/' + id, { method: 'DELETE' }).then(function () {
            toast('已删除会话', 'success');
            if (STATE.chat.currentSessionId == id) STATE.chat.currentSessionId = null;
            loadChatSessions();
          });
        });
      }
    }
    // 加载选中会话消息
    if (selId) {
      STATE.chat.currentSessionId = selId;
      loadChatMessages(selId);
    } else {
      showChatPlaceholder();
    }
  }).catch(function () {
    ul.innerHTML = '<li class="empty-state small">加载失败</li>';
  });
}

function newSession() {
  api('/sessions', { method: 'POST', body: JSON.stringify({ title: '新会话' }) }).then(function (r) {
    STATE.chat.currentSessionId = r ? r.id : null;
    toast('已创建新会话', 'success');
    loadChatSessions();
  });
}

function showChatPlaceholder() {
  var hist = document.getElementById('chatHistory');
  if (!hist) return;
  hist.innerHTML = '<div class="chat-placeholder">' +
    '<div class="chat-hint-card">' +
      '<h2>🎋 AI 教研助手 · RAG 问答</h2>' +
      '<p>基于您的知识库文档，生成教案、解读课文、分析学情。</p>' +
      '<div class="quick-prompts" id="quickPrompts">' +
        '<span>静夜思的教学目标？</span>' +
        '<span>三年级《大青树下的小学》教案</span>' +
        '<span>二年级班主任家长会沟通要点</span>' +
        '<span>学困生如何帮扶？</span>' +
        '<span>《村居》识字教学设计</span>' +
      '</div>' +
    '</div></div>';
  var qp = document.getElementById('quickPrompts');
  if (qp) {
    qp.addEventListener('click', function (ev) {
      var t = ev.target;
      if (t && t.tagName === 'SPAN') {
        var q = t.textContent || '';
        var chatIn = document.getElementById('chatInput');
        if (chatIn) { chatIn.value = q; chatIn.focus(); }
      }
    });
  }
}

function loadChatMessages(sid) {
  var hist = document.getElementById('chatHistory');
  if (!hist) return;
  if (!sid) { showChatPlaceholder(); return; }
  hist.innerHTML = '<div class="empty-state small">加载会话消息…</div>';
  api('/sessions/' + sid + '/messages').then(function (list) {
    hist.innerHTML = '';
    if (!list || list.length === 0) {
      hist.innerHTML = '<div class="chat-bubble ai"><div class="avatar ai">AI</div>' +
        '<div class="bubble-body">您好，' + escapeHtml(STATE.userName || '老师') + '！我是您的教研 AI 助手。有什么可以帮您的？</div>' +
        '</div>';
      return;
    }
    for (var i = 0; i < list.length; i++) {
      var m = list[i];
      appendBubbleToDom(m.role, m.content, m.refs || null, false);
    }
    scrollChatBottom();
  }).catch(function () {
    hist.innerHTML = '<div class="empty-state small">加载失败</div>';
  });
}

function scrollChatBottom() {
  var h = document.getElementById('chatHistory');
  if (h) setTimeout(function () { h.scrollTop = h.scrollHeight; }, 30);
}

function appendBubbleToDom(role, content, refs, withCursor) {
  var hist = document.getElementById('chatHistory');
  if (!hist) return null;
  // 如果存在 placeholder 先清掉
  var ph = hist.querySelector('.chat-placeholder');
  if (ph) hist.innerHTML = '';

  var wrap = document.createElement('div');
  wrap.className = 'chat-bubble ' + (role === 'user' ? 'user' : 'ai');

  var av = document.createElement('div');
  av.className = 'avatar ' + (role === 'user' ? 'user' : 'ai');
  av.textContent = role === 'user' ? (STATE.userName ? STATE.userName.substring(0,1) : '我') : 'AI';

  var body = document.createElement('div');
  body.className = 'bubble-body';
  var txt = document.createElement('div');
  txt.className = 'bubble-text';
  txt.innerHTML = renderAnswerToHtml(content || '');
  body.appendChild(txt);
  if (refs && refs.length) {
    var refsBox = document.createElement('div');
    refsBox.className = 'refs';
    for (var i = 0; i < refs.length; i++) {
      var r = refs[i];
      var name = r.doc_name || r.filename || r.source || '未知文档';
      var idx = r.chunk_index != null ? r.chunk_index : '';
      var snip = (r.page_snippet || r.text || '').toString();
      if (snip.length > 80) snip = snip.substring(0, 80) + '…';
      var span = document.createElement('span');
      span.className = 'ref-item';
      span.innerHTML = '<span class="rf-name">' + escapeHtml(name) + (idx !== '' ? (' · 片段' + idx) : '') + '</span>' +
        '<span class="rf-snip">' + escapeHtml(snip) + '</span>';
      refsBox.appendChild(span);
    }
    body.appendChild(refsBox);
  }
  if (withCursor) {
    var cur = document.createElement('span');
    cur.className = 'type-cursor';
    body.appendChild(cur);
  }
  wrap.appendChild(av);
  wrap.appendChild(body);
  hist.appendChild(wrap);
  scrollChatBottom();
  return { wrap: wrap, textEl: txt };
}

function removeCursorFromLast() {
  var hist = document.getElementById('chatHistory');
  if (!hist) return;
  var c = hist.querySelector('.chat-bubble.ai:last-child .type-cursor');
  if (c) c.remove();
}

// 简易 markdown（支持 \n 换行、加粗、引用）
function renderAnswerToHtml(text) {
  if (text == null) return '';
  var s = String(text);
  s = escapeHtml(s);
  // **bold**
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // ### 标题 (不替换已经有 # 的，行首处理）
  var lines = s.split('\n');
  var out = [];
  for (var i = 0; i < lines.length; i++) {
    var ln = lines[i];
    if (/^#{1,6}\s+/.test(ln)) {
      ln = ln.replace(/^(#{1,6})\s+/, function (m, h) {
        var lvl = h.length;
        return '<strong style="font-size:' + (22 - lvl * 2) + 'px;color:#C8A762;">';
      }) + '</strong>';
    }
    if (/^\s*[-*]\s+/.test(ln)) ln = ln.replace(/^(\s*)([-*])\s+/, '$1• ');
    out.push(ln);
  }
  return out.join('\n');
}

function sendChat() {
  var input = document.getElementById('chatInput');
  if (!input) return;
  var q = (input.value || '').trim();
  if (!q) { toast('请输入问题', 'warn'); return; }
  if (STATE.chat.streaming) { toast('正在生成中，请稍候', 'warn'); return; }

  input.value = '';
  input.style.height = 'auto';

  // 1. 用户气泡
  appendBubbleToDom('user', q, null, false);

  // 2. 若没有 currentSessionId → 新建一个
  var runSend = function (sid) {
    STATE.chat.currentSessionId = sid;
    // 初始 AI 气泡（带光标）
    var p = appendBubbleToDom('ai', '正在思考…', null, true);
    STATE.chat.streaming = true;
    // 尝试流式
    tryStreamChat(q, sid, p).then(function () {
      STATE.chat.streaming = false;
    }).catch(function (err) {
      STATE.chat.streaming = false;
      console.error(err);
    });
  };

  if (STATE.chat.currentSessionId == null) {
    api('/sessions', { method: 'POST', body: JSON.stringify({ title: (q.length > 20 ? (q.substring(0, 20) + '…') : q) }) }).then(function (r) {
      var newId = r ? r.id : null;
      loadChatSessions(); // 刷新左侧列表
      runSend(newId);
    }).catch(function () { runSend(null); });
  } else {
    runSend(STATE.chat.currentSessionId);
  }
}

function tryStreamChat(question, sid, bubbleRefs) {
  // 优先 SSE：POST /ai/stream；若失败或无响应则降级同步
  var textEl = bubbleRefs ? bubbleRefs.textEl : null;
  var streamUrl = API_BASE + '/ai/stream';
  var body = JSON.stringify({ question: question, top_k: 3, session_id: sid || null });
  var metaGot = null;
  var answerBuf = '';
  var doneFlag = false;

  return new Promise(function (resolve) {
    var useFetchStream = (typeof fetch === 'function' && typeof ReadableStream !== 'undefined' && typeof TextDecoder !== 'undefined');
    if (!useFetchStream) return resolve(runSyncFallback(question, sid));

    fetch(streamUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body
    }).then(function (resp) {
      if (resp.status < 200 || resp.status >= 300) {
        throw new Error('HTTP ' + resp.status);
      }
      if (!resp.body) throw new Error('no body');
      var reader = resp.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buf = '';
      function processChunk() {
        return reader.read().then(function (res) {
          if (res.done) { doneFlag = true; finishStream(); return; }
          buf += decoder.decode(res.value || new Uint8Array(), { stream: true });
          // 按 SSE 行解析
          var lines = buf.split(/\r?\n\r?\n/);
          buf = lines.pop() || '';
          for (var i = 0; i < lines.length; i++) {
            var block = lines[i];
            var dataLines = block.split(/\r?\n/);
            for (var j = 0; j < dataLines.length; j++) {
              var line = dataLines[j];
              if (line.indexOf('data:') !== 0) continue;
              var ds = line.substring(5).replace(/^\s+/, '');
              if (ds === '[DONE]') { doneFlag = true; finishStream(); return; }
              try {
                var obj = JSON.parse(ds);
                handleStreamEvent(obj);
              } catch (_) {}
            }
          }
          return processChunk();
        });
      }
      function handleStreamEvent(obj) {
        if (!obj) return;
        var tp = obj.type;
        if (tp === 'meta') {
          metaGot = obj;
          setChatFootMeta(obj);
        } else if (tp === 'token' && obj.content) {
          answerBuf += obj.content;
          if (textEl) textEl.innerHTML = renderAnswerToHtml(answerBuf);
          scrollChatBottom();
        }
      }
      function finishStream() {
        removeCursorFromLast();
        // 若有 meta 且没渲染 refs，补 refs
        if (metaGot && metaGot.refs && textEl) {
          // 找 parent bubble-body
          var body = textEl.parentElement;
          if (body && !body.querySelector('.refs')) {
            appendRefsToBody(body, metaGot.refs);
          }
          if (sid) saveMessagesQuietly(sid, question, answerBuf, metaGot.refs);
        } else if (!metaGot) {
          // meta 未拿到（可能非流式后端），同步再取一次
          runSyncFallbackForFinal(question, sid, answerBuf);
        }
        scrollChatBottom();
        resolve();
      }
      return processChunk();
    }).catch(function (err) {
      console.warn('stream fail, fallback to sync', err);
      // 清掉"正在思考"初始占位
      if (answerBuf === '' && textEl) textEl.innerHTML = renderAnswerToHtml('（流式接口不可用，正在走同步接口…）');
      runSyncFallback(question, sid).then(resolve);
    });
  });
}

function appendRefsToBody(body, refs) {
  if (!refs || !refs.length) return;
  var rb = document.createElement('div');
  rb.className = 'refs';
  for (var i = 0; i < refs.length; i++) {
    var r = refs[i];
    var name = r.doc_name || r.filename || r.source || '未知文档';
    var idx = r.chunk_index != null ? r.chunk_index : '';
    var snip = (r.page_snippet || r.text || '').toString();
    if (snip.length > 100) snip = snip.substring(0, 100) + '…';
    var sp = document.createElement('span');
    sp.className = 'ref-item';
    sp.innerHTML = '<span class="rf-name">' + escapeHtml(name) + (idx !== '' ? (' · 片段' + idx) : '') + '</span>' +
      '<span class="rf-snip">' + escapeHtml(snip) + '</span>';
    rb.appendChild(sp);
  }
  body.appendChild(rb);
}

function setChatFootMeta(meta) {
  var el = document.getElementById('chatFootMeta');
  if (!el) return;
  if (!meta) { el.textContent = '模型：-- ｜ 知识库：已启用（top_k=3）'; return; }
  var model = meta.model_used || '（模板）';
  var refsCount = meta.refs ? meta.refs.length : 0;
  var note = meta.usage_note ? ('｜' + meta.usage_note) : '';
  el.textContent = '模型：' + model + ' ｜ 引用 ' + refsCount + ' 条' + note;
}

function saveMessagesQuietly(sid, userQ, answer, refs) {
  if (!sid) return;
  // 已经在 /ai/ask / stream 后端落库，这里可以不重复
  return;
}

function runSyncFallback(question, sid) {
  return new Promise(function (resolve) {
    // 先找到 AI 气泡里还没结束的那个 textEl
    var hist = document.getElementById('chatHistory');
    var aiLast = hist ? hist.querySelector('.chat-bubble.ai:last-child .bubble-text') : null;
    api('/ai/ask', {
      method: 'POST',
      body: JSON.stringify({ question: question, top_k: 3, session_id: sid || null })
    }).then(function (r) {
      var answer = r ? (r.answer || '') : '';
      var refs = r ? (r.refs || []) : [];
      if (aiLast) aiLast.innerHTML = renderAnswerToHtml(answer);
      var body = aiLast ? aiLast.parentElement : null;
      if (body && refs.length) appendRefsToBody(body, refs);
      setChatFootMeta({ model_used: r ? r.model_used : '', refs: refs, usage_note: r ? r.usage_note : '' });
      removeCursorFromLast();
      scrollChatBottom();
      resolve();
    }).catch(function (err) {
      if (aiLast) aiLast.innerHTML = renderAnswerToHtml('生成失败：' + (err && err.message ? err.message : '未知错误'));
      removeCursorFromLast();
      resolve();
    });
  });
}
function runSyncFallbackForFinal(question, sid, partial) {
  if (partial) return; // 已有 partial，说明流其实工作了只是 meta 没拿到
  runSyncFallback(question, sid);
}

/* ============================================================
 * 12. 教学工具 tools
 * ============================================================ */
var TOOL_TITLE_MAP = {
  lesson_plan: { form: '· 教案生成参数 ·', result: '教案预览' },
  courseware: { form: '· 课件大纲生成参数 ·', result: '课件大纲预览' },
  homework: { form: '· 分层作业设计参数 ·', result: '作业设计预览' },
  paper: { form: '· 教学小论文参数 ·', result: '论文提纲预览' },
  ppt: { form: '· PPT 演示文稿参数 ·', result: 'PPT 幻灯片预览' }
};

function bindToolsUI() {
  var tabs = document.querySelectorAll('#toolsTabs .tools-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var self = this;
      document.querySelectorAll('#toolsTabs .tools-tab').forEach(function (x) { x.classList.remove('active'); });
      self.classList.add('active');
      var t = self.getAttribute('data-tool') || 'lesson_plan';
      STATE.tools.currentTool = t;
      var info = TOOL_TITLE_MAP[t];
      var formT = document.getElementById('toolsFormTitle');
      if (formT && info) formT.textContent = info.form;
      var resT = document.getElementById('toolsResultTitle');
      if (resT && info) resT.textContent = info.result + '（点击「开始生成」）';
    });
  }
  var genBtn = document.getElementById('toolsGenBtn');
  if (genBtn) genBtn.addEventListener('click', generateToolResult);
  var cpBtn = document.getElementById('toolsCopyBtn');
  if (cpBtn) cpBtn.addEventListener('click', function () {
    var body = document.getElementById('toolsResultBody');
    if (!body) return;
    var txt = body.innerText || body.textContent || '';
    if (!txt || txt.indexOf('这里将显示') >= 0) { toast('暂无可复制内容', 'warn'); return; }
    copyToClipboard(txt);
  });
  var dlBtn = document.getElementById('toolsDownloadBtn');
  if (dlBtn) dlBtn.addEventListener('click', function () {
    var resEl = document.getElementById('toolsResultBody');
    if (!resEl) return;
    var raw = resEl.getAttribute('data-raw-md') || (resEl.innerText || resEl.textContent || '');
    if (!raw || raw.indexOf('这里将显示') >= 0) { toast('暂无可下载内容', 'warn'); return; }
    var titleEl = document.getElementById('toolsResultTitle');
    var title = titleEl ? (titleEl.textContent || '生成结果').replace(/[\/\\:*?"<>|]/g,'_') : '生成结果';
    var blob = new Blob([raw], { type: 'text/markdown;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = title + '.md';
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    toast('已下载 Markdown', 'success');
  });
}

function copyToClipboard(txt) {
  try {
    var ta = document.createElement('textarea');
    ta.value = txt; ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    toast('已复制到剪贴板', 'success');
  } catch (_) {
    toast('复制失败', 'error');
  }
}

function loadTools() {
  // 历史
  var histUl = document.getElementById('toolsHistoryList');
  if (histUl) {
    histUl.innerHTML = '<li class="empty-state small">加载中…</li>';
    api('/tools/history').then(function (list) {
      renderToolsHistory(list || []);
    }).catch(function () {
      histUl.innerHTML = '<li class="empty-state small">加载失败</li>';
    });
  }
}

function renderToolsHistory(list) {
  var histUl = document.getElementById('toolsHistoryList');
  if (!histUl) return;
  if (!list.length) {
    histUl.innerHTML = '<li class="empty-state small">暂无历史记录</li>';
    return;
  }
  var typeName = { lesson_plan: '教案', courseware: '课件', homework: '作业', paper: '论文', ppt: 'PPT' };
  var html = '';
  var max = Math.min(20, list.length);
  for (var i = 0; i < max; i++) {
    var r = list[i];
    var tt = r.tool_type || 'lesson_plan';
    var tnm = typeName[tt] || tt;
    var title = r.title || '未命名';
    var date = r.created_at || '';
    if (date && date.length > 16) date = date.substring(0,16).replace('T',' ');
    html += '<li class="hist-item" data-id="' + escapeHtml(String(r.id)) + '">' +
      '<span class="hist-title"><span class="hist-tag">' + escapeHtml(tnm) + '</span>' + escapeHtml(title) + '</span>' +
      '<span class="hist-meta">' + escapeHtml(date) + '</span>' +
    '</li>';
  }
  histUl.innerHTML = html;
  var items = histUl.querySelectorAll('.hist-item');
  for (var k = 0; k < items.length; k++) {
    items[k].addEventListener('click', function () {
      var id = this.getAttribute('data-id');
      var tgt = null;
      for (var j = 0; j < list.length; j++) if (String(list[j].id) === String(id)) { tgt = list[j]; break; }
      if (!tgt) return;
      applyToolRunToResult(tgt);
    });
  }
}

function applyToolRunToResult(r) {
  var result = r.result || {};
  var md = typeof result === 'object' ? (result.markdown || '') : (result || '');
  var refs = typeof result === 'object' ? (result.refs || []) : [];
  var slides = (result && result.ppt_slides) ? result.ppt_slides : [];
  renderResultPanel(r.tool_type, r.title || '生成结果', md, refs, slides, r.id);
  toast('已载入该历史结果', 'info');
}

function generateToolResult() {
  if (STATE.chat.streaming) { toast('当前有生成任务，请稍候', 'warn'); return; }
  var toolType = STATE.tools.currentTool;
  var payload = {
    tool_type: toolType,
    subject: valOf('t-subject', '语文'),
    grade: valOf('t-grade', ''),
    unit: valOf('t-unit', ''),
    topic: (valOf('t-topic') || '').trim(),
    extra: valOf('t-extra', ''),
    top_k: parseInt(valOf('t-topk', '3'), 10) || 3,
    use_rag: true
  };
  // 必填校验：避免标题里出现「(年级待补)」等占位
  if (!payload.topic) {
    toast('请填写【主题 / 课文 / 论文题目】', 'warn');
    var tTopic = document.getElementById('t-topic');
    if (tTopic) tTopic.focus();
    return;
  }
  if (!payload.subject) {
    toast('请选择【学科】', 'warn');
    return;
  }
  if (!payload.grade) {
    toast('请选择【年级 / 学段】', 'warn');
    return;
  }
  var info = TOOL_TITLE_MAP[toolType];
  var resT = document.getElementById('toolsResultTitle');
  if (resT && info) resT.textContent = info.result + ' · 生成中…';
  var pg = document.getElementById('toolsProgress');
  var pb = document.getElementById('toolsProgressBar');
  var pt = document.getElementById('toolsProgressText');
  if (pg) pg.classList.remove('hidden');
  if (pb) pb.style.width = '0%';
  if (pt) pt.textContent = '正在知识库检索 & AI 生成…';

  // 动画进度
  var anim = setInterval(function () {
    if (!pb) return;
    var cur = parseFloat(pb.style.width || '0');
    if (cur < 85) pb.style.width = (cur + 4) + '%';
  }, 220);

  var t0 = Date.now();
  api('/tools/generate', { method: 'POST', body: JSON.stringify(payload) }).then(function (r) {
    clearInterval(anim);
    if (pb) pb.style.width = '100%';
    if (pt) pt.textContent = '✅ 生成完成，耗时 ' + (Date.now() - t0) + 'ms';
    setTimeout(function () { if (pg) pg.classList.add('hidden'); }, 1200);
    var md = (r && r.result && r.result.markdown) ? r.result.markdown : (r && r.result ? r.result : '');
    var refs = (r && r.result && r.result.refs) ? r.result.refs : (r && r.refs ? r.refs : []);
    var slides = (r && r.ppt_slides && r.ppt_slides.length) ? r.ppt_slides : ((r && r.result && r.result.ppt_slides) ? r.result.ppt_slides : []);
    var runId = r ? r.id : null;
    renderResultPanel(toolType, r ? (r.title || info.result) : info.result, md, refs, slides, runId);
    toast('生成成功', 'success');
    loadTools();
  }).catch(function () {
    clearInterval(anim);
    if (pt) pt.textContent = '❌ 生成失败';
    setTimeout(function () { if (pg) pg.classList.add('hidden'); }, 1500);
  });
}

function valOf(id, def) {
  var el = document.getElementById(id);
  if (!el) return def;
  var v = el.value;
  return (v === null || v === undefined || v === '') ? def : v;
}

/* 全局 PPT 预览渲染（给 renderResultPanel 与 demo-ppt.html 复用）*/
function renderPPTPreview(slides, body, runId, title) {
  title = title || '教学演示文稿';
  var wrap = document.createElement('div');
  wrap.className = 'ppt-slides-wrap';
  wrap.innerHTML = '<h3 style="margin:0 0 8px 0;">📽️ 幻灯片结构化预览（共 ' + slides.length + ' 页） · 玻璃拟态国风版</h3>';
  var nav = document.createElement('div');
  nav.className = 'ppt-slide-nav';
  var stage = document.createElement('div');
  stage.className = 'ppt-slide-stage';
  var notesBox = document.createElement('div');
  notesBox.className = 'ppt-slide-notes';
  var cur = 0;

  function render(i) {
    if (i < 0) i = 0;
    if (i >= slides.length) i = slides.length - 1;
    cur = i;
    var s = slides[i] || {};
    var rawContent = s.content || '（该页无内容）';
    var contentHtml = renderMiniMd(rawContent);
    // 自动识别：原文 vs 注释 双栏布局（命中【原文】【注释】等关键词时启用）
    if (/原文|课文|诗句/.test(rawContent) && /注释|批注|解/.test(rawContent)) {
      contentHtml = autoTwoColGlass(rawContent);
    }
    var animTag = '';
    if (s.animation) {
      animTag = '<span class="ppt-anim-tag" title="本页动画配置">✨ ' + escapeHtml(s.animation) + '</span>';
    }
    stage.innerHTML =
      '<div class="ppt-slide-head"><span class="ppt-num">第 ' + (s.idx || (i+1)) + ' 页</span><span class="ppt-title">' + escapeHtml(s.title || '未命名') + '</span>' + animTag + '</div>' +
      '<div class="ppt-slide-body">' + contentHtml + '</div>';
    var note = '';
    if (s.intent) note += '<div class="ppt-meta-line"><b>🎯 设计意图：</b>' + escapeHtml(s.intent) + '</div>';
    if (s.notes) note += '<div class="ppt-meta-line"><b>🗒️ 讲师备注：</b>' + escapeHtml(s.notes).replace(/\n/g, '<br/>') + '</div>';
    if (s.animation) note += '<div class="ppt-meta-line"><b>✨ 动画：</b>' + escapeHtml(s.animation) + '</div>';
    notesBox.innerHTML = note || '<div class="ppt-meta-line gray">该页暂无设计意图和讲师备注。</div>';
    // nav
    var navHtml = '';
    for (var k = 0; k < slides.length; k++) {
      var tt = (slides[k].title || ('第' + (slides[k].idx || (k+1)) + '页'));
      navHtml += '<button data-i="' + k + '" class="ppt-pill' + (k === i ? ' active' : '') + '">' +
        '<span class="pill-idx">' + (slides[k].idx || (k+1)) + '</span>' + escapeHtml(tt) +
      '</button>';
    }
    navHtml += '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;"><button class="btn outline small" id="ppt-prev">⬅ 上一页</button>' +
      '<button class="btn outline small" id="ppt-next">下一页 ➡</button>' +
      '<button class="btn primary small" id="ppt-pptx">⬇ 下载 PPTX</button>' +
      '<button class="btn outline small" id="ppt-json">📋 JSON 数据</button></div>';
    nav.innerHTML = navHtml;
    var pills = nav.querySelectorAll('.ppt-pill');
    for (var m = 0; m < pills.length; m++) {
      pills[m].addEventListener('click', function () {
        render(parseInt(this.getAttribute('data-i'), 10) || 0);
      });
    }
    var pv = nav.querySelector('#ppt-prev');
    if (pv) pv.addEventListener('click', function () { render(cur - 1); });
    var nx = nav.querySelector('#ppt-next');
    if (nx) nx.addEventListener('click', function () { render(cur + 1); });
    var ppx = nav.querySelector('#ppt-pptx');
    if (ppx) ppx.addEventListener('click', function () {
      if (runId == null) {
        toast('当前结果缺少 runId，无法下载 PPTX', 'warn');
        return;
      }
      var a = document.createElement('a');
      a.href = API_BASE + '/tools/' + encodeURIComponent(runId) + '/export_pptx';
      a.download = ((title || '教学演示文稿').replace(/[\/\\:*?"<>|]/g, '_')) + '.pptx';
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { try { document.body.removeChild(a); } catch (_) {} }, 1000);
      toast('正在下载 PPTX 文件…', 'info');
    });
    var pjn = nav.querySelector('#ppt-json');
    if (pjn) pjn.addEventListener('click', function () {
      var blob = new Blob([JSON.stringify({ title: title, slides: slides }, null, 2)], { type: 'application/json;charset=utf-8' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (title || 'PPT') + '.slides.json';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
      toast('已导出 slides.json', 'success');
    });
  }
  wrap.appendChild(nav);
  wrap.appendChild(stage);
  wrap.appendChild(notesBox);
  body.appendChild(wrap);
  render(0);
}

function renderResultPanel(toolType, title, md, refs, slides, runId) {
  var tEl = document.getElementById('toolsResultTitle');
  if (tEl) tEl.textContent = title;
  var body = document.getElementById('toolsResultBody');
  if (body) {
    body.setAttribute('data-raw-md', md || '');
    if (runId != null) body.setAttribute('data-run-id', String(runId)); else body.removeAttribute('data-run-id');
    body.innerHTML = '';

    // PPT 工具：顶部渲染幻灯片预览面板
    if (toolType === 'ppt' && slides && slides.length) {
      renderPPTPreview(slides, body, runId, title);

      var sep = document.createElement('div');
      sep.innerHTML = '<hr style="margin:18px 0 8px 0;border:none;border-top:1px dashed rgba(247,242,227,0.2);"/>' +
        '<h3 style="margin:0 0 8px 0;">📄 完整 Markdown 文稿</h3>';
      body.appendChild(sep);
    }

    var lines = (md || '').split('\n');
    var inList = false;
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i];
      var m;
      // 空行
      if (/^\s*$/.test(ln)) {
        if (inList) { inList = false; }
        else body.appendChild(document.createElement('br'));
        continue;
      }
      // H1-H6
      m = ln.match(/^(#{1,6})\s+(.*)$/);
      if (m) {
        inList = false;
        var lvl = m[1].length;
        var h = document.createElement('h' + (lvl > 6 ? 6 : lvl));
        h.innerHTML = renderInlineMarkdown(m[2]);
        body.appendChild(h);
        continue;
      }
      // HR
      if (/^\s*---+\s*$/.test(ln)) { body.appendChild(document.createElement('hr')); continue; }
      // Blockquote
      if (/^\s*>/.test(ln)) {
        var q = document.createElement('blockquote');
        q.innerHTML = renderInlineMarkdown(ln.replace(/^\s*>\s?/, ''));
        body.appendChild(q); continue;
      }
      // list
      if (/^\s*([-*]|\d+\.)\s+/.test(ln)) {
        if (!inList) {
          var isOl = /^\s*\d+\./.test(ln);
          var ul = document.createElement(isOl ? 'ol' : 'ul');
          body.appendChild(ul);
          inList = true;
          body._listEl = ul;
        }
        var liTxt = ln.replace(/^\s*([-*]|\d+\.)\s+/, '');
        var li = document.createElement('li');
        li.innerHTML = renderInlineMarkdown(liTxt);
        body._listEl.appendChild(li);
        continue;
      }
      // 普通段落
      inList = false;
      var p = document.createElement('p');
      p.innerHTML = renderInlineMarkdown(ln);
      body.appendChild(p);
    }
  }
  var refsEl = document.getElementById('toolsRefsPanel');
  if (refsEl) {
    if (refs && refs.length) {
      refsEl.classList.add('has');
      var h = '<h4>📚 引用来源（' + refs.length + ' 条）</h4>';
      for (var k = 0; k < refs.length; k++) {
        var r = refs[k];
        var name = r.doc_name || r.filename || '未知文档';
        var idx = r.chunk_index != null ? r.chunk_index : '';
        var snip = (r.page_snippet || r.text || '').toString();
        if (snip.length > 120) snip = snip.substring(0, 120) + '…';
        h += '<div class="ref-item">' +
          '<span class="rf-name">' + escapeHtml(name) + (idx !== '' ? (' · 片段 ' + idx) : '') + '</span>' +
          '<span class="rf-snip">' + escapeHtml(snip) + '</span>' +
        '</div>';
      }
      refsEl.innerHTML = h;
    } else {
      refsEl.classList.remove('has');
      refsEl.innerHTML = '';
    }
  }
}

function renderInlineMarkdown(s) {
  s = escapeHtml(s);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  return s;
}

// 简易多行 Markdown（仅用于幻灯片主体）
function renderMiniMd(text) {
  if (!text) return '';
  var lines = String(text).split('\n');
  var html = '';
  var inList = false;
  var listEl = '';
  for (var i = 0; i < lines.length; i++) {
    var ln = lines[i];
    if (/^\s*$/.test(ln)) {
      if (inList) { html += listEl; listEl = ''; inList = false; }
      continue;
    }
    var m = ln.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      if (inList) { html += listEl; listEl = ''; inList = false; }
      var lv = Math.min(6, Math.max(1, m[1].length + 1));
      html += '<h' + lv + ' style="margin:6px 0;">' + renderInlineMarkdown(m[2]) + '</h' + lv + '>';
      continue;
    }
    if (/^\s*>/.test(ln)) {
      if (inList) { html += listEl; listEl = ''; inList = false; }
      html += '<blockquote style="margin:4px 0;">' + renderInlineMarkdown(ln.replace(/^\s*>\s?/, '')) + '</blockquote>';
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(ln)) {
      if (!inList) { inList = true; listEl = /^\s*\d+\./.test(ln) ? '<ol style="margin:4px 0;">' : '<ul style="margin:4px 0;">'; }
      listEl += '<li>' + renderInlineMarkdown(ln.replace(/^\s*([-*]|\d+\.)\s+/, '')) + '</li>';
      continue;
    }
    if (inList) { html += listEl; listEl = ''; inList = false; }
    html += '<p style="margin:3px 0;">' + renderInlineMarkdown(ln) + '</p>';
  }
  if (inList) html += listEl;
  return html;
}

/**
 * 自动把『原文/注释』内容分成双栏玻璃卡片
 * 左：原文（凡包含【原文/课文/诗句/原文左栏】标题的 blockquote，或未命中注释的纯诗句行）
 * 右：注释批注（包含【注释/批注/赏析/右栏】标题的 blockquote 或行）
 */
function autoTwoColGlass(text) {
  if (!text) return '';
  var lines = String(text).split('\n');
  var leftHtml = '';
  var rightHtml = '';
  var curCol = null; // 'left' / 'right'
  // 先清理独立的标题
  for (var i = 0; i < lines.length; i++) {
    var ln = lines[i].replace(/^\s+/, '');
    var plain = ln.replace(/^>\s?/, '').replace(/^>\s?/, '');
    var isQuote = /^>\s?/.test(ln);
    // 标题行判定
    if (/【原文|【课文|【诗句|原文左栏|【正文|【原诗/.test(plain)) {
      curCol = 'left';
      leftHtml += '<div class="ppt-col-title">📖 原文</div>';
      continue;
    }
    if (/【注释|【批注|【赏析|【翻译|【译文|注释右栏|【注/.test(plain)) {
      curCol = 'right';
      rightHtml += '<div class="ppt-col-title accent">🖋 注释 / 批注</div>';
      continue;
    }
    // 空行跳过
    if (!plain) continue;
    var innerHtml = renderInlineMarkdown(plain);
    // 若不是引用块但像诗句/古文行：入左；若是列表入右；否则看当前列
    if (!curCol) {
      if (isQuote || /[-*]\s+/.test(ln)) curCol = 'right';
      else curCol = 'left';
    }
    var wrap;
    if (/^\s*([-*]|\d+\.)\s+/.test(ln)) {
      var li = ln.replace(/^\s*([-*]|\d+\.)\s+/, '');
      wrap = '<li>' + renderInlineMarkdown(li) + '</li>';
    } else {
      wrap = isQuote
        ? '<blockquote>' + innerHtml + '</blockquote>'
        : '<p style="margin:3px 0;">' + innerHtml + '</p>';
    }
    if (curCol === 'left') leftHtml += wrap;
    else rightHtml += wrap;
  }
  // 兜底：若右栏完全为空，回退到普通渲染
  if (!rightHtml) return renderMiniMd(text);
  var left = '<div>' + (leftHtml || '<div class="ppt-col-title">📖 原文</div>') + '</div>';
  var right = '<div>' + rightHtml + '</div>';
  return '<div class="ppt-two-col">' + left + right + '</div>';
}

/* ============================================================
 * 13. 设置 settings
 * ============================================================ */
function bindSettingsUI() {
  var tabs = document.querySelectorAll('#settingsTabs .settings-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var self = this;
      document.querySelectorAll('#settingsTabs .settings-tab').forEach(function (x) { x.classList.remove('active'); });
      self.classList.add('active');
      var tab = self.getAttribute('data-tab');
      document.querySelectorAll('.settings-pane').forEach(function (p) {
        if (p.getAttribute('data-pane') === tab) p.classList.add('active');
        else p.classList.remove('active');
      });
      if (tab === 'about') refreshAbout();
      if (tab === 'data') loadKbDocListIfVisible();
    });
  }
  // 保存个人信息
  var saveProf = document.getElementById('saveProfileBtn');
  if (saveProf) saveProf.addEventListener('click', saveProfile);
  // 保存 AI Keys
  var saveAI = document.getElementById('saveAIKeysBtn');
  if (saveAI) saveAI.addEventListener('click', saveAIKeys);
  // 测试按钮
  var testBtns = document.querySelectorAll('.test-btn');
  for (var t = 0; t < testBtns.length; t++) {
    testBtns[t].addEventListener('click', function () {
      var prov = this.getAttribute('data-prov') || 'deepseek';
      testLLM(prov, this);
    });
  }
  // 重建向量库
  var rb = document.getElementById('rebuildKbBtn');
  if (rb) rb.addEventListener('click', rebuildKb);
  // 导出
  var ex = document.getElementById('exportDataBtn');
  if (ex) ex.addEventListener('click', exportData);
}

function loadSettings() {
  api('/settings').then(function (obj) {
    if (!obj) return;
    STATE.settings = obj;
    // 个人信息：可回填明文（非 key）
    setVal('s-user-name', obj.user_name || '刘老师');
    setVal('s-subject', obj.subject || '');
    setVal('s-grade', obj.grade || '');
    setVal('s-default-city', obj.default_city || '');
    setVal('s-city-lat', obj.city_lat || '');
    setVal('s-city-lon', obj.city_lon || '');
    setVal('s-motto', obj.motto || '');
    // 密码框不回填
    setVal('s-deepseek-key', '');
    setVal('s-openai-key', '');
    setVal('s-zhipu-key', '');
    setVal('s-dashscope-key', '');
    refreshAbout();
  }).catch(function () {});
}

function saveProfile() {
  var pairs = [
    ['user_name', valOf('s-user-name', '老师')],
    ['subject', valOf('s-subject', '')],
    ['grade', valOf('s-grade', '')],
    ['default_city', valOf('s-default-city', '')],
    ['city_lat', valOf('s-city-lat', '')],
    ['city_lon', valOf('s-city-lon', '')],
    ['motto', valOf('s-motto', '')]
  ];
  var i = 0;
  function next() {
    if (i >= pairs.length) {
      toast('✅ 个人信息已保存', 'success');
      // 刷新侧栏
      var nm = pairs[0][1] || '刘老师';
      STATE.userName = nm;
      var sbn = document.getElementById('sidebar-teacher-name');
      if (sbn) sbn.textContent = nm;
      if (STATE.currentPage === 'home') {
        var g = document.getElementById('greetTitle');
        if (g) g.textContent = greetByHour(nm);
      }
      return;
    }
    var p = pairs[i++];
    api('/settings', {
      method: 'PUT',
      body: JSON.stringify({ key: p[0], value: p[1] })
    }).then(next).catch(function () { next(); });
  }
  next();
}

function saveAIKeys() {
  var dk = document.getElementById('s-deepseek-key').value || '';
  var ok = document.getElementById('s-openai-key').value || '';
  var zk = document.getElementById('s-zhipu-key').value || '';
  var dsk = document.getElementById('s-dashscope-key') ? (document.getElementById('s-dashscope-key').value || '') : '';
  var queue = [];
  // DeepSeek Key：两种命名都支持（先存 deepseek_api_key，再存 openai_api_key 给兼容实现）
  if (dk) {
    queue.push(['deepseek_api_key', dk]);
    queue.push(['openai_api_key', dk]);
  }
  if (ok) queue.push(['openai_api_key', ok]);
  if (zk) queue.push(['zhipu_api_key', zk]);
  if (dsk) {
    queue.push(['dashscope_api_key', dsk]);
    queue.push(['qwen_api_key', dsk]);
  }
  if (queue.length === 0) {
    toast('本次未修改任何 Key（密码框保持空代表不更改）', 'warn');
    return;
  }
  var i = 0;
  function next() {
    if (i >= queue.length) {
      toast('✅ API Key 已保存', 'success');
      // 清空密码框
      setVal('s-deepseek-key', '');
      setVal('s-openai-key', '');
      setVal('s-zhipu-key', '');
      setVal('s-dashscope-key', '');
      return;
    }
    var p = queue[i++];
    api('/settings', {
      method: 'PUT',
      body: JSON.stringify({ key: p[0], value: p[1] })
    }).then(next).catch(function () { next(); });
  }
  next();
}

function testLLM(provider, btn) {
  var origTxt = btn.textContent;
  btn.textContent = '测试中…';
  btn.disabled = true;
  var t0 = Date.now();
  api('/settings/test-llm', {
    method: 'POST',
    body: JSON.stringify({ provider: provider })
  }).then(function (r) {
    var dt = (r && r.latency_ms) ? r.latency_ms : (Date.now() - t0);
    if (r && r.success) {
      toast('✅ ' + provider + ' 连通成功，耗时 ' + dt + 'ms', 'success');
    } else {
      toast('❌ ' + provider + ' 失败：' + (r ? (r.error || '未知错误') : '无响应'), 'error');
    }
  }).catch(function () {
    // 已有 toast
  }).then(function () {
    btn.textContent = origTxt;
    btn.disabled = false;
  });
}

function rebuildKb() {
  if (!confirm('确认重建向量库？会对所有 ready 文档重新分块 & Embedding，可能耗时较长。')) return;
  var pg = document.getElementById('kbProgress');
  var pb = document.getElementById('kbProgressBar');
  var pt = document.getElementById('kbProgressText');
  if (pg) pg.classList.remove('hidden');
  if (pb) pb.style.width = '10%';
  if (pt) pt.textContent = '正在分块 & Embedding（请耐心等待）…';
  var anim = setInterval(function () {
    if (!pb) return;
    var cur = parseFloat(pb.style.width || '0');
    if (cur < 88) pb.style.width = (cur + 1.8) + '%';
  }, 300);
  var t0 = Date.now();
  api('/settings/rebuild-kb', { method: 'POST' }).then(function (r) {
    clearInterval(anim);
    if (pb) pb.style.width = '100%';
    var ms = Date.now() - t0;
    if (pt) pt.textContent = '✅ 完成，' + ms + 'ms · 处理文档 ' + (r ? r.docs_processed || 0 : 0) + ' · 总 chunks ' + (r ? r.total_chunks || 0 : 0);
    toast('向量库重建完成', 'success');
    setTimeout(function () { if (pg) pg.classList.add('hidden'); }, 2500);
    loadDocuments();
    refreshAbout();
  }).catch(function () {
    clearInterval(anim);
    if (pt) pt.textContent = '❌ 失败（详情见控制台）';
    setTimeout(function () { if (pg) pg.classList.add('hidden'); }, 2500);
  });
}

function exportData() {
  toast('开始导出…', 'info');
  var url = API_BASE + '/settings/export-data';
  fetch(url).then(function (resp) {
    if (resp.status < 200 || resp.status >= 300) throw new Error('HTTP ' + resp.status);
    return resp.json();
  }).then(function (obj) {
    var blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    var d = new Date();
    var fmt = d.getFullYear() + '-' + (d.getMonth()+1) + '-' + d.getDate();
    a.download = '教研助手数据导出_' + fmt + '.json';
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    toast('✅ 导出成功', 'success');
  }).catch(function (e) {
    toast('导出失败：' + (e.message || '未知错误'), 'error');
  });
}

function refreshAbout() {
  var vEl = document.getElementById('about-version');
  var hEl = document.getElementById('about-health');
  var lEl = document.getElementById('about-has-llm');
  var eEl = document.getElementById('about-has-embed');
  var cEl = document.getElementById('about-kb-chunks');
  var dEl = document.getElementById('about-kb-docs');
  var dimEl = document.getElementById('about-kb-dim');
  Promise.all([
    api('/health').catch(function () { return null; }),
    api('/stats').catch(function () { return null; })
  ]).then(function (r) {
    var h = r[0] || {};
    var st = r[1] || {};
    if (vEl) vEl.textContent = h.version || '--';
    if (hEl) {
      hEl.textContent = '✅ 正常';
      hEl.className = 'ok';
    }
    if (lEl) {
      var okL = h.has_llm_key ? true : false;
      lEl.textContent = okL ? '是 ✅' : '否 ❌';
      lEl.className = okL ? 'ok' : 'no';
    }
    if (eEl) {
      var okE = h.has_embed_key ? true : false;
      eEl.textContent = okE ? '是 ✅' : '否 ❌';
      eEl.className = okE ? 'ok' : 'no';
    }
    var vs = h.vector_stats || {};
    if (cEl) cEl.textContent = (_def(st.kb_vector_chunks, 0)) + ' 条';
    if (dEl) dEl.textContent = (_def(st.doc_ready, 0)) + ' / ' + (_def(st.doc_count, 0)) + ' 份';
    if (dimEl) dimEl.textContent = _def(vs.embedding_dim, st.embedding_dim || '--') + ' 维';
  }).catch(function () {
    if (hEl) { hEl.textContent = '❌ 未连通'; hEl.className = 'err'; }
  });
}

/* ============================================================
 * 14. 全局搜索
 * ============================================================ */
function bindGlobalSearch() {
  var input = document.getElementById('globalSearch');
  if (!input) return;
  input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') {
      var q = (input.value || '').trim();
      if (!q) { toast('请输入搜索关键词', 'warn'); return; }
      runGlobalSearch(q);
    }
  });
}

function runGlobalSearch(q) {
  var body = document.getElementById('searchResultBody');
  if (body) body.innerHTML = '<p class="empty-state small">正在知识库检索：<b>' + escapeHtml(q) + '</b> …</p>';
  openModal('search-modal');
  api('/knowledge/search', {
    method: 'POST',
    body: JSON.stringify({ query: q, top_k: 8 })
  }).then(function (r) {
    var list = r ? (r.chunks || []) : [];
    if (!list.length) {
      body.innerHTML = '<p class="empty-state small">未找到与「' + escapeHtml(q) + '」匹配的知识库片段。</p>';
      return;
    }
    var html = '';
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var meta = c.metadata || c.meta || {};
      var name = meta.doc_name || c.doc_name || c.source || '未知文档';
      var idx = meta.chunk_index != null ? meta.chunk_index : (c.chunk_index != null ? c.chunk_index : '');
      var cat = meta.category || c.category || '';
      var score = c.distance != null ? (Number(c.distance).toFixed(4)) : (c.score != null ? Number(c.score).toFixed(4) : '--');
      var text = c.text || c.page_content || c.content || '';
      if (text.length > 260) text = text.substring(0, 260) + '…';
      html += '<div class="search-result-item">' +
        '<div class="sr-top">' +
          '<span class="sr-name">' + escapeHtml(name) + (idx !== '' ? (' · 片段 ' + idx) : '') +
          (cat ? (' · ' + escapeHtml(cat)) : '') + '</span>' +
          '<span class="sr-score">距离 ' + escapeHtml(String(score)) + '</span>' +
        '</div>' +
        '<div class="sr-text">' + escapeHtml(text) + '</div>' +
      '</div>';
    }
    body.innerHTML = html;
  }).catch(function () {
    if (body) body.innerHTML = '<p class="empty-state small">搜索失败。</p>';
  });
}

/* ============================================================
 * 15. 绑定 Entry 点击 & 初始化
 * ============================================================ */
function bindEntryClicks() {
  var entries = document.querySelectorAll('.entry');
  for (var i = 0; i < entries.length; i++) {
    entries[i].addEventListener('click', function () {
      var g = this.getAttribute('data-go');
      if (g) navigateTo(g);
    });
  }
}

function initCalendarDefaults() {
  var d = new Date();
  STATE.calendar.year = d.getFullYear();
  STATE.calendar.month = d.getMonth() + 1;
  STATE.calendar.selected = fmtISODate(d);
}

window.addEventListener('DOMContentLoaded', function () {
  // API_BASE 已经在文件开头定义
  // 绑定侧栏导航
  var navItems = document.querySelectorAll('.nav-item');
  for (var i = 0; i < navItems.length; i++) {
    navItems[i].addEventListener('click', function () {
      var p = this.getAttribute('data-page');
      if (p) navigateTo(p);
    });
  }

  // 入口卡片
  bindEntryClicks();
  // Modal 关闭
  bindModalMaskClose();
  // 各模块绑定 UI
  bindInboxTabs();
  bindReadingUI();
  bindScheduleUI();
  bindAssistantUI();
  bindToolsUI();
  bindSettingsUI();
  bindGlobalSearch();

  // 日历默认值
  initCalendarDefaults();

  // 应用国风 SVG 图标（替换所有 emoji）
  applyGuoIcons();

  // Token 追踪：初始加载 + 每30秒刷新
  refreshTokenBadge();
  setInterval(refreshTokenBadge, 30 * 1000);

  // 暴露给 HTML inline 调用
  window.refreshWeather = refreshWeather;

  // 启动
  navigateTo('home');

  // ====== 后台守护任务（页面一直开着也会自动更新）======
  // 1) 每分钟检查问候时段（过了12点自动 早上好→中午好；过18点→晚上好；23点后→夜深了）
  refreshGreetingIfNeeded(true);
  setInterval(function () { refreshGreetingIfNeeded(false); }, 60 * 1000);

  // 2) 每 30 分钟自动刷新一次天气缓存（顺带换一句诗）
  setInterval(function () {
    try {
      if (typeof refreshWeather === 'function') refreshWeather();
    } catch (e) {}
  }, 30 * 60 * 1000);
});
