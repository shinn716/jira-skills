# jira-skills

繁體中文 | [English](README.md)

五個給 **Jira Server / Data Center** 用的 skill，都建立在唯讀的 Jira MCP server 之上：

| Skill | 做什麼 |
|---|---|
| `jira-refine` | 讀 ticket 的標題與描述，分析這個 repo，把描述改寫成解決方案規格 —— 表格、編號流程、條列。改寫前先備份舊描述。 |
| `jira-implement` | 讀 ticket（有 `jira-refine` 規格就照它走），開分支，逐步把 Solution 實作成程式碼，並對照 Acceptance Criteria 驗證。只動 repo，不寫 Jira。 |
| `jira-sync` | 讀目前的 git 分支，用 Jira wiki markup 寫一份 ≤1000 字元的變更摘要，貼成分支對應 ticket 的留言（`feature/PROJ-123` → `PROJ-123`）。 |
| `jira-goal` | Goal 模式：事前一次授權，接著 refine → implement → 反覆迭代直到每條 Acceptance Criteria 都通過 → 貼出摘要。遇到語意含糊、憑證外洩或任何對外動作就中止。 |
| `jira-sprint-report` | 拉一個 sprint，把某個人的工作產出成單一 HTML 檔：統計數字、SVG 圖表、可排序／過濾的 issue 表格、每張已結案 ticket 的文字摘要，以及團隊比較區塊。 |

它們沿著一張 ticket 的生命週期組合起來：`jira-refine` 寫計畫，`jira-implement` 做出來，
`jira-sync` 在合併時貼上說明，`jira-sprint-report` 在 sprint 結束時把這些留言收割成報告。
`jira-goal` 則把前三個串在單一次授權底下跑完。

## Goal 模式，以及那一次授權買到什麼

`jira-goal` 是唯一不會每一步都問你的 skill。它只在最前面問一次，並且列出它將要做的每一項寫入
動作；那次授權只涵蓋 **一張 ticket、一次執行**：改寫描述、在新分支上改程式碼、貼出摘要留言。

**`git commit` 與 `git push` 永遠不在授權範圍內。** 執行結束時變更會留在 working tree，
review 與 commit 由你自己來 —— 那是程式碼進入 git 歷史前最後一道人為關卡。因為沒有 commit，
摘要留言是用 `git diff <mainline>` 而不是 commit log 產生的。

不論有沒有授權，遇到下列情況一律中止：需求有兩種以上讀法且會導向不同程式碼、repo 或 ticket 裡
出現憑證、工作需要動到別的 repo 或別的 ticket、任何對外或破壞性動作（commit、push、merge、
ticket 轉換狀態、改寫歷史）。中止的執行只會回報，不會貼出「完成」留言。

兩種 Jira 寫入都可還原：描述在被覆蓋前會先備份成檔案，留言就只是留言。

## 不適用於 Jira Cloud

這裡的留言與描述內容都是 **wiki markup**，驗證方式是 **Personal Access Token**。Jira Cloud
用的是 ADF 與 email + API token —— `post-comment.sh` 和 `update-description.sh` 不改的話在
Cloud 上不會動。讀取路徑（sprint 報告）走 MCP，可攜性較高。

## 安裝

