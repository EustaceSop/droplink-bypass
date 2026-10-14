# DropLink Bypass

貼上 `t.co` 或 `droplink.co` 短鏈,直接解出背後的真實連結(mediafire),並列出資料夾內所有檔案與各自的下載直鏈——跳過廣告、倒數計時與 reCAPTCHA。

```
t.co/xxxx  ──展開──▶  droplink.co/xxxx  ──繞過──▶  mediafire 資料夾  ──列檔──▶  檔案清單 + 直鏈
```

## 檔案

| 檔案 | 用途 |
|------|------|
| `droplink_bypass.py` | 核心邏輯:t.co 展開、droplink 繞過、mediafire 列檔。也可當 CLI 單獨使用。 |
| `server.py` | 本地網頁 UI(Python 標準庫,零第三方依賴)。 |

## 需求

- Python 3.7+
- 無任何第三方套件(只用標準庫 `urllib` / `http.server`)

## 使用

### 網頁(推薦)

```bash
cd droplink-bypass
python server.py
```

自動開啟瀏覽器到 `http://127.0.0.1:8777`。貼上短鏈(或純短碼)→ 按「解析」,畫面顯示真實連結與檔案表格(檔名 / 大小 / 下載直鏈)。`Ctrl+C` 結束服務。

### 命令列

```bash
python droplink_bypass.py 1sL9y                       # 短碼
python droplink_bypass.py https://droplink.co/1sL9y   # 完整 URL
python droplink_bypass.py 1sL9y --json                # 輸出完整 JSON
```

輸出為解析後的真實連結(`--json` 時為含 `status` / `url` 的完整回應)。

## 繞過原理

droplink.co 把「是否發連結」的判斷幾乎全放在前端,伺服器端只信任三樣可被偽造或被動等待的東西:

1. **Referer 白名單** — 以合作發布站(如 `game5s.com`)的 Referer 冒充「已走完導流」,伺服器直接回含表單的最終頁,跳過廣告關卡。
2. **表單 Token 可複用** — 最終頁的 CakePHP `go-link` 表單(`_csrfToken` / `ad_form_data` / `_Token[*]`)在產生時即簽發,不綁定使用者是否真的互動,原樣 POST 回 `/links/go` 即被接受。
3. **reCAPTCHA 未做 server-side 驗證** — 後端對空的 `g-recaptcha-response` 照收,驗證碼純屬前端擺設。

唯一真正的服務端檢查是頁面內的倒數秒數(`counter_value`),腳本老實 `sleep` 等過即可。

mediafire 資料夾清單透過其公開 API `folder/get_content.php` 取得,回傳每檔的 `normal_download` 直鏈。

## 為什麼需要本地後端

droplink.co 與 mediafire API 皆未開放 CORS,瀏覽器內的純靜態 `fetch` 會被跨域阻擋。`server.py` 在本機起服務,繞過與列檔於後端完成,前端僅負責呈現。

## 維護note

兩個時效性假設若 droplink 改版可能失效,屆時調整 `droplink_bypass.py`:

- `MAGIC_REFERER`(目前 `https://game5s.com/`)— 合作站或信任機制若改變需更新。
- 空 `g-recaptcha-response` 被接受 — 若補上 server-side 驗證,需改接真實 captcha solver。

失效時網頁會顯示 `失敗:...` 的 server 回應作為線索。
