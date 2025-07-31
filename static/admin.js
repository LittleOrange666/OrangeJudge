$(function () {
    $("#user_manage").on("show.bs.modal", function (event) {
        let btn = $(event.relatedTarget)
        let username = btn.data('username');
        let displayname = btn.data('displayname');
        let permissions = btn.data('permissions').split(";");
        $("#user_id_input").val(username);
        $("#user_name_input").val(displayname);
        $("#user_password_input").val("");
        $("#user_permission_mp").prop("checked", permissions.includes("make_problems"));
        $("#user_permission_admin").prop("checked", permissions.includes("admin"));
    });
    $("#user_save").click(function () {
        let username = $("#user_id_input").val();
        let display_name = $("#user_name_input").val();
        let password = $("#user_password_input").val();
        let permissions = [];
        if ($("#user_permission_mp").prop("checked")) {
            permissions.push("make_problems");
        }
        if ($("#user_permission_admin").prop("checked")) {
            permissions.push("admin");
        }
        post("/admin", {
            "action": "update_user",
            "username": username,
            "display_name": display_name,
            "password": password,
            "permissions": permissions.join(";")
        }, function (content, status, xhr) {
            if (content === "OK") {
                $("#user_password_input").val("");
                show_modal("成功", "成功更新使用者狀態");
            } else {
                show_modal("失敗", "Error: " + status);
            }
        })
    });
    $("#submit_user_info").click(function () {
        let users = [];
        $("#user_infos tr").each(function () {
            let username = $(this).find("td:nth-child(2)").text();
            let password = $(this).find("td:nth-child(3)").text();
            let email = $(this).find("td:nth-child(4)").text();
            let display_name = $(this).find("td:nth-child(5)").text();
            users.push([username, password, email, display_name]);
        });
        post("/admin", {
            "action": "create_users",
            "users": JSON.stringify(users)
        }, function (content, status, xhr) {
            if (content === "OK") {
                $("#user_infos").empty();
                show_modal("成功", "成功建立使用者");
            } else {
                show_modal("失敗", "Error: " + status);
            }
        })
    });
    $("#parse_user_info").click(function () {
        let form = new FormData();
        form.append("action", "parse_user");
        form.append("file", $("#user_info_file")[0].files[0]);
        let res = fetch("/admin", {
            method: "POST",
            headers: {"x-csrf-token": $("#csrf_token").val()},
            body: form
        });
        res.then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error("Network response was not ok");
            }
        }).then(data => {
            let users = data["users"];
            $("#user_infos").empty();
            for (let i = 0; i < users.length; i++) {
                let user = users[i];
                $("#user_infos").append($("<tr>").append($("<td>").text("" + (i + 1)))
                    .append($("<td>").text(user[0]))
                    .append($("<td>").text(user[1]))
                    .append($("<td>").text(user[2]))
                    .append($("<td>").text(user[3])));
            }
            show_modal("成功", "成功解析使用者資訊");
        }).catch(error => {
            show_modal("失敗", "Error: " + error.message);
        });
    });

    function init_limit_input() {
        let $this = $(this);
        let id = $this.attr("id");
        let val = $this.data("value");
        let vals = val.split(" ");
        let val1 = vals[0];
        let val2 = vals.length > 3 ? vals[2] : "1";
        let val3 = vals.length > 3 ? vals[3] : vals[2];
        let input1 = $(`<input type="number" class="form-control limit-subinput" id="${id}_1" value="${val1}" min="1" step="1">`);
        let input2 = $(`<input type="number" class="form-control limit-subinput" id="${id}_2" value="${val2}" min="1" step="1">`);
        let text1 = $(`<span class="input-group-text">per</span>`);
        let select = $(`<select class="form-select limit-subinput" id="${id}_3"></select>`);
        let options = ["hour", "minute", "second"];
        options.forEach(function (option) {
            let selected = option === val3 ? "selected" : "";
            select.append(`<option value="${option}" ${selected}>${option}</option>`);
        });
        $this.append(input1).append(text1).append(input2).append(select);
    }

    $(".limit-input").each(init_limit_input);

    $("#submit_config").click(async function () {
        let ok = await double_check("確定要更新設定嗎？", "這將會覆蓋目前的設定");
        if (!ok) {
            return;
        }
        let ret = [];
        $(".limit-input").each(function () {
            let $this = $(this);
            let id = $this.attr("id");
            let val1 = $(`#${id}_1`).val();
            let val2 = $(`#${id}_2`).val();
            let val3 = $(`#${id}_3`).val();
            ret.push([id, [val1, val2, val3]]);
        });
        $(".config-input").each(function () {
            let $this = $(this);
            let id = $this.attr("id");
            let val = $this.val();
            if ($this.attr("type") === "checkbox") {
                val = $this.prop("checked") ? "true" : "false";
            }
            ret.push([id, val]);
        });
        console.log(ret);
        let form = new FormData();
        form.append("action", "update_config");
        form.append("config", JSON.stringify(ret));
        let res = await fetch("/admin", {
            method: "POST",
            headers: {"x-csrf-token": $("#csrf_token").val()},
            body: form
        });
        if (res.ok) {
            let content = await res.text();
            if (content === "OK") {
                await async_show_modal("成功", "成功更新設定", 3000);
                location.reload();
            } else {
                show_modal("失敗", "Error: " + content);
            }
        } else {
            let content = await res.text();
            if (res.status === 403) {
                show_modal("失敗", "沒有權限更新設定");
            }else if (res.status === 400){
                show_modal("失敗", "格式錯誤: " + content);
            }else {
                show_modal("失敗", "Error: " + res.statusText);
            }
        }
    });
});