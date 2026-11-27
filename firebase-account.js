/* Firebase adapter for the existing Arena account interface. No Python server. */
(() => {
  const sdkRoot = 'https://www.gstatic.com/firebasejs/11.6.1/';
  let initPromise, auth, db, A, F, stopListener, listenerVersion=0;
  const error = (message, status) => Object.assign(new Error(message), {status});
  const authEmail = handle => `${handle}@arena.example.com`;
  const scholarOnly = u => !!u && /^[a-z0-9_]{3,24}@arena\.example\.com$/.test(u.email || '') && !(u.providerData || []).some(p=>p.providerId==='google.com') && (u.providerData || []).some(p=>p.providerId==='password');
  const validHandle = h => /^[a-z0-9_]{3,24}$/.test(h);
  async function init() {
    if (!initPromise) initPromise = (async () => {
      const c = window.ARENA_FIREBASE_CONFIG;
      if (!c?.apiKey || !c.projectId || !c.appId || !c.authDomain) throw error('Firebase is not configured. Follow SETUP.md or ask your teacher to configure this website.', 503);
      if (location.protocol === 'file:') throw error('Open the published HTTPS website, not the downloaded HTML file.', 503);
      const [app, a, f] = await Promise.all([import(sdkRoot+'firebase-app.js'), import(sdkRoot+'firebase-auth.js'), import(sdkRoot+'firebase-firestore.js')]);
      A=a; F=f; const instance=app.initializeApp(c); auth=A.getAuth(instance); db=F.getFirestore(instance);
      await A.setPersistence(auth,A.browserSessionPersistence);
      await new Promise((resolve,reject)=>{const off=A.onAuthStateChanged(auth,()=>{off();resolve();},reject);});
      if(auth.currentUser && !scholarOnly(auth.currentUser)) await A.signOut(auth);
    })().catch(e=>{initPromise=null;throw e;});
    return initPromise;
  }
  const ref = (collection,id)=>F.doc(db,collection,id);
  const read = (c,id)=>F.getDocFromServer(ref(c,id));
  const user = ()=>{if(!scholarOnly(auth.currentUser))throw error('Please sign in with a Scholar account.',401);return auth.currentUser;};
  const integer=(x,min,max)=>Number.isSafeInteger(x)&&x>=min&&x<=max;
  const safeProfile = (uid,p)=>({entryId:'acct_'+uid,uid,name:String(p.name||'Scholar').slice(0,20),tier:integer(p.tier,1,50)?p.tier:1,placementTier:[1,6,11,16].includes(p.placementTier)?p.placementTier:1,completed:p.completed===true,score:integer(p.score,0,1000000000)?p.score:0,avatar:String(p.avatar||'knight'),pet:String(p.pet||'none'),isVerifiedAccount:true,environment:p.environment,decoration:p.decoration,evolution:p.evolution,title:p.title,badges:p.badges,collection:p.collection});
  function project(s) {return {name:String(s.playerName||'Scholar').slice(0,20),tier:s.currentTier,placementTier:s.placementTier,completed:s.completed===true,score:Math.floor(s.totalScore),avatar:s.equippedAvatar,pet:s.equippedPet,...sharedJourney(s)};}
  function decode(doc){if(!doc.exists())return {revision:0,save:null};const d=doc.data();return {revision:d.revision,save:JSON.parse(d.payload)};}
  async function session(){const u=user(),uid=u.uid;const teacher=await read('teachers',uid);if(teacher.exists())return {handle:uid,role:'teacher',name:'Teacher',revision:0,save:null};const member=await read('members',uid);if(!member.exists()){throw error('This account has not joined the class. Choose Create account and enter the class code.',403);}const saved=decode(await read('saves',uid));return {handle:uid,role:'student',name:saved.save?.playerName||member.data().nickname,...saved};}
  async function register(d){const h=d.handle.trim().toLowerCase(),name=d.name.trim(),code=d.code.trim();if(!validHandle(h)||h==='teacher')throw error('Choose a handle of 3–24 letters, numbers or underscores (not teacher).',400);if(name.length<1||name.length>20)throw error('Enter a nickname of 1–20 characters.',400);if(d.password.length<8)throw error('Choose a password of at least 8 characters.',400);if(code.length<8)throw error('Enter the class enrolment code.',400);let u;try{u=(await A.createUserWithEmailAndPassword(auth,authEmail(h),d.password)).user;}catch(e){if(e.code!=='auth/email-already-in-use')throw e;u=(await A.signInWithEmailAndPassword(auth,authEmail(h),d.password)).user;}
    try {const m=await read('members',u.uid);if(!m.exists())await F.setDoc(ref('members',u.uid),{nickname:name,code});return await session();}catch(e){await A.signOut(auth);if(e.code==='permission-denied')throw error('Class code not accepted, or class enrolment is closed. Check with your teacher and try again using the same handle and password.',403);throw e;}}
  async function save(d){const uid=user().uid;const payload=JSON.stringify(d.save);if(new TextEncoder().encode(payload).length>850000)throw error('Save exceeds the storage limit. Ask your teacher for assistance before signing out.',400);const profile=project(d.save);return F.runTransaction(db,async tx=>{const sr=ref('saves',uid),pr=ref('profiles',uid),prev=await tx.get(sr);const rev=prev.exists()?prev.data().revision:0;if(rev!==d.revision)throw error('Another device has saved newer progress. Reload the cloud save.',409);tx.set(sr,{revision:rev+1,payload,updatedAt:F.serverTimestamp()});tx.set(pr,profile);return {revision:rev+1};});}
  async function teacherRows(){const docs=await F.getDocsFromServer(F.collection(db,'saves'));return {rows:docs.docs.map(doc=>{const d=doc.data(),s=JSON.parse(d.payload);return {name:s.playerName,handle:'Private account',tier:s.currentTier,completed:s.completed,acc:s.totalAttempts?Math.round(s.totalSolved/s.totalAttempts*100):null,attempts:s.totalAttempts,operations:s.operations,placementTier:s.placementTier,diagnostic:s.diagnostic,mastery:s.mastery||{},updated:d.updatedAt?.seconds||0};})};}
  async function request(path,d){await init();switch(path){case 'session':return session();case 'register':return register(d);case 'login':{const h=d.handle.trim().toLowerCase();if(!validHandle(h))throw error('Enter a valid scholar handle.',400);await A.signInWithEmailAndPassword(auth,authEmail(h),d.password);try{return await session();}catch(e){await A.signOut(auth);throw e;}}case 'save':return save(d);case 'logout':stop();return A.signOut(auth);case 'leaderboard':{user();const docs=await F.getDocsFromServer(F.collection(db,'profiles'));return {rows:docs.docs.map(x=>safeProfile(x.id,x.data()))};}case 'teacher':return teacherRows();default:throw error('Unknown account operation.',400);}}
  function stop(){listenerVersion++;if(stopListener){stopListener();stopListener=null;}}
  async function listen(onRows,onError){stop();const version=listenerVersion;await init();if(version!==listenerVersion)return;user();let active=true;const unsub=F.onSnapshot(F.collection(db,'profiles'),snap=>{if(active)onRows(snap.docs.map(d=>safeProfile(d.id,d.data())));},e=>{if(active)onError(e);});stopListener=()=>{active=false;unsub();};}
  function message(e){if(e.status)return e.message;switch(e.code){case 'auth/invalid-credential':case 'auth/wrong-password':case 'auth/user-not-found':return 'Handle or password is incorrect.';case 'auth/too-many-requests':return 'Too many attempts. Try again later.';case 'auth/operation-not-allowed':return 'Your teacher must enable this sign-in provider in Firebase.';case 'auth/unauthorized-domain':return 'This website domain is not authorised in Firebase. Ask your teacher to add the GitHub Pages hostname.';case 'auth/network-request-failed':case 'unavailable':return 'Cannot reach Firebase. Check your internet connection and try again.';case 'permission-denied':return 'Firebase denied access. Ask your teacher to check the database rules and class enrolment.';case 'resource-exhausted':return 'The free Firebase quota has been reached. Your unsaved progress has not been confirmed.';default:return e.message||'Firebase request failed.';}}
  window.ArenaCloud={request,listen,stop,message};
})();
