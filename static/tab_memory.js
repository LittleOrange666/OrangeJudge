$(function() {
    $("a[role='tab']").each(function(){
        $(this).attr("href",$(this).data("bs-target"));
    });
    $("a[role='tab']").click(function(){
        history.pushState({}, '', this.href);
    });
    if(location.hash) {
        $("a[role='tab'][data-bs-target='"+location.hash+"']").each(function(){
            new bootstrap.Tab(this).show();
        });
    }else{
        history.pushState({}, '', "#"+$("div.tab-pane.fade.show.active")[0].id);
    }
});