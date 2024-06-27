$("#uploadfile").on("change",function() {
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
});
$("#uploadfile").prop("accept",lang_exts[$("#langoption").val()]);
$("#langoption").on("change",function(){
    $("#uploadfile").prop("accept",lang_exts[$("#langoption").val()]);
    localStorage.lang = $("#langoption").val();
});
if(localStorage.lang){
    $("#langoption").val(localStorage.lang);
    $("#langoption").trigger("change");
}