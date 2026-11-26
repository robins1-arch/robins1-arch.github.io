"""Single-class MYP Arena server. Python 3.10+, standard library only."""
import os, json, sqlite3, secrets, hashlib, hmac, re, time, threading, argparse, collections
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
BASE=Path(__file__).resolve().parent
DB=os.environ.get('ARENA_DB',str(BASE/'data'/'multiplicative.sqlite3'))
JOIN=os.environ.get('ARENA_JOIN_CODE','')
TEACHER=os.environ.get('ARENA_TEACHER_PASSWORD','')
SECURE=os.environ.get('ARENA_HTTPS','0')=='1'
LIMIT=1_000_000
lock=threading.Lock(); attempts=collections.defaultdict(list)

def db():
 c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def password(p,s): return hashlib.scrypt(p.encode(),salt=bytes.fromhex(s),n=16384,r=8,p=1).hex()
def digest(t): return hashlib.sha256(t.encode()).hexdigest()
def init():
 if len(JOIN)<8 or len(TEACHER)<12: raise SystemExit('Set ARENA_JOIN_CODE (8+ chars) and ARENA_TEACHER_PASSWORD (12+ chars).')
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 with db() as c:
  c.executescript('''PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS users(handle TEXT PRIMARY KEY, name TEXT NOT NULL, salt TEXT NOT NULL, hash TEXT NOT NULL, role TEXT NOT NULL, save TEXT, revision INTEGER NOT NULL DEFAULT 0, updated INTEGER); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, handle TEXT NOT NULL REFERENCES users(handle), expires INTEGER NOT NULL);''')
  for row in c.execute('SELECT save FROM users WHERE save IS NOT NULL'):
   if json.loads(row['save']).get('bankVersion')!=5:raise SystemExit('Use a separate database for the multiplication and division edition.')
  salt=secrets.token_hex(16); c.execute("INSERT INTO users(handle,name,salt,hash,role) VALUES('teacher','Teacher',?,?,'teacher') ON CONFLICT(handle) DO UPDATE SET salt=excluded.salt,hash=excluded.hash",(salt,password(TEACHER,salt)))

