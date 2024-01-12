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
$("textarea").on('keydown', function(e) {
  if (e.key == 'Tab') {
    e.preventDefault();
    var start = this.selectionStart;
    var end = this.selectionEnd;

    // set textarea value to: text before caret + tab + text after caret
    this.value = this.value.substring(0, start) +
      "\t" + this.value.substring(end);

    // put caret at right position again
    this.selectionStart =
      this.selectionEnd = start + 1;
  }
});
$(".date-string").each(function(){
    $(this).text(new Date(+$(this).text()).toLocaleString());
});