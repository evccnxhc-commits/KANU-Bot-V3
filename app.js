(() => {
  const $ = (id) => document.getElementById(id);
  const overlay = $('authOverlay'), authForm = $('authForm'), authError = $('authError');
  const chatForm = $('chatForm'), input = $('messageInput'), sendButton = $('sendButton');
  let csrf = '', mode = 'login', authenticated = false, busy = false, toastTimer;
  const escapeText = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function toast(text) { const el = $('toast'); el.textContent = text; el.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 3000); }
  function openAuth(nextMode='login') { setMode(nextMode); overlay.classList.remove('hidden'); $('username').focus(); }
  function closeAuth() { if (authenticated) overlay.classList.add('hidden'); }
  function setMode(next) { mode = next; document.querySelectorAll('.auth-tab').forEach(b => b.classList.toggle('active', b.dataset.mode === mode)); $('authTitle').textContent = mode === 'login' ? 'ابدأ محادثتك' : 'أنشئ حسابك'; $('authSubmit').innerHTML = mode === 'login' ? 'تسجيل الدخول <span>←</span>' : 'إنشاء الحساب <span>←</span>'; $('password').autocomplete = mode === 'login' ? 'current-password' : 'new-password'; $('passwordHint').classList.toggle('hidden', mode === 'login'); authError.textContent = ''; }
  async function api(url, body) { const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify(body), credentials:'same-origin'}); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.error || 'حدث خطأ. حاول مرة أخرى.'); return data; }
  function showLoggedIn(username) { authenticated = true; overlay.classList.add('hidden'); $('accountButton').textContent = username; input.disabled = false; sendButton.disabled = false; input.placeholder = 'اكتب رسالتك إلى KANU...'; input.focus(); }
  function showLoggedOut() { authenticated = false; input.disabled = true; sendButton.disabled = true; $('accountButton').textContent = 'الحساب'; openAuth('login'); }
  function addMessage(role, text) { const row = document.createElement('div'); row.className = `message ${role}`; const avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.textContent = role === 'assistant' ? 'K' : 'أنت'; const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text; row.append(avatar,bubble); $('messages').append(row); $('welcome').style.display = 'none'; row.scrollIntoView({behavior:'smooth',block:'nearest'}); return row; }
  function setBusy(value) { busy = value; sendButton.disabled = value || !authenticated; input.disabled = value || !authenticated; sendButton.innerHTML = value ? '…' : '<span>↑</span>'; }
  async function loadSession() { try { const r = await fetch('/api/session', {credentials:'same-origin'}); const data = await r.json(); csrf = data.csrf_token || ''; if (data.authenticated) showLoggedIn(data.username); else showLoggedOut(); } catch { toast('تعذّر الاتصال بالخادم. أعد تحميل الصفحة.'); } }
  document.querySelectorAll('.auth-tab').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  $('accountButton').addEventListener('click', async () => { if (authenticated) { if (!confirm('هل تريد تسجيل الخروج؟')) return; try { await api('/api/logout', {}); csrf = ''; await loadSession(); toast('تم تسجيل الخروج.'); } catch(e) { toast(e.message); } } else openAuth(); });
  $('closeAuth').addEventListener('click', closeAuth);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeAuth(); });
  authForm.addEventListener('submit', async e => { e.preventDefault(); authError.textContent = ''; const button = $('authSubmit'); button.disabled = true; try { const data = await api(mode === 'login' ? '/api/login' : '/api/register', {username:$('username').value.trim(),password:$('password').value}); csrf = data.csrf_token || csrf; showLoggedIn(data.username); $('password').value = ''; toast(mode === 'login' ? 'أهلًا بعودتك.' : 'تم إنشاء حسابك بنجاح.'); } catch(err) { authError.textContent = err.message; } finally { button.disabled = false; } });
  async function sendMessage(text) { if (!text || busy || !authenticated) return; addMessage('user', text); input.value = ''; input.style.height = 'auto'; setBusy(true); const typing = document.createElement('div'); typing.className = 'message assistant'; typing.innerHTML = '<div class="avatar">K</div><div class="bubble typing"><i></i><i></i><i></i></div>'; $('messages').append(typing); typing.scrollIntoView({behavior:'smooth',block:'nearest'}); try { const data = await api('/api/chat', {message:text}); typing.remove(); addMessage('assistant', data.reply || 'لم يصل رد. حاول مرة أخرى.'); } catch(err) { typing.remove(); addMessage('assistant', err.message); } finally { setBusy(false); input.focus(); } }
  chatForm.addEventListener('submit', e => { e.preventDefault(); sendMessage(input.value.trim()); });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 180) + 'px'; });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); chatForm.requestSubmit(); } });
  document.querySelectorAll('.suggestion').forEach(b => b.addEventListener('click', () => { if (!authenticated) { openAuth(); return; } input.value = b.dataset.prompt; chatForm.requestSubmit(); }));
  loadSession();
})();