def valid_save(s):
 if not isinstance(s,dict) or s.get('bankVersion')!=5 or s.get('version')!=2 or type(s.get('currentTier'))!=int or not 1<=s['currentTier']<=50: return False
 for k in ('mult','div'):
  m=s.get('operations',{}).get(k) if isinstance(s.get('operations'),dict) else None
  if not isinstance(m,dict) or type(m.get('attempts'))!=int or type(m.get('correct'))!=int or not 0<=m['correct']<=m['attempts']<=10**12:return False
 if s.get('stage') not in ('practice','checkpoint','application','review','promotion','completed'): return False
 if type(s.get('completed'))!=bool or s['completed']!=(s['stage']=='completed') or (s['completed'] and s['currentTier']!=50): return False
 for k in ('coins','totalScore','totalSolved','totalAttempts','streak','bestStreak','attemptClock'):
  if type(s.get(k)) not in (int,float) or not 0<=s[k]<=10**12: return False
 if s.get('placementTier',1) not in (1,6,11,16) or s.get('placementTier',1)>s['currentTier']:return False
 d=s.get('diagnostic')
 if d is not None:
  if not isinstance(d,dict) or d.get('status') not in ('active','done') or type(d.get('passed')) is not int or not 0<=d['passed']<=3 or not isinstance(d.get('answers'),list) or len(d['answers'])>10 or type(d.get('seed')) is not int or not 0<=d['seed']<=4294967295:return False
  blocks=d.get('blocks',[])
  if not isinstance(blocks,list) or len(blocks)>3:return False
  for i,b in enumerate(blocks):
   if not isinstance(b,dict) or b.get('division')!=i or type(b.get('correct')) is not int or not 0<=b['correct']<=10 or type(b.get('passed')) is not bool or not isinstance(b.get('topics'),list) or len(b['topics'])!=10:return False
   if any(not isinstance(x,dict) or type(x.get('t')) is not int or not i*5+1<=x['t']<=i*5+5 or type(x.get('correct')) is not bool for x in b['topics']):return False
   if b['correct']!=sum(x['correct'] for x in b['topics']) or b['passed']!=(b['correct']>=8 and all(any(x['t']==t and x['correct'] for x in b['topics']) for t in range(i*5+1,i*5+6))):return False
  if sum(b['passed'] for b in blocks)!=d['passed'] or (d['status']=='done' and s.get('placementTier',1)!=1+5*d['passed']):return False
  if d['status']=='active' and (d['passed']>=3 or s['currentTier']!=1 or s['totalAttempts']!=0):return False
  if any(not isinstance(x,dict) or type(x.get('t')) is not int or not 1<=x['t']<=15 or type(x.get('correct')) is not bool for x in d['answers']):return False
 hist=s.get('seenQuestions',{})
 if not isinstance(hist,dict) or any(not isinstance(k,str) or not k.isdigit() or not 1<=int(k)<=50 or not isinstance(v,list) or len(v)>800 or any(not isinstance(x,str) or not re.fullmatch(r'[0-9a-z]{1,7}-[0-9a-z]{1,7}',x) for x in v) for k,v in hist.items()):return False
 if s['totalSolved']>s['totalAttempts'] or not isinstance(s.get('mastery'),dict) or not isinstance(s.get('criteria'),dict): return False
 for k,m in s['mastery'].items():
  if not k.isdigit() or not 1<=int(k)<=50 or not isinstance(m,dict): return False
  for a in ('attempts','correct','independent','hints','reviewAttempts','reviewCorrect','lastSeen','due','level','errors','misses'):
   if type(m.get(a)) not in (int,float) or not 0<=m[a]<=10**12: return False
 for k in ('A','B','C','D'):
  m=s['criteria'].get(k)
  if not isinstance(m,dict) or any(type(m.get(a)) not in (int,float) or not 0<=m[a]<=10**12 for a in ('attempts','correct')) or m['correct']>m['attempts']: return False
 return True

def summary(r,teacher=False):
 s=json.loads(r['save']) if r['save'] else {}; a=s.get('totalAttempts',0); correct=s.get('totalSolved',0)
 v=dict(name=r['name'],tier=s.get('currentTier',1),placementTier=s.get('placementTier',1),completed=s.get('completed',False),score=s.get('totalScore',0),acc=round(correct/a*100) if a else None,avatar=s.get('equippedAvatar','knight'),entryId='acct_'+r['handle'],isVerifiedAccount=True)
 if teacher:v.update(placementTier=s.get('placementTier',1),diagnostic=s.get('diagnostic'),handle=r['handle'],updated=r['updated'],attempts=a,mastery=s.get('mastery',{}),criteria=s.get('criteria',{}),operations=s.get('operations',{}))
 return v

