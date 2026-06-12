'use strict';

let weightChart = null;
let selectedCalorieDate = todayStr();
let lastCalorieData = null;

// ── ユーティリティ ────────────────────────────────────────────────────────────

function todayStr() {
  // 日本時間（UTC+9）で今日の日付を返す
  const jst = new Date(Date.now() + 9 * 60 * 60 * 1000);
  return jst.toISOString().split('T')[0];
}

async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(url, opts);
    if (res.status === 401) { showAuthScreen(); return null; }
    return res;
  } catch {
    showToast('サーバーに接続できません', 'danger');
    return null;
  }
}

function showToast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

function showAuthScreen() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

function showAppScreen() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
}

function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  const section = document.getElementById(`tab-${name}`);
  if (section) section.classList.remove('hidden');
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (btn) btn.classList.add('active');

  if (name === 'dashboard') loadDashboard();
  else if (name === 'weight')    loadWeight();
  else if (name === 'calorie')   loadCalories(selectedCalorieDate);
  else if (name === 'analysis')  loadAnalysis();
  else if (name === 'history')   loadHistory();
  else if (name === 'settings')  loadSettings();
}

// ── 認証 ──────────────────────────────────────────────────────────────────────

async function checkAuth() {
  const res = await fetch('/api/auth/status', { credentials: 'include' });
  const data = await res.json();
  if (data.authenticated) {
    showAppScreen();
    showTab('dashboard');
  } else {
    showAuthScreen();
  }
}

async function login(email, password) {
  const res = await api('/api/auth/login', 'POST', { email, password });
  if (!res) return '接続エラー';
  const data = await res.json();
  if (res.ok) { showAppScreen(); showTab('dashboard'); return null; }
  return data.error;
}

async function register(email, password, inviteCode) {
  const res = await api('/api/auth/register', 'POST', { email, password, invite_code: inviteCode });
  if (!res) return '接続エラー';
  const data = await res.json();
  if (res.ok) { showAppScreen(); showTab('dashboard'); return null; }
  return data.error;
}

async function logout() {
  await api('/api/auth/logout', 'POST');
  showAuthScreen();
}

// ── ダッシュボード ────────────────────────────────────────────────────────────

async function loadDashboard() {
  const res = await api('/api/dashboard');
  if (!res) return;
  const d = await res.json();

  // 今日の体重
  const wCard = document.getElementById('today-weight-card');
  if (d.today_weight != null) {
    wCard.innerHTML = `
      <div class="card-label">今日の体重</div>
      <div class="card-value">${d.today_weight.toFixed(1)}<span class="card-unit"> kg</span></div>
      <div class="card-sub">目標まで あと ${d.weight_remaining.toFixed(1)} kg</div>`;
  } else {
    wCard.innerHTML = `
      <div class="card-label">今日の体重</div>
      <div class="card-value text-muted" style="font-size:18px">未記録</div>
      <button class="btn-primary" style="margin-top:10px;padding:8px" onclick="showTab('weight')">記録する</button>`;
  }

  // 残り日数
  document.getElementById('days-remaining-card').innerHTML = `
    <div class="card-label">残り日数</div>
    <div class="card-value">${d.days_remaining}<span class="card-unit"> 日</span></div>
    <div class="card-sub">${d.target_date} まで</div>`;

  // ペース
  const statusMap = {
    on_track:       { label: '順調',     cls: 'text-success' },
    slightly_behind:{ label: 'やや遅れ', cls: 'text-warning' },
    behind:         { label: '遅れ気味', cls: 'text-danger'  },
    no_data:        { label: '記録待ち', cls: 'text-muted'   },
  };
  const st = statusMap[d.pace_status] || statusMap.no_data;
  document.getElementById('pace-card').innerHTML = `
    <div class="card-label">ペース</div>
    <div class="card-value ${st.cls}" style="font-size:20px">${st.label}</div>
    <div class="card-sub">
      必要: ${d.required_pace_per_week} kg/週<br>
      実績: ${d.actual_pace_per_week} kg/週
    </div>`;

  // カロリー
  const remaining = d.calorie_remaining;
  const calCls = remaining < 0 ? 'text-danger' : remaining < 200 ? 'text-warning' : 'text-success';
  document.getElementById('calorie-card').innerHTML = `
    <div class="card-label">今日のカロリー残り</div>
    <div class="card-value ${calCls}">${remaining}<span class="card-unit"> kcal</span></div>
    <div class="card-sub">摂取: ${d.calorie_intake} / 推奨: ${d.recommended_intake} kcal</div>`;
}

