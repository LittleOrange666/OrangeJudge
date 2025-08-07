const lang_opt = $("#langoption");
function update_default_code(){
    let lang = lang_opt.val();
    let code = default_code[lang];
    if (code) {
        $("#codeTextarea").text(code);
    }
}
$("#uploadfile").on("change", function () {
    let files = $(this).prop("files");
    if (!files.length) {
        return false;
    }
    let file = files[0];
    let reader = new FileReader();
    let target = $(this);
    reader.onload = function () {
        $("#codeTextarea").text(this.result);
        target.val(null);
    };
    reader.readAsText(file);
}).prop("accept", lang_exts[lang_opt.val()]);
lang_opt.on("change", function () {
    $("#uploadfile").prop("accept", lang_exts[lang_opt.val()]);
    localStorage.lang = lang_opt.val();
    update_default_code();
});
if (localStorage.lang && lang_opt.find("option[value='" + localStorage.lang + "']").length) {
    lang_opt.val(localStorage.lang).trigger("change");
}
update_default_code();