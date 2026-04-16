"""Settings dashboard — renders a single-page HTML settings UI."""

from __future__ import annotations

import json
from typing import Any


def render_dashboard(settings: dict[str, Any]) -> str:
    """Return a complete HTML page for the settings dashboard."""
    settings_json = json.dumps(settings, default=str).replace("</", "<\\/")
    return _TEMPLATE.replace("__SETTINGS_JSON__", settings_json)


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>JARVIS Settings</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}
  .card{background:#1e293b;border:1px solid #334155;border-radius:0.75rem;padding:1.5rem;margin-bottom:1.5rem}
  .btn{padding:0.5rem 1.25rem;border-radius:0.5rem;font-weight:600;cursor:pointer;transition:all .15s}
  .btn-primary{background:#3b82f6;color:#fff}.btn-primary:hover{background:#2563eb}
  .btn-secondary{background:#334155;color:#e2e8f0}.btn-secondary:hover{background:#475569}
  input[type=text],select{background:#0f172a;border:1px solid #475569;color:#e2e8f0;
    padding:0.5rem 0.75rem;border-radius:0.375rem;width:100%}
  input[type=text]:focus,select:focus{outline:none;border-color:#3b82f6}
  label{font-size:0.875rem;color:#94a3b8;display:block;margin-bottom:0.25rem}
  .toggle{position:relative;width:3rem;height:1.5rem;background:#475569;border-radius:9999px;
    cursor:pointer;transition:background .2s}
  .toggle.on{background:#3b82f6}
  .toggle::after{content:'';position:absolute;top:2px;left:2px;width:1.25rem;height:1.25rem;
    background:#fff;border-radius:50%;transition:transform .2s}
  .toggle.on::after{transform:translateX(1.5rem)}
  .section-title{font-size:1.25rem;font-weight:700;margin-bottom:1rem;color:#f8fafc}
  .toast{position:fixed;bottom:1.5rem;right:1.5rem;padding:0.75rem 1.5rem;border-radius:0.5rem;
    background:#22c55e;color:#fff;font-weight:600;opacity:0;transition:opacity .3s;z-index:50}
  .toast.show{opacity:1}
  table{width:100%;border-collapse:collapse}
  th,td{padding:0.5rem;text-align:center;border-bottom:1px solid #334155}
  th{color:#94a3b8;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em}
  td:first-child,th:first-child{text-align:left}
</style>
</head>
<body>
<div class="max-w-3xl mx-auto py-8 px-4">
<h1 class="text-3xl font-bold mb-1">JARVIS Settings</h1>
<p class="text-slate-400 mb-8">Configure your assistant. Changes save to TOML config files.</p>

<!-- Personality -->
<div class="card" id="sec-personality">
  <div class="section-title">Personality</div>
  <div class="grid grid-cols-2 gap-4 mb-4">
    <div><label>Assistant Name</label>
      <input type="text" id="p-name" /></div>
    <div><label>User Display Name</label>
      <input type="text" id="p-user" /></div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('personality')">Save Personality</button>
</div>

<!-- Voice -->
<div class="card" id="sec-voice">
  <div class="section-title">Voice</div>
  <div class="grid grid-cols-3 gap-4 mb-4">
    <div><label>Profile</label>
      <select id="v-profile"><option>default</option><option>warm</option>
        <option>professional</option></select></div>
    <div><label>Hotkey</label>
      <input type="text" id="v-hotkey" /></div>
    <div class="flex items-end gap-2">
      <label>Wake Word</label>
      <div id="v-wake" class="toggle" onclick="toggleEl(this)"></div>
    </div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('voice')">Save Voice</button>
</div>

<!-- Behavior -->
<div class="card" id="sec-behavior">
  <div class="section-title">Behavior</div>
  <div class="flex gap-8 mb-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-slate-300">Use Claude for Chat</span>
      <div id="b-claude" class="toggle" onclick="toggleEl(this)"></div>
    </div>
    <div class="flex items-center gap-2">
      <span class="text-sm text-slate-300">Do Not Disturb</span>
      <div id="b-dnd" class="toggle" onclick="toggleEl(this)"></div>
    </div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('behavior')">Save Behavior</button>
</div>

<!-- Scout Sources -->
<div class="card" id="sec-scout">
  <div class="section-title">Scout Sources</div>
  <div id="scout-list" class="space-y-2 mb-4"></div>
  <button class="btn btn-primary" onclick="saveSection('scout_sources')">Save Sources</button>
</div>

<!-- Contacts -->
<div class="card" id="sec-contacts">
  <div class="section-title">Contact Nicknames</div>
  <div id="contacts-list" class="space-y-2 mb-4"></div>
  <button class="btn btn-primary" onclick="saveSection('contacts')">Save Contacts</button>
</div>

<!-- Control Tiers -->
<div class="card" id="sec-tiers">
  <div class="section-title">CONTROL Tier Assignments</div>
  <div class="grid grid-cols-2 gap-4 mb-4">
    <div><label>Low Stakes (auto-execute)</label>
      <div id="tier-low" class="text-sm text-slate-300 mt-1"></div></div>
    <div><label>High Stakes (confirm first)</label>
      <div id="tier-high" class="text-sm text-slate-300 mt-1"></div></div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('control_tiers')">Save Tiers</button>
</div>

<!-- Briefing -->
<div class="card" id="sec-briefing">
  <div class="section-title">Briefing Preferences</div>
  <div class="grid grid-cols-2 gap-4 mb-4">
    <div><label>Time</label><input type="text" id="br-time" /></div>
    <div><label>Timezone</label><input type="text" id="br-tz" /></div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('briefing')">Save Briefing</button>
</div>

<!-- Notifications -->
<div class="card" id="sec-notif">
  <div class="section-title">Notification Matrix</div>
  <table id="notif-table" class="mb-4">
    <thead><tr><th>Event</th><th>macOS</th><th>Telegram</th><th>Voice</th><th>Silent</th></tr></thead>
    <tbody id="notif-body"></tbody>
  </table>
  <button class="btn btn-primary" onclick="saveNotifications()">Save Notifications</button>
</div>

<!-- Privacy -->
<div class="card" id="sec-privacy">
  <div class="section-title">Privacy &amp; Data</div>
  <div class="flex gap-8 mb-4">
    <div class="flex items-center gap-2">
      <span class="text-sm text-slate-300">Telemetry</span>
      <div id="pr-tele" class="toggle" onclick="toggleEl(this)"></div>
    </div>
    <div class="flex items-center gap-2">
      <span class="text-sm text-slate-300">Local Only</span>
      <div id="pr-local" class="toggle" onclick="toggleEl(this)"></div>
    </div>
  </div>
  <button class="btn btn-primary" onclick="saveSection('privacy')">Save Privacy</button>
  <button class="btn btn-secondary ml-2" onclick="exportData()">Export All Data</button>
</div>

<div class="toast" id="toast">Saved</div>
</div>

<script>
const S = __SETTINGS_JSON__;
const channels = ['macos','telegram','voice','silent'];

function toggleEl(el){el.classList.toggle('on')}
function isOn(el){return el.classList.contains('on')}
function setToggle(id,v){const el=document.getElementById(id);if(v)el.classList.add('on');else el.classList.remove('on')}
function toast(msg){const t=document.getElementById('toast');t.textContent=msg||'Saved';
  t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2000)}

// Populate simple fields
document.getElementById('p-name').value=S.personality?.assistant_name||S.personality?.identity?.assistant_name||'';
document.getElementById('p-user').value=S.personality?.user_display_name||S.personality?.identity?.user_display_name||'';
document.getElementById('v-profile').value=S.voice?.profile||'default';
document.getElementById('v-hotkey').value=S.voice?.hotkey||'';
setToggle('v-wake',S.voice?.wake_word_enabled);
setToggle('b-claude',S.behavior?.use_claude_for_chat);
setToggle('b-dnd',S.behavior?.do_not_disturb);
setToggle('pr-tele',S.privacy?.telemetry_enabled);
setToggle('pr-local',S.privacy?.local_only);
document.getElementById('br-time').value=S.briefing?.time||'07:00';
document.getElementById('br-tz').value=S.briefing?.timezone||'';

// Scout sources — safe DOM construction
(function(){
  var sl=document.getElementById('scout-list');
  var sources=S.scout_sources?.sources||{};
  Object.keys(sources).forEach(function(k){
    var v=sources[k];
    var row=document.createElement('div');row.className='flex items-center gap-2';
    var tog=document.createElement('div');tog.className='toggle'+(v.enabled?' on':'');
    tog.setAttribute('data-src',k);tog.onclick=function(){toggleEl(this)};
    var name=document.createElement('span');name.className='text-sm text-slate-300';name.textContent=k;
    var cad=document.createElement('span');cad.className='text-xs text-slate-500';cad.textContent=v.cadence||'';
    row.appendChild(tog);row.appendChild(name);row.appendChild(cad);sl.appendChild(row);
  });
})();

// Contacts — safe DOM construction
(function(){
  var cl=document.getElementById('contacts-list');
  var nicks=S.contacts?.nicknames||{};
  Object.keys(nicks).forEach(function(k){
    var row=document.createElement('div');row.className='flex gap-2';
    var inp1=document.createElement('input');inp1.type='text';inp1.value=k;inp1.className='w-32';
    inp1.setAttribute('data-nick-key','');
    var inp2=document.createElement('input');inp2.type='text';inp2.value=nicks[k];inp2.className='flex-1';
    inp2.setAttribute('data-nick-val','');
    row.appendChild(inp1);row.appendChild(inp2);cl.appendChild(row);
  });
})();

// Control tiers
document.getElementById('tier-low').textContent=(S.control_tiers?.low_stakes||[]).join(', ');
document.getElementById('tier-high').textContent=(S.control_tiers?.high_stakes||[]).join(', ');

// Notification matrix — safe DOM construction
(function(){
  var nb=document.getElementById('notif-body');
  var notifs=S.notifications||{};
  Object.keys(notifs).forEach(function(ev){
    var ch=notifs[ev];
    var tr=document.createElement('tr');
    var tdName=document.createElement('td');tdName.className='text-sm text-slate-300';
    tdName.textContent=ev.replace(/_/g,' ');tr.appendChild(tdName);
    channels.forEach(function(c){
      var td=document.createElement('td');
      var cb=document.createElement('input');cb.type='checkbox';
      cb.setAttribute('data-ev',ev);cb.setAttribute('data-ch',c);
      if(ch[c])cb.checked=true;
      td.appendChild(cb);tr.appendChild(td);
    });
    nb.appendChild(tr);
  });
})();

// Save helpers
async function saveSection(section){
  var body={};
  if(section==='personality')body={identity:{assistant_name:document.getElementById('p-name').value,
    user_display_name:document.getElementById('p-user').value}};
  else if(section==='voice')body={profile:document.getElementById('v-profile').value,
    hotkey:document.getElementById('v-hotkey').value,wake_word_enabled:isOn(document.getElementById('v-wake'))};
  else if(section==='behavior')body={use_claude_for_chat:isOn(document.getElementById('b-claude')),
    do_not_disturb:isOn(document.getElementById('b-dnd'))};
  else if(section==='scout_sources'){
    var srcs={};var sources=S.scout_sources?.sources||{};
    document.querySelectorAll('[data-src]').forEach(function(el){
      srcs[el.getAttribute('data-src')]={enabled:isOn(el),cadence:(sources[el.getAttribute('data-src')]||{}).cadence||'daily'};
    });body={sources:srcs};
  }else if(section==='contacts'){
    var n={};var keys=document.querySelectorAll('[data-nick-key]');
    var vals=document.querySelectorAll('[data-nick-val]');
    keys.forEach(function(el,i){if(el.value)n[el.value]=vals[i].value;});
    body={nicknames:n};
  }else if(section==='control_tiers'){body=S.control_tiers||{};}
  else if(section==='briefing')body={time:document.getElementById('br-time').value,
    timezone:document.getElementById('br-tz').value,sections_enabled:S.briefing?.sections_enabled||{}};
  else if(section==='privacy')body={telemetry_enabled:isOn(document.getElementById('pr-tele')),
    local_only:isOn(document.getElementById('pr-local')),auto_delete_logs_days:30};
  var r=await fetch('/settings/'+section,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(r.ok)toast();else toast('Error saving');
}

async function saveNotifications(){
  var body={};
  document.querySelectorAll('#notif-table input[type=checkbox]').forEach(function(cb){
    var ev=cb.getAttribute('data-ev');var ch=cb.getAttribute('data-ch');
    if(!body[ev])body[ev]={};body[ev][ch]=cb.checked;});
  var r=await fetch('/settings/notifications',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(r.ok)toast();else toast('Error saving');
}

async function exportData(){
  var r=await fetch('/settings/export',{method:'POST'});
  var d=await r.json();toast('Exported to '+d.path);
}
</script>
</body>
</html>"""
