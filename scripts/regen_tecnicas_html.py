"""
Script de regeneracion completa de ESPECIFICACIONES_TECNICAS.html
y ESPECIFICACIONES_FUNCIONALES.html con todo el contenido actualizado.
"""
import pathlib, re, subprocess

# ============================================================
# PASO 1: Leer el MD con encoding correcto
# ============================================================
md_path = pathlib.Path('ESPECIFICACIONES_TECNICAS.md')
md_raw = md_path.read_bytes()

# Detectar y decodificar correctamente
try:
    md_text = md_raw.decode('utf-8')
except UnicodeDecodeError:
    md_text = md_raw.decode('latin-1')

print(f"MD leido: {len(md_text)} chars, {len(md_text.splitlines())} lineas")

# ============================================================
# PASO 2: Convertidor Markdown a HTML (manual, sin dependencias)
# ============================================================
def md_to_html_body(md):
    """Convierte Markdown a HTML con soporte para headings, code, tables, lists, bold."""
    lines = md.splitlines()
    html_lines = []
    in_code = False
    in_ul = False
    in_ol = False
    in_table = False
    i = 0

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append('</ul>')
            in_ul = False
        if in_ol:
            html_lines.append('</ol>')
            in_ol = False

    def inline(text):
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Code inline
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Links [text](url)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        return text

    while i < len(lines):
        line = lines[i]

        # Fenced code blocks
        if line.startswith('```'):
            close_lists()
            if not in_code:
                lang = line[3:].strip() or ''
                html_lines.append(f'<pre><code class="lang-{lang}">')
                in_code = True
            else:
                html_lines.append('</code></pre>')
                in_code = False
            i += 1
            continue

        if in_code:
            # Escape HTML in code
            safe = line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            html_lines.append(safe)
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^---+\s*$', line):
            close_lists()
            html_lines.append('<hr>')
            i += 1
            continue

        # Blockquote (> ...)
        if line.startswith('> '):
            close_lists()
            content = inline(line[2:])
            html_lines.append(f'<blockquote>{content}</blockquote>')
            i += 1
            continue

        # Headings
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            close_lists()
            level = len(m.group(1))
            text = inline(m.group(2))
            slug = re.sub(r'[^a-z0-9]+', '-', text.lower().strip())[:50]
            html_lines.append(f'<h{level} id="{slug}">{text}</h{level}>')
            i += 1
            continue

        # Tables
        if '|' in line and re.match(r'^\s*\|', line):
            if not in_table:
                close_lists()
                in_table = True
                html_lines.append('<div class="table-wrap"><table>')
                # Header row
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                html_lines.append('<thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in cells) + '</tr></thead><tbody>')
                i += 1
                # Skip separator line
                if i < len(lines) and re.match(r'^\s*\|[\s\-:|]+\|', lines[i]):
                    i += 1
                continue
            else:
                if re.match(r'^\s*\|[\s\-:|]+\|', line):
                    i += 1
                    continue
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                html_lines.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in cells) + '</tr>')
                i += 1
                continue
        else:
            if in_table:
                html_lines.append('</tbody></table></div>')
                in_table = False

        # Unordered list
        m = re.match(r'^(\s*)[*\-]\s+(.*)', line)
        if m:
            indent = len(m.group(1))
            content = inline(m.group(2))
            if not in_ul:
                close_lists()
                in_ul = True
                html_lines.append('<ul>')
            html_lines.append(f'<li>{content}</li>')
            i += 1
            continue

        # Ordered list
        m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if m:
            content = inline(m.group(2))
            if not in_ol:
                close_lists()
                in_ol = True
                html_lines.append('<ol>')
            html_lines.append(f'<li>{content}</li>')
            i += 1
            continue

        # Close lists on blank or non-list lines
        if in_ul or in_ol:
            close_lists()

        # Blank line -> paragraph break
        if not line.strip():
            html_lines.append('<br>')
            i += 1
            continue

        # Normal paragraph
        html_lines.append(f'<p>{inline(line)}</p>')
        i += 1

    # Close any open blocks
    if in_table:
        html_lines.append('</tbody></table></div>')
    close_lists()
    if in_code:
        html_lines.append('</code></pre>')

    return '\n'.join(html_lines)

body_html = md_to_html_body(md_text)
print(f"Body HTML generado: {len(body_html)} chars")

