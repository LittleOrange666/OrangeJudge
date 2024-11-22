const main = $("#main_area");
//code copy
const copyer = document.createElement("textarea");
document.body.appendChild(copyer);
$(copyer).hide();

function add_copy() {
    let p = $(this);
    let text = p.text();
    let copy = $('<button class="copy_btn">copy</button>');
    p.append(copy);
    p.css("position", "relative");
    copy.click(function () {
        copyer.value = text;
        copyer.select();
        copyer.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyer.value);
    });
}

$("div.highlight").addClass("codehilite").removeClass("highlight").each(add_copy);
$("pre.can-copy").each(add_copy);
$("pdf-file").each(function () {
    $(this).append('<embed src="' + $(this).attr("src") + '" type="application/pdf" width="100%" height="100%">')
});
window.setInterval(function () {
    $("textarea").each(function () {
        if (+$(this).prop("scrollHeight") < +$(this).prop("offsetHeight")) $(this).css("height", "100px");
        $(this).css("height", $(this).prop("scrollHeight") + "px");
    });
}, 500);
// textarea resolver
$("textarea").on("input", function () {
    $(this).css("height", $(this).prop("scrollHeight") + "px");
}).on('keydown', function (e) {
    const start = this.selectionStart;
    const end = this.selectionEnd;
    const indent = 4;
    const indents = " ".repeat(indent);
    const old = this.value;
    if (e.key === 'Tab') {
        e.preventDefault();
        let nw = old;
        if (start === end) {
            if (e.shiftKey) {
                if (start >= 4 && old.substring(start - indent, start) === indents) {
                    this.value = old.substring(0, start - indent) + old.substring(start);
                    this.selectionStart = this.selectionEnd = start - indent;
                }
            } else {
                this.value = old.substring(0, start) + indents + old.substring(end);
                this.selectionStart = this.selectionEnd = start + indent;
            }
        } else {
            let pln = old.substring(0, start).lastIndexOf("\n");
            let de = 0;
            if (pln !== -1) de = start - pln - 1;
            if (e.shiftKey) {
                let cur = start;
                cur = nw.indexOf("\n", cur) + 1;
                let cnt = 0;
                while (cur !== 0 && cur <= end - indent * cnt) {
                    if (nw.substring(cur, cur + indent) === indents) {
                        cnt++;
                        nw = nw.substring(0, cur) + nw.substring(cur + indent);
                    }
                    cur = nw.indexOf("\n", cur) + 1;
                }
                this.selectionEnd = end - indent * cnt;
                if (nw.substring(start - de, start - de + indent) === indents) {
                    cnt++;
                    this.value = nw.substring(0, start - de) + nw.substring(start - de + indent);
                    this.selectionStart = start - indent;
                }
            } else {
                let cur = start;
                cur = nw.indexOf("\n", cur) + 1;
                let cnt = 1;
                while (cur !== 0 && cur <= end + indent * cnt) {
                    cnt++;
                    nw = nw.substring(0, cur) + indents + nw.substring(cur);
                    cur = nw.indexOf("\n", cur + indent) + 1;
                }
                this.value = nw.substring(0, start - de) + indents + nw.substring(start - de);
                this.selectionEnd = end + indent * cnt;
                this.selectionStart = start + indent;
            }
        }
    } else if (e.key === "Backspace") {
        if (start === end) {
            let p = old.lastIndexOf("\n", start - 1) + 1;
            let pp = p === 0 ? -1 : old.lastIndexOf("\n", p - 2) + 1;
            let pre = old.substring(p, start);
            let pre2 = pp === -1 ? "" : old.substring(pp, p);
            if (pre === " ".repeat(pre.length)) {
                e.preventDefault();
                let de = pre2.startsWith(pre) ? pre.length + 1 : indent - pre.length % indent;
                this.value = old.substring(0, start - de) + old.substring(start);
                this.selectionStart = this.selectionEnd = start - de;
            } else if (old.substring(start - indent, start) === indents) {
                e.preventDefault();
                this.value = old.substring(0, start - indent) + old.substring(start);
                this.selectionStart = this.selectionEnd = start - indent;
            }
        }
    } else if (e.key === "Delete") {
        if (start === end) {
            if (old.substring(start, start + indent) === indents) {
                e.preventDefault();
                this.value = old.substring(0, start) + old.substring(start + indent);
            }
        }
    } else if (e.key === "Enter") {
        if (start === end) {
            e.preventDefault();
            let p = old.lastIndexOf("\n", start - 1) + 1;
            let c = 0;
            while (old.substring(p, p + indent) === indents) {
                p += indent;
                c++;
            }
            let ch = '';
            if (start > 0) ch = old.substring(start - 1, start + 1);
            if (ch === "{}") {
                c++;
                this.value = old.substring(0, start) + "\n" + indents.repeat(c) + "\n" + old.substring(start);
                this.selectionStart = this.selectionEnd = start + 1 + indent * c;
            } else {
                this.value = old.substring(0, start) + "\n" + indents.repeat(c) + old.substring(start);
                this.selectionStart = this.selectionEnd = start + 1 + indent * c;
            }
        }
    } else if (e.key === "(") {
        if (start === end) {
            e.preventDefault();
            this.value = old.substring(0, start) + "()" + old.substring(start);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    } else if (e.key === "[") {
        if (start === end) {
            e.preventDefault();
            this.value = old.substring(0, start) + "[]" + old.substring(start);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    } else if (e.key === "{") {
        if (start === end) {
            e.preventDefault();
            this.value = old.substring(0, start) + "{}" + old.substring(start);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    }
}).each(function () {
    $(this).data("default-rows", $(this).attr("rows"));
});

function timestamp_to_str(i) {
    return new Date(+i * 1000).toLocaleString()
}

$(".date-string").each(function () {
    $(this).text(timestamp_to_str($(this).text()));
});
$("input[type='datetime-local'][data-value]").each(function () {
    let $this = $(this);
    let s = new Date(+$this.data("value") * 1000 - (new Date()).getTimezoneOffset() * 60000).toISOString();
    $this.val(s.substring(0, s.length - 1));
});
$("input[type='datetime-local']").each(function () {
    let $this = $(this);
    let nw = $("<input>").attr("type", "hidden").attr("name", $this.attr("name")).val(new Date($this.val()).getTime() / 1000);
    $this.after(nw);
    $this.removeAttr("name");
    $this.on("input", function () {
        nw.val(new Date($this.val()).getTime() / 1000);
    });
});
$(".countdown-timer").each(function () {
    let $this = $(this);
    let target = +$this.data("target") * 1000;
    let is_zero = target - (new Date()).getTime() <= 0;
    window.setInterval(function () {
        let delta = Math.max(0, target - (new Date()).getTime());
        delta = Math.floor(delta / 1000);
        let sec = "" + (delta % 60);
        let min = "" + (Math.floor(delta / 60) % 60);
        let hr = "" + Math.floor(delta / 3600);
        if (sec.length < 2) sec = "0" + sec;
        if (min.length < 2) min = "0" + min;
        $this.text(hr + ":" + min + ":" + sec);
        if (!is_zero && (delta <= 0)) location.reload();
    }, 100);
});
$("select[data-value]").each(function () {
    let val = $(this).data("value");
    let vals = $(this).find('option').toArray().map(item => item.value)
    if(vals.includes(val)) $(this).val(val).change();
});
$(".time-string").each(function () {
    let t = Math.floor(+$(this).text());
    let d = Math.floor(t / 1440);
    let h = Math.floor((t % 1440) / 60);
    let m = t % 60;
    $(this).text((d > 0 ? d + ':' : '') + (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m);
});
const myModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('myModal'));
let current_modal_session = "";

function show_modal(title, text, refresh, next_page, skip) {
    document.getElementById('myModal').focus();
    $("#myModalTitle").text(title);
    $("#myModalText").text(text);
    let session_id = +new Date() + "" + Math.random();
    current_modal_session = session_id;
    if (skip) {
        if (next_page) {
            location.href = next_page;
        } else {
            location.reload();
        }
        return;
    }
    if (next_page) {
        $("#myModal").on("hidden.bs.modal", function () {
            if (session_id === current_modal_session) {
                location.href = next_page;
            }
        });
    } else if (refresh) {
        $("#myModal").on("hidden.bs.modal", function () {
            if (session_id === current_modal_session) {
                location.reload();
            }
        });
    }
    myModal.show();
    if (title === "成功") {
        let timeout_id = window.setTimeout(function () {
            myModal.hide();
        }, 3000);
        let close_evt = function (){
            myModal.hide();
        };
        document.addEventListener("keypress", close_evt);
        $("#myModal").on("hidden.bs.modal", function () {
            if (timeout_id !== -1) {
                window.clearTimeout(timeout_id);
                timeout_id = -1;
            }
            if (close_evt){
                document.removeEventListener("keypress", close_evt);
                close_evt = null;
            }
        });
    }
}

$("input[data-checked]").each(function () {
    $(this).prop("checked", $(this).data("checked") === "True")
});
$("div.radio-selector[data-value]").each(function () {
    let val = $(this).data("value");
    $(this).find("input[value=" + val + "][type='radio']").prop("checked", true);
});
$("*[data-disabled]").each(function () {
    if ($(this).data("disabled") === "True") {
        $(this).prop("disabled", true);
        $(this).addClass("disabled");
    }
});
$("*[data-active]").each(function () {
    if ($(this).data("active") === "True") {
        $(this).addClass("active");
    }
});
$("a[data-args]").each(function () {
    let o = $(this).data("args").split("=");
    let url = new URL(location.href);
    if (url.searchParams.has(o[0])) {
        url.searchParams.set(o[0], o[1]);
    } else {
        url.searchParams.append(o[0], o[1]);
    }
    $(this).attr("href", url.href);
});

function _uuid() {
    let d = Date.now();
    if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
        d += performance.now(); //use high-precision timer if available
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = (d + Math.random() * 16) % 16 | 0;
        d = Math.floor(d / 16);
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

$("form").each(function () {
    $(this).append($("#csrf_token").clone().removeAttr("id"));
});

function fetching(form) {
    return fetch(form.attr("action"), {
        method: form.attr("method"),
        headers: {"x-csrf-token": $("#csrf_token").val()},
        body: new FormData(form[0])
    });
}

function post(url, data, callback) {
    $.ajax({
        url: url,
        method: "POST",
        contentType: "application/x-www-form-urlencoded",
        headers: {"x-csrf-token": $("#csrf_token").val()},
        data: data,
        error: function (xhr, status, content) {
            callback(content, status, xhr)
        },
        success: function (content, status, xhr) {
            callback(content, status, xhr)
        }
    });
}

$(".submitter").each(function () {
    let spin = $('<span class="visually-hidden spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>');
    $(this).prepend(spin);
}).click(function (e) {
    e.preventDefault();
    let $this = $(this);
    let action_name = $this.text().trim();
    let ok = true;
    let missings = [];
    $this.parents("form").find("input,select,textarea").each(function () {
        if ($(this).prop("required") && !$(this).val()) {
            let id = $(this).attr("id");
            let label = $("label[for=" + id + "]");
            let name = label.length ? label.text() : $(this).attr("name");
            missings.push('"'+name+'"');
            ok = false;
        }
    });
    if (!ok) {
        show_modal("錯誤", missings.join(", ") + " 未填寫");
        return;
    }
    let bads = [];
    $this.parents("form").find("input,select,textarea").each(function () {
        if(!$(this).prop("required")) return;
        let bad_pattern = $(this).prop("pattern") && !$(this).val().match(RegExp($(this).prop("pattern")));
        let bad_number = $(this).prop("type") === "number" &&
            (isNaN(+$(this).val()) || +$(this).val() < $(this).prop("min") || +$(this).val() > $(this).prop("max"));
        let id = $(this).attr("id");
        let label = $("label[for=" + id + "]");
        let name = label.length ? label.text() : $(this).attr("name");
        if (bad_pattern) {
            let info = $(this).data("format") || "格式不正確";
            bads.push('"'+name+'" '+info);
            ok = false;
        }
        if (bad_number) {
            let info = $(this).data("format") || "應界於 "+$(this).prop("min")+" 與 "+$(this).prop("max")+" 之間";
            bads.push('"'+name+'" '+info);
            ok = false;
        }
    });
    if (!ok || $this.parents("form")[0].onsubmit && !$this.parents("form")[0].onsubmit()) {
        show_modal("錯誤", bads.join("\n"));
        return;
    }
    $this.find("span").removeClass("visually-hidden");
    let modals = $this.parents(".modal");
    let modal = null;
    if (modals.length) modal = bootstrap.Modal.getOrCreateInstance(modals[0]);
    $this.trigger("saved_data");
    fetching($this.parents("form").first()).then(function (response) {
        console.log(response);
        if (modal) modal.hide();
        $this.find("span").addClass("visually-hidden");
        if (response.ok) {
            if (!!$this.data("redirect")) {
                response.text().then(function (text) {
                    show_modal("成功", "成功" + action_name, !$this.data("no-refresh"), text, !!$this.data("skip-success"));
                });
            } else if ($this.data("filename")) {
                response.blob().then(function (blob) {
                    let url = window.URL.createObjectURL(blob);
                    let a = $("<a/>").attr("href", url).attr("download", $this.data("filename"));
                    a[0].click();
                    window.URL.revokeObjectURL(url);
                });
            } else {
                show_modal("成功", "成功" + action_name, !$this.data("no-refresh"), $this.data("next"), !!$this.data("skip-success"));
            }
        } else {
            response.text().then(function (text) {
                if (response.status === 500) {
                    show_modal("失敗", "伺服器內部錯誤，log uid=" + text);
                } else {
                    let msg = $this.data("msg-" + response.status);
                    if ($this.data("msg-type-" + response.status) === "return") msg = text;
                    if (!msg && response.status === 400) {
                        if (text.includes("The CSRF token")) msg = "CSRF token失效，請刷新頁面再試一次";
                        else msg = "輸入格式不正確"
                    }
                    if (!msg && response.status === 403) msg = "您似乎沒有權限執行此操作"
                    show_modal("失敗", msg ? msg : "Error Code: " + response.status);
                }
            });
        }
    });
});