五個都是單純的 [Agent Skills](https://developers.openai.com/codex/skills) —— 一個資料夾配
一份帶有 `name` 與 `description` 的 `SKILL.md`。任何看得懂這個格式的 agent 都能跑。只有
Claude Code 這條路徑會用到 plugin marketplace，其餘就是複製資料夾。

### Claude Code

```bash
claude plugin marketplace add shinn716/jira-skills
claude plugin install jira-skills@jira-skills
```

或是 clone 下來後加本機路徑（`claude plugin marketplace add /path/to/jira-skills`），
或直接把 `skills/*` 複製到 `~/.claude/skills/`。

### OpenAI Codex

```bash
git clone https://github.com/shinn716/jira-skills
cp -r jira-skills/skills/* ~/.codex/skills/
```

要限定在專案內就複製到 `.agents/skills/` 並 commit。`/skills` 會列出來，`$` 可以提及某一個。
剛複製的 skill 沒出現就重啟 Codex。

### opencode

```bash
cp -r jira-skills/skills/* ~/.config/opencode/skills/
```

opencode 也讀 Claude 相容的路徑，所以 `~/.claude/skills/` 或專案的 `.claude/skills/` 都能直接
用 —— 一份複製同時服務兩個 agent。

### 跨 agent 注意事項

- **skill 裡的 MCP tool 名稱都是裸寫的**（`jira_get_sprint_issues`），沒有 Claude 的
  `mcp__jira__` 前綴。每個 agent 加前綴的方式不同，用後綴比對就好。
- **Codex 預設把網路關在沙箱外。** `post-comment.sh` 與 `update-description.sh` 會走 HTTPS
  連 Jira，在預設沙箱下會失敗 —— 開啟網路權限執行 Codex，或在跳出提示時核准該指令。sprint
  報告不受影響：它透過 MCP 讀取，`render.py` 只寫本機檔案。
- **`render.py` 只需要 Python 3，沒有其他相依**，所以到哪都跑得一樣。
- 兩支腳本需要 PATH 上有 `bash`、`curl`、`python`。Windows 上用 Git Bash。

## 設定

### JIRA_URL 與 JIRA_PERSONAL_TOKEN

`post-comment.sh` 與 `update-description.sh` 都從環境變數讀這兩個值，缺任一個就以具名錯誤結束。
MCP server 要的是同一組（見下）。

**1. 建立 token。** Jira → 頭像 → **Profile** → **Personal Access Tokens** → *Create token*。
命名、設定到期日、複製值 —— Jira 只顯示一次。token 繼承你自己的權限，所以它能留言的 ticket
就是你能留言的那些。

Personal Access Token 是 Jira **Server / Data Center**（8.14+）的東西。Jira Cloud 上同一個
選單給的是 API token，走 Basic 的 `email:token` 而不是 Bearer —— 見上面「不適用於 Jira Cloud」。

**2. 設定變數。** `JIRA_URL` 是 base URL，後面不要接路徑 —— `/rest/...` 由腳本自己補。
結尾的斜線會幫你去掉。

用 Claude Code 最簡單的做法：**`~/.claude/settings.json`** 的 `env` 區塊。每次 Bash tool
呼叫都會繼承，所以 `post-comment.sh` 在任何專案都能用，不必動你的 shell profile：

```json
{
  "env": {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_PERSONAL_TOKEN": "NDU2..."
  }
}
```

已經有 `env` 物件就併進去，然後重啟 Claude Code。要放在 **user 層級** 的
`~/.claude/settings.json`，絕對不要放專案的 `.claude/settings.json` —— 那個檔會被 commit。
token 兩種放法都是明文，所以把這個檔當 SSH key 對待：只給自己讀寫，不要同步進任何 repo。

其他 agent，或你不想把 token 放在設定檔裡 —— 用 shell 環境變數，寫進
`~/.bashrc` / `~/.zshrc`：

```bash
export JIRA_URL=https://jira.example.com
export JIRA_PERSONAL_TOKEN=NDU2...          # 剛剛複製的值
```

Windows 從 PowerShell —— `setx` 寫進使用者環境，所以之後要**開新的終端機**：

```powershell
setx JIRA_URL "https://jira.example.com"
setx JIRA_PERSONAL_TOKEN "NDU2..."
```

**3. 驗證有效。** 回 200 並帶出你的帳號名稱，代表兩個變數都對：

```bash
curl -s -H "Authorization: Bearer $JIRA_PERSONAL_TOKEN" \
  "$JIRA_URL/rest/api/2/myself" | head -c 200
```

`401` → token 錯誤或過期。這裡出現 `404` → `JIRA_URL` 指到的不是 Jira base URL（像 `/jira`
這種 context path 很容易漏掉）。連線錯誤 → DNS、VPN 或 TLS 的問題，不是驗證問題。

**選用：`JIRA_COMMENT_MAX`。** 以字元數限制留言長度 —— 預設 `1000`，設 `0` 關閉檢查。設定方式
和上面兩個一樣。`post-comment.sh` 算的是字元數（CJK 一字算 1），超長會拒絕送出而不是截斷。

skill 本身不會把 token 寫到任何地方 —— 但上面 `settings.json` 那條路確實會把它明文放在磁碟上，
所以那個檔要保持只有自己能讀，也別放進 dotfiles repo 或雲端同步資料夾。token 不要進
`config.json`、不要進 commit message、不要進 Jira 留言；外洩就從同一個 Profile 頁面輪換。

### jira-sprint-report —— 一個設定檔

把 `skills/jira-sprint-report/config.example.json` 複製成同目錄下的 `config.json`：

```json
{
  "jira_url": "https://jira.example.com",
  "board_id": "1234",
  "board_name": "My Scrum Board",
  "me": "your.jira.username"
}
```

沒有機密 —— sprint 報告透過 MCP server 讀 Jira，憑證由 MCP server 自己持有。`config.json`
被 gitignore，因為 board id 和使用者名稱是你的。

指派人解析順序，先命中者勝：CLI 參數 → 輸入 JSON 裡的 `"me"` → `JIRA_ME` → `config.json`。
以顯示名稱的子字串做不分大小寫比對，所以 `jane.doe` 會對到 `jane.doe Jane Doe`。

### MCP server

五個 skill 都透過 Atlassian MCP server 讀取，用的是與上面同一組 URL 和 token：

```json
{
  "type": "stdio",
  "command": "uvx",
  "args": ["mcp-atlassian"],
  "env": {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_PERSONAL_TOKEN": "...",
    "READ_ONLY_MODE": "true"
  }
}
```

Claude Code 會展開 MCP 設定值裡的 `${JIRA_URL}` / `${JIRA_PERSONAL_TOKEN}`，所以如果你走了
上面 `settings.json` 那條路，這裡可以直接引用，不必再貼一次 token。

Codex 要把同一個 server 放進 `~/.codex/config.toml`：

```toml
[mcp_servers.jira]
command = "uvx"
args = ["mcp-atlassian"]
env = { JIRA_URL = "https://jira.example.com", JIRA_PERSONAL_TOKEN = "...", READ_ONLY_MODE = "true" }
```

opencode 放在 `opencode.json` 的 `mcp` key 底下（`"type": "local"`，`command` 是 argv 陣列）。

`READ_ONLY_MODE=true` 就是為什麼 `jira-sync` 和 `jira-refine` 走 REST 而不是走 MCP 寫入：
唯讀的 server 不會暴露留言或更新的 tool。維持唯讀代表沒有任何 skill 會意外改到 ticket ——
寫入路徑就只有兩支會先要求確認的腳本，而且 `update-description.sh` 在覆蓋前會備份舊描述。

## 手動產生報告

`render.py` 不需要任何第三方套件 —— 只用 Python 3 標準函式庫。

```bash
python skills/jira-sprint-report/render.py sprint.json out.html ["Assignee Name"]
```

輸入 JSON 是原始的 MCP issue 物件加上一個 `sprint` 區塊；每張 issue 選用的 `work_summary`
就是顯示在該列底下的內容。同一份 dump 要換人重新產生，一行指令就好。

`sample-sprint.json` 是可以直接跑、不用碰 Jira 的範例輸入：

```bash
python skills/jira-sprint-report/render.py \
  skills/jira-sprint-report/sample-sprint.json out.html
python skills/jira-sprint-report/test_render.py   # 同一份檔案，當作 smoke test
```

## 處理 ticket 裡的機密

大家會把金鑰、token、連線字串貼進 Jira 留言。五個 skill 都被要求只摘要*事實*（「簽章金鑰已輪換」），
絕不把值複製進報告或新留言。如果在 ticket 裡發現還有效的憑證，skill 會直接告訴你，而不是安靜地
把它傳播出去。

## 值得知道的坑

- **「Done」是 status category，不是 status 名稱。** 像 `Terminated` 或 `Closed` 這種自訂狀態
  也落在 `Done` 這個 category。用字面名稱過濾會少算。
- **Sprint issue 端點每頁上限 50 筆。** 兩個 skill 都會一直翻頁到 `total`；少抓一頁會讓報告裡
  每個百分比都悄悄失真。
- **留言串會自我修正。** 後面的留言常常推翻前面的結論。摘要步驟讀的是整串，而不是抓最長的那則
  留言 —— 最長的通常正是被推翻的那則。

## 授權

MIT。
