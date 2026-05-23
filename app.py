from flask import Flask, request, jsonify, render_template_string, session, redirect
import asyncio
import aiohttp
import requests
import json
import binascii
import time
import random
import os
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import like_pb2
import like_count_pb2
import uid_generator_pb2
import warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = "adnan_like_panel_secret_key"  # Admin session এর জন্য

# ─── Firebase Config ──────────────────────────────────────────────────────────
FIREBASE_API_KEY = "AIzaSyDTO0i4jDNJTiyY6YdQCMxaq0svyewhn5E"
FIREBASE_DB_URL  = "https://like-api-a8bcb-default-rtdb.firebaseio.com"
FIREBASE_EMAIL   = "7hsiam123@gmail.com"
FIREBASE_PASS    = "siam123@."

firebase_token = None
token_expiry = 0

def get_fb_token():
    global firebase_token, token_expiry
    # টোকেন এর মেয়াদ থাকলে পুনরায় লগইন করবে না
    if time.time() < token_expiry and firebase_token:
        return firebase_token
    
    # অটোমেটিক Firebase Auth Login (Background API request)
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": FIREBASE_EMAIL,
        "password": FIREBASE_PASS,
        "returnSecureToken": True
    }
    try:
        res = requests.post(url, json=payload).json()
        if "idToken" in res:
            firebase_token = res["idToken"]
            token_expiry = time.time() + int(res["expiresIn"]) - 300 # ৫ মিনিট আগে রিফ্রেশ হবে
            return firebase_token
        else:
            print("Firebase Auth Error:", res)
            return None
    except Exception as e:
        print("Firebase Request Failed:", e)
        return None

def get_db_key(key_name):
    token = get_fb_token()
    if not token: return None
    res = requests.get(f"{FIREBASE_DB_URL}/keys/{key_name}.json?auth={token}").json()
    return res

def update_db_key(key_name, data):
    token = get_fb_token()
    if token:
        requests.patch(f"{FIREBASE_DB_URL}/keys/{key_name}.json?auth={token}", json=data)

liked_cache = defaultdict(set)

