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
 name='student_'+str(int(time())); a=page();login(a,name,'test-pass-123',True)
 a.wait_for_function('!dirty&&!saving');assert a.evaluate('state.currentTier')==1;assert not a.locator('#tab-teacher').is_visible()
 a.locator('#hint-btn').click();assert a.locator('#hint-btn').is_disabled();a.wait_for_function('!dirty&&!saving');prompt=a.evaluate('currentQuestion.prompt')
 b=page();login(b,name,'test-pass-123');assert b.evaluate('currentQuestion.prompt')==prompt;assert b.evaluate('state.hintUsed');assert b.locator('#hint-btn').is_disabled();b.wait_for_function('!dirty&&!saving')
 # An assisted answer gives feedback but neither progress nor coins.
 coins=b.evaluate("state.coins");b.locator('#answer-input').fill(b.evaluate('String(currentQuestion.answer)'));b.locator('#submit-btn').click();assert b.evaluate("state.practiceCount")==0;assert b.evaluate("state.coins")==coins;b.locator('#continue-feedback').click();assert b.evaluate("currentQuestion.prompt")!=prompt
 # Finish two independent questions and checkpoint on second device.
 for _ in range(2):
  b.locator('#answer-input').fill(b.evaluate('String(currentQuestion.answer)'));b.locator('#submit-btn').click();b.locator('#continue-feedback').click()
 b.locator('.concept-opt-btn[onclick^="handleConceptOptionClick(true"]').click();b.locator('#trophy-modal button').click();b.wait_for_function('!dirty&&!saving');assert b.evaluate('state.currentTier')==2
 # stale device writes get rejected, not silently overwritten
 a.evaluate('saveState()');a.wait_for_function('conflict');assert a.locator('#reload-cloud').is_visible()
 c=page();login(c,name+'b','other-pass-123',True);c.wait_for_function('!dirty&&!saving');assert c.evaluate('state.currentTier')==1
 c.locator('#tab-leaderboard').click();c.wait_for_function('liveCloudLeaderboard.length>=2');assert name in c.locator('#leaderboard-tbody').inner_text();assert 'BOT' not in c.locator('#leaderboard-tbody').inner_text();assert c.evaluate("fetch('/api/teacher').then(r=>r.status)")==403
 t=page();login(t,'teacher','teacher-test-123');t.wait_for_function("document.querySelector('#teacher-table').innerText.includes('"+name+"')");assert 'Tier 2' in t.locator('#teacher-table').inner_text();assert not t.locator('#tab-arena').is_visible()
 assert b.evaluate("api('session').then(r=>r.save.currentTier)")==2
 b.evaluate('openAccount()');b.locator('button[onclick="signOut()"]').click();b.locator('#account-overlay').wait_for(state='visible');assert b.evaluate("fetch('/api/session').then(r=>r.status)")==401
 print('Passed: registration, persistent saves, hint restoration, cross-device login, progression, isolated accounts, conflict protection, actual class leaderboard, teacher permissions, reload, sign-out. JS errors:',errors);assert not errors
 browser.close()
