## 已知問題
+ 許多Internal server error 沒有反饋給前端
+ 許多空白&斜線的處理不知道是不是OK的
+ (出題)許多修改不應重新整理
+ create version 未檢查checker是否能正確check測資
+ interactive problem 的時間&空間計算不知道對不對
+ 驗題會在解題動態洩漏題目名稱
+ 賽後可以提出詢問

## 潛在威脅
+ 出題者可能可以實行XSS attack
+ 缺乏Dos防護 (重要)
+ 許多地方缺乏長度限制，包括但不限於：檔名、檔案大小、各種名稱、密碼...
+ 應該限制各項操作的時限

## 未實裝特性
+ problem set
+ exam
+ background action log (不完整)
+ better editer(自動縮排&空格縮排)
+ import from Codeforces Polygon (部分完成, 可用但後續修改困難) (附加檔案未匯入)
+ API
+ 資料用ajax拿
+ judge error log (不完整)
+ tutorial
+ language limit and specify ML, TL
+ 標準化計時
+ latex/md題敘 (只支持Polygon import 且後續修改困難)
+ Two-steps
+ Output-Only
+ Custom summary
+ nginx?

## contests 特性
+ ioi/icpc/ioic/custom ranking strategic
+ heuristic rejudge
+ 隱藏競賽