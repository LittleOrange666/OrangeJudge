$("#get-code").click(function () {
    let email = $("#email").val();
    if (!email.match(/^[\w-.]+@([\w-]+\.)+[\w-]{2,4}$/g)) show_modal("錯誤", "email格式不合法");
    else {
        $.ajax({
            url: "/get_code",
            method: "POST",
            contentType: "application/x-www-form-urlencoded",
            headers: {"x-csrf-token": $("#csrf_token").val()},
            data: {"email": email},
            error: function (xhr, status, content) {
                show_modal("錯誤", "獲取失敗");
            },
            success: function (content, status, xhr) {
                if (content) {
                    show_modal("成功", "驗證碼為'" + content + "'，十分鐘內有效");
                } else {
                    show_modal("成功", "驗證碼已發送至'" + email + "'，十分鐘內有效");
                }
            }
        });
    }
});

function validateForm() {
    if ($("#password").val() !== $("#password_again").val()) {
        show_modal("錯誤", "密碼不一致");
        return false;
    }
    return true;
}