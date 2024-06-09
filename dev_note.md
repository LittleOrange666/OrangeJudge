## 已知問題
+ 許多Internal server error 沒有反饋給前端
+ 許多空白&斜線的處理不知道是不是OK的
+ 可偷用python
+ (出題)許多修改不應重新整理
+ python 版本不固定
+ 登入狀態丟失?
+ create version 未檢查checker是否能正確check測資
+ interactive problem 的時間&空間計算不知道對不對

## 潛在威脅
+ lxc中nobody可以執行真內建的system call
+ 出題者可能可以實行XSS attack
+ 缺乏Dos防護 (重要)
+ 許多地方缺乏長度限制，包括但不限於：檔名、檔案大小、各種名稱、密碼...
+ 應該限制各項操作的時限
+ server 不應使用root user

## 未實裝特性
+ problem set
+ exam
+ custom languages
+ ans generator
+ background action log (不完整)
+ better editer(自動縮排&空格縮排)
+ 出題小組 (虛擬使用者?)
+ admin UI
+ code checker
+ import from Codeforces Polygon (部分完成, 可用但後續修改困難) (附加檔案未匯入)
+ API
+ 資料用ajax拿
+ seccomp
+ judge error log (不完整)
+ tutorial
+ all submissions
+ language limit and specify ML, TL
+ 標準化計時
+ latex/md題敘 (只支持Polygon import 且後續修改困難)
+ Two-steps
+ Output-Only
+ 驗題者(readonly)

## contests 特性
+ ioi/icpc/ioic/custom ranking strategic
+ 封版
+ 後測
+ heuristic rejudge
+ 隱藏詳細結果
+ 賽後看題&練習&看舊code
+ 賽中提問