class Handler(BaseHTTPRequestHandler):
 def reply(self,status,data,cookie=None):
  b=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(b)
 def cookie(self,token='',age=0):return f'arena_multiplicative_session={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict'+('; Secure' if SECURE else '')
 def token(self):
  try:return SimpleCookie(self.headers.get('Cookie',''))['arena_multiplicative_session'].value
  except (KeyError,ValueError):return ''
 def user(self,c):return c.execute('SELECT u.* FROM users u JOIN sessions s ON u.handle=s.handle WHERE s.token=? AND s.expires>?',(digest(self.token()),int(time.time()))).fetchone()
 def view(self,r):return dict(handle=r['handle'],name=r['name'],role=r['role'],revision=r['revision'],save=json.loads(r['save']) if r['save'] else None)
 def do_GET(self):
  p=urlsplit(self.path).path
  if p=='/':
   b=(BASE/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b);return
  with db() as c:
   u=self.user(c)
   if not u:return self.reply(401,{'error':'Sign in first.'})
   if p=='/api/session':return self.reply(200,self.view(u))
   if p=='/api/leaderboard':
    rows=c.execute("SELECT * FROM users WHERE role='student'").fetchall();return self.reply(200,{'rows':[summary(r) for r in rows]})
   if p=='/api/teacher':
    if u['role']!='teacher':return self.reply(403,{'error':'Teacher access required.'})
    return self.reply(200,{'rows':[summary(r,True) for r in c.execute("SELECT * FROM users WHERE role='student' ORDER BY handle")]})
  self.reply(404,{'error':'Not found.'})
 def do_POST(self):
  if self.headers.get('X-Arena-Request')!='1' or self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(403,{'error':'Invalid request.'})
  try:
   n=int(self.headers.get('Content-Length','0'));assert 0<n<=LIMIT;d=json.loads(self.rfile.read(n));assert isinstance(d,dict)
  except Exception:return self.reply(400,{'error':'Invalid request body.'})
  p=urlsplit(self.path).path
  if p in ('/api/register','/api/login'):
   now=time.time();ip=self.client_address[0];handle=str(d.get('handle','')).strip().lower();pw=d.get('password','')
   if not re.fullmatch(r'[a-z0-9_]{3,24}',handle) or not isinstance(pw,str) or not 8<=len(pw)<=128:return self.reply(400,{'error':'Use a 3–24 character handle and 8–128 character password.'})
   with lock:
    for k in list(attempts):
     attempts[k]=[t for t in attempts[k] if t>now-300]
     if not attempts[k]:del attempts[k]
    for k,lim in [('ip:'+ip,80),('handle:'+handle,12)]:
     if len(attempts[k])>=lim:return self.reply(429,{'error':'Too many attempts. Try again in five minutes.'})
     attempts[k].append(now)
   with db() as c:
    if p.endswith('register'):
     if not hmac.compare_digest(str(d.get('code','')),JOIN):return self.reply(403,{'error':'Incorrect class code.'})
     name=str(d.get('name','')).strip()[:20] or handle; salt=secrets.token_hex(16)
     try:c.execute("INSERT INTO users(handle,name,salt,hash,role) VALUES(?,?,?,?,'student')",(handle,name,salt,password(pw,salt)))
     except sqlite3.IntegrityError:return self.reply(409,{'error':'Handle is already in use.'})
    u=c.execute('SELECT * FROM users WHERE handle=?',(handle,)).fetchone();expected=password(pw,u['salt'] if u else '00'*16)
    if not u or not hmac.compare_digest(expected,u['hash']):return self.reply(401,{'error':'Incorrect handle or password.'})
    token=secrets.token_urlsafe(32);c.execute('DELETE FROM sessions WHERE expires<=? OR token=?',(int(now),digest(self.token())));c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),handle,int(now)+86400*7));c.commit();return self.reply(200,self.view(u),self.cookie(token,86400*7))
  with db() as c:
   u=self.user(c)
   if not u:return self.reply(401,{'error':'Sign in first.'})
   if p=='/api/logout':c.execute('DELETE FROM sessions WHERE token=?',(digest(self.token()),));c.commit();return self.reply(200,{},self.cookie())
   if p=='/api/save':
    if u['role']!='student':return self.reply(403,{'error':'Student account required.'})
    s=d.get('save');rev=d.get('revision')
    if not valid_save(s) or type(rev)!=int:return self.reply(400,{'error':'Invalid save data.'})
    name=str(s.get('playerName','')).strip()[:20] or u['name'];s['playerName']=name;s['accountHandle']='';data=json.dumps(s,allow_nan=False,separators=(',',':'))
    result=c.execute('UPDATE users SET save=?,revision=revision+1,name=?,updated=? WHERE handle=? AND revision=?',(data,name,int(time.time()),u['handle'],rev));c.commit()
    if not result.rowcount:return self.reply(409,{'error':'Progress changed on another device. Reload the cloud save.'})
    return self.reply(200,{'revision':rev+1})
  self.reply(404,{'error':'Not found.'})

if __name__=='__main__':
 init(); parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000')));args=parser.parse_args();print(f'Arena listening on {args.host}:{args.port}',flush=True);ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
