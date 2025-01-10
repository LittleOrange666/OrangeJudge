# OrangeJudge

這是一個自製的Judge

目前還在開發中，不保證能正確運行

## 安裝

先想辦法裝好docker和docker-compose後

下載docker-compos.yml

可以用
```bash
wget https://raw.githubusercontent.com/LittleOrange666/OrangeJudge/refs/heads/main/docker-compose.yml
```
來一鍵下載

接著執行

```bash
docker-compose up -d
```

應該就會好了

網頁開在8080 port，可以改docker-compose.yml來改

目前只有http，之後有空再處裡https的問題

沙盒伺服器會在9132 port開一個測試用的接口，可以改docker-compose.yml來關掉

要注意初次執行會建立帳密都是root的管理者帳號，記得改密碼

然後資料會被存在 \[跑上面那個指令的資料夾\]/data

部分系統設置在 data/config.yaml，要重啟才生效

剩下請自行通靈

本judge不保證能在 非 x86_64,x64,AMD64 架構主機上運行