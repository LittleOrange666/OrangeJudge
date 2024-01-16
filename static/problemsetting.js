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
    }
    const pid = $("#pid").val();
    const number_reg = /^\d+$/;
    var myModal = new bootstrap.Modal(document.getElementById('myModal'));
    var version_checked = false;
    var version_changed = false;
    var version_checking = false;
    function fetching(form){
        return fetch(form.attr("action"),{
            method: form.attr("method"),
            body: new FormData(form[0])
        });
    }
    function post(url, data, callback){
        $.ajax({
            url: url,
            method: "POST",
            contentType: "application/x-www-form-urlencoded",
            data: data,
            error: function(xhr, status, content){
                callback(content, status, xhr)
            },
            success: function(content, status, xhr){
                callback(content, status, xhr)
            }
        });
    }
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
    function is_changed(e){
        return $(e).data("old_value") != $(e).val();
    }
    $("form[the_action]").each(function(){
        let $this = $(this);
        $this.attr("action","/problemsetting_action");
        $this.attr("method","post");
        $this.attr("target","_self");
        $this.attr("enctype","multipart/form-data");
        $this.prepend($('<input name="pid" value="'+pid+'" hidden>'));
        $this.prepend($('<input name="action" value="'+$(this).attr("the_action")+'" hidden>'));
    });
    $("input[data-checked]").each(function(){
        $(this).prop("checked",$(this).data("checked")==="True")
    });
    $(".edit-detector").each(function(){
        let div = $(this);
        div.addClass("alert");
        div.addClass("alert-danger");
        div.hide();
        div.attr("role","alert");
        div.text("注意!此處有變更尚未儲存!");
        let parent = div.parent();
        let eles = parent.find(".form-control");
        eles.each(function(){
            $(this).data("old_value", $(this).val());
        });
        let checks = parent.find(".form-check-input");
        checks.each(function(){
            $(this).data("old_value", $(this).prop("checked"));
        });
        let saver = parent.find(".data-saver");
        saver.prop("disabled", true);
        let checkers = parent.find(".update-checker");
        checkers.data("changed",false)
        function check(){
            let changed = false;
            eles.each(function(){
                if ($(this).data("old_value") != $(this).val()) changed = true;
            });
            checks.each(function(){
                if ($(this).data("old_value") != $(this).prop("checked")) changed = true;
            });
            checkers.each(function(){
                if ($(this).data("changed")) changed = true;
            });
            if (changed) {
                div.show();
                saver.prop("disabled", false);
            }else{
                div.hide();
                saver.prop("disabled", true);
            }
        }
        eles.on("change",check);
        eles.on("input",check);
        checks.on("change",check);
        checks.on("input",check);
        div.on("check_update",check);
        saver.on("check_update",check);
        saver.on("saved_data", function(){
            eles.each(function(){
                $(this).data("old_value", $(this).val());
            });
            checks.each(function(){
                $(this).data("old_value", $(this).prop("checked"));
            });
            div.hide();
            version_checked = false;
            $("#version_checker").addClass("alert-warning");
            $("#version_checker").removeClass("alert-danger");
            $("#version_checker").removeClass("alert-success");
            $("#version_checker").text("正在檢測版本是否有更新，請稍候...");
        });
    });
    $(".submitter").click(function(e){
        e.preventDefault();
        let $this = $(this);
        let action_name = $this.text().trim();
        let ok = true;
        $this.parents("form").find("input,select,textarea").each(function(){
            if($(this).prop("required")&&!$(this).val()) ok = false;
        });
        if(!ok){
            show_modal("錯誤","部分資訊未填寫");
            return;
        }
        fetching($this.parents("form").first()).then(function (response) {
            console.log(response);
            if(response.ok) {
                show_modal("成功","成功"+action_name, !$this.data("no-refresh"));
                $("#save_general_info").trigger("saved_data");
            }else {
                let msg = $this.data("msg-"+response.status);
                show_modal("失敗",msg?msg:"Error Code: " + response.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    // general info
    $("#save_general_info").click(function(){
        $("#save_general_info").prop("disabled", true);
        $("#create_version").prop("disabled", true);
        let title = $("#title_input").val();
        let time = $("#time_input").val();
        let memory = $("#memory_input").val();
        if (!number_reg.test(time)){
            show_modal("時間限制格式錯誤","\""+time+"\"不是一個合法的數字");
            return;
        }
        if (Number(time) < 250 || Number(time) > 10000){
            show_modal("時間限制格式錯誤","時間限制需在250至10000之間");
            return;
        }
        if (!number_reg.test(memory)){
            show_modal("空間限制格式錯誤","\""+memory+"\"不是一個合法的數字");
            return;
        }
        if (Number(memory) < 4 || Number(memory) > 1024){
            show_modal("空間限制格式錯誤","空間限制需在4至1024之間");
            return;
        }
        post("/problemsetting_action", {
            "action": "save_general_info",
            "pid": pid,
            "title": title,
            "timelimit": time,
            "memorylimit": memory
        }, function(data,status,xhr){
            $("#save_general_info").prop("disabled",false);
            if(status == "success") {
                show_modal("成功","儲存成功");
                $("#save_general_info").trigger("saved_data");
            }else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    // statement
    $("#save_statement").click(function(){
        $("#save_statement").prop("disabled", true);
        $("#create_version").prop("disabled", true);
        let main = $("#statement_main_area").val();
        let input = $("#statement_input_area").val();
        let output = $("#statement_output_area").val();
        post("/problemsetting_action", {
            "action": "save_statement",
            "pid": pid,
            "statement_main": main,
            "statement_input": input,
            "statement_output": output
        }, function(data,status,xhr){
            $("#save_statement").prop("disabled",false);
            if(status == "success") {
                show_modal("成功","儲存成功");
                $("#save_statement").trigger("saved_data");
            }else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    // files
    $(".remove_public_file").click(function(){
        let filename = $(this).parent().parent().find("a").text();
        $("#create_version").prop("disabled", true);
        $(this).prop("disabled",true);
        post("/problemsetting_action", {
            "action": "remove_public_file",
            "pid": pid,
            "filename": filename
        }, function(data,status,xhr){
            if(status == "success") {
                show_modal("成功","成功刪除公開檔案\""+filename+"\"", true);
            }else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $(".remove_file").click(function(){
        let filename = $(this).parent().parent().find("a").text();
        $("#create_version").prop("disabled", true);
        $(this).prop("disabled",true);
        post("/problemsetting_action", {
            "action": "remove_file",
            "pid": pid,
            "filename": filename
        }, function(data,status,xhr){
            if(status == "success") {
                show_modal("成功","成功刪除程式檔案\""+filename+"\"", true);
            }else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $(".collapse_file_edit").each(function(){
        let $this = $(this);
        let $line = $this.prev();
        $this.data("filename",$line.find("a").text());
        let $btn = $this.find("button");
        let $select = $this.find("select");
        $select.val($line.find(".file_type").text())
        $btn.click(function(){
            $btn.prop("disabled", true);
            let content = $this.find("textarea").val();
            let filename = $this.data("filename");
            post("/problemsetting_action", {
                "action": "save_file_content",
                "pid": pid,
                "filename": filename,
                "content": content,
                "type": $select.val()
            }, function(data,status,xhr){
                if(status == "success") {
                    show_modal("成功","儲存成功");
                    $this.find("textarea").data("old_value",$this.find("textarea").val());
                    $btn.trigger("check_update");
                    $btn.prop("disabled", false);
                    $line.find(".file_type").text($select.val())
                }
                else {
                    show_modal("失敗","Error Code: " + xhr.status);
                    $btn.prop("disabled", false);
                }
            });
        });
    });
    $(".collapse_file_edit").on("show.bs.collapse",function(){
        let $this = $(this);
        $.get('/problemsetting_preview?pid='+pid+'&type=file&name='+$this.data("filename"),function(data,status){
            $this.find("textarea").val(data);
            $this.find("textarea").trigger("input");
        });
    });
    $(".collapse_file_edit").on("shown.bs.collapse",function(){
        $('html, body').scrollTop($(this).offset().top);
    });
    // judge
    $("#choose_checker").submit(function(){
        let dat = new FormData(this);
        let ret = dat.get(dat.get("checker_type")+"_checker")!="選擇檔案";
        if(!ret)
            show_modal("錯誤","請選擇一個檔案");
        return ret;
    });
    $(".alternative_fileselect").change(function(){
        $(this).prev().find("input").click();
    });
    // tests
    $("#upload_zipfile").click(function(){
        $(this).prop("disabled",true);
        $(this).find("span").removeClass("visually-hidden");
        fetching($(this).parent()).then(()=>location.reload());
    });
    var moveing_testcase = null;
    $("tr.testcase").attr("draggable","true");
    $("tr.testcase").on("dragstart",function(e){
        moveing_testcase = $(this);
    });
    $("tr.testcase").on("dragover",function(e){e.preventDefault();});
    $("tr.testcase").on("dragenter",function(e){e.preventDefault();});
    $("tr.testcase").on("drop",function(e){
        e.preventDefault();
        $(this).before(moveing_testcase);
        moveing_testcase = null;
        $("#tests .update-checker").data("changed",!$("tr.testcase th").toArray().map((o)=>+o.textContent).every((v,i,a) => !i || a[i-1] <= v));
        $("#tests .edit-detector").trigger("check_update");
    });
    $("#save_testcase").click(function(){
        $("#save_testcase").prop("disabled", true);
        let dat = $("tr.testcase-normal").toArray().map(function(o){
            return [+$(o).find("th").text(),$(o).find("input[type='checkbox']").prop("checked")];
        });
        post("/problemsetting_action", {
            "action": "save_testcase",
            "pid": pid,
            "modify": JSON.stringify(dat)
        }, function(data,status,xhr){
            if(status == "success") {
                show_modal("成功","儲存成功");
                $("#save_testcase").trigger("saved_data");
                let ths = $("tr.testcase th");
                for(let i in ths){
                    ths[i].textContent = ""+i;
                }
            }
            else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $("#save_testcase_gen").click(function(){
        $("#save_testcase_gen").prop("disabled", true);
        let dat = $("tr.testcase-gen").toArray().map(function(o){
            return [+$(o).find("th").text(),$(o).find("input[type='checkbox']").prop("checked")];
        });
        post("/problemsetting_action", {
            "action": "save_testcase_gen",
            "pid": pid,
            "modify": JSON.stringify(dat)
        }, function(data,status,xhr){
            if(status == "success") {
                show_modal("成功","儲存成功");
                $("#save_testcase_gen").trigger("saved_data");
                let ths = $("tr.testcase th");
                for(let i in ths){
                    ths[i].textContent = ""+i;
                }
            }
            else {
                show_modal("失敗","Error Code: " + xhr.status);
                $("#create_version").prop("disabled", false);
            }
        });
    });
    $("#create_group").click(function(){
        let content = $("#group_name_input").val();
        if (!content){
            show_modal("錯誤","名稱不可為空");
            return;
        }
        $("#create_group").prop("disabled", true);
        $(this).find("span").removeClass("visually-hidden");
        post("/problemsetting_action", {
            "action": "create_group",
            "pid": pid,
            "name": content
        }, function(data,status,xhr){
            $(this).find("span").addClass("visually-hidden");
            $("#create_group").prop("disabled", false);
            if(status == "success") {
                show_modal("成功","建立成功", true);
            }
            else {
                show_modal("失敗","Error Code: " + xhr.status);
            }
        });
    });
    $(".remove_group").click(function(){
        let $this = $(this);
        $this.prop("disabled", true);
        post("/problemsetting_action", {
            "action": "remove_group",
            "pid": pid,
            "name": $this.data("gp")
        }, function(data,status,xhr){
            $this.prop("disabled", false);
            if(status == "success") {
                show_modal("成功","刪除成功", true);
            }
            else {
                show_modal("失敗","Error Code: " + xhr.status);
            }
        });
    });
    // versions
    $("#create_version").click(function(){
        let content = $("#version_name_input").val();
        if (!content){
            show_modal("錯誤","描述不可為空");
            return;
        }
        $("#create_version").prop("disabled", true);
        $(this).find("span").removeClass("visually-hidden");
        post("/problemsetting_action", {
            "action": "create_version",
            "pid": pid,
            "description": content
        }, function(data,status,xhr){
            $(this).find("span").addClass("visually-hidden");
            $("#create_version").prop("disabled", false);
            if(status == "success") {
                show_modal("成功","建立成功", true);
            }
            else {
                show_modal("失敗","Error Code: " + xhr.status);
            }
        });
    });
});