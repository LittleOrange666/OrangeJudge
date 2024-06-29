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
sudo python3 main.py
```
啟動伺服器

然後到config.yaml裡面填上必要的東東

如果安裝過程出現temporary failure resolving ...

且無法跑程式

可能可以用
```shell
sudo lxc-stop -n lxc-test
sudo lxc-destroy -n lxc-test
sudo ./tools/autoinit.sh
```
把沙盒砸掉重裝，可能會好

然後初次執行會建立帳密都是root的管理者帳號

記得改密碼

剩下請自行通靈

本judge不保證能在 非 x86_64,x64,AMD64 架構主機上運行

我不知道啥配置會好

但建議用Ubuntu 22.04.3 LTS + Python 3.10.X

非Ubuntu可能會爛，非Linux一定會爛

Python版本太新可能會有套件裝不下來