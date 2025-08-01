$(function () {
    const cid = $("#cid").val();
    const username = $("#username").val();
    function mk_input(name, value) {
        return $('<input name="' + name + '" value="' + value + '" hidden>');
    }
    $("form[the_action]").each(function () {
        let $this = $(this);
        $this.attr("action", "/contest_action");
        $this.attr("method", "post");
        $this.attr("target", "_self");
        $this.attr("enctype", "multipart/form-data");
        $this.prepend(mk_input("cid", cid));
        $this.prepend(mk_input("action", $this.attr("the_action")));
    });
    function changing_page(page) {
        let $this = this;
        let pf = $this.my ? "#my_status" : "#status";
        this.current_page = page;
        let fd = new FormData();
        let user_key = $this.my ? "#username" : "#status_filter_username";
        fd.append("user", $(user_key).val().toLowerCase());
        fd.append("pid", $this.pid);
        fd.append("lang", $this.lang);
        fd.append("result", $this.result);
        fetch("/contest/" + cid + "/status/" + page, {
            method: "POST",
            headers: {"x-csrf-token": $("#csrf_token").val()},
            body: fd
        }).then(function (response) {
            return response.json();
        }).then(function (data) {
            page = +data["page"];
            let table = $(pf+"_table");
            table.empty();
            for (let obj of data["data"]) {
                let line = $("<tr>");
                if (obj["can_see"]) {
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href", "/submission/" + obj["idx"])));
                } else {
                    line.append($('<th scope="row">').text(obj["idx"]));
                }
                line.append($('<td>').text(timestamp_to_str(obj["time"])));
                if(!$this.my){
                    if(obj["user_id"]==="???"){
                        line.append($('<td>').text("???"));
                    }else {
                        line.append($('<td>').append($("<a>").text(obj["user_name"]).attr("href", "/user/" + obj["user_id"])));
                    }
                }
                if(obj["problem"]==="?"){
                    line.append($('<td>').text("???"));
                }else{
                    line.append($('<td>').append($("<a>").text(obj["problem"] + ". " + obj["problem_name"]).attr("href", "/contest/" + cid + "/problem/" + obj["problem"])));
                }
                line.append($('<td>').text(obj["lang"]));
                line.append($('<td>').text(obj["result"]));
                if (!$this.my&&obj["can_rejudge"]){
                    let btn = $('<button class="btn btn-primary btn-sm">').text("Rejudge").data("no-refresh", "true");
                    resolve_submitter.call(btn);
                    let form = $('<form action="/rejudge" method="post" target="_self" enctype="multipart/form-data">')
                    form.append(mk_input("cid", cid)).append(mk_input("idx", obj["idx"])).append(btn);
                    line.append($('<td>').append(form));
                    let btn0 = $('<button class="btn btn-danger btn-sm">').text("Reject").data("no-refresh", "true");
                    resolve_submitter.call(btn0);
                    let form0 = $('<form action="/reject" method="post" target="_self" enctype="multipart/form-data">')
                    form0.append(mk_input("cid", cid)).append(mk_input("idx", obj["idx"])).append(btn0);
                    line.append($('<td>').append(form0));
                }
                table.append(line);
            }
            let pagination = $(pf+"_page");
            pagination.empty();
            let first = $('<li class="page-item">');
            if (page === 1) {
                first.addClass("disabled");
            }
            let first_btn = $('<a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>');
            first_btn.click(function () {
                $this.change_page(1)
            });
            first.append(first_btn);
            pagination.append(first);
            for (let i of data["show_pages"]) {
                let li = $('<li class="page-item">');
                if (i === page)
                    li.addClass("active");
                let a = $('<a class="page-link">').text(i);
                a.click(function () {
                    $this.change_page(i)
                });
                li.append(a);
                pagination.append(li);
            }
            let last = $('<li class="page-item">');
            if (page === data["page_cnt"]) {
                last.addClass("disabled");
            }
            let last_btn = $('<a class="page-link" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>');
            last_btn.click(function () {
                $this.change_page(data["page_cnt"])
            });
            last.append(last_btn);
            pagination.append(last);
        });
    }
    function status_resolve(my){
        let obj = {
            my: my,
            current_page: 1,
            pid: "",
            lang: "",
            result: ""
        }
        obj.change_page = changing_page.bind(obj);
        let pf = obj.my ? "#my_status" : "#status";

        let inited = false;
        $(pf+"_tab").click(function () {
            if (!inited) {
                inited = true;
                obj.change_page(obj.current_page);
            }
        });
        if (location.hash === pf) $(pf+"_tab").click();
        $(pf+"_filter").click(function () {
            obj.pid = $(pf+"_filter_pid").val();
            obj.lang = $(pf+"_filter_lang").val();
            obj.result = $(pf+"_filter_result").val();
            obj.change_page(obj.current_page);
        });
    }
    status_resolve(false);
    status_resolve(true);
    $("#rejudge_btn").click(async function () {
        let fd = new FormData();
        fd.append("user", $("#status_filter_username").val().toLowerCase());
        let pid = $("status_filter_pid").val();
        let lang = $("#status_filter_lang").val();
        let result = $("#status_filter_result").val();
        if (pid) fd.append("pid", pid);
        if (lang) fd.append("lang", lang);
        if (result) fd.append("result", result);
        fd.append("cid", cid);
        let res = await fetch("/rejudge_all", {
            method: "POST",
            headers: {"x-csrf-token": $("#csrf_token").val()},
            body: fd
        });
        if (res.ok){
            show_modal("成功", "Rejudge", false, text, false);
        }else {
            let text = await res.text();
            if (res.status === 500) {
                show_modal("失敗", "伺服器內部錯誤，log uid=" + text);
            } else {
                let msg = text;
                if (res.status === 403) msg = "您似乎沒有權限執行此操作"
                show_modal("失敗", msg);
            }
        }
    });
    {
        var data;
        var standing_ok = false;

        function refresh_standing() {
            if (!standing_ok) return;
            $("#standing_loading").removeClass("d-none", true);
            $("#standing_table thead tr").empty();
            $("#standing_table tbody").empty();
            if (data["judging"]) {
                $("#standing_judging").removeClass("d-none");
            } else {
                $("#standing_judging").addClass("d-none");
            }
            console.log(data);
            let pers = {};
            for (let o of data["pers"]) {
                pers[o["idx"]] = o;
            }
            let official_only = $("#standing_official_only").prop("checked");
            if (data['rule'] === "ioi") {
                let out = {};
                for (let user of data["participants"]) {
                    let key = user + ";" + data["main_per"];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "last_update": 0,
                            "is_main": true, "is_practice": false
                        }
                        for (let pid of data["pids"]) out[key]["scores"][pid] = {}
                    }
                }
                for (let user in data["virtual_participants"]) {
                    let key = user + ";" + data["virtual_participants"][user];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "last_update": 0,
                            "is_main": false, "is_practice": false
                        }
                        for (let pid of data["pids"]) out[key]["scores"][pid] = {}
                    }
                }
                for (let obj of data['submissions']) {
                    let key = obj["user"] + ";" + obj["per"];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "last_update": 0,
                            "is_main": (obj["per"] === data["main_per"]), "is_practice": (obj["per"] == null)
                        }
                        for (let pid of data["pids"]) out[key]["scores"][pid] = {}
                    }
                    for (let k in obj["scores"]) {
                        out[key]["scores"][obj["pid"]][k] = Math.max(out[key]["scores"][obj["pid"]][k] || 0, obj["scores"][k]);
                    }
                    let tot = 0;
                    for (let pid of data["pids"]) {
                        for (let k in out[key]["scores"][pid]) {
                            tot += out[key]["scores"][pid][k];
                        }
                    }
                    if (Number(tot) !== Number(out[key]["total_score"])) {
                        out[key]["total_score"] = tot;
                        out[key]["last_update"] = obj["time"] - (obj["per"] == null ? 0 : pers[obj["per"]]["start_time"]);
                    }
                }
                let arr = [];
                for (let k in out) {
                    let obj = out[k];
                    obj["user"] = k;
                    arr.push(obj);
                }

                function le(x, y) {
                    if (x["is_practice"] < y["is_practice"]) return true;
                    if (x["is_practice"] > y["is_practice"]) return false;
                    if (x["total_score"] > y["total_score"]) return true;
                    if (x["total_score"] < y["total_score"]) return false;
                    return x["last_update"] < y["last_update"];
                }

                arr.sort(function (x, y) {
                    if (le(x, y)) {
                        return -1;
                    }
                    if (le(y, x)) {
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
                for (let pid of data["pids"]) {
                    tl.append($('<th scope="col">').text(pid));
                }
                tl.append($('<th scope="col">').text("Time"));
                let cur_rank = 1;
                for (let obj of arr) {
                    if (official_only && !obj["is_main"]) continue;
                    let key = obj["user"];
                    let username = key.substring(0, key.lastIndexOf(";"));
                    let per_id = key.substring(key.lastIndexOf(";") + 1, key.length);
                    let rank = "";
                    if (obj["is_main"]) {
                        rank = "" + cur_rank;
                        cur_rank++;
                    } else if (obj["is_practice"]) {
                        rank = "*";
                    }
                    let tr = $("<tr>");
                    tr.append($('<th scope="row">').text(rank));
                    tr.append($('<td>').text(username));
                    tr.append($('<td>').text(obj["total_score"]));
                    for (let pid of data["pids"]) {
                        let cur = 0;
                        for (let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                        tr.append($('<td>').text("" + cur));
                    }
                    let time = "";
                    if (!obj["is_practice"]) time = "" + Math.floor(obj["last_update"] / 60);
                    tr.append($('<td>').text(time));
                    tb.find("tbody").append(tr);
                }
            } else if (data['rule'] === "icpc") {
                let out = {};
                let penalty = data['penalty'];
                for (let user of data["participants"]) {
                    let key = user + ";" + data["main_per"];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "total_penalty": 0,
                            "is_main": true, "is_practice": false
                        }
                        for (let pid of data["pids"]) {
                            out[key]["scores"][pid] = {"score": 0, "penalty_cnt": 0, "cnt": 0, "penalty": 0}
                        }
                    }
                }
                for (let user in data["virtual_participants"]) {
                    let key = user + ";" + data["virtual_participants"][user];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "total_penalty": 0,
                            "is_main": false, "is_practice": false
                        }
                        for (let pid of data["pids"]) {
                            out[key]["scores"][pid] = {"score": 0, "penalty_cnt": 0, "cnt": 0, "penalty": 0}
                        }
                    }
                }
                for (let obj of data['submissions']) {
                    let key = obj["user"] + ";" + obj["per"];
                    if (out[key] === undefined) {
                        out[key] = {
                            "scores": {}, "total_score": 0, "total_penalty": 0,
                            "is_main": (obj["per"] == data["main_per"]), "is_practice": (obj["per"] == null)
                        }
                        for (let pid of data["pids"]) {
                            out[key]["scores"][pid] = {"score": 0, "penalty_cnt": 0, "cnt": 0, "penalty": 0}
                        }
                    }
                    let start_time = pers[data["main_per"]]["start_time"];
                    if (obj["per"]) start_time = pers[obj["per"]]["start_time"];
                    let cur_time = Math.floor((obj["time"] - start_time) / 60);
                    let cur = out[key]["scores"][obj["pid"]];
                    if (obj["total_score"] > cur["score"]) {
                        cur["score"] = obj["total_score"];
                        cur["penalty_cnt"] = cur["cnt"];
                        cur["penalty"] = cur_time + cur["penalty_cnt"] * penalty;
                    }
                    cur["cnt"]++;
                    let tot = 0;
                    let totp = 0;
                    for (let pid of data["pids"]) {
                        tot += out[key]["scores"][pid]["score"];
                        totp += out[key]["scores"][pid]["penalty"];
                    }
                    out[key]["total_score"] = tot;
                    out[key]["total_penalty"] = totp;
                }
                let arr = [];
                for (let k in out) {
                    let obj = out[k];
                    obj["user"] = k;
                    arr.push(obj);
                }

                function le(x, y) {
                    if (x["is_practice"] < y["is_practice"]) return true;
                    if (x["is_practice"] > y["is_practice"]) return false;
                    if (x["total_score"] > y["total_score"]) return true;
                    if (x["total_score"] < y["total_score"]) return false;
                    return x["total_penalty"] < y["total_penalty"];
                }

                arr.sort(function (x, y) {
                    if (le(x, y)) {
                        return -1;
                    }
                    if (le(y, x)) {
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
                for (let pid of data["pids"]) {
                    tl.append($('<th scope="col">').text(pid));
                }
                let cur_rank = 1;
                console.log(arr)
                for (let obj of arr) {
                    if (official_only && !obj["is_main"]) continue;
                    let key = obj["user"];
                    let username = key.substring(0, key.lastIndexOf(";"));
                    let per_id = key.substring(key.lastIndexOf(";") + 1, key.length);
                    let tr = $("<tr>");
                    let rank = "";
                    if (obj["is_main"]) {
                        rank = "" + cur_rank;
                        cur_rank++;
                    } else if (obj["is_practice"]) {
                        rank = "*";
                    }
                    tr.append($('<th scope="row">').text(rank));
                    tr.append($('<td>').text(username));
                    tr.append($('<td>').text(obj["total_score"]));
                    tr.append($('<td>').text(obj["is_practice"] ? "" : obj["total_penalty"]));
                    for (let pid of data["pids"]) {
                        let cur = 0;
                        let cnt = obj["scores"][pid]["penalty_cnt"];
                        let rt = obj["scores"][pid]["penalty"] - cnt * penalty;
                        for (let k in obj["scores"][pid]) cur += obj["scores"][pid][k];
                        let line = "" + obj["scores"][pid]["score"];
                        if (!obj["is_practice"]) line += "/" + rt + "+" + cnt;
                        tr.append($('<td>').text(line));
                    }
                    tb.find("tbody").append(tr);
                }
            }
            $("#standing_loading").addClass("d-none", true);
        }

        function load_standing() {
            standing_ok = false;
            $("#standing_loading").removeClass("d-none", true);
            $("#standing_error").addClass("d-none", true);
            $("#standing_table thead tr").empty();
            $("#standing_table tbody").empty();
            fetch("/contest/" + cid + "/standing", {
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()}
            }).then(function (response) {
                if (response.ok) {
                    return response.json();
                } else if (response.status === 403) {
                    $("#standing_error").text("目前無法觀看記分板").removeClass("d-none");
                } else {
                    $("#standing_error").text("Error " + response.status + " " + response.statusText).removeClass("d-none");
                }
                $("#standing_loading").addClass("d-none", true);
                throw new Error("Network response was not ok.");
            }).then(function (got_data) {
                data = got_data;
                standing_ok = true;
                refresh_standing();
            });
        }

        let inited = false;
        $("#standing_tab").click(function () {
            if (!inited) {
                inited = true;
                load_standing();
            }
        });
        $("#standing_official_only").on("change", refresh_standing);
        if (location.hash == "#standing") $("#standing_tab").click();
        $("#standing_refresh").click(load_standing);
        let auto_refresh = false;
        $("#standing_auto_refresh").change(function () {
            auto_refresh = $(this).prop("checked");
        });
        window.setInterval(function () {
            if (auto_refresh) load_standing();
        }, 20000);
    }
    let contest_status = $("#contest_status").data("status");
    let status_mp = {
        "practice": "練習模式",
        "waiting_virtual": "等待模擬競賽開始",
        "waiting": "等待競賽開始",
        "running": "競賽進行中",
        "running_virtual": "模擬競賽進行中",
        "guest": "僅觀看",
        "testing": "測試模式"
    };
    $("#contest_status").text(status_mp[contest_status]);
    if ($("#save_order").length) {
        let moveing_problem = null;
        $("tr.problem").attr("draggable", "true").on("dragstart", function (e) {
            moveing_problem = $(this);
        }).on("dragover", function (e) {
            e.preventDefault();
        }).on("dragenter", function (e) {
            e.preventDefault();
        }).on("drop", function (e) {
            e.preventDefault();
            $(this).before(moveing_problem);
            moveing_problem = null;
        });
        $("#save_order").click(function () {
            let fd = new FormData();

            fd.append("cid", cid);
            fd.append("action", "save_order");
            let arr = [];
            $("tr.problem").each(function () {
                arr.push($(this).data("index"));
            });
            fd.append("order", arr.join(","));
            fetch("/contest_action", {
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function (response) {
                if (response.ok) {
                    show_modal("成功", "成功儲存順序", true);
                } else {
                    let msg = null;
                    if (!msg && response.status == 400) msg = "輸入格式不正確"
                    if (!msg && response.status == 403) msg = "您似乎沒有權限執行此操作"
                    show_modal("失敗", msg ? msg : "Error Code: " + response.status);
                }
            });
        });
    }
    $("#save_question_modal").on("show.bs.modal", function (event) {
        let id = $(event.relatedTarget).data("id");
        $("#save_question_id").val(id);
        let reply = $(".question-tr[data-id='" + id + "'] .message-area.reply").text();
        $("#save_question_content").val(reply);
        $("#save_question_check").prop("checked", $(event.relatedTarget).data("public") === "True");
    });
});