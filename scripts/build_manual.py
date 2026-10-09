#!/usr/bin/env python3
"""Build the technical manual — docs/manual.html — from the documentation in docs/.

The owner (10 Oct 2026): "the manual must be updated systematically, if needed, with every commit / change in the app".
One page, self-contained: a map of the system (scripts/manual/map-svg.html, drawn by hand — change it when a source, a
thread, a table or a route is added or removed), three journeys and the ground rules (scripts/manual/template.html),
then TECHNICAL.md, SAFETY.md and the appendices in full, with contents and search. It carries the hash of the Markdown
it was built from (`heimdall-docs`): tests/test_manual.py fails when a document changed and the manual was not rebuilt.

    python scripts/build_manual.py            # docs/manual.html
    python scripts/build_manual.py --pdf F    # and a PDF (needs Playwright with Chromium)

Needs markdown-it-py (requirements-dev.txt).
"""
import datetime as dt
import hashlib
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
HERE = os.path.join(ROOT, "scripts", "manual")
# file, id prefix, part anchor, label in the contents, short label in search results
PARTS = [("TECHNICAL.md", "", "tech", "Part I · The reference", "Reference"),
         ("SAFETY.md", "s-", "safety", "Part II · The safety rules", "Safety"),
         ("DEPLOY.md", "d-", "deploy", "Appendix A · Deployment", "Deployment"),
         ("I18N.md", "i-", "i18n", "Appendix B · Languages", "Languages"),
         ("CORPUS.md", "c-", "corpus", "Appendix C · The regression corpus", "Corpus"),
         ("DEMARRAGE-FR.md", "f-", "demarrage", "Appendix D · Démarrage (FR)", "Démarrage")]
PREFIX = {p[0]: p[1] for p in PARTS}
ANCHOR = {p[0]: p[2] for p in PARTS}


