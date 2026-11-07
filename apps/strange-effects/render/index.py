# Builds renders/index.html: newest renders first, each with its video, sound and report.
import os,html,json,pathlib,re
root=pathlib.Path(__file__).resolve().parent.parent/'renders'
items=[]
for d in sorted([p for p in root.iterdir() if p.is_dir()],key=lambda p:p.stat().st_mtime,reverse=True):
    rep=(d/'report.md').read_text() if (d/'report.md').exists() else ''
    meta=json.loads((d/'meta.json').read_text()) if (d/'meta.json').exists() else {}
    items.append((d.name,rep,meta))
rows=[]
for name,rep,meta in sorted(items,key=lambda x:x[2].get('when',''),reverse=True):
    lines=[l for l in rep.splitlines() if l.strip() and not l.startswith('# ')]
    title=html.escape(meta.get('title',name));when=html.escape(meta.get('when',''))
    media=''
    if meta.get('ok'):media=f'<video controls preload="none" playsinline src="{name}/video.mp4"></video><p class="links"><a href="{name}/video.mp4">Video</a> · <a href="{name}/audio.mp3">Sound only</a></p>'
    rows.append(f'<article><h2>{title}</h2><p class="when">{when}</p>{media}<div class="rep">'+''.join(f'<p>{html.escape(l)}</p>' for l in lines)+'</div></article>')
page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Strange Effects Renders</title>
<style>:root{{--bg:#0e1019;--fg:#e9e4d8;--dim:#9a96a8;--line:#2a2d3d;--acc:#f0b35a}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif}}
main{{max-width:760px;margin:auto;padding:24px max(16px,env(safe-area-inset-left,0px)) 64px max(16px,env(safe-area-inset-right,0px))}}h1{{font-weight:600;margin:0 0 4px}}.sub{{color:var(--dim);margin:0 0 24px}}
article{{border-top:1px solid var(--line);padding:18px 0}}h2{{font-size:18px;margin:0}}.when{{color:var(--dim);font-size:13px;margin:2px 0 10px}}video{{width:100%;border-radius:6px;background:#000}}.links a{{color:var(--acc)}}.rep p{{margin:4px 0;color:var(--dim);font-size:14px}}</style></head>
<body><main><h1>Strange Effects renders</h1><p class="sub">Made on GitHub with the app's own engine. Newest first.</p>{"".join(rows) or "<p>No renders yet.</p>"}</main></body></html>'''
(root/'index.html').write_text(page);print('index with',len(rows),'renders')
