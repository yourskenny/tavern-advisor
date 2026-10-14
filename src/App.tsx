import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, ArrowLeft, ArrowRight, Check, ChevronRight, Coins, Download, FileUp, Heart, History, LayoutDashboard, Plug, RefreshCw, Shield, Sparkles, Swords, TriangleAlert, X } from 'lucide-react';
import type { Advice, Card, Payload, Settings, Snapshot } from './types';

const sources = { live: '实时', demo: '演练', import: '日志导入' };
const phases = { recruit: '招募阶段', combat: '战斗阶段', ended: '对局结束', unknown: '阶段未知' };
const races: Record<string, string> = { BEAST: '野兽', DEMON: '恶魔', DRAGON: '龙', ELEMENTAL: '元素', MECHANICAL: '机械', MURLOC: '鱼人', NAGA: '纳迦', PIRATE: '海盗', QUILBOAR: '野猪人', UNDEAD: '亡灵', ALL: '全部' };

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, { method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `请求失败 (${response.status})`);
  }
  return response.json();
}

function CardTile({ card, highlighted = false }: { card: Card; highlighted?: boolean }) {
  const [failed, setFailed] = useState(false);
  const description = card.text.replace(/<[^>]+>/g, '').replace(/\[x\]/g, '');
  return <article className={`minion ${highlighted ? 'highlighted' : ''}`}>
    <div className="art">
      {!failed && !card.card_id.startsWith('DEMO_') ? <img src={`https://art.hearthstonejson.com/v1/tiles/${encodeURIComponent(card.card_id)}.png`} alt={card.name} onError={() => setFailed(true)} /> : <Swords size={28} />}
      <span className="tier-token" title="酒馆等级">{card.tier ?? '?'}</span>
      {card.cost !== null && <span className="price"><Coins size={12} />{card.cost}</span>}
    </div>
    <div className="minion-body"><h3>{card.name}</h3><div className="card-meta"><span>{card.races.map(r => races[r] ?? r).join(' / ') || '无种族'}</span><b><span className="attack">{card.attack ?? '?'}</span><span className="stat-divider">/</span><span className="health">{card.health ?? '?'}</span></b></div>
      <p title={description}>{description || '无额外效果'}</p>
    </div>
  </article>;
}

function CardSection({ title, cards, limit, advice, empty }: { title: string; cards: Card[]; limit?: number; advice: Advice[]; empty: string }) {
  return <section className="card-section"><div className="section-heading"><h2>{title}</h2><span>{cards.length}{limit ? ` / ${limit}` : ''}</span></div>
    {cards.length ? <div className="minion-grid">{cards.map(card => <CardTile key={`${card.entity_id}-${card.card_id}`} card={card} highlighted={advice.some(a => a.entity_id === card.entity_id)} />)}</div> : <div className="empty-row">{empty}</div>}
  </section>;
}

