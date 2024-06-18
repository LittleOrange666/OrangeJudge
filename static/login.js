next.value = new URL(document.location).searchParams.get("next");
if (location.hash=="#fail"){
    let url = new URL(location.href);
    url.hash = ""
    history.replaceState({}, "", url.href);
    show_modal("登入失敗","帳號或密碼錯誤");
}