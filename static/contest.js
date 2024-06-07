$(function() {
    const cid = $("#cid").val();
    const username = $("#username").val();
    $("form[the_action]").each(function(){
        let $this = $(this);
        $this.attr("action","/contest_action");
        $this.attr("method","post");
        $this.attr("target","_self");
        $this.attr("enctype","multipart/form-data");
        $this.prepend($('<input name="cid" value="'+cid+'" hidden>'));
        $this.prepend($('<input name="action" value="'+$(this).attr("the_action")+'" hidden>'));
    });
    (function(){
        let current_page = 1;
        function change_page(page){
            current_page = page;
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()}
            }).then(function(response){
                return response.json();
            }).then(function(data){
                let table = $("#status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    line.append($('<td>').text(obj["time"]));
                    line.append($('<td>').append($("<a>").text(obj["user_name"]).attr("href","/user/"+obj["user_id"])));
                    line.append($('<td>').append($("<a>").text(obj["problem"]+". "+obj["problem_name"]).attr("href","/contest/"+cid+"/problem/"+obj["problem"])));
                    line.append($('<td>').text(obj["lang"]));
                    line.append($('<td>').text(obj["result"]));
                    table.append(line);
                }
                let pagination = $("#status_page");
                pagination.empty();
                let first = $('<li class="page-item">');
                if (page==1){
                    first.addClass("disabled");
                }
                let first_btn = $('<a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>');
                first_btn.click(function(){change_page(1)});
                first.append(first_btn);
                pagination.append(first);
                for(let i of data["show_pages"]){
                    let li = $('<li class="page-item">');
                    if (i==page)
                        li.addClass("active");
                    let a = $('<a class="page-link">').text(i);
                    a.click(function(){change_page(i)});
                    li.append(a);
                    pagination.append(li);
                }
                let last = $('<li class="page-item">');
                if (page==data["page_cnt"]){
                    last.addClass("disabled");
                }
                let last_btn = $('<a class="page-link" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>');
                last_btn.click(function(){change_page(data["page_cnt"])});
                last.append(last_btn);
                pagination.append(last);
            });
        }
        change_page(current_page);
    })();
    (function(){
        let current_page = 1;
        function change_page(page){
            current_page = page;
            let fd = new FormData();
            fd.append("user", $("#username").val());
            fetch("/contest/"+cid+"/status/"+page,{
                method: "POST",
                headers: {"x-csrf-token": $("#csrf_token").val()},
                body: fd
            }).then(function(response){
                return response.json();
            }).then(function(data){
                let table = $("#my_status_table");
                table.empty();
                for(let obj of data["data"]){
                    let line = $("<tr>");
                    line.append($('<th scope="row">').append($("<a>").text(obj["idx"]).attr("href","/submission/"+obj["idx"])));
                    line.append($('<td>').text(obj["time"]));
                    // line.append($('<td>').append($("<a>").text(obj["user_name"]).attr("href","/user/"+obj["user_id"])));
                    line.append($('<td>').append($("<a>").text(obj["problem"]+". "+obj["problem_name"]).attr("href","/contest/"+cid+"/problem/"+obj["problem"])));
                    line.append($('<td>').text(obj["lang"]));
                    line.append($('<td>').text(obj["result"]));
                    table.append(line);
                }
                let pagination = $("#my_status_page");
                pagination.empty();
                let first = $('<li class="page-item">');
                if (page==1){
                    first.addClass("disabled");
                }
                let first_btn = $('<a class="page-link" aria-label="Previous"><span aria-hidden="true">&laquo;</span></a>');
                first_btn.click(function(){change_page(1)});
                first.append(first_btn);
                pagination.append(first);
                for(let i of data["show_pages"]){
                    let li = $('<li class="page-item">');
                    if (i==page)
                        li.addClass("active");
                    let a = $('<a class="page-link">').text(i);
                    a.click(function(){change_page(i)});
                    li.append(a);
                    pagination.append(li);
                }
                let last = $('<li class="page-item">');
                if (page==data["page_cnt"]){
                    last.addClass("disabled");
                }
                let last_btn = $('<a class="page-link" aria-label="Next"><span aria-hidden="true">&raquo;</span></a>');
                last_btn.click(function(){change_page(data["page_cnt"])});
                last.append(last_btn);
                pagination.append(last);
            });
        }
        change_page(current_page);
    })();
});