// ── 体重タブ ──────────────────────────────────────────────────────────────────

async function loadWeight() {
  const [weightRes, profileRes] = await Promise.all([api('/api/weight'), api('/api/profile')]);
  if (!weightRes || !profileRes) return;
  const logs = await weightRes.json();
  const profile = await profileRes.json();
  renderWeightChart(logs, profile);
  renderWeightTable(logs);
}

function generateDateRange(startStr, endStr) {
  const dates = [];
  const end = new Date(endStr);
  const cur = new Date(startStr);
  while (cur <= end) {
    dates.push(cur.toISOString().split('T')[0]);
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

function renderWeightChart(logs, profile) {
  const ctx = document.getElementById('weight-chart').getContext('2d');
  if (weightChart) { weightChart.destroy(); weightChart = null; }
  if (logs.length === 0) return;

  const firstDate = new Date(logs[0].date);
  const targetDateStr = profile.target_date;        // '2026-08-11'
  const targetDate   = new Date(targetDateStr);
  const startWeight  = logs[0].weight;              // 最初の記録体重
  const targetWeight = profile.target_weight;       // 54.0

  // X軸: 最初の記録日〜目標日
  const allLabels = generateDateRange(logs[0].date, targetDateStr);

  // 実績体重（将来日付は null）
  const weightMap = Object.fromEntries(logs.map(l => [l.date, l.weight]));
  const actualData = allLabels.map(d => weightMap[d] ?? null);

  // 目標ライン（最初の記録体重 → 目標体重・目標日）
  const goalData = allLabels.map(d => {
    const cur = new Date(d);
    const ratio = (cur - firstDate) / (targetDate - firstDate);
    return parseFloat((startWeight + (targetWeight - startWeight) * ratio).toFixed(2));
  });

  // トレンドライン（実績データで線形回帰 → 目標日まで延長）
  let trendData = null;
  if (logs.length >= 2) {
    const xs = logs.map(l => (new Date(l.date) - firstDate) / 86400000);
    const ys = logs.map(l => l.weight);
    const n = xs.length;
    const sx = xs.reduce((a,b)=>a+b,0), sy = ys.reduce((a,b)=>a+b,0);
    const sxy = xs.reduce((a,x,i)=>a+x*ys[i],0);
    const sx2 = xs.reduce((a,x)=>a+x*x,0);
    const denom = n*sx2 - sx*sx;
    if (denom !== 0) {
      const slope = (n*sxy - sx*sy) / denom;
      const intercept = (sy - slope*sx) / n;
      trendData = allLabels.map(d => {
        const days = (new Date(d) - firstDate) / 86400000;
        return parseFloat((intercept + slope * days).toFixed(2));
      });
    }
  }

  const datasets = [
    {
      label: '実績体重',
      data: actualData,
      borderColor: '#4fc3f7',
      backgroundColor: 'rgba(79,195,247,0.08)',
      tension: 0.3,
      pointRadius: ctx => actualData[ctx.dataIndex] !== null ? 4 : 0,
      fill: true,
      spanGaps: false,
    },
    {
      label: '目標ライン',
      data: goalData,
      borderColor: '#f44336',
      borderDash: [6, 4],
      pointRadius: 0,
      borderWidth: 1.5,
      fill: false,
    },
  ];
  if (trendData) {
    datasets.push({
      label: '予測トレンド',
      data: trendData,
      borderColor: '#4caf50',
      borderDash: [4, 4],
      pointRadius: 0,
      borderWidth: 1.5,
      fill: false,
    });
  }

  weightChart = new Chart(ctx, {
    type: 'line',
    data: { labels: allLabels, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: '#9e9e9e', font: { size: 12 } } } },
      scales: {
        x: {
          ticks: { color: '#9e9e9e', font: { size: 11 }, maxTicksLimit: 6 },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          min: Math.floor(targetWeight) - 1,
          max: Math.ceil(startWeight) + 1,
          ticks: { color: '#9e9e9e', callback: v => v + 'kg' },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
      },
    },
  });
}