def docs_hash():
    """The hash of the Markdown the manual is built from, in PARTS order."""
    h = hashlib.sha256()
    for f, *_ in PARTS:
        with open(os.path.join(DOCS, f), "rb") as fh:
            h.update(f.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()[:16]


def _slug(text, seen):
    """GitHub's heading anchors: lower case, punctuation out, spaces to hyphens, a number for a repeat."""
    s = re.sub(r"[^\w\- ]", "", text.strip().lower(), flags=re.UNICODE).replace(" ", "-")
    base, n = s, 1
    while s in seen:
        s, n = f"{base}-{n}", n + 1
    seen.add(s)
    return s


def _fix_link(href, me):
    if href.startswith(("http://", "https://", "mailto:")):
        return href, True
    if href.startswith("#"):
        return "#" + PREFIX[me] + href[1:], True
    m = re.match(r"^(?:\./)?([A-Z0-9_\-]+\.md)(#.*)?$", href)
    if m and m.group(1) in PREFIX:
        f, frag = m.group(1), m.group(2)
        return ("#" + PREFIX[f] + frag[1:]) if frag else ("#" + ANCHOR[f]), True
    return href, False            # a file of the repository: shown as text, not a dead link


def render(fname):
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")
    with open(os.path.join(DOCS, fname), encoding="utf-8") as fh:
        toks = md.parse(fh.read())
    seen, heads, pre = set(), [], PREFIX[fname]
    for i, t in enumerate(toks):
        if t.type == "heading_open":
            txt = "".join(c.content for c in (toks[i + 1].children or []) if c.type in ("text", "code_inline"))
            hid = pre + _slug(txt, seen)
            t.attrSet("id", hid)
            heads.append((int(t.tag[1]), hid, txt))
        if t.type != "inline":
            continue
        kids = t.children or []
        for j, c in enumerate(kids):
            if c.type != "link_open":
                continue
            href, ok = _fix_link(c.attrGet("href") or "", fname)
            if ok:
                c.attrSet("href", href)
                if href.startswith("http"):
                    c.attrSet("target", "_blank")
                    c.attrSet("rel", "noopener")
                continue
            c.type, c.tag, c.content = "html_inline", "", '<span class="repo-file" title="' + html.escape(href) + '">'
            depth = 0
            for k in range(j + 1, len(kids)):
                if kids[k].type == "link_open":
                    depth += 1
                elif kids[k].type == "link_close":
                    if depth == 0:
                        kids[k].type, kids[k].tag, kids[k].content = "html_inline", "", "</span>"
                        break
                    depth -= 1
    out = md.renderer.render(toks, md.options, {})
    out = out.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    return out, heads


def build():
    """The page as a fragment (what the artifact publishes) and as a standalone document; and the version text."""
    with open(os.path.join(DOCS, "TECHNICAL.md"), encoding="utf-8") as fh:
        m = re.search(r"\*\*Documented version: ([\d.]+)\*\* · last updated (\d{4}-\d{2}-\d{2}) \(([\d.]+)\)", fh.read())
    full, day = m.group(3), dt.date.fromisoformat(m.group(2))
    long_v = f"version {full}, {day.day} {day.strftime('%B')} {day.year}"
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        tpl = fh.read()
    with open(os.path.join(HERE, "map-svg.html"), encoding="utf-8") as fh:
        svg = fh.read()
    docs, toc = [], []
    for f, _pre, anchor, label, short in PARTS:
        body, heads = render(f)
        body = re.sub(r'(<h([23]) id="([^"]+)">)(.*?)(</h\2>)',
                      lambda mm: f'{mm.group(1)}{mm.group(4)}<a class="anc" href="#{mm.group(3)}" aria-label="Link to this section">#</a>{mm.group(5)}',
                      body)
        docs.append(f'<section class="part" id="{anchor}" data-label="{html.escape(short)}"><p class="partlabel">{html.escape(label)}</p>\n{body}\n</section>')
        if f == "TECHNICAL.md":
            items, cur = [], None
            for lv, hid, txt in heads:
                if lv == 2 and hid != "contents":
                    cur = [hid, txt, []]
                    items.append(cur)
                elif lv == 3 and cur:
                    cur[2].append((hid, txt))
            li = "".join(f'<li><a href="#{a}">{html.escape(t)}</a>'
                         + (("<ul>" + "".join(f'<li><a href="#{b}">{html.escape(u)}</a></li>' for b, u in sub) + "</ul>") if sub else "")
                         + "</li>" for a, t, sub in items)
            toc.append(f'<p class="grp">{html.escape(label)}</p><ul>{li}</ul>')
        elif f == "SAFETY.md":
            li = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for lv, a, t in heads if lv == 2)
            toc.append(f'<p class="grp">{html.escape(label)}</p><ul>{li}</ul>')
        else:
            g, name = label.split(" · ")
            toc.append(f'<p class="grp">{html.escape(g)}</p><ul><li><a href="#{anchor}">{html.escape(name)}</a></li></ul>')
    frag = (tpl.replace("{{MAP}}", svg).replace("{{TOC}}", "\n".join(toc)).replace("{{DOCS}}", "\n".join(docs))
            .replace("{{VERSION}}", full).replace("{{VERSION_LONG}}", long_v))
    i = frag.index('<header class="top">')
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="description" content="Heimdall (Kyiv Air Watch) — the full technical documentation, with a map of the system.">\n'
            f'<meta name="heimdall-version" content="{full}">\n<meta name="heimdall-docs" content="{docs_hash()}">\n'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}'
            'img{max-width:100%}[hidden]{display:none!important}</style>\n')
    page = head + frag[:i] + "</head>\n<body>\n" + frag[i:] + "\n</body>\n</html>\n"
    return frag, page, full, long_v


def pdf(page_path, out, version, long_v):
    """Print the standalone page to A4 with Playwright's Chromium (the map alone on a landscape page)."""
    from playwright.sync_api import sync_playwright
    foot = ('<div style="font:7.5px Helvetica,Arial,sans-serif;color:#6b7280;width:100%;padding:0 12mm;display:flex;'
            f'justify-content:space-between"><span>Heimdall Technical Manual · {html.escape(long_v)}</span>'
            '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(color_scheme="light")
        pg.goto("file://" + os.path.abspath(page_path), wait_until="networkidle")
        pg.evaluate("async()=>{ document.getElementById('tocd').open=true; await document.fonts.ready; }")
        pg.emulate_media(media="print", color_scheme="light")
        pg.pdf(path=out, print_background=True, prefer_css_page_size=True, display_header_footer=True,
               header_template="<div></div>", footer_template=foot)
        b.close()


def main(argv):
    frag, page, full, long_v = build()
    out = os.path.join(DOCS, "manual.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"{out}: {len(page):,} bytes, {long_v}, docs {docs_hash()}")
    if "--fragment" in argv:
        dest = argv[argv.index("--fragment") + 1]
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(frag)
        print(f"{dest}: the page without its document shell (for the artifact)")
    if "--pdf" in argv:
        dest = argv[argv.index("--pdf") + 1]
        pdf(out, dest, full, long_v)
        print(f"{dest}: PDF")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