export default function App() {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [tab, setTab] = useState<'board' | 'history' | 'connection'>('board');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [selected, setSelected] = useState<{ snapshot: Snapshot; advice: Advice[] } | null>(null);
  const [logPath, setLogPath] = useState('');
  const [playerId, setPlayerId] = useState('');
  const [saved, setSaved] = useState(false);
  const upload = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => { setPayload(await request<Payload>('state')); }, []);
  useEffect(() => {
    let disposed = false;
    let running = false;
    const poll = async () => {
      if (running) return;
      running = true;
      try { const next = await request<Payload>('state'); if (!disposed) setPayload(next); }
      catch { if (!disposed) setError('本地服务未连接，请检查后端进程。'); }
      finally { running = false; }
    };
    void poll();
    const timer = setInterval(poll, 1500);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!payload) return;
    setLogPath(payload.settings.log_path);
    setPlayerId(payload.settings.player_id?.toString() ?? '');
  }, [payload?.settings.log_path, payload?.settings.player_id]);
  useEffect(() => {
    if (tab === 'history') void request<Snapshot[]>('history').then(setHistory).catch(e => setError(e.message));
  }, [tab, payload?.snapshot?.id]);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError(''); setSaved(false);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  async function changeSettings(patch: Partial<Settings>) {
    if (!payload) return;
    await perform(async () => { setPayload(await request<Payload>('settings', 'PUT', { ...payload.settings, ...patch })); setSelected(null); });
  }
  async function importFile(file: File) {
    await perform(async () => {
      if (file.size > 20_000_000) throw new Error('日志超过 20 MB，请先截取包含完整 CREATE_GAME 的对局。');
      const result = await request<{ snapshot: Snapshot; advice: Advice[] }>('import', 'POST', { text: await file.text(), player_id: playerId ? Number(playerId) : null });
      setSelected(result); setTab('board');
    });
  }
  const state = selected?.snapshot ?? payload?.snapshot;
  const advice = selected?.advice ?? payload?.advice ?? [];
  const mode = payload?.settings.mode ?? 'live';
  const connectionText = mode === 'demo' ? '演练中' : ({ connected: '日志已连接', waiting: '等待日志', waiting_game: '等待完整对局', error: '读取异常', stale: '等待日志更新' }[payload?.status ?? 'waiting'] ?? '等待日志');
  const current = state ? sources[state.source] : sources[mode];

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><Swords size={24} /><span>酒馆<span className="brand-sub">决策工作台</span></span></div>
      <nav aria-label="主导航">
        {([{ id: 'board', label: '当前局面', icon: LayoutDashboard }, { id: 'history', label: '局面历史', icon: History }, { id: 'connection', label: '日志连接', icon: Plug }] as const).map(item => <button key={item.id} aria-label={item.label} title={item.label} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}><item.icon size={18} /><span>{item.label}</span>{tab === item.id && <ChevronRight size={14} />}</button>)}
      </nav>
      <div className="sidebar-bottom"><span className="version">LOCAL / v0.1</span><span className="side-status"><span className={`dot ${payload?.status === 'connected' ? 'connected' : ''}`} />{connectionText}</span></div>
    </aside>
    <main>
      <header className="topbar"><div><div className="eyebrow">BATTLEGROUNDS</div><h1>酒馆决策助手</h1></div><div className="top-controls"><div className="segmented" aria-label="数据来源">{(['live', 'demo'] as const).map(m => <button key={m} aria-pressed={mode === m} disabled={busy || !payload} className={mode === m ? 'selected' : ''} onClick={() => void changeSettings({ mode: m })}>{sources[m]}</button>)}</div><button className="icon-button" title="刷新状态" aria-label="刷新状态" disabled={busy} onClick={() => void perform(refresh)}><RefreshCw size={18} /></button></div></header>
      {error && <div role="alert" className="error-banner"><TriangleAlert size={16} /><span>{error}</span><button aria-label="关闭错误" onClick={() => setError('')}><X size={16} /></button></div>}
      <div className="content">
        {tab === 'board' && <>
          <div className="workspace-heading"><div className="heading-left"><span className={`source-label ${current === '演练' ? 'demo' : ''}`}>{current}</span>{selected && <span className="muted">历史快照</span>}<span>{state ? phases[state.phase] : '尚无对局'}</span>{state?.turn != null && <span className="muted">TURN {state.turn}</span>}</div><div className="heading-actions">{selected ? <button className="text-button" onClick={() => setSelected(null)}><ArrowLeft size={15} />返回当前局面</button> : mode === 'demo' && <button className="text-button" disabled={busy} onClick={() => void perform(async () => { setPayload(await request<Payload>('demo/next', 'POST')); })}>下一演练局面<ArrowRight size={15} /></button>}</div></div>
          <div className="metrics"><div className="hero-metric"><span className="metric-label">英雄</span><strong>{state?.hero ?? '等待对局'}</strong></div><div><span className="metric-label"><Heart size={14} />生命</span><strong className="red">{state?.health ?? '--'}<small> / 护甲 {state?.armor ?? '--'}</small></strong></div><div><span className="metric-label"><Coins size={14} />可用金币</span><strong className="gold">{state?.gold ?? '--'}</strong></div><div><span className="metric-label"><Shield size={14} />酒馆等级</span><strong>{state?.tier ?? '--'}</strong></div></div>
          <div className="workspace-grid"><div className="board-area">
            <CardSection title="我的战场" cards={state?.board ?? []} limit={7} advice={advice} empty={state ? '暂无已确认的场上随从' : '等待对局状态'} />
            <CardSection title="酒馆商店" cards={state?.shop ?? []} advice={advice} empty={state?.phase === 'combat' ? '战斗阶段' : '商店内容尚未确认'} />
            <CardSection title="手牌" cards={state?.hand ?? []} limit={10} advice={advice} empty="暂无已确认的手牌" />
          </div><aside className="advice-area"><div className="section-heading"><h2><Sparkles size={16} />决策建议</h2><span>规则基线</span></div><div className="preference"><span>策略偏好</span><div className="segmented compact">{([{ value: 'balanced', text: '均衡' }, { value: 'survival', text: '保分' }] as const).map(p => <button key={p.value} aria-pressed={payload?.settings.preference === p.value} className={payload?.settings.preference === p.value ? 'selected' : ''} disabled={busy || !payload || !!selected} onClick={() => void changeSettings({ preference: p.value })}>{p.text}</button>)}</div></div>
            {advice.length ? <ol className="advice-list">{advice.map((a, i) => <li key={a.rule}><div className="advice-title"><span className="advice-index">0{i+1}</span><h3>{a.title}</h3></div><p>{a.reason}</p><div className="advice-footer"><span>{a.confidence}</span>{a.remaining_gold !== null && <span><Coins size={12} />余 {a.remaining_gold}</span>}</div></li>)}</ol> : <div className="advice-empty"><Activity size={27} /><h3>{state?.phase === 'combat' ? '等待下一招募阶段' : '等待可验证的局面'}</h3><span>{state ? '当前数据不足以生成操作建议' : connectionText}</span>{!state && <button className="primary-button" onClick={() => setTab('connection')}><Plug size={15} />连接日志</button>}</div>}
            <div className="simulation-status"><Swords size={16} /><span>战斗模拟</span><b>未接入</b></div>
          </aside></div>
          {(state?.warnings.length || payload?.error) ? <div className="observations"><div className="section-heading"><h2><TriangleAlert size={15} />局面校验</h2><span>{state?.warnings.length ?? 1} 项</span></div>{payload?.error && !selected && <p className="red">{payload.error}</p>}{state?.warnings.map(w => <p key={w}>{w}</p>)}</div> : null}
        </>}
        {tab === 'connection' && <div className="connection-page"><div className="page-heading"><h2>日志连接</h2><span className="source-label">{connectionText}</span></div><form onSubmit={event => { event.preventDefault(); void perform(async () => { if (!payload) return; await request<Payload>('settings', 'PUT', { ...payload.settings, mode: 'live', log_path: logPath.trim(), player_id: playerId ? Number(playerId) : null }); setPayload(await request<Payload>('reconnect', 'POST')); setSelected(null); setSaved(true); }); }}>
          <label htmlFor="log-path">Power.log 文件或 Logs 文件夹</label><div className="path-control"><input id="log-path" value={logPath} onChange={e => { setLogPath(e.target.value); setSaved(false); }} placeholder="D:\Games\Hearthstone\Logs" autoComplete="off" /><button type="submit" className="primary-button" disabled={busy || !payload || !logPath.trim()}>{saved ? <Check size={16} /> : <Plug size={16} />}{saved ? '已保存' : '连接'}</button></div>
          <label htmlFor="player-id">友方玩家编号</label><select id="player-id" value={playerId} onChange={e => setPlayerId(e.target.value)}><option value="">自动识别</option>{Array.from({ length: 16 }, (_, i) => <option key={i} value={i+1}>玩家 {i+1}</option>)}</select>
        </form><dl className="connection-details"><div><dt>当前日志</dt><dd>{payload?.active_log ?? '未连接'}</dd></div><div><dt>卡牌数据</dt><dd>{payload?.catalog.count ? `${payload.catalog.count.toLocaleString()} 条 · build ${payload.catalog.build}` : '未同步'}</dd></div><div><dt>启用卡池</dt><dd>待验证</dd></div><div><dt>解析器</dt><dd>HearthSim / hslog 1.20.0</dd></div><div><dt>实时适配</dt><dd>待实局验证</dd></div></dl><section className="import-section"><h2>历史日志</h2><button className="text-button bordered" disabled={busy} onClick={() => upload.current?.click()}><FileUp size={16} />导入 Power.log</button></section></div>}
        {tab === 'history' && <div className="history-page"><div className="page-heading"><h2>局面历史</h2><div className="heading-actions"><button className="icon-button" title="刷新历史" aria-label="刷新历史" disabled={busy} onClick={() => void perform(async () => setHistory(await request<Snapshot[]>('history')))}><RefreshCw size={17} /></button><a className="icon-button" title="导出历史 JSON" aria-label="导出历史 JSON" href="/api/export" download="tavern-history.json"><Download size={17} /></a></div></div>{history.length ? <div className="table-wrap"><table><thead><tr><th>记录时间</th><th>来源</th><th>阶段</th><th>金币</th><th>场上</th><th></th></tr></thead><tbody>{history.map(s => <tr key={s.id}><td>{new Date(s.observed_at).toLocaleString('zh-CN', { timeZone: 'Asia/Hong_Kong', hour12: false })}</td><td><span className={`source-label ${s.source === 'demo' ? 'demo' : ''}`}>{sources[s.source]}</span></td><td>{phases[s.phase]}</td><td>{s.gold ?? '--'}</td><td>{s.board.length} / 7</td><td><button className="icon-button" title="查看局面" aria-label="查看局面" onClick={() => void perform(async () => { setSelected(await request(`history/${s.id}`)); setTab('board'); })}><ChevronRight size={17} /></button></td></tr>)}</tbody></table></div> : <div className="history-empty"><History size={32} /><h3>暂无局面记录</h3></div>}</div>}
      </div>
      <footer><span><span className={`dot ${mode === 'demo' ? 'demo-dot' : payload?.status === 'connected' ? 'connected' : ''}`} />{connectionText}</span><span>{busy ? '正在处理…' : state ? `最近快照 ${new Date(state.observed_at).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Hong_Kong', hour12: false })}` : '本地存储'}<span className="footer-divider">/</span>v0.1</span></footer>
    </main><input ref={upload} type="file" accept=".log,.txt" hidden onChange={e => { const file = e.target.files?.[0]; if (file) void importFile(file); e.target.value = ''; }} />
  </div>;
}
