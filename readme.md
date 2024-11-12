# OrangeJudge

這是一個自製的Judge

目前還在開發中，不保證能正確運行

如要使用的話，可以直接clone下來或下載zip檔

clone的時候記得加--recursive

建議裝在虛擬機或Docker裡面執行

然後執行
```shell
./runserver.sh
```
初次執行會安裝需要的東東

或是手動打
```shell
chmod +x tools/autoinit.sh
sudo ./tools/autoinit.sh
```
再用
```shell
python3 main.py
```
啟動伺服器

然後到config.yaml裡面填上必要的東東

然後初次執行會建立帳密都是root的管理者帳號

記得改密碼

要注意autoinit.sh會在這個repo的上層資料夾下載

https://github.com/LittleOrange666/OrangeJudge_Judger

並build docker image

然後再用這裡的docker-compose.yml開judge server

有時候可能需要去想辦法打開他

目前這repo還沒有Dockerfile，之後大概會有吧

要用全docker可能要自己通靈一下docker-compose.yml怎寫

再去modules.constants.py改些參數

剩下請自行通靈

本judge不保證能在 非 x86_64,x64,AMD64 架構主機上運行

我不知道啥配置會好

但建議用Ubuntu 22.04.3 LTS + Python 3.10.X

非Ubuntu可能會爛，非Linux一定會爛

Python版本太新可能會有套件裝不下來