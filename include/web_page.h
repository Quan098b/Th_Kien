#pragma once

// Dashboard served at "/". Polls /api/state; no external resources.
static const char kWebPage[] = R"HTML(<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nhận diện giọng nói</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#1d2330;--mute:#6b7280;--line:#e5e7eb;
--on:#16a34a;--off:#2563eb;--noise:#9ca3af;--bad:#dc2626;--lamp:#facc15}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#181c24;--ink:#e8eaf0;
--mute:#9aa3b2;--line:#2a303c;--noise:#6b7280}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px;display:grid;gap:14px;
grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
header{max-width:980px;margin:0 auto;padding:16px 16px 0;display:flex;justify-content:space-between;
align-items:center;gap:8px;flex-wrap:wrap}
h1{font-size:19px;margin:0}h2{font-size:13px;margin:0 0 10px;color:var(--mute);
text-transform:uppercase;letter-spacing:.05em}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.wide{grid-column:1/-1}
#conn{font-size:13px;padding:4px 10px;border-radius:99px;background:var(--line)}
#conn.ok{background:var(--on);color:#fff}#conn.err{background:var(--bad);color:#fff}
#hero{display:flex;align-items:center;gap:18px}
#badge{flex:1;border-radius:12px;padding:18px;color:#fff;background:var(--noise);transition:background .2s}
#badge .big{font-size:30px;font-weight:700}#badge .sub{opacity:.9}
#badge.flash{animation:fl .6s}@keyframes fl{0%{transform:scale(1.04)}100%{transform:none}}
.lamp{width:92px;text-align:center;font-size:13px;color:var(--mute)}
.bulb{width:64px;height:64px;margin:0 auto 6px;border-radius:50%;background:var(--line);
transition:all .3s}.bulb.on{background:var(--lamp);box-shadow:0 0 30px 8px var(--lamp)}
.row{display:flex;align-items:center;gap:10px;margin:7px 0}
.row .n{width:78px;font-size:14px}.row .v{width:56px;text-align:right;font-variant-numeric:tabular-nums}
.bar{flex:1;height:14px;background:var(--line);border-radius:7px;overflow:hidden}
.bar i{display:block;height:100%;width:0;border-radius:7px;transition:width .25s}
.chk{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);font-size:14px}
.chk:last-child{border:0}.chk b{font-variant-numeric:tabular-nums}
.ok{color:var(--on)}.no{color:var(--bad)}
#hist{list-style:none;margin:0;padding:0;max-height:300px;overflow:auto}
#hist li{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--line);font-size:14px}
#hist .t{color:var(--mute);width:62px;font-variant-numeric:tabular-nums}
.dot{width:10px;height:10px;border-radius:50%;margin-top:6px;flex:none}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center}
.stats div{background:var(--bg);border-radius:10px;padding:8px}.stats b{display:block;font-size:22px}
.note{color:var(--mute);font-size:13px;margin:8px 0 0}
</style></head><body>
<header><h1>Nhận diện giọng nói · ESP32-S3</h1><span id="conn">Đang kết nối…</span></header>
<main>
<section class="card wide"><div id="hero">
<div id="badge"><div class="big" id="kind">—</div><div class="sub" id="detail">Chờ dữ liệu…</div></div>
<div class="lamp"><div class="bulb" id="bulb"></div><span id="lampTxt">LED: tắt</span></div>
</div><p class="note">Nói “bật đèn” hoặc “tắt đèn” gần micro. Biểu tượng đèn hiển thị trạng thái LED thật ở GPIO7.</p></section>

<section class="card"><h2>Xác suất model</h2><div id="probs"></div>
<p class="note">Model luôn chọn nhãn cao nhất, kể cả khi không phải lệnh. Chỉ Bật/Tắt đèn kèm bộ lọc đạt mới được chấp nhận.</p></section>

<section class="card"><h2>Bộ lọc giọng nói</h2><div id="gate"></div>
<p class="note" id="gateSum"></p></section>

<section class="card"><h2>Mức âm thanh</h2>
<div class="row"><span class="n">RMS</span><div class="bar"><i id="rmsBar"></i></div><span class="v" id="rmsV">—</span></div>
<div class="stats" style="margin-top:12px">
<div><b id="cBat">0</b>Bật đèn</div><div><b id="cTat">0</b>Tắt đèn</div>
<div><b id="cNoise">0</b>Nhiễu</div><div><b id="cSil">0</b>Im lặng</div></div>
<p class="note" id="meta"></p></section>

