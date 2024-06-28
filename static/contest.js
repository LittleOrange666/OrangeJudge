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
        let pid = "";
        function change_page(page){
            current_page = page;
            let fd = new FormData();
            fd.append("user", $("#status_filter_username").val().toLowerCase());
            fd.append("pid", pid);
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function(response){
                return response.json();
            }).then(function(data){
                current_page = data["page"];
                let table = $("#status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    line.append($('<td>').text(timestamp_to_str(obj["time"])));
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
                    if (i==current_page)
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
        $("#status_filter").click(function(){
            pid = $("#status_filter_pid").val();
            change_page(current_page);
        });
    }
    {
        let current_page = 1;
        let pid = "";
        function change_page(page){
            current_page = page;
            let fd = new FormData();
            fd.append("user", $("#username").val());
            fd.append("pid", pid);
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function(response){
                return response.json();
            }).then(function(data){
                page = data["page"];
                let table = $("#my_status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    if (obj["can_see"]){
                        line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    }else{
                        line.append($('<th scope="row">').text(obj["idx"]));
                    }
                    line.append($('<td>').text(timestamp_to_str(obj["time"])));
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
        $("#my_status_filter").click(function(){
            pid = $("#my_status_filter_pid").val();
            change_page(current_page);
        });
    }
    {
        var data;
        var standing_ok = false;
        function refresh_standing(){
            if(!standing_ok) return;
            $("#standing_loading").removeClass("d-none",true);
            $("#standing_table thead tr").empty();
            $("#standing_table tbody").empty();
            if(data["judging"]){
                $("#standing_judging").removeClass("d-none");
            }else{
                $("#standing_judging").addClass("d-none");
            }
            console.log(data);
            let pers = {};
            for(let o of data["pers"]){
                pers[o["idx"]] = o;
            }
            let official_only = $("#standing_official_only").prop("checked");
            if (data['rule']=="ioi"){
                let out = {};
                for(let obj of data['submissions']){
                    let key = obj["user"]+";"+obj["per"];
                    if (out[key] === undefined){
                        out[key] = {"scores":{},"total_score":0,"last_update":0,
                        "is_main":(obj["per"]==data["main_per"]),"is_practice":(obj["per"]==null)}
                        for(let pid of data["pids"]) out[key]["scores"][pid] = {}
                    }
                    for (let k in obj["scores"]){
                        out[key]["scores"][obj["pid"]][k] = Math.max(out[key]["scores"][obj["pid"]][k] || 0, obj["scores"][k]);
                    }
                    let tot = 0;
                    for(let pid of data["pids"]){
                        for (let k in out[key]["scores"][pid]){
                            tot += out[key]["scores"][pid][k];
                        }
                    }
                    if (Number(tot) != Number(out[key]["total_score"])){
                        out[key]["total_score"] = tot;
                        out[key]["last_update"] = obj["time"]-(obj["per"]==null?0:pers[obj["per"]]["start_time"]);
                    }
                }
                let arr = [];
                for (let k in out){
                    let obj = out[k];
                    obj["user"]  = k;
                    arr.push(obj);
                }
                function le(x, y){
                    if (x["is_practice"]<y["is_practice"]) return true;
                    if (x["is_practice"]>y["is_practice"]) return false;
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
                let cur_rank = 1;
                for(let obj of arr){
                    if(official_only&&!obj["is_main"]) continue;
                    let key = obj["user"];
                    let username = key.substring(0,key.lastIndexOf(";"));
                    let per_id = key.substring(key.lastIndexOf(";")+1,key.length);
                    let rank = "";
                    if (obj["is_main"]){
                        rank = ""+cur_rank;
                        cur_rank++;
                    }else if (obj["is_practice"]){
                        rank = "*";
                    }
                    let tr = $("<tr>");
                    tr.append($('<th scope="row">').text(rank));
                    tr.append($('<td>').text(username));
                    tr.append($('<td>').text(obj["total_score"]));
                    for(let pid of data["pids"]){
                        let cur = 0;
                        for(let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                        tr.append($('<td>').text(""+cur));
                    }
                    let time = "";
                    if(!obj["is_practice"]) time = ""+Math.floor(obj["last_update"]/60);
                    tr.append($('<td>').text(time));
                    tb.find("tbody").append(tr);
                }
            }else if(data['rule']=="icpc"){
                let out = {};
                let penalty = data['penalty'];
                for(let obj of data['submissions']){
                    let key = obj["user"]+";"+obj["per"];
                    if (out[key] === undefined){
                        out[key] = {"scores":{},"total_score":0,"total_penalty":0,
                        "is_main":(obj["per"]==data["main_per"]),"is_practice":(obj["per"]==null)}
                        for(let pid of data["pids"]) {
                            out[key]["scores"][pid] = {"score":0,"penalty_cnt":0,"cnt":0,"penalty":0}
                        }
                    }
                    let start_time = pers[data["main_per"]]["start_time"];
                    if(obj["per"]) start_time = pers[obj["per"]]["start_time"];
                    let cur_time = Math.floor((obj["time"]-start_time)/60);
                    let cur = out[key]["scores"][obj["pid"]];
                    if (obj["total_score"]>cur["score"]){
                        cur["score"] = obj["total_score"];
                        cur["penalty_cnt"] = cur["cnt"];
                        cur["penalty"] = cur_time+cur["penalty_cnt"]*penalty;
                    }
                    cur["cnt"]++;
                    let tot = 0;
                    let totp = 0;
                    for(let pid of data["pids"]){
                        tot += out[key]["scores"][pid]["score"];
                        totp += out[key]["scores"][pid]["penalty"];
                    }
                    out[key]["total_score"] = tot;
                    out[key]["total_penalty"] = totp;
                }
                let arr = [];
                for (let k in out){
                    let obj = out[k];
                    obj["user"] = k;
                    arr.push(obj);
                }
                function le(x, y){
                    if (x["is_practice"]<y["is_practice"]) return true;
                    if (x["is_practice"]>y["is_practice"]) return false;
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
                let cur_rank = 1;
                console.log(arr)
                for(let obj of arr){
                    if(official_only&&!obj["is_main"]) continue;
                    let key = obj["user"];
                    let username = key.substring(0,key.lastIndexOf(";"));
                    let per_id = key.substring(key.lastIndexOf(";")+1,key.length);
                    let tr = $("<tr>");
                    let rank = "";
                    if (obj["is_main"]){
                        rank = ""+cur_rank;
                        cur_rank++;
                    }else if (obj["is_practice"]){
                        rank = "*";
                    }
                    tr.append($('<th scope="row">').text(rank));
                    tr.append($('<td>').text(username));
                    tr.append($('<td>').text(obj["total_score"]));
                    tr.append($('<td>').text(obj["is_practice"]?"":obj["total_penalty"]));
                    for(let pid of data["pids"]){
                        let cur = 0;
                        let cnt = obj["scores"][pid]["penalty_cnt"];
                        let rt = obj["scores"][pid]["penalty"]-cnt*penalty;
                        for(let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                        let line = ""+obj["scores"][pid]["score"];
                        if(!obj["is_practice"]) line += "/"+rt+"+"+cnt;
                        tr.append($('<td>').text(line));
                    }
                    tb.find("tbody").append(tr);
                }
            }
            $("#standing_loading").addClass("d-none",true);
        }
        function load_standing(){
            standing_ok = false;
            $("#standing_loading").removeClass("d-none",true);
            $("#standing_error").addClass("d-none",true);
            $("#standing_table thead tr").empty();
            $("#standing_table tbody").empty();
            fetch("/contest/"+cid+"/standing",{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()}
            }).then(function(response){
                if (response.ok) {
                    return response.json();
                }else if (response.status==403){
                    $("#standing_error").text("目前無法觀看記分板").removeClass("d-none");
                }else{
                    $("#standing_error").text("Error "+response.status+" "+response.statusText).removeClass("d-none");
                }
                $("#standing_loading").addClass("d-none",true);
                throw new Error("Network response was not ok.");
            }).then(function(got_data){
                data = got_data;
                standing_ok = true;
                refresh_standing();
            });
        }
        let inited = false;
        $("#standing_tab").click(function(){
            if(!inited){
                inited = true;
                load_standing();
            }
        });
        $("#standing_official_only").on("change", refresh_standing);
        if (location.hash=="#standing") $("#standing_tab").click();
        $("#standing_refresh").click(load_standing);
        let auto_refresh = false;
        $("#standing_auto_refresh").change(function(){
            auto_refresh = $(this).prop("checked");
        });
        window.setInterval(function(){
            if(auto_refresh) load_standing();
        },20000);
    }
    let contest_status = $("#contest_status").data("status");
    let status_mp = {"practice": "練習模式", "waiting_virtual": "等待模擬競賽開始", "waiting": "等待競賽開始", "running": "競賽進行中", "running_virtual": "模擬競賽進行中",
                    "guest": "僅觀看", "testing": "測試模式"};
    $("#contest_status").text(status_mp[contest_status]);
    if($("#save_order").length){
        let moveing_problem = null;
        $("tr.problem").attr("draggable","true");
        $("tr.problem").on("dragstart",function(e){
            moveing_problem = $(this);
        });
        $("tr.problem").on("dragover",function(e){e.preventDefault();});
        $("tr.problem").on("dragenter",function(e){e.preventDefault();});
        $("tr.problem").on("drop",function(e){
            e.preventDefault();
            $(this).before(moveing_problem);
            moveing_problem = null;
        });
        $("#save_order").click(function(){
            let fd = new FormData();;
            fd.append("cid",cid);
            fd.append("action","save_order");
            let arr = [];
            $("tr.problem").each(function(){
                arr.push($(this).data("index"));
            });
            fd.append("order",arr.join(","));
            fetch("/contest_action",{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function(response){
                if (response.ok){
                    show_modal("成功","成功儲存順序", true);
                }else {
                    let msg = null;
                    if(!msg&&response.status==400) msg = "輸入格式不正確"
                    if(!msg&&response.status==403) msg = "您似乎沒有權限執行此操作"
                    show_modal("失敗",msg?msg:"Error Code: " + response.status);
                }
            });
        });
    }
    $("#save_question_modal").on("show.bs.modal", function(event){
        let id = $(event.relatedTarget).data("id");
        $("#save_question_id").val(id);
        let reply = $(".question-tr[data-id='"+id+"'] .message-area.reply").text();
        $("#save_question_content").val(reply);
        $("#save_question_check").prop("checked", $(event.relatedTarget).data("public")==="True");
    });
});