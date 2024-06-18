$(function(){
    $("#user_manage").on("show.bs.modal",function(event){
        let btn = $(event.relatedTarget)
        let username = btn.data('username');
        let displayname = btn.data('displayname');
        let permissions = btn.data('permissions').split(";");
        $("#user_id_input").val(username);
        $("#user_name_input").val(displayname);
        $("#user_password_input").val("");
        $("#user_permission_mp").prop("checked",permissions.includes("make_problems"));
        $("#user_permission_admin").prop("checked",permissions.includes("admin"));
    });
    $("#user_save").click(function(){
        let username = $("#user_id_input").val();
        let display_name = $("#user_name_input").val();
        let password = $("#user_password_input").val();
        let permissions = [];
        if($("#user_permission_mp").prop("checked")){
            permissions.push("make_problems");
        }
        if($("#user_permission_admin").prop("checked")){
            permissions.push("admin");
        }
        post("/admin",{
            "action": "update_user",
            "username":username,
            "display_name":display_name,
            "password":password,
            "permissions":permissions.join(";")
        },function(content, status, xhr){
            if (content=="OK"){
                $("#user_password_input").val("");
                show_modal("成功","成功更新使用者狀態");
            }else{
                show_modal("失敗","Error: " + status);
            }
        })
    });
});