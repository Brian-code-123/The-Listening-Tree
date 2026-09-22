# Hooks + Headless Mode — 修正版說明

## 檔案
- `settings.json` → 放入你 repo 嘅 `.claude/settings.json`
- `preflight.sh` → 放入你 repo 嘅 `scripts/preflight.sh`

## settings.json 改咗咩

1. **Secret regex 由 `{20}` 改成 `{20,}`**
   原本嘅精確長度匹配對唔中大部分真實 token（GitHub PAT 而家係 40 字符、
   OpenAI/Anthropic key 通常更長），`{20}` 令個 hook 形同虛設。而家加埋
   `sk-ant-`、`sk-proj-`、`gho_`、JWT (`eyJ...`) pattern，覆蓋 Supabase 呢類
   JWT 格式 key。

2. **Matcher 由 `Bash` 擴展到 `Bash|Write|Edit`**
   原本淨係擋 bash command 入面嘅 secret，而家 Claude 直接寫入檔案內容
   （`content`/`new_string`）都會被掃描。

3. **新增獨立 hook：擋 production DB 連接**
   針對你原本提到嘅「test 撞到 production Supabase」問題，偵測命令入面
   有冇 `supabase.co`、`DATABASE_URL...prod`、`NODE_ENV=production` 呢類
   pattern，有就 block 並要求你確認。

4. **修正 prettier 嘅 quoting bug**
   原本 `"$CLAUDE_FILE_PATHS"` 加咗 quote，當多過一個檔案時會將全部路徑
   當成一個 argument 傳俾 prettier，導致 file-not-found。而家改用
   `xargs -r`，逐個檔案分開處理。

## preflight.sh 改咗咩

1. **加入 gitleaks 做 deterministic secret scan**
   原本淨係靠 Claude（LLM）做 secret scan，non-deterministic、唔可靠。
   而家 gitleaks 做 hard gate（tracked files + git history 都掃），
   Claude 只負責需要語意理解嘅部分（README 對唔對得上 code、AI attribution）。
   需要自行安裝 gitleaks: https://github.com/gitleaks/gitleaks#installing

2. **明確 PASS/FAIL 訊號，真正會 block**
   原本個 script 就算揾到問題都唔會令 push 失敗，得個 `audit.md` 檔案
   放喺度冇人望。而家要求 Claude 輸出結尾一定要有
   `STATUS: PASS` 或 `STATUS: FAIL`，script grep 呢一行決定 exit code，
   可以直接掛落 `.git/hooks/pre-push` 或者 CI。

3. **唔再將 audit 結果寫落追蹤緊嘅檔案**
   原本 `> audit.md` 有機會將偵測到但冧漏 redact 嘅 secret 意外 commit
   落去。而家結果只印去 stdout/log，唔落地做檔案。同時明確要求 Claude
   唔好喺 output 入面覆述任何實際 secret 值。

## 你仲要自己做嘅嘢

- 安裝 gitleaks（`brew install gitleaks` 或者睇返上面連結）
- 如果想接 CI，將 `preflight.sh` 嘅內容搬去 `.github/workflows/audit.yml`,
  用 `run: ./scripts/preflight.sh` 呢一行就得
- 想接 git pre-push hook 就:
  ```bash
  ln -s ../../scripts/preflight.sh .git/hooks/pre-push
  ```
# Hooks + Headless Preflight — 改善說明

## settings.json 改咗咩

1. **Regex長度**:`{20}` → `{20,}`。原本嘅精確20字符匹配唔到而家嘅token
   長度(GitHub PAT其實36字符,OpenAI/Anthropic key更長),部落原版等於冇
   保護。

2. **加咗Supabase/DB endpoint檢查**:原版card嘅「why for you」提到production
   DB係痛點,但sample code完全冇處理呢個。新增第二個PreToolUse hook,見到
   command入面提及supabase.co/DATABASE_URL/SUPABASE_URL但冇local/test/
   staging字眼,就block並要求確認。**呢個係heuristic,唔係100%準確**——
   如果你嘅test環境變數命名冇呢啲關鍵字,自己要調整pattern或者改用
   allowlist方式(明確list出邊啲host係safe)。

3. **加咗Write|Edit matcher嘅secret檢查**:原版淨係喺Bash指令度攔secret,
   如果Claude直接用Write/Edit將secret寫入檔案內容,原版攔唔到。新增一個
   針對`tool_input.content`/`tool_input.new_string`嘅檢查。

4. **加咗JWT pattern**(`eyJ...`):Supabase key本身多數係JWT格式,原本嘅
   regex set冧唔到呢種格式。

5. **修正prettier多檔案bug**:原版將`$CLAUDE_FILE_PATHS`加咗quote,
   如果一次改多過一個檔案,會變成一個帶空格嘅單一argument,prettier會
   報錯揾唔到檔案。新版用`read -ra`拆返做array,逐個檔案傳俾prettier,
   而且失敗時會有warning而唔係完全靜默。

## preflight.sh 改咗咩

1. **Secret scan交返俾gitleaks(如有安裝)**:LLM做secret scan本質上係
   non-deterministic,同一個repo跑兩次可能揾到唔同結果。gitleaks呢類
   工具用嘅係固定pattern set,可重複、快、亦已經涵蓋咗git history
   (原本嘅token長度問題喺呢度都唔存在)。如果冇裝gitleaks,會fallback
   落claude-only模式並提示你呢個限制。

2. **Claude淨係負責語意層面嘅檢查**:AI-attribution(commit/branch/trailer
   有冇"claude"字眼)同「README同code對唔對得上」呢兩樣先至真係需要
   語言理解,交返俾claude做,唔再叫佢兼顧secret scan。

3. **加咗STATUS line做machine-readable gate**:原版prompt冇要求固定
   output格式,個script亦冧咗checking——就算揾到問題,都唔會令pipeline
   fail。新版要求model輸出第一行必須係`STATUS: PASS`或`STATUS: FAIL`,
   script`grep`嗰行,揾到FAIL就`exit 1`,先真正可以接落pre-push hook
   或者CI令個push/merge被擋。

3. **唔再落地寫`audit.md`**:原版將可能包含(未完全redact嘅)secret嘅
   內容寫落一個檔案,呢個檔案本身有機會被誤commit,變成新嘅洩漏來源。
   新版直接輸出去stdout/CI log,唔落地。如果你堅持要一份存檔,記得
   先將`audit.md`加入`.gitignore`。

4. **明確叫claude唔好嘗試重現任何secret值**:原本prompt話「redact any
   secret values you find」,但冇保證做得到。新版明確要求佢淨係講
   位置,唔好輸出個值本身,降低殘留風險。

## 用法

```bash
chmod +x scripts/preflight.sh
./scripts/preflight.sh   # 手動跑,或者掛落 .git/hooks/pre-push
```

CI (.github/workflows/audit.yml) 可以直接call呢個script,exit code
非0就會令workflow fail。

## 你仍然要自己判斷嘅位

- Supabase檢查嘅keyword heuristic(local/test/staging)未必啱你嘅
  環境變數命名習慣,自己要對返實際config調整。
- gitleaks嘅default rule set未必涵蓋晒你公司自訂嘅內部token格式,
  有需要可以寫`.gitleaks.toml`自訂規則。
- 呢啲hook係「減少人為疏忽」,唔係「保證零洩漏」——commit前自己都應該
  睇一眼diff。
