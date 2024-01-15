/*
* File: shell.cpp 
* Designed for: 
* 高中生程式解題系統 ZeroJudge(http://zerojudge.tw)
* Lastest Modified: May, 2008
* Author: Jiangsir (jiangsir@tea.nknush.kh.edu.tw)
*/

#include <iostream>
#include <sstream>
#include <sys/wait.h>
#include <cstdlib>
#include <unistd.h>
#include <sys/time.h>
#include <sys/resource.h>

using namespace std;

int main(int argc, char *argv[]){
    int basestatus, status;
    rusage baseusage, usage;
    long long int time, memory, outfilesize;
    stringstream(argv[1]) >> time;
    stringstream(argv[2]) >> memory;
    stringstream(argv[3]) >> outfilesize;
    string argv4 = argv[4];
    if (argv4[0]=='\"'||argv4[0]=='\'') argv4 = argv4.substr(1,argv4.size()-2);
    argv4 = "sudo -u nobody "s+argv4;
    argv4 = "socat exec:'"s+argv4+"' exec:'"s+argv4+"'"s;
    string argv5 = argv[5];
    if (argv5[0]=='\"'||argv5[0]=='\'') argv5 = argv5.substr(1,argv5.size()-2);
    argv5 = "sudo -u nobody "s+argv5;
    string argv6 = argv[6];
    if (argv6[0]=='\"'||argv6[0]=='\'') argv6 = argv6.substr(1,argv6.size()-2);
    argv6 = "sudo -u judge "s+argv6;
//    pid_t baseid = fork();
    if(fork()==0){
        rlimit timelimit, memorylimit;
        timelimit.rlim_cur = 1; // seconds
        timelimit.rlim_max = 1;
        memorylimit.rlim_cur = memory; // 單位 Byte
        memorylimit.rlim_max = memory;
        setrlimit(RLIMIT_CPU, &timelimit);
        setrlimit(RLIMIT_AS, &memorylimit);
    system(argv4.c_str());
    return 0;
    }
    wait3(&basestatus, 0, &baseusage);

//    pid_t childid = fork();
    if(fork()==0){
        rlimit timelimit, memorylimit, filelimit;
    timelimit.rlim_cur = time; // seconds
    timelimit.rlim_max = time;
    memorylimit.rlim_cur = memory; // 單位 Byte
    memorylimit.rlim_max = memory;
    filelimit.rlim_cur = outfilesize; // 單位 Byte
    filelimit.rlim_max = outfilesize;
        setrlimit(RLIMIT_CPU, &timelimit);
    setrlimit(RLIMIT_AS, &memorylimit);
    setrlimit(RLIMIT_FSIZE, &filelimit);
    string cmd = argv6;
    cmd += " "s + argv[7];
    cmd += " "s + argv[8];
    cmd = "socat exec:'"s+argv5+"' exec:'"s+cmd+"'"s;
    cout << "maincmd=" << cmd << endl;
        int childstatus = system(cmd.c_str());
    cout << "childstatus=" << childstatus << endl;
        cout << "WIFSIGNALED=" << WIFSIGNALED(childstatus) << endl; // 非零代表因某個 signal 沒有 catch 而結束
        cout << "WTERMSIG=" << WTERMSIG(childstatus) << endl; // 造成行程結束的 signal 編號
        cout << "WEXITSTATUS=" << WEXITSTATUS(childstatus) << endl;  // 取得 exit status 最小 8 bits
        cout << "WIFEXITED=" << WIFEXITED(childstatus) << endl; // 非零代表正常結束
        cout << "WCOREDUMP=" << WCOREDUMP(childstatus) << endl; // 非零代表產生 core dump
        cout << "WSTOPSIG=" << WSTOPSIG(childstatus) << endl; // 取得造成行程 stop 的 signal
        cout << "WIFSTOPPED=" << WIFSTOPPED(childstatus) << endl; // 非零代表子行程已被 stop
        return 0;
    }
    wait3(&status, 0, &usage);

    double exectime = usage.ru_utime.tv_sec + usage.ru_stime.tv_sec + (double)(usage.ru_utime.tv_usec + 
usage.ru_stime.tv_usec) / 1000000;
    double basetime = baseusage.ru_utime.tv_sec + baseusage.ru_stime.tv_sec + (double)(baseusage.ru_utime.tv_usec +
baseusage.ru_stime.tv_usec) / 1000000;
    cout << "basetime=" << basetime << endl;
    cout << "time=" << exectime << endl;
    cout << "basemem=" << baseusage.ru_minflt << endl;
    cout << "mem=" << usage.ru_minflt << endl;
    cout << "pagesize=" << getpagesize() << endl;
    cout << "ru_majflt=" << usage.ru_majflt << endl;
    cout << "pid=" << getpid() << endl;
    cout << "ppid=" << getppid() << endl;

    return 0;
}
