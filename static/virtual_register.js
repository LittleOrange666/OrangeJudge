(function () {
    let d = new Date(Date.now() - (new Date()).getTimezoneOffset() * 60000 + 600000);
    d.setSeconds(0);
    d.setMilliseconds(0);
    let s = d.toISOString();
    $("#start_time").val(s.substr(0, s.length - 1)).trigger("input");
})();