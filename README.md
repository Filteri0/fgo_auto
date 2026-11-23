# FGO Auto

FGO 自動周回小工具：同一關無限周回、自動吃蘋果、依條件選助戰、照腳本開技能放寶具。
用截圖 + 圖片比對判斷畫面，透過 ADB 點擊 MuMu 模擬器。

## 需要準備

- **MuMu 模擬器**，解析度設成 **1280×720**
- [uv](https://docs.astral.sh/uv/)（Python 套件管理工具，會自動裝好需要的 Python 版本）
- `adb` 要能在命令列直接執行：把 MuMu 安裝資料夾裡含 `adb.exe` 的資料夾加進 PATH
  （例如 `C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell`，版本號可能不同）

遊戲內設定：

- 關閉 **技能使用確認**
- 關卡要有 **連續出擊**（結算後的「是否連續進行同一任務？」）

## 安裝

```bash
git clone https://github.com/Filteri0/fgo_auto.git
cd fgo_auto
uv sync
```

## 使用（圖形介面）

```bash
uv run python gui.py
```

1. **設定**：確認 ADB 位址（MuMu 預設 `127.0.0.1:16384`），按「測試連線」，右上角亮綠燈就成功了。
2. **助戰**：把遊戲停在「支援選擇」畫面 → 按「擷取模擬器畫面」→ 點你要的那一列 →
   勾選要比對的條件（玩家名稱、從者、寶具等級、從者等級、禮裝、禮裝滿破）→ 按「測試比對」確認。
   也可以選職階頁籤。找不到時會自動按「列表更新」。
3. **戰鬥腳本**：填 1～3 號位的名字，選「第 N 波」，點技能格加入動作。
   需要目標的技能會跳出選單；寶具沒打死的話，之後的回合會自動補刀（NP 滿就放寶具，其他照卡色出卡）。
4. **周回**：設定場數（0 = 無限）、最多吃幾顆蘋果、可以吃哪些果實（可拖曳排序）→ 按「開始周回」。
   第一次請手動點進關卡，之後會一直用連續出擊。

## 使用（命令列）

```bash
uv run python main.py --list
uv run python main.py --profile default --runs 10 --max-apples 5
```

## 安全機制

- **聖晶石永遠不會吃**
- **全滅時停止**
- 連續 120 秒認不出畫面、找不到助戰太多次等情況會自動停止，並把當下截圖存到 `logs/`。

## 遇到問題

- 停下來的原因會寫在介面的 log 裡，截圖在 `logs/`（設定頁有按鈕可以直接打開）。
- 新的遊戲畫面（活動、新的彈出視窗）可能認不出來，需要補模板：
  `uv run python capture.py` 可以截圖存到 `screenshots/`。

## 開發

```bash
uv run pytest            # 用 screenshots/ 裡的截圖回放測試，不需要開模擬器
```

| 檔案 | 內容 |
|---|---|
| `bot.py` | 周回主迴圈（截圖 → 判斷畫面 → 做一個動作） |
| `states.py` / `templates.py` | 畫面辨識與模板定義 |
| `battle.py` | 戰鬥腳本、技能冷卻 / NP / 卡色判斷 |
| `support.py` | 支援列表比對 |
| `profile_store.py` | 設定組存讀（`profiles/`） |
| `ui/` | 圖形介面（PySide6） |
