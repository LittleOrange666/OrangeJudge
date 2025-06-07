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
    $("#parse_user_info").click(function(){
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
            for(let i=0; i<users.length; i++) {
                let user = users[i];
                $("#user_infos").append($("<tr>").append($("<td>").text(""+(i+1)))
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
});