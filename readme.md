# OrangeJudge

這是一個自製的Judge

目前還在開發中，不保證能正確運行

## 安裝

建議用 https://github.com/LittleOrange666/OrangeJudgeDeploy 來輔助安裝

但也可以照以下步驟手動來

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

資料庫會在3306 port開一個管理用的接口，也可以改docker-compose.yml來關掉

要注意初次執行會建立帳密都是root的管理者帳號，記得改密碼

然後資料會被存在 \[跑上面那個指令的資料夾\]/data

部分系統設置在 data/config.yaml，也可以在伺服器上的管理頁面改，要重啟才生效

剩下請自行通靈

本judge不保證能在 非 x86_64,x64,AMD64 架構主機上運行

### TOKEN

judge server的token默認是自動生成的，可能比較不穩定，最好是在docker-compose.yml裡面設定一下固定的token

在judge_server和judge_backend的environment裡面加上

```yaml
- JUDGE_SERVER_TOKEN=your_token
```

即可

### TOKEN

judge backend的secret key用於保護登入狀態，默認是自動生成的，會導致重啟時丟失登入狀態，可以是在docker-compose.yml裡面設定一下固定的secret key

在judge_backend的environment裡面加上

```yaml
- FLASK_SECRET_KEY=your_secret
```

即可

## 手動安裝

若有修改程式之需求，可以把這個repo跟[OrangeJudge_Judger](https://github.com/LittleOrange666/OrangeJudge_Judger) clone下來

改好之後分別執行

```bash
docker build -t orange_judge .
```

```bash
docker build -t judge_server .
```

然後改docker-compose.yml裡面的image名稱

再執行

```bash
docker-compose up -d
```

就好了