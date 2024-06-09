$(function() {
    const cid = $("#cid").val();
    const username = $("#username").val();
    $("form[the_action]").each(function(){
        let $this = $(this);
        $this.attr("action","/contest_action");
        $this.attr("method","post");
        $this.attr("target","_self");
        $this.attr("enctype","multipart/form-data");
        $this.prepend($('<input name="cid" value="'+cid+'" hidden>'));
        $this.prepend($('<input name="action" value="'+$(this).attr("the_action")+'" hidden>'));
    });
    {
        let current_page = 1;
        function change_page(page){
            current_page = page;
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()}
            }).then(function(response){
                return response.json();
            }).then(function(data){
                let table = $("#status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    line.append($('<td>').text(obj["time"]));
                    line.append($('<td>').append($("<a>").text(obj["user_name"]).attr("href","/user/"+obj["user_id"])));
                    line.append($('<td>').append($("<a>").text(obj["problem"]+". "+obj["problem_name"]).attr("href","/contest/"+cid+"/problem/"+obj["problem"])));
                    line.append($('<td>').text(obj["lang"]));
                    line.append($('<td>').text(obj["result"]));
                    table.append(line);
                }
                let pagination = $("#status_page");
                pagination.empty();
                let first = $('<li class="page-item">');
                if (page==1){
                    first.addClass("disabled");
                }
                let first_btn = $('<a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>');
                first_btn.click(function(){change_page(1)});
                first.append(first_btn);
                pagination.append(first);
                for(let i of data["show_pages"]){
                    let li = $('<li class="page-item">');
                    if (i==page)
                        li.addClass("active");
                    let a = $('<a class="page-link">').text(i);
                    a.click(function(){change_page(i)});
                    li.append(a);
                    pagination.append(li);
                }
                let last = $('<li class="page-item">');
                if (page==data["page_cnt"]){
                    last.addClass("disabled");
                }
                let last_btn = $('<a class="page-link" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>');
                last_btn.click(function(){change_page(data["page_cnt"])});
                last.append(last_btn);
                pagination.append(last);
            });
        }
        let inited = false;
        $("#status_tab").click(function(){
            if(!inited){
                inited = true;
                change_page(current_page);
            }
        });
        if (location.hash=="#status") $("#status_tab").click();
    };
    {
        let current_page = 1;
        function change_page(page){
            current_page = page;
            let fd = new FormData();
            fd.append("user", $("#username").val());
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function(response){
                return response.json();
            }).then(function(data){
                let table = $("#my_status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    line.append($('<td>').text(obj["time"]));
                    // line.append($('<td>').append($("<a>").text(obj["user_name"]).attr("href","/user/"+obj["user_id"])));
                    line.append($('<td>').append($("<a>").text(obj["problem"]+". "+obj["problem_name"]).attr("href","/contest/"+cid+"/problem/"+obj["problem"])));
                    line.append($('<td>').text(obj["lang"]));
                    line.append($('<td>').text(obj["result"]));
                    table.append(line);
                }
                let pagination = $("#my_status_page");
                pagination.empty();
                let first = $('<li class="page-item">');
                if (page==1){
                    first.addClass("disabled");
                }
                let first_btn = $('<a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>');
                first_btn.click(function(){change_page(1)});
                first.append(first_btn);
                pagination.append(first);
                for(let i of data["show_pages"]){
                    let li = $('<li class="page-item">');
                    if (i==page)
                        li.addClass("active");
                    let a = $('<a class="page-link">').text(i);
                    a.click(function(){change_page(i)});
                    li.append(a);
                    pagination.append(li);
                }
                let last = $('<li class="page-item">');
                if (page==data["page_cnt"]){
                    last.addClass("disabled");
                }
                let last_btn = $('<a class="page-link" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>');
                last_btn.click(function(){change_page(data["page_cnt"])});
                last.append(last_btn);
                pagination.append(last);
            });
        }
        let inited = false;
        $("#my_status_tab").click(function(){
            if(!inited){
                inited = true;
                change_page(current_page);
            }
        });
        if (location.hash=="#my_status") $("#my_status_tab").click();
    }
    {
        function load_standing(){
            fetch("/contest/"+cid+"/standing",{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()}
            }).then(function(response){
                return response.json();
            }).then(function(data){
                console.log(data['submissions']);
                if (data['rule']=="ioi"){
                    let out = {};
                    for(let obj of data['submissions']){
                        if (out[obj["user"]] === undefined){
                            out[obj["user"]] = {"scores":{},"total_score":0,"last_update":0}
                            for(let pid of data["pids"]) out[obj["user"]]["scores"][pid] = {}
                        }
                        for (let k in obj["scores"]){
                            out[obj["user"]]["scores"][obj["pid"]][k] = Math.max(out[obj["user"]]["scores"][obj["pid"]][k] || 0, obj["scores"][k]);
                        }
                        let tot = 0;
                        for(let pid of data["pids"]){
                            for (let k in out[obj["user"]]["scores"][pid]){
                                tot += out[obj["user"]]["scores"][pid][k];
                            }
                        }
                        if (Number(tot) != Number(out[obj["user"]]["total_score"])){
                            out[obj["user"]]["total_score"] = tot;
                            out[obj["user"]]["last_update"] = obj["time"];
                        }
                    }
                    let arr = [];
                    for (let k in out){
                        let obj = out[k];
                        obj["user"]  = k;
                        arr.push(obj);
                    }
                    function le(x, y){
                        if (x["total_score"]>y["total_score"]) return true;
                        if (x["total_score"]<y["total_score"]) return false;
                        return x["last_update"]<y["last_update"];
                    }
                    arr.sort(function(x, y) {
                      if (le(x,y)) {
                        return -1;
                      }
                      if (le(y,x)) {
                        return 1;
                      }
                      return 0;
                    });
                    console.log(arr);
                    let tb = $("#standing_table");
                    let tl = tb.find("tr");
                    tl.append($('<th scope="col">').text("#"));
                    tl.append($('<th scope="col">').text("User"));
                    tl.append($('<th scope="col">').text("Score"));
                    for(let pid of data["pids"]){
                        tl.append($('<th scope="col">').text(pid));
                    }
                    tl.append($('<th scope="col">').text("Time"));
                    for(let i in arr){
                        let obj = arr[i];
                        let tr = $("<tr>");
                        tr.append($('<th scope="row">').text(""+(+i+1)));
                        tr.append($('<td>').text(obj["user"]));
                        tr.append($('<td>').text(obj["total_score"]));
                        for(let pid of data["pids"]){
                            let cur = 0;
                            for(let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                            tr.append($('<td>').text(""+cur));
                        }
                        tr.append($('<td>').text(""+Math.floor((obj["last_update"]-data["start_time"])/60)));
                        tb.find("tbody").append(tr);
                    }
                }else if(data['rule']=="icpc"){
                    let out = {};
                    let penalty = data['penalty'];
                    for(let obj of data['submissions']){
                        if (out[obj["user"]] === undefined){
                            out[obj["user"]] = {"scores":{},"total_score":0,"total_penalty":0}
                            for(let pid of data["pids"]) {
                                out[obj["user"]]["scores"][pid] = {"score":0,"penalty_cnt":0,"cnt":0,"penalty":0}
                            }
                        }
                        let cur_time = Math.floor((obj["time"]-data["start_time"])/60);
                        let cur = out[obj["user"]]["scores"][obj["pid"]];
                        if (obj["total_score"]>cur["score"]){
                            cur["score"] = obj["total_score"];
                            cur["penalty_cnt"] = cur["cnt"];
                            cur["penalty"] = cur_time+cur["penalty_cnt"]*penalty;
                        }
                        cur["cnt"]++;
                        let tot = 0;
                        let totp = 0;
                        for(let pid of data["pids"]){
                            tot += out[obj["user"]]["scores"][pid]["score"];
                            totp += out[obj["user"]]["scores"][pid]["penalty"];
                        }
                        out[obj["user"]]["total_score"] = tot;
                        out[obj["user"]]["total_penalty"] = totp;
                    }
                    let arr = [];
                    for (let k in out){
                        let obj = out[k];
                        obj["user"]  = k;
                        arr.push(obj);
                    }
                    function le(x, y){
                        if (x["total_score"]>y["total_score"]) return true;
                        if (x["total_score"]<y["total_score"]) return false;
                        return x["total_penalty"]<y["total_penalty"];
                    }
                    arr.sort(function(x, y) {
                      if (le(x,y)) {
                        return -1;
                      }
                      if (le(y,x)) {
                        return 1;
                      }
                      return 0;
                    });
                    console.log(arr);
                    let tb = $("#standing_table");
                    let tl = tb.find("tr");
                    tl.append($('<th scope="col">').text("#"));
                    tl.append($('<th scope="col">').text("User"));
                    tl.append($('<th scope="col">').text("Score"));
                    tl.append($('<th scope="col">').text("Penalty"));
                    for(let pid of data["pids"]){
                        tl.append($('<th scope="col">').text(pid));
                    }
                    for(let i in arr){
                        let obj = arr[i];
                        let tr = $("<tr>");
                        tr.append($('<th scope="row">').text(""+(+i+1)));
                        tr.append($('<td>').text(obj["user"]));
                        tr.append($('<td>').text(obj["total_score"]));
                        tr.append($('<td>').text(obj["total_penalty"]));
                        for(let pid of data["pids"]){
                            let cur = 0;
                            let cnt = obj["scores"][pid]["penalty_cnt"];
                            let rt = obj["scores"][pid]["penalty"]-cnt*penalty;
                            for(let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                            tr.append($('<td>').text(""+obj["scores"][pid]["score"]+"/"+rt+"+"+cnt));
                        }
                        tb.find("tbody").append(tr);
                    }
                }
            });
        }
        let inited = false;
        $("#standing_tab").click(function(){
            if(!inited){
                inited = true;
                load_standing();
            }
        });
        if (location.hash=="#standing") $("#standing_tab").click();
    }
});