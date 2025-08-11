"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2025 LittleOrange666 (orangeminecraft123@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import html as html_
import re
import shutil

import mistune
from mistune.plugins import footnotes, \
    table, url, \
    task_lists, def_list, abbr, spoiler, formatting
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

from . import tools, constants
from .constants import preparing_problem_path
from .constants import tmp_path

the_headers = ("h1", "h2", "h3")
the_contents = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "ol", "ul")


class HighlightRenderer(mistune.HTMLRenderer):
    def block_code(self, code, info=None):
        if info:
            try:
                lexer = get_lexer_by_name(info.strip())
            except ClassNotFound:
                lexer = guess_lexer(code)
        else:
            try:
                lexer = guess_lexer(code)
            except ClassNotFound:
                lexer = get_lexer_by_name("text")

        formatter = HtmlFormatter()
        return highlight(code, lexer, formatter)


def plugin_math_tex_v2_full(md):
    # 行內公式：\(...\)
    backslash_inline = re.compile(r'\\\((.+?)\\\)')
    # 行內公式：$...$，避免跟 $$...$$ 衝突
    dollar_inline = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')

    # 區塊公式：$$...$$（跨行支援）
    block_math_pattern = re.compile(r'^\$\$\s*([\s\S]+?)\s*\$\$', re.MULTILINE)

    # --- 行內公式 ---
    def parse_backslash_math(inline, m, state):
        return 'inline_math', m.group(1)

    def parse_dollar_math(inline, m, state):
        return 'inline_math', m.group(1)

    def render_inline_math(self, text):
        return f'<script type="math/tex">{mistune.escape(text)}</script>'

    # --- 區塊公式 ---
    def parse_block_math(block, m, state):
        return {'type': 'block_math', 'raw': m.group(1).strip()}

    def render_block_math(self, text):
        return f'<script type="math/tex; mode=display">{mistune.escape(text)}</script>'

    # 註冊行內
    md.inline.register('math_backslash', backslash_inline, parse_backslash_math)
    md.inline.register('math_dollar', dollar_inline, parse_dollar_math)
    md.renderer.register('inline_math', render_inline_math)

    # 註冊區塊
    md.block.register('block_math', block_math_pattern, parse_block_math)
    md.renderer.register('block_math', render_block_math)


renderer = HighlightRenderer()
mistune_markdown = mistune.create_markdown(hard_wrap=True, renderer=renderer, plugins=[
    footnotes.footnotes,
    table.table,
    url.url,
    task_lists.task_lists,
    def_list.def_list,
    abbr.abbr,
    spoiler.spoiler,
    plugin_math_tex_v2_full,
    formatting.strikethrough,
    formatting.mark,
    formatting.insert,
    formatting.superscript,
    formatting.subscript,
])


def addattr(attrs: dict[str, str], name: str, new: str):
    if name in attrs:
        attrs[name] += " " + new
    else:
        attrs[name] = new


def run_markdown(source: str) -> str:
    source = html_.escape(source)
    # 處理參數
    args: dict[str, str] = {"title": "LittleOrange's page"}
    if source.startswith("---"):
        end = source.find("---", 3)
        li: list[str] = source[source.find("\n") + 1:source.rfind("\n", 0, end)].split("\n")
        for t in li:
            if ":" in t:
                k, v = t.split(":")[:2]
                while v.startswith(" "):
                    v = v[1:]
                args[k] = v
        source = source[end + 4:]
    # source = escape(source)
    # 預處理spoiler
    reg1 = re.compile("^:::spoiler(?:_template|_repeat)?\\s+(\\S+ +.*)$", re.M)
    get = reg1.search(source)
    while get:
        source = f"{source[:get.span(1)[0]]}{get.group(1).replace(' ', '&nbsp;')}{source[get.span(1)[1]:]}"
        get = reg1.search(source)
    # 主要部分
    html = mistune_markdown(source)
    # spoiler轉成details
    html = html.replace("<br />", "<br>").replace("<br/>", "<br>").replace("</br>", "<br>").replace("<br>",
                                                                                                    " NEXTLINE ")
    reg = re.compile(":::spoiler\\s(\\S+)", re.M)
    reg1 = re.compile(":::spoiler_template\\s(\\S+)", re.M)
    reg2 = re.compile(":::spoiler_repeat\\s(\\S+)", re.M)
    reg0 = re.compile(":::", re.M)

    get = reg.search(html)
    while get:
        html = f"{html[:get.span()[0]]}<details><summary>{get.group(1)}</summary>{html[get.span()[1]:]}"
        get = reg.search(html)

    get = reg1.search(html)
    while get:
        html = f"{html[:get.span()[0]]}<details class='spoiler_template'><summary>{get.group(1)}</summary>{html[get.span()[1]:]}"
        get = reg1.search(html)

    get = reg2.search(html)
    while get:
        html = f"{html[:get.span()[0]]}<div class='spoiler_repeat'>{get.group(1)}</div>{html[get.span()[1]:]}"
        get = reg2.search(html)

    get = reg0.search(html)
    while get:
        html = f"{html[:get.span()[0]]}</details>{html[get.span()[1]:]}"
        get = reg0.search(html)
    html = html.replace(" NEXTLINE ", "<br>")
    #
    # html = parse.solve(html)
    html = re.sub("<br>\\s*<br>", "<br>", html.replace("</br>", "<br>"))
    return html


def run_latex(pid: str, strings: list[str]):
    files = preparing_problem_path / pid / "public_file"
    folder = tmp_path / tools.random_string()
    folder.mkdir(parents=True, exist_ok=True)
    for f in files.iterdir():
        shutil.copy(f, folder)
    outs = []
    for s in strings:
        s = s.strip()
        if not s:
            outs.append("")
            continue
        s = "".join(ch if ord(ch) < 128 else f"\\&\\#x{hex(ord(ch))[2:]};" for ch in s)
        s = s.replace("\n", "<br>")
        s = constants.latex_begin + s + constants.latex_end
        tools.write(s, folder / "tmp.tex")
        tools.system("htxelatex tmp.tex", folder)
        out = tools.read_default(folder / "tmp.html")
        if out:
            out = out.replace("&amp;#", "&#").replace("\n", "")
            out = out[out.find(">", out.find("<body")) + 1:out.find("</body")] + "\n"
        outs.append(out)
    shutil.rmtree(folder)
    return outs
