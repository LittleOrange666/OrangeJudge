$(function () {
    const pid = $("#pid").val();
    const username = $("#username").val();
    const number_reg = /^\d+$/;
    let version_checked = false;

    $("form[the_action]").each(function () {
        let $this = $(this);
        $this.attr("action", "/problemsetting_action");
        $this.attr("method", "post");
        $this.attr("target", "_self");
        $this.attr("enctype", "multipart/form-data");
        $this.prepend($('<input name="pid" value="' + pid + '" hidden>'));
        $this.prepend($('<input name="user" value="' + username + '" hidden>'));
        $this.prepend($('<input name="action" value="' + $(this).attr("the_action") + '" hidden>'));
    });
    $("a[href^='/problemsetting_preview']").each(function () {
        $(this).attr("href", $(this).attr("href") + "&user=" + username)
    });
    $(".edit-detector").each(function () {
        let div = $(this);
        div.addClass("alert");
        div.addClass("alert-danger");
        div.hide();
        div.attr("role", "alert");
        div.text("注意!此處有變更尚未儲存!");
        let parent = div.parent();
        let eles = parent.find(".form-control");
        let checks = parent.find(".form-check-input");
        eles.each(function () {
            $(this).data("old_value", $(this).val());
        });
        checks.each(function () {
            $(this).data("old_value", $(this).prop("checked"));
        });
        let saver = parent.find(".data-saver");
        saver.prop("disabled", true);
        let checkers = parent.find(".update-checker");
        checkers.data("changed", false)

        function check() {
            let changed = false;
            eles.each(function () {
                if ($(this).data("old_value") !== $(this).val()) changed = true;
            });
            checks.each(function () {
                if ($(this).data("old_value") !== $(this).prop("checked")) changed = true;
            });
            checkers.each(function () {
                if ($(this).data("changed")) changed = true;
            });
            if (changed) {
                div.show();
                saver.prop("disabled", false);
            } else {
                div.hide();
                saver.prop("disabled", true);
            }
        }

        eles.on("change", check);
        eles.on("input", check);
        checks.on("change", check);
        checks.on("input", check);
        div.on("check_update", check);
        saver.on("check_update", check);
        saver.on("saved_data", function () {
            eles.each(function () {
                $(this).data("old_value", $(this).val());
            });
            checks.each(function () {
                $(this).data("old_value", $(this).prop("checked"));
            });
            div.hide();
            version_checked = false;
            $("#version_checker").addClass("alert-warning").removeClass("alert-danger").removeClass("alert-success")
                .text("正在檢測版本是否有更新，請稍候...");
        });
    });
    // general info
    // statement
    $("#save_statement").click(function () {
        $("#save_statement").prop("disabled", true);
        $("#create_version").prop("disabled", true);
        let main = $("#statement_main_area").val();
        let input = $("#statement_input_area").val();
        let output = $("#statement_output_area").val();
        let interaction = $("#statement_interaction_area").val();
        let scoring = $("#statement_scoring_area").val();
        let note = $("#statement_note_area").val();
        let full = $("#statement_full_area").val();
        let samples = [];
        $("#manual_samples").find(".row").each(function () {
            samples.push([$(this).find("textarea").eq(0).val(), $(this).find("textarea").eq(1).val()]);
        });
        post("/problemsetting_action", {
            "action": "save_statement",
            "pid": pid,
            "statement_main": main,
            "statement_input": input,
            "statement_output": output,
            "statement_interaction": interaction,
            "statement_scoring": scoring,
            "statement_note": note,
            "statement_full": full,
            "samples": JSON.stringify(samples)
        }, function (data, status, xhr) {
            let btn = $("#save_statement");
            btn.prop("disabled", false);
            if (status === "success") {
                show_modal("成功", "儲存成功");
                btn.trigger("saved_data");
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });

    function remove_sample() {
        $(this).parents(".row").first().remove();
        let it = 1;
        $("#manual_samples").find(".row").each(function () {
            $(this).find("label").eq(0).text("Input " + it);
            $(this).find("label").eq(1).text("Output " + it);
            it++;
        });
    }

    $(".remove_sample").click(remove_sample);
    $("#add_sample").click(function () {
        let id = _uuid();
        let e = $(`                <div class="row">
                    <div class="col">
                        <label for="sample_input_${id}" class="form-label">Input 1</label>
                        <textarea class="form-control" id="sample_input_${id}"
                                  rows="3"></textarea>
                    </div>
                    <div class="col">
                        <label for="sample_output_${id}" class="form-label">Output 1</label>
                        <textarea class="form-control" id="sample_output_${id}"
                                  rows="3"></textarea>
                    </div>
                    <div class="col">
                        <button class="btn btn-danger remove_sample">刪除範例</button>
                    </div>
                </div>`);
        $(this).before(e);
        let it = 1;
        $("#manual_samples").find(".row").each(function () {
            $(this).find("label").eq(0).text("Input " + it);
            $(this).find("label").eq(1).text("Output " + it);
            it++;
        });
        e.find(".remove_sample").click(remove_sample);
    });
    // files
    $(".remove_public_file").click(function () {
        let filename = $(this).parent().parent().find("a").text();
        $("#create_version").prop("disabled", true);
        $(this).prop("disabled", true);
        post("/problemsetting_action", {
            "action": "remove_public_file",
            "pid": pid,
            "filename": filename
        }, function (data, status, xhr) {
            if (status === "success") {
                show_modal("成功", "成功刪除公開檔案\"" + filename + "\"", true);
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $(".remove_file").click(function () {
        let filename = $(this).parent().parent().find("a").text();
        $("#create_version").prop("disabled", true);
        $(this).prop("disabled", true);
        post("/problemsetting_action", {
            "action": "remove_file",
            "pid": pid,
            "filename": filename
        }, function (data, status, xhr) {
            if (status === "success") {
                show_modal("成功", "成功刪除程式檔案\"" + filename + "\"", true);
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $(".collapse_file_edit").each(function () {
        let $this = $(this);
        let $line = $this.prev();
        $this.data("filename", $line.find("a").text());
        let $btn = $this.find("button");
        let $select = $this.find("select");
        $select.val($line.find(".file_type").text())
        $btn.click(function () {
            $btn.prop("disabled", true);
            let content = $this.find("textarea").val();
            let filename = $this.data("filename");
            post("/problemsetting_action", {
                "action": "save_file_content",
                "pid": pid,
                "filename": filename,
                "content": content,
                "type": $select.val()
            }, function (data, status, xhr) {
                if (status === "success") {
                    show_modal("成功", "儲存成功");
                    $this.find("textarea").data("old_value", $this.find("textarea").val());
                    $btn.trigger("check_update");
                    $btn.prop("disabled", false);
                    $line.find(".file_type").text($select.val())
                } else {
                    show_modal("失敗", "Error Code: " + xhr.status);
                    $btn.prop("disabled", false);
                }
            });
        });
    }).on("show.bs.collapse", function () {
        let $this = $(this);
        $.get('/problemsetting_preview?pid=' + pid + '&type=file&name=' + $this.data("filename"), function (data, status) {
            $this.find("textarea").val(data);
            $this.find("textarea").trigger("input");
        });
    }).on("shown.bs.collapse", function () {
        $('html, body').scrollTop($(this).offset().top);
    });
    // judge
    $("#choose_checker").submit(function () {
        let dat = new FormData(this);
        let ret = dat.get(dat.get("checker_type") + "_checker") !== "選擇檔案";
        if (!ret)
            show_modal("錯誤", "請選擇一個檔案");
        return ret;
    });
    $(".alternative_fileselect").change(function () {
        $(this).prev().find("input").click();
    });
    // tests
    $("#upload_zipfile").click(function () {
        $(this).prop("disabled", true);
        $(this).find("span").removeClass("visually-hidden");
        fetching($(this).parent().parent()).then(() => location.reload());
    });
    var moveing_testcase = null;
    $("tr.testcase").attr("draggable", "true").on("dragstart", function (e) {
        moveing_testcase = $(this);
    }).on("dragover", function (e) {
        e.preventDefault();
    }).on("dragenter", function (e) {
        e.preventDefault();
    }).on("drop", function (e) {
        e.preventDefault();
        $(this).before(moveing_testcase);
        moveing_testcase = null;
        $("#tests .update-checker").data("changed", !$("tr.testcase th").toArray().map((o) => +o.textContent).every((v, i, a) => !i || a[i - 1] <= v));
        $("#tests .edit-detector").trigger("check_update");
    });
    $("#save_testcase").click(function () {
        $("#save_testcase").prop("disabled", true);
        let dat = $("tr.testcase-normal").toArray().map(function (o) {
            return [+$(o).find("th").text(), $(o).find("input[type='checkbox'].is_sample").prop("checked"),
                $(o).find("input[type='checkbox'].is_pretest").prop("checked"),
                $(o).find("select.form-select").val()];
        });
        post("/problemsetting_action", {
            "action": "save_testcase",
            "pid": pid,
            "modify": JSON.stringify(dat)
        }, function (data, status, xhr) {
            if (status === "success") {
                show_modal("成功", "儲存成功");
                $("#save_testcase").trigger("saved_data");
                let ths = $("tr.testcase th");
                for (let i in ths) {
                    ths[i].textContent = "" + i;
                }
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $("#save_testcase_gen").click(function () {
        $("#save_testcase_gen").prop("disabled", true);
        let dat = $("tr.testcase-gen").toArray().map(function (o) {
            return [+$(o).find("th").text(), $(o).find("input[type='checkbox']").prop("checked")];
        });
        post("/problemsetting_action", {
            "action": "save_testcase_gen",
            "pid": pid,
            "modify": JSON.stringify(dat)
        }, function (data, status, xhr) {
            if (status === "success") {
                show_modal("成功", "儲存成功");
                $("#save_testcase_gen").trigger("saved_data");
                let ths = $("tr.testcase th");
                for (let i in ths) {
                    ths[i].textContent = "" + i;
                }
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $("#create_group").click(function () {
        let content = $("#group_name_input").val();
        if (!content) {
            show_modal("錯誤", "名稱不可為空");
            return;
        }
        $("#create_group").prop("disabled", true);
        $(this).find("span").removeClass("visually-hidden");
        post("/problemsetting_action", {
            "action": "create_group",
            "pid": pid,
            "name": content
        }, function (data, status, xhr) {
            $(this).find("span").addClass("visually-hidden");
            $("#create_group").prop("disabled", false);
            if (status === "success") {
                show_modal("成功", "建立成功", true);
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
            }
        });
    });
    $(".remove_group").click(function () {
        let $this = $(this);
        $this.prop("disabled", true);
        post("/problemsetting_action", {
            "action": "remove_group",
            "pid": pid,
            "name": $this.data("gp")
        }, function (data, status, xhr) {
            $this.prop("disabled", false);
            if (status === "success") {
                show_modal("成功", "刪除成功", true);
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
            }
        });
    });
    {
        let groups = [];
        let dependency = {};
        $("#group_list tr").each(function () {
            let name = $(this).find("th").text().trim();
            groups.push(name);
            dependency[name] = [];
            $(this).find(".dependency span.parents").each(function () {
                dependency[name].push($(this).text().trim());
            });
        });

        function add_dependency(name, parent) {
            dependency[name].push(parent);
            update_dependency();
        }

        function remove_dependency(name, parent) {
            dependency[name].pop(parent);
            update_dependency();
        }

        function update_dependency() {
            $("#group_list tr").each(function () {
                let name = $(this).find("th").text().trim();
                $(this).find(".dependency").empty();
                for (let parent of dependency[name]) {
                    let rmbtn = $('<button type="button" class="btn-close close-sm" aria-label="Close"></button>');
                    rmbtn.click(function () {
                        remove_dependency(name, parent);
                    });
                    $(this).find(".dependency").append(
                        $('<div class="col-auto">').append(
                            $('<div class="alert alert-primary alert-sm-border btn-group" role="alert">')
                                .append($("<span>").text(parent)).append(rmbtn)
                        ).append($('<input type="hidden" name="dependency_' + groups.indexOf(name) + '_' + groups.indexOf(parent) + '" value="yes">'))
                    );
                }
                let remain = [];
                for (let parent of groups) if (parent !== name && !dependency[name].includes(parent)) {
                    remain.push(parent);
                }
                if (remain.length > 0) {
                    let select = $('<select class="form-select" aria-label="select dependency">');
                    let btn = $('<button type="button" class="btn btn-primary btn-sm">+</button>');
                    for (let parent of remain) {
                        select.append($('<option>').val(parent).text(parent));
                    }
                    btn.click(function () {
                        add_dependency(name, select.val());
                    });
                    $(this).find(".dependency").append(
                        $('<div class="col-auto btn-group">').append(select).append(btn)
                    );
                }
            });
        }

        update_dependency();
    }
    // versions
    $("#create_version").click(function () {
        let content = $("#version_name_input").val();
        if (!content) {
            show_modal("錯誤", "描述不可為空");
            return;
        }
        $("#create_version").prop("disabled", true);
        $(this).find("span").removeClass("visually-hidden");
        post("/problemsetting_action", {
            "action": "create_version",
            "pid": pid,
            "description": content
        }, function (data, status, xhr) {
            $(this).find("span").addClass("visually-hidden");
            $("#create_version").prop("disabled", false);
            if (status === "success") {
                show_modal("成功", "建立成功", true);
            } else {
                show_modal("失敗", "Error Code: " + xhr.status);
            }
        });
    });
});