function renderWeightTable(logs) {
  const tbody = document.querySelector('#weight-table tbody');
  const emptyMsg = document.getElementById('weight-empty');
  tbody.innerHTML = '';
  if (logs.length === 0) { emptyMsg.classList.remove('hidden'); return; }
  emptyMsg.classList.add('hidden');

  const reversed = [...logs].reverse();
  reversed.forEach((log, i) => {
    const prev = reversed[i + 1];
    let diffHtml = '<span class="text-muted">-</span>';
    if (prev) {
      const diff = log.weight - prev.weight;
      const sign = diff > 0 ? '+' : '';
      const cls = diff < 0 ? 'text-success' : diff > 0 ? 'text-danger' : 'text-muted';
      diffHtml = `<span class="${cls}">${sign}${diff.toFixed(1)}</span>`;
    }
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${log.date}</td>
      <td>${log.weight.toFixed(1)} kg</td>
      <td>${diffHtml}</td>
      <td><button class="btn-delete" onclick="deleteWeight(${log.id})">×</button></td>`;
    tbody.appendChild(tr);
  });
}

async function deleteWeight(id) {
  if (!confirm('この記録を削除しますか？')) return;
  const res = await api(`/api/weight/${id}`, 'DELETE');
  if (res && res.ok) { showToast('削除しました'); loadWeight(); }
}

// ── カロリータブ ──────────────────────────────────────────────────────────────

// 複数行の入力を1リクエストにまとめて送信する（並列POSTによるDBロック競合を回避）
async function submitBulkCalories(type, formSel, nameSel, calSel) {
  const rows = document.querySelectorAll(`${formSel} .bulk-input-row`);
  const items = [];
  rows.forEach(row => {
    const name     = row.querySelector(nameSel).value.trim();
    const calories = parseInt(row.querySelector(calSel).value);
    if (name && calories > 0) items.push({ type, name, calories });
  });
  if (!items.length) return;

  const res = await api('/api/calories/bulk', 'POST', { items, date: selectedCalorieDate });
  if (res && (res.ok || res.status === 201)) {
    document.querySelectorAll(`${formSel} ${nameSel}, ${formSel} ${calSel}`).forEach(i => i.value = '');
    showToast(`${items.length}件を追加しました`);
    loadCalories(selectedCalorieDate);
  } else {
    showToast('追加に失敗しました', 'danger');
  }
}

async function loadCalories(dateStr) {
  selectedCalorieDate = dateStr || todayStr();
  document.getElementById('calorie-date-input').value = selectedCalorieDate;

  const res = await api(`/api/calories/${selectedCalorieDate}`);
  if (!res) return;
  const data = await res.json();
  lastCalorieData = data;
  renderCalories(data);
}

function renderCalories(data) {
  const remaining = data.remaining;
  const remainCls = remaining < 0 ? 'text-danger' : remaining < 200 ? 'text-warning' : 'text-success';

  document.getElementById('calorie-summary').innerHTML = `
    <div class="calorie-row"><span>摂取カロリー</span><span>${data.total_intake} kcal</span></div>
    <div class="calorie-row"><span>消費（運動）</span><span>${data.total_burned > 0 ? '-' : ''}${data.total_burned} kcal</span></div>
    <div class="calorie-row">
      <span>基礎代謝（BMR）<span class="text-muted text-sm">※推奨摂取に織り込み済み</span></span>
      <span class="text-muted">${data.bmr ?? '--'} kcal/日</span>
    </div>
    <div class="calorie-row"><span>推奨摂取上限</span><span>${data.recommended_intake} kcal</span></div>
    <div class="calorie-row total">
      <span>残り予算</span>
      <span class="${remainCls}">${remaining} kcal</span>
    </div>`;

  renderCalorieList('meal-list', data.meals);
  renderCalorieList('exercise-list', data.exercises);
}

function escapeAttr(str) {
  return String(str).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderCalorieList(elementId, items) {
  const el = document.getElementById(elementId);
  if (!items.length) { el.innerHTML = '<p class="text-muted text-sm" style="margin-top:8px">記録なし</p>'; return; }
  el.innerHTML = items.map(item => `
    <div class="calorie-item" data-id="${item.id}" data-name="${escapeAttr(item.name)}" data-calories="${item.calories}">
      <span class="calorie-item-name">${escapeAttr(item.name)}</span>
      <span class="calorie-item-kcal">${item.calories} kcal</span>
      <button type="button" class="btn-edit" onclick="editCalorie(${item.id})">✎</button>
      <button type="button" class="btn-delete" onclick="deleteCalorie(${item.id})">×</button>
    </div>`).join('');
}

function editCalorie(id) {
  const item = document.querySelector(`.calorie-item[data-id="${id}"]`);
  if (!item) return;
  const name     = item.dataset.name;
  const calories = item.dataset.calories;
  item.classList.add('editing');
  item.innerHTML = `
    <input type="text"   class="edit-name" value="${escapeAttr(name)}">
    <input type="number" class="edit-cal"  value="${calories}" min="1" max="5000">
    <button type="button" class="btn-save-edit" onclick="saveCalorieEdit(${id})">✓</button>
    <button type="button" class="btn-cancel-edit" onclick="loadCalories(selectedCalorieDate)">取消</button>`;
  item.querySelector('.edit-name').focus();
}

async function saveCalorieEdit(id) {
  const item     = document.querySelector(`.calorie-item[data-id="${id}"]`);
  const name     = item.querySelector('.edit-name').value.trim();
  const calories = parseInt(item.querySelector('.edit-cal').value);
  if (!name || !calories) return;
  const res = await api(`/api/calories/${id}`, 'PUT', { name, calories });
  if (res && res.ok) loadCalories(selectedCalorieDate);
}

async function deleteCalorie(id) {
  const res = await api(`/api/calories/${id}`, 'DELETE');
  if (res && res.ok) loadCalories(selectedCalorieDate);
}

// ── 予測・分析タブ ────────────────────────────────────────────────────────────

async function loadAnalysis() {
  const res = await api('/api/analysis');
  if (!res) return;
  const data = await res.json();
  const el = document.getElementById('analysis-content');

  if (!data.has_data) {
    el.innerHTML = `<p class="text-muted">${data.error}</p>`;
    return;
  }

  const paceSign = data.slope_per_week < 0 ? '' : '+';
  const paceCls  = data.slope_per_week < 0 ? 'text-success' : 'text-danger';
  const goalCls  = data.will_reach_goal ? 'text-success' : 'text-danger';
  const goalMsg  = data.will_reach_goal ? '達成見込み' : '要ペースアップ';

  el.innerHTML = `
    <h3 style="margin-bottom:4px">予測レポート</h3>
    <p class="text-muted text-sm" style="margin-bottom:16px">${data.data_points}件の記録から算出</p>

    <div class="analysis-grid">
      <div>
        <div class="analysis-label">現在の減量ペース</div>
        <div class="analysis-value ${paceCls}">${paceSign}${data.slope_per_week} kg/週</div>
      </div>
      <div>
        <div class="analysis-label">目標到達予測日</div>
        <div class="analysis-value">${data.predicted_goal_date || '予測不可'}</div>
      </div>
      <div>
        <div class="analysis-label">目標日(${data.target_date})の予測体重</div>
        <div class="analysis-value ${goalCls}">${data.predicted_weight_at_target} kg</div>
      </div>
      <div>
        <div class="analysis-label">判定</div>
        <div class="analysis-value ${goalCls}">${goalMsg}</div>
      </div>
    </div>

    <hr>
    <h4>カロリー目安（現在の体重基準）</h4>
    <div class="analysis-grid">
      <div>
        <div class="analysis-label">基礎代謝（BMR）</div>
        <div class="analysis-value">${data.bmr} kcal</div>
      </div>
      <div>
        <div class="analysis-label">消費カロリー（TDEE）</div>
        <div class="analysis-value">${data.tdee} kcal</div>
      </div>
      <div>
        <div class="analysis-label">必要1日赤字</div>
        <div class="analysis-value">${data.required_deficit} kcal</div>
      </div>
      <div>
        <div class="analysis-label">推奨摂取カロリー</div>
        <div class="analysis-value text-accent">${data.recommended_intake} kcal</div>
      </div>
    </div>`;
}

// ── 履歴タブ ──────────────────────────────────────────────────────────────────

async function loadHistory() {
  const el = document.getElementById('history-content');
  el.innerHTML = '<p class="text-muted text-sm">読み込み中...</p>';
  const res = await api('/api/history');
  if (!res) { el.innerHTML = '<p class="text-muted text-sm">読み込めませんでした。通信状況を確認してください。</p>'; return; }
  if (!res.ok) { el.innerHTML = '<p class="text-danger text-sm">読み込みエラー（サーバー側で問題が発生しました）。</p>'; return; }

  let days;
  try {
    days = await res.json();
  } catch {
    el.innerHTML = '<p class="text-danger text-sm">データの解析に失敗しました。</p>';
    return;
  }

  if (days.length === 0) {
    el.innerHTML = '<p class="text-muted text-sm">記録がありません</p>';
    return;
  }

  el.innerHTML = days.map(day => {
    const net = day.total_intake - day.total_burned;
    const netCls = net > 2000 ? 'text-danger' : net > 1500 ? 'text-warning' : 'text-success';

    const mealRows = day.meals.map(m =>
      `<div class="history-item" data-id="${m.id}" data-name="${escapeAttr(m.name)}" data-calories="${m.calories}" data-max="5000">
        <span class="history-item-name">${escapeAttr(m.name)}</span>
        <span class="history-item-cal">${m.calories} kcal</span>
        <button type="button" class="btn-edit" onclick="editHistoryItem(${m.id})">✎</button>
        <button type="button" class="btn-delete" onclick="deleteHistoryItem(${m.id})">×</button>
      </div>`
    ).join('');

    const exRows = day.exercises.map(e =>
      `<div class="history-item" data-id="${e.id}" data-name="${escapeAttr(e.name)}" data-calories="${e.calories}" data-max="3000">
        <span class="history-item-name">${escapeAttr(e.name)}</span>
        <span class="history-item-cal text-success">-${e.calories} kcal</span>
        <button type="button" class="btn-edit" onclick="editHistoryItem(${e.id})">✎</button>
        <button type="button" class="btn-delete" onclick="deleteHistoryItem(${e.id})">×</button>
      </div>`
    ).join('');

    const mealSection = day.meals.length > 0
      ? `<div class="history-section"><div class="history-section-title">🍽 食事</div>${mealRows}</div>`
      : '';
    const exSection = day.exercises.length > 0
      ? `<div class="history-section"><div class="history-section-title">🏃 運動</div>${exRows}</div>`
      : '';

    return `
      <div class="card history-card">
        <div class="history-day-header">
          <div class="history-date">${day.date}</div>
          <div class="history-badges">
            <span class="history-badge">食 ${day.total_intake} kcal</span>
            ${day.total_burned > 0 ? `<span class="history-badge badge-exercise">運 -${day.total_burned} kcal</span>` : ''}
            <span class="history-badge ${netCls}">計 ${net} kcal</span>
          </div>
        </div>
        ${mealSection}${exSection}
      </div>`;
  }).join('');
}

function editHistoryItem(id) {
  const item = document.querySelector(`.history-item[data-id="${id}"]`);
  if (!item) return;
  const name     = item.dataset.name;
  const calories = item.dataset.calories;
  const max      = item.dataset.max || 5000;
  item.classList.add('editing');
  item.innerHTML = `
    <input type="text"   class="edit-name" value="${escapeAttr(name)}">
    <input type="number" class="edit-cal"  value="${calories}" min="1" max="${max}">
    <button type="button" class="btn-save-edit" onclick="saveHistoryEdit(${id})">✓</button>
    <button type="button" class="btn-cancel-edit" onclick="loadHistory()">取消</button>`;
  item.querySelector('.edit-name').focus();
}

async function saveHistoryEdit(id) {
  const item     = document.querySelector(`.history-item[data-id="${id}"]`);
  const name     = item.querySelector('.edit-name').value.trim();
  const calories = parseInt(item.querySelector('.edit-cal').value);
  if (!name || !calories) return;
  const res = await api(`/api/calories/${id}`, 'PUT', { name, calories });
  if (res && res.ok) { showToast('修正しました'); loadHistory(); }
}

async function deleteHistoryItem(id) {
  if (!confirm('この記録を削除しますか？')) return;
  const res = await api(`/api/calories/${id}`, 'DELETE');
  if (res && res.ok) { showToast('削除しました'); loadHistory(); }
}

// ── 設定タブ ──────────────────────────────────────────────────────────────────

async function loadSettings() {
  const res = await api('/api/profile');
  if (!res) return;
  const d = await res.json();
  document.getElementById('s-height').value       = d.height;
  document.getElementById('s-age').value          = d.age;
  document.getElementById('s-start-weight').value = d.start_weight;
  document.getElementById('s-target-weight').value= d.target_weight;
  document.getElementById('s-target-date').value  = d.target_date;
  document.getElementById('s-activity').value     = d.activity_level;
  loadInviteCodes();
}

// ── 招待コード管理 ────────────────────────────────────────────────────────────

async function loadInviteCodes() {
  const res = await api('/api/invite-codes');
  if (!res) return;
  const codes = await res.json();
  const el = document.getElementById('invite-code-list');
  if (codes.length === 0) {
    el.innerHTML = '<p class="text-muted text-sm">発行済みのコードはありません</p>';
    return;
  }
  el.innerHTML = codes.map(c => `
    <div class="invite-code-item ${c.used ? 'invite-used' : ''}">
      <span class="invite-code-str">${c.code}</span>
      <span class="invite-code-status ${c.used ? 'text-muted' : 'text-success'}">${c.used ? '使用済み' : '未使用'}</span>
      ${!c.used
        ? `<button class="btn-copy-code" onclick="copyInviteCode('${c.code}')">コピー</button>
           <button class="btn-delete" onclick="deleteInviteCode(${c.id})">×</button>`
        : ''}
    </div>`).join('');
}

async function generateInviteCode() {
  const res = await api('/api/invite-codes', 'POST');
  if (!res || !res.ok) { showToast('生成に失敗しました', 'danger'); return; }
  const data = await res.json();
  showToast(`発行しました: ${data.code}`, 'success');
  loadInviteCodes();
}

async function copyInviteCode(code) {
  try {
    await navigator.clipboard.writeText(code);
    showToast(`コピーしました: ${code}`, 'success');
  } catch {
    showToast('コピーに失敗しました', 'danger');
  }
}

async function deleteInviteCode(id) {
  if (!confirm('このコードを削除しますか？')) return;
  const res = await api(`/api/invite-codes/${id}`, 'DELETE');
  if (res && res.ok) { showToast('削除しました'); loadInviteCodes(); }
}

async function saveSettings(e) {
  e.preventDefault();
  const body = {
    height:        parseInt(document.getElementById('s-height').value),
    age:           parseInt(document.getElementById('s-age').value),
    start_weight:  parseFloat(document.getElementById('s-start-weight').value),
    target_weight: parseFloat(document.getElementById('s-target-weight').value),
    target_date:   document.getElementById('s-target-date').value,
    activity_level:document.getElementById('s-activity').value,
  };
  const res = await api('/api/profile', 'PUT', body);
  if (res && res.ok) showToast('設定を保存しました');
}

// ── Claudeモーダル ────────────────────────────────────────────────────────────

async function showClaudeModal(type) {
  const [dashRes, profileRes] = await Promise.all([api('/api/dashboard'), api('/api/profile')]);
  if (!dashRes || !profileRes) return;
  const dash    = await dashRes.json();
  const profile = await profileRes.json();

  const weight    = dash.current_weight?.toFixed(1) ?? '不明';
  const target    = profile.target_weight;
  const targetDate= profile.target_date;
  const remaining = dash.weight_remaining?.toFixed(1) ?? '不明';
  const days      = dash.days_remaining;
  const bmr       = lastCalorieData?.bmr ?? Math.round(10 * parseFloat(weight) + 6.25 * profile.height - 5 * profile.age + 5);
  const tdee      = lastCalorieData?.tdee ?? Math.round(bmr * 1.2);
  const recommended = dash.recommended_intake;

  const header = `【私のダイエット情報】
・身長: ${profile.height}cm / 年齢: ${profile.age}歳 / 性別: 男性
・現在体重: ${weight}kg → 目標: ${target}kg（${targetDate}まで、残り${days}日）
・残り減量: ${remaining}kg
・基礎代謝(BMR): ${bmr} kcal/日
・消費カロリー(TDEE): ${tdee} kcal/日
・推奨摂取カロリー: ${recommended} kcal/日`;

  let prompt;
  if (type === 'food') {
    document.getElementById('claude-modal-title').textContent = '食事カロリーをClaudeで確認';
    prompt = `${header}

【お願い】
以下の食事（または添付した写真の食事）のカロリーを教えてください。
食事名や内容を入力します → ここに食事名を書いてください

できれば以下も一緒に教えてください：
1. 推定カロリー（kcal）
2. 主な栄養素の概算（タンパク質・脂質・炭水化物）
3. 私の推奨摂取カロリー（${recommended} kcal）に対してこの食事をとるべきか一言アドバイス

※食事の写真があれば一緒に送ると精度が上がります。`;
  } else {
    document.getElementById('claude-modal-title').textContent = '運動カロリーをClaudeで確認';
    prompt = `${header}

【お願い】
以下の運動の消費カロリーを教えてください。
運動内容を入力します → ここに運動名・時間・強度を書いてください

できれば以下も一緒に教えてください：
1. 推定消費カロリー（kcal）
2. 私の体重（${weight}kg）基準の計算根拠
3. この運動の効果や注意点を一言`;
  }

  document.getElementById('claude-prompt-text').value = prompt;
  document.getElementById('claude-modal').classList.remove('hidden');
}

function closeClaudeModal() {
  document.getElementById('claude-modal').classList.add('hidden');
}

async function copyClaudePrompt() {
  const text = document.getElementById('claude-prompt-text').value;
  try {
    await navigator.clipboard.writeText(text);
    showToast('コピーしました', 'success');
  } catch {
    showToast('コピーに失敗しました', 'danger');
  }
}

// ── イベントリスナー登録 ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // 認証タブ切り替え
  document.querySelectorAll('.auth-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.auth-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
      document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
      document.getElementById('login-error').textContent = '';
      document.getElementById('register-error').textContent = '';
    });
  });

  // ログインフォーム
  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const err = await login(
      document.getElementById('login-email').value,
      document.getElementById('login-password').value
    );
    if (err) document.getElementById('login-error').textContent = err;
  });

  // 新規登録フォーム
  document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const err = await register(
      document.getElementById('reg-email').value,
      document.getElementById('reg-password').value,
      document.getElementById('reg-invite-code').value.trim().toUpperCase()
    );
    if (err) document.getElementById('register-error').textContent = err;
  });

  // ログアウト
  document.getElementById('logout-btn').addEventListener('click', logout);

  // アプリタブ
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });

  // 体重フォーム
  document.getElementById('weight-date').value = todayStr();
  document.getElementById('weight-form').addEventListener('submit', async e => {
    e.preventDefault();
    const weight = parseFloat(document.getElementById('weight-value').value);
    const date   = document.getElementById('weight-date').value;
    if (!weight || !date) return;
    const res = await api('/api/weight', 'POST', { weight, date });
    if (res && (res.ok || res.status === 201)) {
      document.getElementById('weight-value').value = '';
      showToast('体重を記録しました');
      loadWeight();
    }
  });

  // カロリー日付
  document.getElementById('calorie-date-input').value = todayStr();
  document.getElementById('calorie-date-input').addEventListener('change', e => {
    loadCalories(e.target.value);
  });

  // 食事フォーム（一括）
  document.getElementById('meal-form').addEventListener('submit', e => {
    e.preventDefault();
    submitBulkCalories('meal', '#meal-form', '.meal-name-input', '.meal-cal-input');
  });

  // 運動フォーム（一括）
  document.getElementById('exercise-form').addEventListener('submit', e => {
    e.preventDefault();
    submitBulkCalories('exercise', '#exercise-form', '.exercise-name-input', '.exercise-cal-input');
  });

  // 設定フォーム
  document.getElementById('settings-form').addEventListener('submit', saveSettings);

  // Claudeモーダルの背景クリックで閉じる
  document.getElementById('claude-modal').addEventListener('click', e => {
    if (e.target === document.getElementById('claude-modal')) closeClaudeModal();
  });

  // 起動時の認証チェック
  await checkAuth();
});
