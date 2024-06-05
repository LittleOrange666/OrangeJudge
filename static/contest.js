$(function() {
    const cid = $("#cid").val();
    $("form[the_action]").each(function(){
        let $this = $(this);
        $this.attr("action","/contest_action");
        $this.attr("method","post");
        $this.attr("target","_self");
        $this.attr("enctype","multipart/form-data");
        $this.prepend($('<input name="cid" value="'+cid+'" hidden>'));
        $this.prepend($('<input name="action" value="'+$(this).attr("the_action")+'" hidden>'));
    });
});