<section class="card"><h2>Lịch sử gần đây</h2><ul id="hist"></ul></section>
</main>
<script>
const L={Bat_Den:"Bật đèn",Tap_Am:"Tạp âm",Tat_Den:"Tắt đèn",Unknown:"Không rõ"};
const K={BAT_DEN:["BẬT ĐÈN","var(--on)"],TAT_DEN:["TẮT ĐÈN","var(--off)"],
NOISE:["Không phải lệnh","var(--noise)"],SILENCE:["Im lặng","var(--noise)"]};
const PC={Bat_Den:"var(--on)",Tat_Den:"var(--off)",Tap_Am:"var(--noise)",Unknown:"var(--noise)"};
const $=id=>document.getElementById(id);let last=-1;
function pct(x){return(x*100).toFixed(1)+"%"}
function render(s){
 $("conn").className="ok";$("conn").textContent="Trực tiếp · "+s.ip;
 $("bulb").className="bulb"+(s.lamp?" on":"");$("lampTxt").textContent="LED: "+(s.lamp?"bật":"tắt");
 $("cBat").textContent=s.counts[0];$("cTat").textContent=s.counts[1];
 $("cNoise").textContent=s.counts[2];$("cSil").textContent=s.counts[3];
 $("meta").textContent="Cửa sổ #"+s.seq+" · nguồn "+s.source+" · DSP "+s.dsp_ms+" ms · NN "+s.nn_ms+" ms · chạy "+Math.round(s.uptime/1000)+" s";
 if(s.seq===last||s.seq===0)return;last=s.seq;
 const k=K[s.kind]||K.NOISE,b=$("badge");b.style.background=k[1];$("kind").textContent=k[0];
 $("detail").textContent=s.kind==="SILENCE"?"Âm lượng quá nhỏ (RMS "+s.rms.toFixed(0)+")":
  "Model: "+L[s.label]+" "+pct(s.conf)+(s.accept?" · CHẤP NHẬN":" · TỪ CHỐI");
 if(s.accept){b.classList.remove("flash");void b.offsetWidth;b.classList.add("flash")}
 $("probs").innerHTML=s.labels.map((l,i)=>`<div class="row"><span class="n">${L[l]}</span>
  <div class="bar"><i style="width:${s.probs[i]*100}%;background:${PC[l]}"></i></div>
  <span class="v">${pct(s.probs[i])}</span></div>`).join("");
 const g=s.gate,t=s.th;const c=[
  ["Âm lượng (RMS)",s.rms.toFixed(0),"≥ "+t.rms,s.rms>=t.rms],
  ["Tỉ lệ khung có tiếng",g.active.toFixed(3),"≥ "+t.active,g.active>=t.active],
  ["Độ phẳng phổ (nhiễu trắng)",g.flat.toFixed(3),"≤ "+t.flat,g.flat<=t.flat],
  ["Năng lượng tần thấp (ù)",g.low.toFixed(3),"≤ "+t.low,g.low<=t.low],
  ["Tỉ lệ qua điểm 0",g.zcr.toFixed(3),"≥ "+t.zcr,g.zcr>=t.zcr]];
 $("gate").innerHTML=c.map(r=>`<div class="chk"><span>${r[3]?"✔":"✘"} ${r[0]}</span>
  <span><b class="${r[3]?"ok":"no"}">${r[1]}</b> <small>${r[2]}</small></span></div>`).join("");
 $("gateSum").textContent=g.pass?"Bộ lọc: ĐẠT — âm thanh giống giọng nói.":"Bộ lọc: KHÔNG ĐẠT — bị loại trước khi xét lệnh.";
 $("gateSum").className="note "+(g.pass?"ok":"no");
 const r=Math.min(1,Math.log10(1+s.rms)/Math.log10(2001));$("rmsBar").style.width=r*100+"%";
 $("rmsBar").style.background=s.rms<t.rms?"var(--noise)":"var(--on)";$("rmsV").textContent=s.rms.toFixed(0);
 $("hist").innerHTML=s.history.map(h=>{const kk=K[h.k]||K.NOISE;
  return `<li><span class="t">${(h.ms/1000).toFixed(1)}s</span><span class="dot" style="background:${kk[1]}"></span>
  <span>${kk[0]}${h.k==="SILENCE"?"":" · "+L[h.l]+" "+pct(h.c)} · RMS ${h.r}</span></li>`}).join("");
}
function poll(){fetch("/api/state",{cache:"no-store"}).then(r=>r.json()).then(render)
 .catch(()=>{$("conn").className="err";$("conn").textContent="Mất kết nối"})
 .finally(()=>setTimeout(poll,400))}
poll();
</script></body></html>)HTML";
