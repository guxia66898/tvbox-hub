"""体检面板：单文件自包含 HTML（无外部资源，离线可用，GitHub Pages 友好）。"""
from __future__ import annotations

import json


_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TVBox 线路中枢 · 体检面板</title>
<style>
  :root { --bg:#f1f5f9; --card:#fff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0;
          --ok:#16a34a; --bad:#dc2626; --warn:#d97706; --primary:#2563eb; --violet:#7c3aed; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --line:#334155; } }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; padding-bottom:60px; }
  .wrap { max-width:1080px; margin:0 auto; padding:0 16px; }
  header { padding:18px 0 10px; }
  header h1 { font-size:20px; font-weight:800; }
  header .sub { color:var(--muted); font-size:12px; margin-top:4px; line-height:1.6; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; margin:12px 0; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; text-align:center; }
  .card .num { font-size:22px; font-weight:800; font-variant-numeric:tabular-nums; }
  .card .num.ok { color:var(--ok); } .card .num.vi { color:var(--violet); }
  .card .label { color:var(--muted); font-size:11px; margin-top:2px; }
  section { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin-bottom:14px; }
  section h2 { font-size:14px; margin-bottom:10px; }
  .diff .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
  .chip { font-size:11px; padding:2px 9px; border-radius:999px; max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .chip.g { background:rgba(22,163,74,.12); color:var(--ok); }
  .chip.r { background:rgba(220,38,38,.12); color:var(--bad); }
  .none { color:var(--muted); font-size:12px; }
  .filters { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
  .filters input, .filters select { background:var(--bg); color:var(--text); border:1px solid var(--line); border-radius:8px; padding:7px 10px; font-size:12px; }
  .filters input { flex:1 1 200px; }
  .count { color:var(--muted); font-size:11px; margin-left:auto; align-self:center; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th { text-align:left; color:var(--muted); font-weight:600; padding:6px 8px; border-bottom:1px solid var(--line); white-space:nowrap; }
  td { padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
  td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
  td .u { color:var(--muted); font-size:10px; word-break:break-all; }
  .badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:10px; font-weight:600; color:#fff; }
  .b-ok { background:var(--ok); } .b-bad { background:var(--bad); } .b-new { background:var(--primary); } .b-dead { background:var(--warn); }
  .pc-g { color:var(--ok); font-weight:700; } .pc-y { color:var(--warn); font-weight:700; } .pc-r { color:var(--bad); font-weight:700; } .pc-n { color:var(--muted); }
  tr.err td { opacity:.62; }
  footer { color:var(--muted); font-size:11px; text-align:center; padding:16px 0; line-height:1.8; }
  @media (max-width:640px) { .hide-sm { display:none; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>TVBox 线路中枢 · 体检面板</h1>
    <div class="sub" id="meta"></div>
  </header>
  <div class="cards" id="cards"></div>
  <section id="trendSec"><h2>可用趋势</h2><div id="trend"></div></section>
  <section class="diff"><h2>与上次快照差异</h2><div id="diff"></div></section>
  <section>
    <h2>线路明细</h2>
    <div class="filters">
      <input id="kw" type="text" placeholder="搜索名称或地址…">
      <select id="fKind"><option value="">全部类型</option><option value="single">单线路</option>
        <option value="multi_storehouse">多仓 storeHouse</option><option value="multi_urls">多仓 urls</option>
        <option value="unknown">未知</option></select>
      <select id="fStatus"><option value="">全部状态</option><option value="ok">可用</option><option value="fail">不可用</option></select>
      <span class="count" id="cnt"></span>
    </div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>名称</th><th>类型</th><th class="hide-sm">格式</th><th>耗时</th><th class="hide-sm">速度</th>
        <th>站点</th><th>L2 通过率</th><th>状态</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    </div>
  </section>
  <footer>由 tvbox-hub 生成 · 仅做接口可用性检测与汇总，不存储/分发任何内容<br>
    数据来源：内置种子线路 + 聚合页自动采集 · 三个订阅产物：merged.json / curated.json / tvbox.json</footer>
</div>
<script>
const DATA = __DATA__;
const R = DATA.report || {}, H = DATA.history || [];
const KIND = {single:"单线路", multi_storehouse:"多仓 storeHouse", multi_urls:"多仓 urls", unknown:"未知"};
const FMT = {plain_json:"明文JSON", json_relaxed:"带注释JSON", image_stego:"图片隐写", aes_hex:"2423加密", base64_json:"Base64"};
const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MAX_ROWS = 400;   // 首屏渲染上限（千级节点时避免卡顿）
const rows = [];
(function walk(list, d){ for (const n of (list||[])) { rows.push(Object.assign({}, n, {_d:d})); walk(n.children, d+1); } })(R.lines, 0);
const nAvail = new Set((R.diff&&R.diff.newly_available)||[]);
const nDead = new Set((R.diff&&R.diff.newly_dead)||[]);
const m = R.meta||{}, s = R.summary||{};
document.getElementById("meta").textContent =
  "生成于 " + esc((m.generated_at||"").replace("T"," ").slice(0,19)) + " UTC"
  + " · 耗时 " + esc(m.duration_s) + "s"
  + " · 采集页 " + ((m.harvest&&m.harvest.pages_ok)||0) + "/" + ((m.harvest&&m.harvest.pages)||0)
  + " · L2 抽样 " + (m.l2_enabled ? "开" : "关");
const cards = [["线路总数", s.lines_total, ""],["可用", s.available, "ok"],["可用单仓", s.singles_ok, "ok"],
  ["可用多仓", s.multis_ok, "vi"],["平均响应", s.avg_total_ms!=null ? s.avg_total_ms+"ms" : "-", ""],
  ["L2 抽样节点", s.l2_probed, ""]];
document.getElementById("cards").innerHTML = cards.map(c =>
  '<div class="card"><div class="num '+c[2]+'">'+esc(c[1])+'</div><div class="label">'+esc(c[0])+'</div></div>').join("");
// 趋势图（内联 SVG）
(function(){
  if (!H.length) { document.getElementById("trendSec").style.display="none"; return; }
  const W=1000, Hh=150, P=24, n=H.length;
  const maxV = Math.max(1, ...H.map(p => Math.max(p.lines_total||0, p.available||0)));
  const x = i => n===1 ? W/2 : P + i*(W-2*P)/(n-1);
  const y = v => Hh-P - v*(Hh-2*P)/maxV;
  const poly = key => H.map((p,i)=>x(i)+","+y(p[key]||0)).join(" ");
  const lab = H.map((p,i)=> (i===0||i===n-1) ? '<text x="'+x(i)+'" y="'+(Hh-4)+'" font-size="10" fill="#94a3b8" text-anchor="middle">'+esc(p.date)+'</text>' : '').join("");
  const end = '<text x="'+(W-P)+'" y="'+y(H[n-1].available||0)-6+'" font-size="11" fill="#16a34a">'+esc(H[n-1].available)+'</text>';
  document.getElementById("trend").innerHTML =
    '<svg viewBox="0 0 '+W+' '+Hh+'" style="width:100%;height:auto">'
    + '<polyline points="'+poly("lines_total")+'" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4 3"/>'
    + '<polyline points="'+poly("available")+'" fill="none" stroke="#16a34a" stroke-width="2.5"/>'
    + lab + end + '</svg>'
    + '<div style="color:#94a3b8;font-size:11px;margin-top:4px">— 可用（绿） · 总线路（灰虚线）· 共 '+n+' 次快照，纵轴 0-'+maxV+'</div>';
})();
// 差异区
(function(){
  const d = R.diff||{}, na = d.newly_available||[], nd = d.newly_dead||[];
  let html = "";
  html += "<div>今日新增可用（"+na.length+"）</div><div class='chips'>"
    + (na.length ? na.slice(0,40).map(u=>"<span class='chip g'>"+esc(u)+"</span>").join("") : "<span class='none'>无</span>") + "</div>";
  html += "<div style='margin-top:10px'>今日失效（"+nd.length+"）</div><div class='chips'>"
    + (nd.length ? nd.slice(0,40).map(u=>"<span class='chip r'>"+esc(u)+"</span>").join("") : "<span class='none'>无</span>") + "</div>";
  document.getElementById("diff").innerHTML = html;
})();
// 明细表
function fmtMs(v){ return v==null ? "-" : Math.round(v)+"ms"; }
function fmtSp(v){ if (v==null) return "-"; return v>=1024 ? (v/1024).toFixed(2)+"MB/s" : v.toFixed(0)+"KB/s"; }
function pc(v){ if (v==null) return "<span class='pc-n'>未抽样</span>";
  const cls = v>=0.8?"pc-g":(v>=0.5?"pc-y":"pc-r"); return "<span class='"+cls+"'>"+Math.round(v*100)+"%</span>"; }
function render(){
  const kw = document.getElementById("kw").value.trim().toLowerCase();
  const fk = document.getElementById("fKind").value, fs = document.getElementById("fStatus").value;
  let shown = 0;
  const html = rows.map(n => {
    const hay = ((n.name||"")+" "+(n.url||"")).toLowerCase();
    if (kw && !hay.includes(kw)) return "";
    if (fk && n.kind !== fk) return "";
    if (fs && n.status !== fs) return "";
    shown++;
    if (shown > MAX_ROWS) return "";   // 限制首屏行数，避免千级节点卡顿
    const ok = n.status === "ok";
    const extra = nAvail.has(n.url) ? " <span class='badge b-new'>新增</span>"
                : nDead.has(n.url) ? " <span class='badge b-dead'>失效</span>" : "";
    const kindB = n.kind==="single" ? "单线路" : (n.kind&&n.kind.startsWith("multi")) ? "多仓" : "未知";
    const subOk = (n.kind||"").startsWith("multi") ? " <span style='color:var(--muted)'>✓"+(n.children||[]).filter(c=>c.status==="ok").length+"</span>" : "";
    return "<tr class='"+(ok?"":"err")+"'>"
      + "<td><div style='padding-left:"+(n._d*12)+"px'><b>"+esc(n.name||"(未命名)")+"</b>"+extra+"</div><div class='u'>"+esc(n.url)+"</div>"
      + (ok?"":(n.error?"<div class='u' style='color:var(--bad)'>"+esc(n.error)+"</div>":""))+"</td>"
      + "<td>"+kindB+"</td>"
      + "<td class='hide-sm'>"+esc(FMT[n.format]||"-")+"</td>"
      + "<td class='num'>"+fmtMs(n.total_ms)+"</td>"
      + "<td class='num hide-sm'>"+fmtSp(n.speed_kbps)+"</td>"
      + "<td class='num'>"+(n.site_count||0)+(subOk)+"</td>"
      + "<td>"+pc(n.l2&&n.l2.pass_rate)+"</td>"
      + "<td><span class='badge "+(ok?"b-ok":"b-bad")+"'>"+(ok?"可用":"不可用")+"</span></td></tr>";
  }).join("");
  document.getElementById("rows").innerHTML = html || "<tr><td colspan='8' style='text-align:center;color:var(--muted)'>无匹配线路</td></tr>";
  document.getElementById("cnt").textContent = "显示 " + Math.min(shown, MAX_ROWS) + " / " + rows.length + " 条"
    + (shown > MAX_ROWS ? "（已截断，请用筛选缩小范围）" : "");
}
document.getElementById("kw").oninput = render;
document.getElementById("fKind").onchange = render;
document.getElementById("fStatus").onchange = render;
render();
</script>
</body>
</html>
"""


def build_panel(report: dict, history: list, out_path: str) -> None:
    """生成体检面板 HTML：report 与 history 内嵌进页面。"""
    payload = json.dumps({"report": report, "history": history},
                         ensure_ascii=False).replace("</", "<\\/")
    html = _HTML.replace("__DATA__", payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
