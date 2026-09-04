"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const human = value => String(value ?? "").replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
const et = value => value ? new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(value)) : '—';
const money = value => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(value);
let demo, local = null, source = 'replay', scenario = 'entry', step = 0;
function view(){
  if(source === 'local_journal') return {events:local?.events||[],spread:null,model_source:local?.model_source};
  return {...demo.scenarios.find(s=>s.id===scenario),model_source:demo.model_source};
}
function selectScenario(id){if(!demo.scenarios.some(s=>s.id===id)) throw Error('Unknown replay scenario');source='replay';scenario=id;step=0;$('scenario').value=id;render();return {scenario,step,action:view().events[step]?.action};}
function payoff(spread){
 if(!spread){$('legs').innerHTML='';$('chart').innerHTML='<p class="empty">No selected spread in this journal record.<br>Open Replay to inspect a complete example.</p>';$('payoff-metrics').innerHTML='';$('expiry').textContent='No position assumed';return;}
 const a=spread.long,b=spread.short,k1=+a.strike,k2=+b.strike,debit=+a.quote.ask-+b.quote.bid,width=Math.abs(k2-k1),bull=a.kind==='call';
 $('expiry').textContent=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(a.expiry+'T12:00:00Z'));
 $('legs').innerHTML=`<div class="leg"><span class="leg-label">BUY TO OPEN · 1</span><strong>${esc(money(k1))} ${esc(a.kind)}</strong><span>Ask ${esc(money(+a.quote.ask))} · Δ ${esc(a.greeks.delta)}</span></div><div class="leg"><span class="leg-label sell">SELL TO OPEN · 1</span><strong>${esc(money(k2))} ${esc(b.kind)}</strong><span>Bid ${esc(money(+b.quote.bid))} · Δ ${esc(b.greeks.delta)}</span></div>`;
 const lo=Math.min(k1,k2)-6,hi=Math.max(k1,k2)+6,base=width*100,x=s=>55+(s-lo)/(hi-lo)*545,y=p=>125-p/base*135;
 const profit=s=>((bull?Math.max(s-k1,0)-Math.max(s-k2,0):Math.max(k1-s,0)-Math.max(k2-s,0))-debit)*100;
 const pts=[lo,Math.min(k1,k2),Math.max(k1,k2),hi],path=pts.map((s,i)=>`${i?'L':'M'} ${x(s)} ${y(profit(s))}`).join(' '),be=bull?k1+debit:k1-debit;
 $('chart').innerHTML=`<svg viewBox="0 0 650 245" role="img" aria-label="Theoretical expiration payoff. Maximum premium loss ${esc(money(debit*100))}; maximum profit before costs ${esc(money((width-debit)*100))}; breakeven ${esc(money(be))}."><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#b7ef6a" stop-opacity=".14"/><stop offset="100%" stop-color="#b7ef6a" stop-opacity="0"/></linearGradient></defs><path d="${path} L 600 205 L 55 205 Z" fill="url(#area)"/><line x1="55" x2="600" y1="125" y2="125" stroke="#425167" stroke-dasharray="4 5"/><text x="10" y="130">$0</text><path d="${path}" stroke="#b7ef6a" fill="none" stroke-width="3" stroke-linejoin="round"/><circle cx="${x(be)}" cy="125" r="4" fill="#b7ef6a"/><text x="${x(be)}" y="109" text-anchor="middle">${esc(money(be))}</text>${[Math.min(k1,k2),Math.max(k1,k2)].map(k=>`<line x1="${x(k)}" x2="${x(k)}" y1="35" y2="207" stroke="#354155" stroke-dasharray="3 5"/><text x="${x(k)}" y="233" text-anchor="middle">${esc(money(k))}</text>`).join('')}<text x="600" y="${y((width-debit)*100)-12}" text-anchor="end">+${esc(money((width-debit)*100))}</text><text x="55" y="${y(-debit*100)+23}">−${esc(money(debit*100))}</text></svg>`;
 $('payoff-metrics').innerHTML=`<div><span>Premium at risk</span><strong class="red">${esc(money(debit*100))}</strong></div><div><span>Max. profit at expiry</span><strong class="green">${esc(money((width-debit)*100))}</strong></div><div><span>Breakeven at expiry</span><strong>${esc(money(be))}</strong></div>`;
}
function render(){
 const replay=source==='replay',v=view(),events=v.events,idx=replay?Math.min(step,events.length-1):events.length-1,event=events[idx]||{},history=events.slice(0,idx+1),reasons=event.reasons||[],latestDecision=[...history].reverse().find(e=>e.decision),decision=event.decision||latestDecision?.decision;
 $('notice').textContent=replay?demo.notice:local.notice;$('notice').classList.remove('error');
 $('replay-tab').setAttribute('aria-pressed',String(replay));$('journal-tab').setAttribute('aria-pressed',String(!replay));$('replay-controls').hidden=!replay;
 $('action').textContent=human(event.action||'No records');$('action').className='status'+(event.action==='WAIT'?' wait':event.action==='ATTENTION'?' danger':'');
 $('decision-time').textContent=et(event.timestamp)+' ET';$('decision-kind').textContent=replay?'SPY bull call spread':'Actual agent journal';
 $('decision-copy').textContent=event.action==='WAIT'&&reasons[0]!=='model_abstained'?(reasons.map(human).join('. ')+'. No new order authorized.'):(decision?.reason||reasons.map(human).join('. ')||'No decision has been recorded yet.');
 $('invalidation').textContent=decision?.invalidation||'The agent needs current market, account, quote, and event-calendar checks before entry.';
 $('reason-tags').innerHTML=reasons.map(r=>`<span>${esc(human(r))}</span>`).join('');
 $('step-label').textContent=`Event ${idx+1} / ${events.length}`;$('previous').disabled=idx<=0;$('next').disabled=idx>=events.length-1;
 payoff(v.spread);
 const reached=!!latestDecision,blocked=reasons.includes('stale_or_future_option_quote'),marketClosed=reasons.includes('market_closed');
 const checks=[['Market session',marketClosed?'Closed':replay?'Open':'Not rechecked',marketClosed?'fail':replay?'':'unknown'],['Quote freshness',blocked?'VETO · 90 sec':replay?'3 sec · fresh':'Not rechecked',blocked?'fail':replay?'':'unknown'],['Entry premium',replay?'$200 / $300':'No new proposal',replay?'':'unknown'],['Calendar coverage',replay?'Fixture only':'Review required',replay?'unknown':'fail'],['Post-inference refresh',blocked?'Rejected':reached?'Checked':'Not reached',blocked?'fail':reached?'':'unknown']];
 $('risk-checks').innerHTML=checks.map(([label,value,cls])=>`<div class="risk-row"><span>${label}</span><span class="risk-value ${cls}">${value}</span></div>`).join('');$('gate-status').textContent=event.action==='WAIT'?'ENTRY BLOCKED':replay?'FIXTURE CHECKS':'READ ONLY';
 const actions=history.map(e=>e.action),life=[['Model proposal',reached],['Entry submitted',actions.includes('ENTRY_SUBMITTED')],['Position confirmed',actions.includes('HOLD')||actions.includes('EXIT_SUBMITTED')],['Exit submitted',actions.includes('EXIT_SUBMITTED')],['Flat confirmed',actions.includes('CLOSED')]];
 $('lifecycle').innerHTML=life.map(([title,done],i)=>`<li class="${done?'done':''}"><span class="life-dot">${done?'✓':i+1}</span><span class="life-title">${title}</span></li>`).join('');
 $('lifecycle-note').textContent=replay?'All broker transitions here are simulated. Actual paper fills remain unverified.':'Only recorded transitions are shown. Refresh does not query the broker or run the agent.';
 $('model-source').textContent=v.model_source||'No inference recorded';
 const ev=event.evidence?.evidence||latestDecision?.evidence?.evidence||[];
 $('evidence').innerHTML=ev.length?ev.map(e=>`<article class="evidence-item"><div class="evidence-meta"><span>${esc(e.id)}</span><span>${esc(e.source||'Supplied evidence')}</span><span>${esc(et(e.timestamp))} ET</span></div>${e.headline?`<p>${esc(e.headline)}</p>`:''}${e.return_5_bars!==undefined?`<div class="signal-values"><span>5-bar return<strong>${esc((e.return_5_bars*100).toFixed(2))}%</strong></span><span>20-bar return<strong>${esc((e.return_20_bars*100).toFixed(2))}%</strong></span></div>`:''}<p>${esc(e.note||'')}</p></article>`).join(''):'<p class="empty">No model evidence needed for this decision.<br>Deterministic checks stopped the cycle first.</p>';
 $('activity').innerHTML=history.length?[...history].reverse().map(e=>`<tr><td class="mono">${esc(et(e.timestamp))}</td><td>${esc(human(e.action))}</td><td>${esc((e.reasons||['Decision recorded']).map(human).join(' · '))}</td><td>${replay?'Synthetic replay':esc(human(e.mode||'Journal'))}</td></tr>`).join(''):'<tr><td colspan="4" class="empty">No journal records yet.</td></tr>';
 $('journal-caption').textContent=replay?`${history.length} replay events`:`${history.length} recent records · ${et(local.generated_at)} ET`;
}
async function refresh(){
 try{
  if(!demo){const response=await fetch('/demo.json');if(!response.ok)throw Error('Replay data unavailable');demo=await response.json();}
  if(location.hostname==='127.0.0.1'||location.hostname==='localhost'){
   const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw Error('Journal unavailable');local=await response.json();$('journal-tab').disabled=false;
  }
  render();
 }catch(error){$('notice').textContent='Could not refresh data. '+error.message;$('notice').classList.add('error');}
}
$('scenario').addEventListener('change',e=>selectScenario(e.target.value));$('previous').addEventListener('click',()=>{step=Math.max(0,step-1);render();});$('next').addEventListener('click',()=>{step=Math.min(view().events.length-1,step+1);render();});$('replay-tab').addEventListener('click',()=>{source='replay';render();});$('journal-tab').addEventListener('click',()=>{source='local_journal';render();});$('refresh').addEventListener('click',refresh);
refresh();
const lifecycle = new AbortController();
if(document.modelContext?.registerTool){
 const tools=[{name:'select_replay_scenario',description:'Display a synthetic OneSpread replay scenario. Changes only the visible view; never submits an order.',inputSchema:{type:'object',properties:{scenario:{type:'string',enum:['entry','veto','exit']}},required:['scenario'],additionalProperties:false},annotations:{readOnlyHint:false},execute(input){if(!input||Object.keys(input).length!==1||!['entry','veto','exit'].includes(input.scenario))throw Error('Invalid scenario');if(!demo)throw Error('Replay not loaded');return selectScenario(input.scenario);}}, {name:'read_visible_decision',description:'Read the currently displayed decision and its source.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute(){const v=view();return {source,scenario:source==='replay'?scenario:null,decision:source==='replay'?v.events[step]:v.events.at(-1)};}}];
 for(const tool of tools)Promise.resolve(document.modelContext.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});
 window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
}
