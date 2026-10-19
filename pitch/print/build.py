"""Builds the printable poster and script PDFs with headless Chrome.

Usage: .venv-local/bin/python pitch/print/build.py
Needs wave.svg and qr.svg in this folder (made from web/audio/uk_chest.wav and the app URL)."""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Same shapes as BODY_SHAPES.front in web/app.js (patient's right side on the viewer's left)
FRONT = [
    ('head', 'e', 100, 36, 24, 28), ('neck', 'r', 89, 66, 22, 16, 6),
    ('chest_r', 'r', 60, 84, 39, 54, 14), ('chest_l', 'r', 101, 84, 39, 54, 14),
    ('abd_upper', 'r', 62, 140, 76, 32, 10), ('abd_r', 'r', 62, 174, 37, 40, 10), ('abd_l', 'r', 101, 174, 37, 40, 10),
    ('groin', 'r', 66, 216, 68, 24, 12),
    ('arm_r', 'r', 34, 86, 22, 78, 11), ('hand_r', 'r', 28, 166, 22, 84, 11),
    ('arm_l', 'r', 144, 86, 22, 78, 11), ('hand_l', 'r', 150, 166, 22, 84, 11),
    ('thigh_r', 'r', 66, 242, 32, 80, 14), ('thigh_l', 'r', 102, 242, 32, 80, 14),
    ('knee_r', 'r', 67, 324, 30, 22, 10), ('knee_l', 'r', 103, 324, 30, 22, 10),
    ('leg_r', 'r', 68, 348, 28, 66, 12), ('leg_l', 'r', 104, 348, 28, 66, 12),
]


def body(selected, off, on, label, height):
    parts = []
    for s in FRONT:
        fill = on if s[0] in selected else off
        if s[1] == 'e':
            parts.append(f'<ellipse cx="{s[2]}" cy="{s[3]}" rx="{s[4]}" ry="{s[5]}" fill="{fill}"/>')
        else:
            parts.append(f'<rect x="{s[2]}" y="{s[3]}" width="{s[4]}" height="{s[5]}" rx="{s[6]}" fill="{fill}"/>')
    labels = (f'<text x="8" y="80" font-size="16" font-weight="700" fill="{label}">R</text>'
              f'<text x="180" y="80" font-size="16" font-weight="700" fill="{label}">L</text>')
    return f'<svg viewBox="0 0 200 420" style="height:{height};width:auto">{"".join(parts)}{labels}</svg>'


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


ICON = ('<svg viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2f80ff"/>'
        '<stop offset=".5" stop-color="#0a5bd8"/><stop offset="1" stop-color="#12a3b8"/></linearGradient></defs>'
        '<rect width="64" height="64" rx="14" fill="url(#g)"/><g fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="M10 43h44M14 43V31M50 43V31M10 31c9-12 35-12 44 0M23 43v-9M32 43v-11M41 43v-9"/></g></svg>')
TICK = ('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#1E8E3E"/>'
        '<path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def render(src, pdf):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-background",
                    f"--print-to-pdf={os.path.join(HERE, pdf)}", "file://" + os.path.join(HERE, src)],
                   check=True, capture_output=True)


def main():
    html = read("poster.html")
    fills = {
        "{{ICON}}": ICON, "{{TICK}}": TICK,
        "{{WAVE}}": read("wave.svg"), "{{QR}}": read("qr.svg"),
        "{{BODY_P1}}": body({"chest_l", "arm_l"}, "#2A3140", "#FF6B5E", "#8C95A8", "64mm"),
        "{{BODY_P4}}": body({"abd_r"}, "#DADCE2", "#D12B1F", "#9AA0AD", "13mm"),
        "{{DOTS}}": "<i></i>" * 27 + '<i class="miss"></i>',
    }
    for k, v in fills.items():
        html = html.replace(k, v)
    with open(os.path.join(HERE, "poster.built.html"), "w", encoding="utf-8") as f:
        f.write(html)
    render("poster.built.html", "CareBridge-poster.pdf")
    if os.path.exists(os.path.join(HERE, "script.html")):
        render("script.html", "CareBridge-pitch-script.pdf")


if __name__ == "__main__":
    main()