# ============================================================
# PASO 3: Construir el HTML completo para TECNICAS
# ============================================================

# Build sidebar from headings
headings = re.findall(r'<h([23]) id="([^"]+)">(.+?)</h\1>', body_html)
sidebar_items = ''
for level, slug, text in headings:
    clean = re.sub(r'<[^>]+>', '', text)
    cls = 'nav-item-h2' if level == '2' else 'nav-item-h3'
    sidebar_items += f'<li class="{cls}"><a href="#{slug}">{clean}</a></li>\n'

TECNICAS_HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Especificaciones Tecnicas v3.0.0 | Poliverso Transit | GVMT 065/2024</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #0b0f19;
      --bg-secondary: #111827;
      --bg-card: rgba(17,24,39,0.75);
      --border-color: rgba(255,255,255,0.08);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent-blue: #3b82f6;
      --accent-indigo: #6366f1;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --code-bg: #0d1117;
      --sidebar-width: 280px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Inter', sans-serif; background: var(--bg-primary); color: var(--text-main); line-height: 1.7; overflow-x: hidden; scroll-behavior: smooth; }}

    /* Layout */
    .app-container {{ display: flex; min-height: 100vh; }}

    /* Sidebar */
    .sidebar {{ width: var(--sidebar-width); background: var(--bg-secondary); border-right: 1px solid var(--border-color); position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; z-index: 100; padding: 0 0 40px 0; }}
    .sidebar-logo {{ padding: 20px 20px 16px; border-bottom: 1px solid var(--border-color); }}
    .sidebar-logo-title {{ font-family: 'Outfit', sans-serif; font-size: 14px; font-weight: 800; background: linear-gradient(90deg, #6366f1, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .sidebar-logo-sub {{ font-size: 10px; color: var(--text-muted); margin-top: 3px; }}
    .version-badge {{ display: inline-block; background: rgba(16,185,129,.2); border: 1px solid rgba(16,185,129,.4); color: #10b981; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; margin-top: 6px; }}
    .sidebar nav ul {{ list-style: none; padding: 12px 0; }}
    .nav-item-h2 > a {{ display: block; padding: 7px 20px; font-size: 11px; font-weight: 700; color: var(--text-muted); text-decoration: none; text-transform: uppercase; letter-spacing: .06em; transition: all .2s; }}
    .nav-item-h2 > a:hover {{ color: var(--accent-cyan); background: rgba(6,182,212,.06); }}
    .nav-item-h3 > a {{ display: block; padding: 5px 20px 5px 32px; font-size: 11px; color: #6b7280; text-decoration: none; border-left: 2px solid transparent; transition: all .2s; }}
    .nav-item-h3 > a:hover {{ color: var(--text-main); border-left-color: var(--accent-indigo); }}

    /* Main Content */
    .main-content {{ margin-left: var(--sidebar-width); flex: 1; max-width: 960px; padding: 48px 52px 80px; }}

    /* Feature badges strip */
    .feature-strip {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 32px; padding: 16px 20px; background: rgba(99,102,241,.07); border: 1px solid rgba(99,102,241,.2); border-radius: 14px; }}
    .fbadge {{ display: inline-flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: .03em; }}
    .fbadge-version {{ background: rgba(16,185,129,.15); border: 1px solid rgba(16,185,129,.35); color: #10b981; }}
    .fbadge-blue {{ background: rgba(56,189,248,.12); border: 1px solid rgba(56,189,248,.3); color: #38bdf8; }}
    .fbadge-purple {{ background: rgba(129,140,248,.12); border: 1px solid rgba(129,140,248,.3); color: #818cf8; }}
    .fbadge-red {{ background: rgba(239,68,68,.12); border: 1px solid rgba(239,68,68,.3); color: #ef4444; }}
    .fbadge-amber {{ background: rgba(245,158,11,.12); border: 1px solid rgba(245,158,11,.3); color: #f59e0b; }}
    .fbadge-green {{ background: rgba(16,185,129,.12); border: 1px solid rgba(16,185,129,.3); color: #10b981; }}

    /* Headings */
    h1 {{ font-family: 'Outfit', sans-serif; font-size: 2rem; font-weight: 900; color: #f9fafb; letter-spacing: -.03em; line-height: 1.2; margin-bottom: 8px; }}
    h2 {{ font-family: 'Outfit', sans-serif; font-size: 1.4rem; font-weight: 800; color: #e5e7eb; margin: 44px 0 16px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,.08); letter-spacing: -.02em; }}
    h3 {{ font-family: 'Outfit', sans-serif; font-size: 1.05rem; font-weight: 700; color: #d1d5db; margin: 28px 0 10px; }}
    h4 {{ font-size: .95rem; font-weight: 700; color: #9ca3af; margin: 20px 0 8px; text-transform: uppercase; letter-spacing: .06em; font-size: .78rem; }}

    /* Paragraphs */
    p {{ color: #d1d5db; margin-bottom: 10px; font-size: .95rem; }}

    /* Code */
    pre {{ background: var(--code-bg); border: 1px solid rgba(255,255,255,.08); border-radius: 10px; padding: 18px 20px; overflow-x: auto; margin: 16px 0; }}
    pre code {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: #c9d1d9; line-height: 1.65; }}
    p code, li code {{ font-family: 'JetBrains Mono', monospace; font-size: .82em; background: rgba(99,102,241,.15); color: #a5b4fc; padding: 2px 6px; border-radius: 5px; }}

    /* Tables */
    .table-wrap {{ overflow-x: auto; margin: 20px 0; border-radius: 10px; border: 1px solid var(--border-color); }}
    table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
    thead {{ background: rgba(99,102,241,.12); }}
    th {{ padding: 11px 14px; text-align: left; font-weight: 700; color: #a5b4fc; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; border-bottom: 1px solid var(--border-color); }}
    td {{ padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.04); color: #d1d5db; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(255,255,255,.02); }}

    /* Lists */
    ul, ol {{ padding-left: 22px; margin: 10px 0 14px; }}
    li {{ color: #d1d5db; margin-bottom: 5px; font-size: .93rem; line-height: 1.65; }}
    li strong {{ color: #f3f4f6; }}

    /* Blockquote / callout */
    blockquote {{ background: rgba(99,102,241,.08); border-left: 4px solid #6366f1; border-radius: 0 8px 8px 0; padding: 12px 18px; margin: 16px 0; color: #c7d2fe; font-size: .92rem; }}

    /* HR */
    hr {{ border: none; border-top: 1px solid rgba(255,255,255,.07); margin: 36px 0; }}

    /* Links */
    a {{ color: var(--accent-cyan); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Scrollbar */
    .sidebar::-webkit-scrollbar {{ width: 4px; }}
    .sidebar::-webkit-scrollbar-thumb {{ background: #374151; border-radius: 2px; }}

    /* Responsive */
    @media(max-width: 900px) {{
      .sidebar {{ display: none; }}
      .main-content {{ margin-left: 0; padding: 24px 20px 60px; }}
    }}
  </style>
</head>
<body>
<div class="app-container">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-logo">
      <div class="sidebar-logo-title">Poliverso Transit</div>
      <div class="sidebar-logo-sub">Especificaciones Tecnicas</div>
      <div class="version-badge">v3.0.0 &bull; Sep 2026</div>
    </div>
    <nav>
      <ul>
        {sidebar_items}
      </ul>
    </nav>
  </aside>

  <!-- Main Content -->
  <main class="main-content">

    <!-- Feature badges strip -->
    <div class="feature-strip">
      <span class="fbadge fbadge-version">&#10003; v3.0.0 &mdash; Septiembre 2026</span>
      <span class="fbadge fbadge-blue">&#9889; ETA Predictivo por Parada</span>
      <span class="fbadge fbadge-purple">&#10003; Cumplimiento VMT Res.065/2024</span>
      <span class="fbadge fbadge-red">&#128680; Bunching API REST</span>
      <span class="fbadge fbadge-amber">&#128652; Linea 20 Electrica</span>
      <span class="fbadge fbadge-green">&#128202; 692 despachos/dia</span>
    </div>

    <!-- Contenido principal del MD -->
    {body_html}

  </main>
</div>
</body>
</html>
"""

out_path = pathlib.Path('ESPECIFICACIONES_TECNICAS.html')
out_path.write_text(TECNICAS_HTML, encoding='utf-8')
print(f"TECNICAS.html generado: {out_path.stat().st_size:,} bytes, {len(TECNICAS_HTML.splitlines())} lineas")
