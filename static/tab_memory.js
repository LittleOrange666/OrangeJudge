$(function () {
    $("a[role='tab']").each(function () {
        $(this).attr("href", $(this).data("bs-target"));
    }).click(function () {
        history.replaceState({}, '', this.href);
    });
    if (location.hash) {
        $("a[role='tab'][data-bs-target='" + location.hash + "']").each(function () {
            new bootstrap.Tab(this).show();
        });
    } else {
        history.replaceState({}, '', "#" + $("div.tab-pane.fade.show.active")[0].id);
    }
});