# ─── HTML Templates ────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>7H SIAM – Like Panel</title>
<link rel="icon" type="image/png" href="https://i.ibb.co.com/Dg5NNK2G/logo.png"/>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #060910; --surface: #0d1117; --card: #111820; --border: #1e2d3d;
    --accent: #00d4ff; --accent2: #ff6b35; --text: #e8f4fd; --muted: #5a7a8a;
    --success: #00e676; --error: #ff4757; --warn: #ffa502;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif;
    min-height: 100vh; display: flex; flex-direction: column; overflow-x: hidden;
  }
  body::before {
    content:''; position:fixed; inset:0;
    background-image: linear-gradient(rgba(0,212,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,.04) 1px, transparent 1px);
    background-size: 40px 40px; pointer-events:none; z-index:0;
  }
  .orb { position:fixed; border-radius:50%; filter:blur(120px); pointer-events:none; z-index:0; animation:drift 10s ease-in-out infinite alternate; }
  .orb1 { width:500px; height:500px; background:rgba(0,212,255,.07); top:-100px; left:-100px; }
  .orb2 { width:400px; height:400px; background:rgba(255,107,53,.06); bottom:-80px; right:-80px; animation-delay:-5s; }
  @keyframes drift { from{transform:translate(0,0);} to{transform:translate(30px,20px);} }
  header { position:relative; z-index:10; text-align:center; padding:52px 20px 24px; }
  .site-title {
    font-family:'Bebas Neue',sans-serif; font-size:clamp(72px,16vw,130px);
    letter-spacing:8px; line-height:1;
    background:linear-gradient(135deg,#fff 0%,var(--accent) 50%,var(--accent2) 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
    animation:titleIn .8s cubic-bezier(.16,1,.3,1) both;
  }
  @keyframes titleIn { from{opacity:0;transform:translateY(-30px) scale(.95);} to{opacity:1;transform:none;} }
  .tagline { font-size:13px; letter-spacing:4px; text-transform:uppercase; color:var(--muted); margin-top:8px; animation:fadeUp .6s .3s both; }
  @keyframes fadeUp { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:none;} }
  main { flex:1; position:relative; z-index:10; max-width:620px; width:100%; margin:0 auto; padding:0 16px 40px; animation:fadeUp .6s .5s both; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:32px; position:relative; overflow:hidden; }
  .card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,var(--accent),var(--accent2)); }
  .card-title { font-family:'Bebas Neue',sans-serif; font-size:22px; letter-spacing:3px; color:var(--accent); margin-bottom:24px; }
  .field { margin-bottom:18px; }
  label { display:block; font-size:11px; letter-spacing:2px; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }
  input, select {
    width:100%; background:var(--surface); border:1px solid var(--border); border-radius:10px;
    color:var(--text); font-family:'Outfit',sans-serif; font-size:15px; padding:13px 16px;
    outline:none; transition:border-color .2s, box-shadow .2s;
  }
  input:focus, select:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(0,212,255,.12); }
  select option { background:var(--card); }
  .pw-wrap { position:relative; }
  .pw-toggle { position:absolute; right:14px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; color:var(--muted); font-size:18px; padding:0; transition:color .2s; }
  .pw-toggle:hover { color:var(--accent); }
  .btn {
    width:100%; padding:15px; border:none; border-radius:10px;
    font-family:'Bebas Neue',sans-serif; font-size:18px; letter-spacing:3px;
    cursor:pointer; transition:transform .15s,box-shadow .15s,opacity .2s;
    position:relative; overflow:hidden;
  }
  .btn:active { transform:scale(.98); }
  .btn-primary { background:linear-gradient(135deg,var(--accent),#0099cc); color:#000; box-shadow:0 4px 20px rgba(0,212,255,.25); }
  .btn-primary:hover { box-shadow:0 6px 28px rgba(0,212,255,.4); }
  .btn-secondary { background:linear-gradient(135deg,var(--accent2),#cc4422); color:#fff; box-shadow:0 4px 20px rgba(255,107,53,.25); }
  .btn-secondary:hover { box-shadow:0 6px 28px rgba(255,107,53,.4); }
  .btn:disabled { opacity:.5; cursor:not-allowed; transform:none !important; }
  .btn::after { content:''; position:absolute; top:-50%; left:-60%; width:40%; height:200%; background:rgba(255,255,255,.2); transform:skewX(-20deg); transition:left .4s; }
  .btn:hover::after { left:120%; }
  .limit-bar-wrap { margin-bottom:20px; }
  .limit-label { display:flex; justify-content:space-between; font-size:11px; letter-spacing:1.5px; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }
  .limit-label span:last-child { color:var(--accent); font-weight:600; }
  .limit-bar { height:6px; background:var(--border); border-radius:3px; overflow:hidden; }
  .limit-fill { height:100%; background:linear-gradient(90deg,var(--accent),var(--accent2)); border-radius:3px; transition:width .5s cubic-bezier(.4,0,.2,1); }
  #response-area { margin-top:24px; display:none; }
  .res-card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:24px; animation:popIn .4s cubic-bezier(.16,1,.3,1); }
  @keyframes popIn { from{opacity:0;transform:scale(.97) translateY(8px);} to{opacity:1;transform:none;} }
  .res-card.success { border-color:rgba(0,230,118,.3); }
  .res-card.error   { border-color:rgba(255,71,87,.3); }
  .res-status { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
  .status-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
  .dot-success { background:var(--success); box-shadow:0 0 8px var(--success); }
  .dot-partial { background:var(--warn); box-shadow:0 0 8px var(--warn); }
  .dot-error   { background:var(--error); box-shadow:0 0 8px var(--error); }
  .status-text { font-size:13px; letter-spacing:2px; text-transform:uppercase; font-weight:600; }
  .text-success { color:var(--success); }
  .text-partial { color:var(--warn); }
  .text-error   { color:var(--error); }
  .res-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .res-item { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 14px; }
  .res-item-label { font-size:10px; letter-spacing:2px; text-transform:uppercase; color:var(--muted); margin-bottom:4px; }
  .res-item-value { font-size:20px; font-weight:700; color:var(--text); }
  .res-item-value.highlight { color:var(--accent); }
  .res-item-value.big { font-size:28px; font-family:'Bebas Neue',sans-serif; letter-spacing:2px; }
  .spinner-wrap { display:none; flex-direction:column; align-items:center; gap:14px; padding:24px 0; }
  .spinner { width:44px; height:44px; border:3px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin .8s linear infinite; }
  @keyframes spin { to{transform:rotate(360deg);} }
  .spinner-text { font-size:13px; letter-spacing:2px; text-transform:uppercase; color:var(--muted); }
  .auth-error { color:var(--error); font-size:13px; margin-top:10px; display:none; text-align:center; letter-spacing:1px; }
  .divider { height:1px; background:var(--border); margin:24px 0; }
  #panel { display:none; }
  footer { position:relative; z-index:10; text-align:center; padding:24px 16px; font-size:12px; color:var(--muted); letter-spacing:1px; border-top:1px solid var(--border); }
  footer a { color:var(--accent); text-decoration:none; font-weight:600; transition:color .2s,text-shadow .2s; }
  footer a:hover { color:var(--accent2); text-shadow:0 0 8px var(--accent2); }
  @media(max-width:480px) { .card { padding:22px 18px; } .res-grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="orb orb1"></div>
<div class="orb orb2"></div>

<header>
  <h1 class="site-title">7H SIAM - LIKE PANEL</h1>
  <p class="tagline">Free Fire · Like Panel · v2</p>
</header>

<main>
  <div id="auth-gate">
    <div class="card">
      <div class="card-title">🔐 Access Required</div>
      <div class="field">
        <label>Panel Password</label>
        <div class="pw-wrap">
          <input type="password" id="pw-input" placeholder="Enter password..." autocomplete="off"/>
          <button class="pw-toggle" onclick="togglePw()">👁</button>
        </div>
      </div>
      <button class="btn btn-primary" onclick="checkAuth()">UNLOCK PANEL</button>
      <p class="auth-error" id="auth-err">❌ Wrong password. Try again.</p>
    </div>
  </div>

  <div id="panel">
    <div class="card">
      <div class="card-title">⚡ Send Likes</div>

      <div class="limit-bar-wrap">
        <div class="limit-label">
          <span>Key Usage (Used / Limit)</span>
          <span id="limit-text">? / ?</span>
        </div>
        <div class="limit-bar">
          <div class="limit-fill" id="limit-fill" style="width:0%"></div>
        </div>
      </div>

      <div class="field">
        <label>Player UID</label>
        <input type="text" id="uid" placeholder="e.g. 2815662785"/>
      </div>

      <div class="field">
        <label>Server</label>
        <select id="server">
          <option value="IND">🇮🇳 IND – India</option>
          <option value="BD" selected>🇧🇩 BD – Bangladesh</option>
          <option value="BR">🇧🇷 BR – Brazil</option>
          <option value="US">🇺🇸 US – United States</option>
          <option value="SAC">🌎 SAC – South America</option>
          <option value="NA">🌏 NA – North America</option>
          <option value="RU">🇷🇺 RU – Russia</option>
        </select>
      </div>

      <div class="spinner-wrap" id="spinner">
        <div class="spinner"></div>
        <div class="spinner-text">Sending likes...</div>
      </div>

      <button class="btn btn-secondary" id="send-btn" onclick="sendLike()">🚀 SEND LIKES</button>

      <div id="response-area">
        <div class="divider"></div>
        <div id="res-card" class="res-card">
          <div class="res-status">
            <div class="status-dot" id="res-dot"></div>
            <div class="status-text" id="res-status-text"></div>
          </div>
          <div class="res-grid" id="res-grid"></div>
        </div>
      </div>
    </div>
  </div>
</main>

<footer>
  © Copyright 2026. All Rights Reserved. Developed by <a href="https://t.me/DEV_7H_SIAM" target="_blank">7H SIAM</a>
</footer>

<script>
  const PASS  = "199113";

  function togglePw() {
    const i = document.getElementById('pw-input');
    i.type = i.type === 'password' ? 'text' : 'password';
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('pw-input').addEventListener('keydown', e => { if (e.key === 'Enter') checkAuth(); });
    document.getElementById('uid').addEventListener('keydown', e => { if (e.key === 'Enter') sendLike(); });
  });

  function checkAuth() {
    if (document.getElementById('pw-input').value === PASS) {
      document.getElementById('auth-gate').style.display = 'none';
      document.getElementById('panel').style.display = 'block';
    } else {
      const err = document.getElementById('auth-err');
      err.style.display = 'block';
      document.getElementById('pw-input').style.borderColor = 'var(--error)';
      setTimeout(() => { err.style.display='none'; document.getElementById('pw-input').style.borderColor=''; }, 3000);
    }
  }

  function updateBar(used, limit) {
    if(limit > 0){
        const pct = Math.min((used / limit) * 100, 100);
        document.getElementById('limit-fill').style.width = pct + '%';
        document.getElementById('limit-text').textContent = used + ' / ' + limit;
    }
  }

  async function sendLike() {
    const uid    = document.getElementById('uid').value.trim();
    const server = document.getElementById('server').value;
    
    if (!uid)          { alert('UID দিন!'); return; }

    const btn     = document.getElementById('send-btn');
    const spinner = document.getElementById('spinner');
    btn.disabled  = true;
    spinner.style.display = 'flex';
    document.getElementById('response-area').style.display = 'none';

    try {
      const res  = await fetch(`/like?server_name=${server}&uid=${encodeURIComponent(uid)}`);
      const data = await res.json();
      spinner.style.display = 'none';

      if(data.limit !== undefined) {
         updateBar(data.used, data.limit);
      }

      if (data.error) {
        showError(data.error);
      } else {
        showSuccess(data);
      }
    } catch (e) {
      spinner.style.display = 'none';
      showError('Connection error. Server may be offline.');
    }
    btn.disabled = false;
  }

  function showSuccess(d) {
    const area = document.getElementById('response-area');
    const card = document.getElementById('res-card');
    const dot  = document.getElementById('res-dot');
    const txt  = document.getElementById('res-status-text');
    const grid = document.getElementById('res-grid');
    const given = d.LikesGivenByAPI || 0;
    const ok    = given > 0;

    card.className = 'res-card ' + (ok ? 'success' : 'error');
    dot.className  = 'status-dot ' + (ok ? 'dot-success' : d.status===2 ? 'dot-partial' : 'dot-error');
    txt.className  = 'status-text ' + (ok ? 'text-success' : d.status===2 ? 'text-partial' : 'text-error');
    txt.textContent = ok ? 'Likes Sent!' : d.status===2 ? 'Already Liked' : 'Failed';

    grid.innerHTML = `
      <div class="res-item" style="grid-column:1/-1">
        <div class="res-item-label">Player</div>
        <div class="res-item-value" style="font-size:18px">${d.PlayerNickname || '—'}</div>
      </div>
      <div class="res-item">
        <div class="res-item-label">Before Likes</div>
        <div class="res-item-value big">${d.LikesbeforeCommand ?? '—'}</div>
      </div>
      <div class="res-item">
        <div class="res-item-label">Likes Given</div>
        <div class="res-item-value big highlight">+${given}</div>
      </div>
      <div class="res-item" style="grid-column:1/-1">
        <div class="res-item-label">Total Likes</div>
        <div class="res-item-value big">${d.LikesafterCommand ?? '—'}</div>
      </div>
    `;
    area.style.display = 'block';
  }

  function showError(msg) {
    const area = document.getElementById('response-area');
    const card = document.getElementById('res-card');
    const dot  = document.getElementById('res-dot');
    const txt  = document.getElementById('res-status-text');
    const grid = document.getElementById('res-grid');
    card.className = 'res-card error';
    dot.className  = 'status-dot dot-error';
    txt.className  = 'status-text text-error';
    txt.textContent = 'Error';
    grid.innerHTML = `<div class="res-item" style="grid-column:1/-1">
      <div class="res-item-label">Message</div>
      <div class="res-item-value" style="font-size:15px;color:var(--error)">${msg}</div>
    </div>`;
    area.style.display = 'block';
  }
</script>
</body>
</html>"""

ADMIN_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>7H SIAM - Admin Panel</title>
<link rel="icon" type="image/png" href="https://i.ibb.co.com/Dg5NNK2G/logo.png">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
<style>
  body { background: #060910; color: #e8f4fd; font-family: 'Outfit', sans-serif; padding: 20px; }
  .container { max-width: 800px; margin: 0 auto; background: #111820; padding: 30px; border-radius: 12px; border: 1px solid #1e2d3d; }
  h2 { color: #00d4ff; text-align: center; margin-bottom: 20px; }
  .form-group { display: flex; gap: 10px; margin-bottom: 20px; }
  input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #1e2d3d; background: #0d1117; color: white; }
  button { padding: 12px 20px; background: #00d4ff; color: #000; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; }
  button:hover { background: #0099cc; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th, td { border: 1px solid #1e2d3d; padding: 12px; text-align: left; }
  th { background: #0d1117; color: #00d4ff; }
  .btn-action { color: #00e676; cursor: pointer; font-weight: bold; margin-right: 8px; }
  .btn-action:hover { text-decoration: underline; }
  .btn-del { color: #ff4757; cursor: pointer; font-weight: bold; }
  .btn-del:hover { text-decoration: underline; }
</style>
</head>
<body>
  <div class="container">
    <h2>⚡ API Key Management</h2>
    <div class="form-group">
      <input type="text" id="newKey" placeholder="Enter New Key Name (e.g. STAR)">
      <input type="number" id="newLimit" placeholder="Limit">
      <button onclick="addKey()">+ Add Key</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>API Key</th>
          <th>Total Limit</th>
          <th>Used</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="keyList"></tbody>
    </table>
  </div>
  <script>
    function loadKeys() {
        fetch('/admin/api/keys').then(r=>r.json()).then(d=>{
            let h='';
            if(d && !d.error){
                for(let k in d) {
                    h+=`<tr>
                          <td>${k}</td>
                          <td>${d[k].limit}</td>
                          <td>${d[k].used}</td>
                          <td>
                            <span class="btn-action" onclick="editKey('${k}', ${d[k].limit})">Edit</span> |
                            <span class="btn-action" onclick="resetKey('${k}')">Reset</span> |
                            <span class="btn-del" onclick="delKey('${k}')">Delete</span>
                          </td>
                        </tr>`;
                }
            }
            document.getElementById('keyList').innerHTML=h;
        });
    }
    function addKey() {
        let k = document.getElementById('newKey').value;
        let l = document.getElementById('newLimit').value;
        if(!k || !l) return alert("Fill all fields!");
        let fd = new FormData(); fd.append('key', k); fd.append('limit', l);
        fetch('/admin/api/add', {method:'POST', body:fd}).then(()=>loadKeys());
    }
    function editKey(k, oldLimit) {
        let n = prompt("Enter new limit for " + k + ":", oldLimit);
        if(n !== null && n !== "") {
            let fd = new FormData(); fd.append('key', k); fd.append('limit', n);
            fetch('/admin/api/edit', {method:'POST', body:fd}).then(()=>loadKeys());
        }
    }
    function resetKey(k) {
        if(confirm('Reset usage for ' + k + ' to 0?')) {
            let fd = new FormData(); fd.append('key', k);
            fetch('/admin/api/reset', {method:'POST', body:fd}).then(()=>loadKeys());
        }
    }
    function delKey(k) {
        if(confirm('Are you sure?')){
            let fd = new FormData(); fd.append('key', k);
            fetch('/admin/api/delete', {method:'POST', body:fd}).then(()=>loadKeys());
        }
    }
    loadKeys();
  </script>
</body>
</html>"""

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_accounts(server_name):
    filename_map = {
        "IND": "account_ind.json", "BR": "account_br.json", "US": "account_br.json",
        "SAC": "account_br.json", "NA": "account_br.json",
    }
    filename = filename_map.get(server_name, "account_bd.json")
    if not os.path.exists(filename):
        for fallback in ["account_ind.json", "account_bd.json", "account_br.json"]:
            if os.path.exists(fallback):
                filename = fallback; break
        else: return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [{"uid": str(i["uid"]).strip(), "password": str(i["password"]).strip()} for i in data if i.get("uid") and i.get("password")]
    except:
        return []

def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv  = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode()

def enc(uid):
    msg = uid_generator_pb2.uid_generator()
    msg.krishna_   = int(uid)
    msg.teamXdarks = 1
    return encrypt_message(msg.SerializeToString())

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except:
        return None

def get_api_url(server_name, endpoint):
    if server_name == "IND": return f"https://client.ind.freefiremobile.com/{endpoint}"
    elif server_name in {"BR", "US", "SAC", "NA"}: return f"https://client.us.freefiremobile.com/{endpoint}"
    return f"https://clientbp.ggpolarbear.com/{endpoint}"

def get_player_info(encrypted_uid, server_name, token):
    url = get_api_url(server_name, "GetPlayerPersonalShow")
    edata = bytes.fromhex(encrypted_uid)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
        'X-GA': "v1 1", 'ReleaseVersion':"OB53"
    }
    try:
        r = requests.post(url, data=edata, headers=headers, verify=False, timeout=10)
        return decode_protobuf(r.content)
    except:
        return None

# ─── Async core ───────────────────────────────────────────────────────────────
async def generate_jwt_token(uid, password, session_obj):
    try:
        url = f"http://157.15.98.85:25565/generate-jwt?uid={uid}&password={urllib.parse.quote(password)}"
        async with session_obj.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                d = await r.json()
                return d.get('jwt_token') or d.get('token')
    except: pass
    return None

async def send_like_req(encrypted_uid, token, url, session_obj):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded",
            'X-GA': "v1 1", 'ReleaseVersion':"OB53"
        }
        async with session_obj.post(url, data=edata, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
            return r.status
    except: return 500

async def process_account(target_uid, encrypted_uid, account, url, semaphore, session_obj):
    async with semaphore:
        token = await generate_jwt_token(account['uid'], account['password'], session_obj)
        if not token: return 500, account['uid']
        status = await send_like_req(encrypted_uid, token, url, session_obj)
        if status == 200: liked_cache[target_uid].add(account['uid'])
        return status, account['uid']

async def get_token_fast(accounts, n=5):
    connector = aiohttp.TCPConnector(limit=n, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session_obj:
        tasks = [generate_jwt_token(a['uid'], a['password'], session_obj) for a in accounts[:n]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, str) and r: return r
    return None

async def send_all_likes_async(target_uid, server_name):
    proto = like_pb2.like()
    proto.uid = int(target_uid)
    proto.region = server_name
    encrypted_uid = encrypt_message(proto.SerializeToString())

    accounts = load_accounts(server_name)
    if not accounts: return {'success': 0, 'failed': 0, 'total': 0}

    already = liked_cache.get(target_uid, set())
    fresh = [a for a in accounts if a['uid'] not in already]
    random.shuffle(fresh)
    batch = fresh[:200]

    like_url = get_api_url(server_name, "LikeProfile")
    semaphore = asyncio.Semaphore(30)

    connector = aiohttp.TCPConnector(limit=60, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session_obj:
        tasks = [process_account(target_uid, encrypted_uid, a, like_url, semaphore, session_obj) for a in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if isinstance(r, tuple) and r[0] == 200)
    return {'success': success, 'failed': len(results)-success, 'total': len(accounts)}

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# Admin Panel UI & Auth
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        if request.form.get('password') == 'siam123@.':
            session['admin_logged_in'] = True
            return redirect('/admin')
        return render_template_string('<script>alert("Wrong Password!"); window.location.href="/admin";</script>')
    
    if not session.get('admin_logged_in'):
        return '''
        <body style="background:#060910; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
        <form method="post" style="display:flex; flex-direction:column; gap:15px; background:#111820; padding:40px; border-radius:10px; border:1px solid #1e2d3d;">
            <h2 style="color:#00d4ff; margin:0; text-align:center;">Admin Login</h2>
            <input type="password" name="password" placeholder="Password..." style="padding:12px; border-radius:5px; border:1px solid #1e2d3d; background:#0d1117; color:white;" required>
            <button type="submit" style="padding:12px; background:#00d4ff; color:black; font-weight:bold; cursor:pointer; border:none; border-radius:5px;">ENTER PANEL</button>
        </form>
        </body>
        '''
    return render_template_string(ADMIN_HTML_TEMPLATE)

# Admin API endpoints
@app.route('/admin/api/keys', methods=['GET'])
def admin_keys():
    if not session.get('admin_logged_in'): return jsonify({"error": "unauthorized"}), 401
    token = get_fb_token()
    res = requests.get(f"{FIREBASE_DB_URL}/keys.json?auth={token}").json()
    return jsonify(res if res else {})

@app.route('/admin/api/add', methods=['POST'])
def admin_add():
    if not session.get('admin_logged_in'): return jsonify({"error": "unauthorized"}), 401
    key = request.form.get('key')
    limit = int(request.form.get('limit', 0))
    token = get_fb_token()
    requests.put(f"{FIREBASE_DB_URL}/keys/{key}.json?auth={token}", json={"limit": limit, "used": 0})
    return jsonify({"success": True})

@app.route('/admin/api/edit', methods=['POST'])
def admin_edit():
    if not session.get('admin_logged_in'): return jsonify({"error": "unauthorized"}), 401
    key = request.form.get('key')
    limit = int(request.form.get('limit', 0))
    token = get_fb_token()
    requests.patch(f"{FIREBASE_DB_URL}/keys/{key}.json?auth={token}", json={"limit": limit})
    return jsonify({"success": True})

@app.route('/admin/api/reset', methods=['POST'])
def admin_reset():
    if not session.get('admin_logged_in'): return jsonify({"error": "unauthorized"}), 401
    key = request.form.get('key')
    token = get_fb_token()
    requests.patch(f"{FIREBASE_DB_URL}/keys/{key}.json?auth={token}", json={"used": 0})
    return jsonify({"success": True})

@app.route('/admin/api/delete', methods=['POST'])
def admin_del():
    if not session.get('admin_logged_in'): return jsonify({"error": "unauthorized"}), 401
    key = request.form.get('key')
    token = get_fb_token()
    requests.delete(f"{FIREBASE_DB_URL}/keys/{key}.json?auth={token}")
    return jsonify({"success": True})

# Like API
@app.route('/like', methods=['GET'])
def handle_like():
    uid         = request.args.get("uid", "").strip()
    server_name = request.args.get("server_name", "").upper()

    if not uid or not server_name:
        return jsonify({"error": "uid and server_name are required"}), 400

    valid_servers = {"IND","BR","US","SAC","NA","BD","RU"}
    if server_name not in valid_servers:
        return jsonify({"error": f"Invalid server. Use: {sorted(valid_servers)}"}), 400

    accounts = load_accounts(server_name) or load_accounts("IND")
    if not accounts:
        return jsonify({"error": "No accounts available"}), 500

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        token = loop.run_until_complete(get_token_fast(accounts, n=5))
        if not token:
            return jsonify({"error": "Token generation failed"}), 500

        encrypted_uid = enc(uid)

        # Before Request
        before = get_player_info(encrypted_uid, server_name, token)
        if before is None: return jsonify({"error": "Invalid UID or server"}), 200

        try:
            bd = json.loads(MessageToJson(before))
            before_like = int(bd['AccountInfo'].get('Likes', 0))
        except: return jsonify({"error": "Data parsing failed"}), 200

        # Send likes
        loop.run_until_complete(send_all_likes_async(uid, server_name))

        # After Request
        after = get_player_info(encrypted_uid, server_name, token)
        if after is None: return jsonify({"error": "Could not verify after likes"}), 200

        ad          = json.loads(MessageToJson(after))
        after_like  = int(ad['AccountInfo']['Likes'])
        player_id   = int(ad['AccountInfo']['UID'])
        player_name = str(ad['AccountInfo']['PlayerNickname'])
        like_given  = after_like - before_like
        status      = 1 if like_given > 0 else 2

        return jsonify({
            "LikesGivenByAPI":    like_given,
            "LikesafterCommand":  after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname":     player_name,
            "UID":                player_id,
            "status":             status
        })

    except Exception as e:
        return jsonify({"error": str(e), "status": 0}), 500
    finally:
        loop.close()

@app.route('/reset-cache', methods=['GET'])
def reset_cache():
    liked_cache.clear()
    return jsonify({"message": "Cache cleared"})

# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("🚀 7H SIAM Like Panel started!")
    print("🌐 Website: http://0.0.0.0:5001")
    print("🛠️ Admin Panel: http://0.0.0.0:5001/admin")
    print("📡 API Format: http://0.0.0.0:5001/like?server_name=BD&uid=UID")
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False, threaded=True)