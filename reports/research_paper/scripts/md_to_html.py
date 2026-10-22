"""Minimal Markdown -> print-ready HTML for the NexRoute AI reports (headings, paragraphs, lists, tables,
blockquotes, bold/italic, images embedded inline as SVG)."""
import re, sys
from html import escape
from pathlib import Path

src = Path(sys.argv[1]); out = Path(sys.argv[2])
base = src.parent
lines = src.read_text(encoding="utf-8").split("\n")


def inline(t):
    t = escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


html, i, para = [], 0, []
first_h1 = True


def flush():
    global para
    if para:
        html.append(f"<p>{inline(' '.join(para))}</p>")
        para = []


while i < len(lines):
    ln = lines[i]
    s = ln.strip()
    if not s:
        flush(); i += 1; continue
    if s.startswith("```"):
        flush(); i += 1; code = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            code.append(escape(lines[i], quote=False)); i += 1
        html.append("<pre>" + chr(10).join(code) + "</pre>"); i += 1; continue
    if s == "---":
        flush(); html.append("<hr/>"); i += 1; continue
    m = re.match(r"^(#{1,3})\s+(.*)", s)
    if m:
        flush(); lvl = len(m.group(1))
        if lvl == 1 and first_h1:
            html.append('<header class="cover">'); first_h1 = False
            html.append(f"<h1>{inline(m.group(2))}</h1>"); i += 1
            # cover block runs until the first hr
            while i < len(lines) and lines[i].strip() != "---":
                t = lines[i].strip()
                if t.startswith("## "):
                    html.append(f'<div class="subtitle">{inline(t[3:])}</div>')
                elif t:
                    html.append(f'<div class="coverline">{inline(t)}</div>')
                i += 1
            html.append("</header>"); i += 1; continue
        html.append(f"<h{lvl + 0}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
    m = re.match(r"^!\[(.*?)\]\((.*?)\)", s)
    if m:
        flush()
        svg = (base / m.group(2)).read_text(encoding="utf-8")
        cap = "" if m.group(1).startswith("Figure") else f"<figcaption>{inline(m.group(1))}</figcaption>"
        html.append(f'<figure>{svg}{cap}</figure>'); i += 1; continue
    if s.startswith("|"):
        flush(); rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
        aligns = ["right" if c.endswith(":") and not c.startswith(":") else "left" for c in rows[1]]
        h = "<table><thead><tr>" + "".join(f'<th style="text-align:{a}">{inline(c)}</th>' for c, a in zip(rows[0], aligns)) + "</tr></thead><tbody>"
        for r in rows[2:]:
            h += "<tr>" + "".join(f'<td style="text-align:{a}">{inline(c)}</td>' for c, a in zip(r, aligns)) + "</tr>"
        html.append(h + "</tbody></table>"); continue
    if s.startswith(">"):
        flush(); q = []
        while i < len(lines) and lines[i].strip().startswith(">"):
            q.append(lines[i].strip()[1:].strip()); i += 1
        html.append(f'<blockquote>{inline(" ".join(q))}</blockquote>'); continue
    if re.match(r"^(-|\d+\.)\s", s):
        flush(); ordered = bool(re.match(r"^\d+\.", s)); tag = "ol" if ordered else "ul"
        items = []
        while i < len(lines) and lines[i].strip() and (re.match(r"^(-|\d+\.)\s", lines[i].strip()) or lines[i].startswith(" ")):
            t = lines[i]
            if re.match(r"^\s{2,}-\s", t):            # nested bullet
                items[-1][1].append(t.strip()[2:])
            elif re.match(r"^(-|\d+\.)\s", t.strip()) and not t.startswith(" "):
                items.append([re.sub(r"^(-|\d+\.)\s+", "", t.strip()), []])
            else:                                     # continuation line
                if items[-1][1]:
                    items[-1][1][-1] += " " + t.strip()
                else:
                    items[-1][0] += " " + t.strip()
            i += 1
        h = f"<{tag}>"
        for text, sub in items:
            h += f"<li>{inline(text)}" + ("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in sub) + "</ul>" if sub else "") + "</li>"
        html.append(h + f"</{tag}>"); continue
    para.append(s); i += 1
flush()

CSS = """
@page { size: A4; margin: 18mm 17mm 18mm 17mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", system-ui, Arial, sans-serif; color: #1b1b1a; font-size: 10.6pt; line-height: 1.5; margin: 0; }
.cover { border-left: 6px solid #2a78d6; padding: 6mm 0 6mm 7mm; margin-bottom: 6mm; background: #f4f7fc; }
.cover h1 { font-size: 30pt; margin: 0 0 2mm; color: #0d366b; letter-spacing: -0.5px; border: 0; }
.cover .subtitle { font-size: 15pt; font-weight: 600; color: #1c5cab; margin-bottom: 3mm; }
.coverline { font-size: 10.5pt; color: #3b3a37; margin: 1mm 0; }
h2 { font-size: 14.5pt; color: #0d366b; margin: 7mm 0 2.5mm; padding-bottom: 1.2mm; border-bottom: 1.5px solid #cde2fb; break-after: avoid; }
h3 { font-size: 12pt; color: #184f95; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.6mm; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin: 0 0 1.2mm; }
li ul { margin-top: 1mm; }
strong { color: #0b0b0b; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; font-size: 9.6pt; break-inside: avoid; }
th { background: #eaf1fb; color: #0d366b; font-weight: 600; padding: 1.8mm 2.4mm; border-bottom: 1.5px solid #9ec5f4; }
td { padding: 1.6mm 2.4mm; border-bottom: 1px solid #e1e0d9; vertical-align: top; }
tbody tr:nth-child(even) td { background: #fafaf8; }
blockquote { margin: 3mm 0; padding: 3mm 4mm; background: #fff6e0; border-left: 4px solid #eda100; font-size: 9.8pt; break-inside: avoid; }
figure { margin: 3mm 0 5mm; text-align: center; break-inside: avoid; }
figure svg { max-width: 100%; height: auto; border: 1px solid #ecebe6; border-radius: 6px; padding: 3mm; }
figcaption { font-size: 8.8pt; color: #6b6a66; margin-top: 1mm; }
hr { border: 0; border-top: 1px solid #d8d7d0; margin: 5mm 0; }
pre { font-family: Consolas, monospace; font-size: 9.2pt; background: #f4f7fc; border-left: 3px solid #9ec5f4; padding: 3mm 4mm; white-space: pre-wrap; break-inside: avoid; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f0ec; padding: 0 1mm; border-radius: 2px; }
em { color: #3b3a37; }
"""
TITLE = sys.argv[3] if len(sys.argv) > 3 else "NexRoute AI"
doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>
<style>{CSS}</style></head><body>{''.join(html)}</body></html>"""
out.write_text(doc, encoding="utf-8")
print("wrote", out, len(doc))
