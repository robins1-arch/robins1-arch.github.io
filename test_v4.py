from playwright.sync_api import sync_playwright
from time import time
import os, http.client
from urllib.parse import urlsplit
URL=os.environ.get('ARENA_TEST_URL','http://127.0.0.1:8799')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']); errors=[]
 def page():
  ctx=browser.new_context(viewport={'width':900,'height':800}); pg=ctx.new_page();pg.on('pageerror',lambda e:errors.append(str(e)));
  import urllib.request, urllib.error, http.cookiejar
  from pathlib import Path
  jar=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
  def proxy(path,method,body,headers):
   req=urllib.request.Request(URL+path,data=body.encode() if body else None,headers=headers or {},method=method)
   try: res=opener.open(req)
   except urllib.error.HTTPError as e:res=e
   return {'status':res.status,'body':res.read().decode()}
  pg.expose_function('testProxy',proxy)
  html=Path(__file__).with_name('index.html').read_text().replace('<script>','<script>window.fetch=async(path,o={})=>{const r=await testProxy(path,o.method||"GET",o.body||null,o.headers||{});return new Response(r.body,{status:r.status,headers:{"Content-Type":"application/json"}});};</script><script>',1)
  pg.set_content(html);pg.wait_for_timeout(200);pg._test_html=html;return pg

 def login(pg,handle,pw,register=False):
  pg.locator('#account-handle').fill(handle);pg.locator('#account-password').fill(pw)
  if register:
   pg.locator('#account-mode').click();pg.locator('#account-name').fill(handle);pg.locator('#account-code').fill('testclass123')
  pg.locator('#account-submit').click();pg.locator('#account-overlay').wait_for(state='hidden',timeout=10000)
 name='v4_'+str(int(time())); a=page();login(a,name,'test-pass-123',True)
 a.wait_for_function('!dirty&&!saving');assert a.locator('#placement-offer').is_visible();a.locator('button[onclick="beginPlacement()"]').click();a.locator('#placement-modal').wait_for(state='visible');assert a.evaluate('state.totalAttempts')==0
 def answer(pg,correct=True):
  assert pg.evaluate("placementTask().op") == ('×' if pg.evaluate('state.diagnostic.answers.length')<5 else '÷')
  if correct:
   val=pg.evaluate('(()=>{const q=placementTask();return q.pointAnswer?q.pointAnswer.join(","):q.fraction?q.fraction.join("/"):String(q.answer)})()');pg.locator('#placement-answer').fill(val);pg.locator('#placement-modal form button').click()
  else:pg.locator('button[onclick="skipPlacementQuestion()"]').click()
 for _ in range(7):answer(a)
 a.wait_for_function('!dirty&&!saving'); prompt=a.locator('#placement-question').inner_text()
 b=page();login(b,name,'test-pass-123');assert b.locator('#placement-modal').is_visible();assert b.locator('#placement-question').inner_text()==prompt;assert b.evaluate('state.diagnostic.answers.length')==7
 for _ in range(23):answer(b)
 b.locator('#placement-modal').wait_for(state='hidden');b.wait_for_function('!dirty&&!saving');assert b.evaluate('state.currentTier')==16;assert b.evaluate('state.totalAttempts')==0;assert b.evaluate('state.coins')==0;assert b.evaluate('state.diagnostic.passed')==3;assert b.evaluate('state.placementTier')==16
 b.locator('#tab-vault').click();assert b.locator('#emblem-vault-grid').inner_text().count('Placement credit')==3;b.locator('#tab-mastery').click();assert b.locator('#mastery-table').inner_text().count('Placement credit')==15
 # All four possible outcomes; 8/10 but two misses on one topic fails the block.
 for passes in [0,1,2]:
  c=page();login(c,name+'_'+str(passes),'test-pass-123',True);c.locator('button[onclick="beginPlacement()"]').click();
  for _ in range(passes*10):answer(c)
  for i in range(10):answer(c,i not in [0,5])
  c.locator('#placement-modal').wait_for(state='hidden');c.wait_for_function('!dirty&&!saving');assert c.evaluate('state.currentTier')==1+5*passes;assert c.evaluate('state.diagnostic.blocks.at(-1).correct')==8;assert c.evaluate('state.diagnostic.blocks.at(-1).passed')==False
 # Across all numerical families: check finite expected values, fraction/coordinate answer consistency, prompt variety.
 result=b.evaluate('''()=>{let tested=0,unique=0,min=Infinity,forms=0;for(let t=1;t<=50;t++)for(let v=0;v<4;v++){const seen=new Set();for(let i=0;i<200;i++){let q=v<2?CURRICULUM[t-1].make(v):extras[t-1](v-2);if(!q.prompt||!Number.isFinite(q.answer)||!q.steps[0]||!q.hints[0]||!answerMatches(q.pointAnswer?q.pointAnswer.join(','):q.fraction?q.fraction.join('/'):String(q.answer),q))throw Error('Invalid '+t+' form '+v+' '+JSON.stringify(q));if(q.pointAnswer&&q.graph&&!q.graph.points.some(p=>p.select&&p.x===q.pointAnswer[0]&&p.y===q.pointAnswer[1]))throw Error('Invalid graph');seen.add(questionKey(q));tested++;}unique+=seen.size;min=Math.min(min,seen.size);forms++;}let checks=0;for(const [t,f] of Object.entries(reasoningBanks))for(let i=0;i<100;i++){const q=f();if(new Set(q.options).size!==4||!q.why)throw Error('Bad reasoning options '+t+' '+JSON.stringify(q));checks++;}return {tested,unique,min,forms,checks};}''');print('BANK TEST',result)
 # Full progression simulation with server writes suppressed only for this test; normal UI methods used.
 b.locator('#tab-arena').click();result=b.evaluate('''()=>{accountLoading=true;state=freshState();loadNextChallenge();let steps=0,keys=new Set(),repeated=0;while(!state.completed&&steps<800){const q=currentQuestion;if(!q)throw Error('No question');if(keys.has(q.key))repeated++;keys.add(q.key);submitTask(steps!==1&&steps!==2&&steps!==20,'test');if(isModalOpen)closeTrophyModal();else if(autoAdvanceTimeout)nextAfterFeedback();steps++;}const coins=state.coins;finishTier();if(coins!==state.coins)throw Error('Duplicate reward');return {steps,completed:state.completed,tier:state.currentTier,repeated,keys:keys.size};}''');print('FULL RUN',result);assert result['completed'] and result['repeated']==0
 t=page();login(t,'teacher','teacher-test-123');t.wait_for_function("document.querySelector('#teacher-table').innerText.includes('"+name+"')");t.locator('details').filter(has_text=name+' • Tier 16').locator('summary').click();assert 'Entry tier 16' in t.locator('#teacher-table').inner_text();assert not errors,errors;print('Passed: four entry routes, 8/10 topic-floor failure, saved placement resumption, no diagnostic rewards, vault & mastery labels, teacher diagnostic summary, all-tier progression. JS errors:',errors);browser.close()
