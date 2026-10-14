"""
droplink bypass 本地網頁。
  python server.py                # 開 http://127.0.0.1:8777
貼 t.co / droplink 短鏈 → 解出 mediafire → 列出資料夾內所有檔案 + 直鏈。
"""
import json
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from droplink_bypass import extract_code, resolve, mediafire_list

HOST, PORT = "127.0.0.1", 8777

PAGE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DropLink Bypass</title>
<style>
  :root{
    --bg:#0f1115; --card:#171a21; --line:#2a2f3a; --fg:#e6e9ef;
    --muted:#8b93a5; --accent:#4f8cff; --accent2:#2bd9a3; --danger:#ff6b6b;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
    font:15px/1.5 -apple-system,"Segoe UI",system-ui,"Microsoft JhengHei",sans-serif}
  .wrap{max-width:860px;margin:0 auto;padding:32px 16px 64px}
  h1{font-size:22px;margin:0 0 4px}
  .sub{color:var(--muted);margin:0 0 24px;font-size:13px}
  .bar{display:flex;gap:8px;margin-bottom:20px}
  input[type=text]{flex:1;min-width:0;background:var(--card);border:1px solid var(--line);
    color:var(--fg);border-radius:10px;padding:12px 14px;font-size:14px}
  input:focus{outline:none;border-color:var(--accent)}
  button{background:var(--accent);color:#fff;border:0;border-radius:10px;
    padding:0 20px;font-size:14px;font-weight:600;cursor:pointer;white-space:nowrap}
  button:disabled{opacity:.5;cursor:default}
  .status{min-height:20px;color:var(--muted);font-size:13px;margin-bottom:16px}
  .status.err{color:var(--danger)}
  .meta{background:var(--card);border:1px solid var(--line);border-radius:10px;
    padding:12px 14px;margin-bottom:16px;font-size:13px;word-break:break-all;display:none}
  .meta a{color:var(--accent2);text-decoration:none}
  .meta a:hover{text-decoration:underline}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
  td.size,th.size{text-align:right;white-space:nowrap;color:var(--muted)}
  tr:hover td{background:#1c202a}
  .fname{word-break:break-word}
  .dl{color:var(--accent);text-decoration:none;font-weight:600;white-space:nowrap}
  .dl:hover{text-decoration:underline}
  .count{color:var(--muted);font-size:13px;margin:0 0 8px}
  .spin{display:inline-block;width:14px;height:14px;border:2px solid var(--line);
    border-top-color:var(--accent);border-radius:50%;animation:s .7s linear infinite;
    vertical-align:-2px;margin-right:6px}
  @keyframes s{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="wrap">
  <h1>DropLink Bypass</h1>
  <p class="sub">貼 t.co 或 droplink.co 短鏈,直接解出真實連結並列出 mediafire 資料夾內檔案。</p>
  <div class="bar">
    <input id="u" type="text" placeholder="https://t.co/... 或 https://droplink.co/xxxx 或短碼"
           autocomplete="off" autofocus>
    <button id="go">解析</button>
  </div>
  <div id="status" class="status"></div>
  <div id="meta" class="meta"></div>
  <p id="count" class="count"></p>
  <table id="tbl" style="display:none">
    <thead><tr><th>檔名</th><th class="size">大小</th><th>下載</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
const $ = s => document.querySelector(s);
const go = $('#go'), inp = $('#u'), st = $('#status'),
      meta = $('#meta'), tbl = $('#tbl'), rows = $('#rows'), count = $('#count');

function fmtSize(n){
  if(n==null) return '';
  const u=['B','KB','MB','GB']; let i=0;
  while(n>=1024 && i<u.length-1){n/=1024;i++;}
  return n.toFixed(i?1:0)+' '+u[i];
}
function esc(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML;}

async function run(){
  const url = inp.value.trim();
  if(!url) return;
  go.disabled = true;
  st.className='status'; st.innerHTML='<span class="spin"></span>解析中(含倒數等待,約數秒)…';
  meta.style.display='none'; tbl.style.display='none'; rows.innerHTML=''; count.textContent='';
  try{
    const r = await fetch('/api/resolve?url='+encodeURIComponent(url));
    const d = await r.json();
    if(!d.ok){ st.className='status err'; st.textContent='失敗:'+d.error; go.disabled=false; return; }
    st.textContent='完成。';
    meta.style.display='block';
    meta.innerHTML = '真實連結:<a href="'+esc(d.real_url)+'" target="_blank" rel="noopener">'
                   + esc(d.real_url)+'</a>'
                   + (d.message? '<br><span style="color:var(--muted)">server: '+esc(d.message)+'</span>':'');
    const files = d.files||[];
    if(files.length){
      count.textContent = files.length+' 個檔案';
      for(const f of files){
        const tr=document.createElement('tr');
        tr.innerHTML = '<td class="fname">'+esc(f.filename)+'</td>'
                     + '<td class="size">'+fmtSize(f.size)+'</td>'
                     + '<td>'+(f.download? '<a class="dl" href="'+esc(f.download)+'" target="_blank" rel="noopener">下載 ↗</a>':'—')+'</td>';
        rows.appendChild(tr);
      }
      tbl.style.display='table';
    } else {
      count.textContent = d.kind==='folder' ? '資料夾為空。' : '目標不是 mediafire 資料夾,只有上方直鏈。';
    }
  }catch(e){
    st.className='status err'; st.textContent='請求錯誤:'+e;
  }
  go.disabled=false;
}
go.onclick = run;
inp.onkeydown = e => { if(e.key==='Enter') run(); };
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")

        if parsed.path == "/api/resolve":
            qs = urllib.parse.parse_qs(parsed.query)
            url = (qs.get("url") or [""])[0]
            try:
                code = extract_code(url)
                res = resolve(code)
                real = res["url"]
                listing = mediafire_list(real)
                return self._send(200, json.dumps({
                    "ok": True,
                    "real_url": real,
                    "message": res.get("message"),
                    "kind": listing["kind"],
                    "files": listing["files"],
                }, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

        return self._send(404, json.dumps({"ok": False, "error": "not found"}))


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"DropLink Bypass web running at {url}  (Ctrl+C 結束)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        srv.shutdown()


if __name__ == "__main__":
    main()
