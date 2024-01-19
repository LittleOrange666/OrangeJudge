var main = $("#main_area");
var $body = (window.opera) ? (document.compatMode == "CSS1Compat" ? $('html') : $('body')) : $('html,body');
//code copy
var copyer = document.createElement("textarea");
document.body.appendChild(copyer);
$(copyer).hide();
$("div.highlight").addClass("codehilite");
$("div.highlight").removeClass("highlight");
$("div.codehilite").each(function() {
    let text = $(this).text();
    let p = $(this);
    let copy = $('<button class="copy_btn">copy</button>');
    p.append(copy);
    p.css("position","relative");
    copy.click(function() {
        copyer.value = text;
        copyer.select();
        copyer.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyer.value);
    });
});
$("pdf-file").each(function(){
    $(this).append('<embed src="'+$(this).attr("src")+'" type="application/pdf" width="100%" height="100%">')
});
$("textarea").each(function(){
    $(this).data("default-rows",$(this).attr("rows"));
});
$("textarea").on("input",function(){
    let rc = 1 + ($(this).val().match(/\n/g) || []).length;
    $(this).attr("rows",Math.max(rc,+$(this).data("default-rows")));
});
$("textarea").trigger("input");
$("textarea").on('keydown', function(e) {
  if (e.key == 'Tab') {
    e.preventDefault();
    var start = this.selectionStart;
    var end = this.selectionEnd;

    // set textarea value to: text before caret + tab + text after caret
    this.value = this.value.substring(0, start) +
      "    " + this.value.substring(end);

    // put caret at right position again
    this.selectionStart =
      this.selectionEnd = start + 1;
  }
});
$(".date-string").each(function(){
    $(this).text(new Date(+$(this).text()).toLocaleString());
});
var myModal = new bootstrap.Modal(document.getElementById('myModal'));
function show_modal(title, text, refresh){
    $("#myModalTitle").text(title);
    $("#myModalText").text(text);
    myModal.show();
    if (refresh) {
        $("#myModal").on("hidden.bs.modal", function(){
            location.reload();
        });
    }
}
$("input[data-checked]").each(function(){
    $(this).prop("checked",$(this).data("checked")==="True")
});
$("*[data-disabled]").each(function(){
    if($(this).data("disabled")==="True"){
        $(this).prop("disabled",true);
        $(this).addClass("disabled");
    }
});
$("*[data-active]").each(function(){
    if($(this).data("active")==="True"){
        $(this).addClass("active");
    }
});
$("a[data-args]").each(function(){
    let o = $(this).data("args").split("=");
    let url = new URL(location.href);
    if (url.searchParams.has(o[0])){
        url.searchParams.set(o[0],o[1]);
    }else{
        url.searchParams.append(o[0],o[1]);
    }
    $(this).attr("href",url.href);
});
let url = new URL(location.href);
url.pathname = "/login"
url.searchParams.append("next",location.pathname);
if (location.pathname=="/login"){
    $("#login_btn").hide();
}else{
    $("#login_btn").attr("href",url.href)
}
function _uuid() {
  var d = Date.now();
  if (typeof performance !== 'undefined' && typeof performance.now === 'function'){
    d += performance.now(); //use high-precision timer if available
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = (d + Math.random() * 16) % 16 | 0;
    d = Math.floor(d / 16);
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}