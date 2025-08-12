const lang_opt = $("#langoption");
const load_sample = $("#load_sample");
function update_default_code(){
    let lang = lang_opt.val();
    let code = default_code[lang];
    if (code) {
        $("#codeTextarea").text(code);
    }
}
function check_default_code() {
    let code = default_code[lang];
    if (code){
        load_sample.prop("disabled", false);
    }else{
        load_sample.prop("disabled", true);
    }
}
load_sample.on("click", update_default_code);
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
    check_default_code();
});
if (localStorage.lang && lang_opt.find("option[value='" + localStorage.lang + "']").length) {
    lang_opt.val(localStorage.lang).trigger("change");
}
check_default_code();