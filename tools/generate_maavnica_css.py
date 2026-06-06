"""Generate maavnica.css as strict duplicate of wellness-soft + wellness-soft-minimal."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend" / "static" / "public-card"


def strip_to_maavnica_selectors(selector_block: str, source_themes: tuple[str, ...]) -> str | None:
    parts = [p.strip() for p in selector_block.split(",") if p.strip()]
    kept = []
    for part in parts:
        matched = False
        if 'data-theme|="wellness-soft"' in part:
            part = re.sub(
                r'body\[data-theme\|="wellness-soft"\]',
                'body[data-theme="maavnica"]',
                part,
            )
            matched = True
        for theme in source_themes:
            if f'data-theme="{theme}"' in part:
                part = part.replace(f'data-theme="{theme}"', 'data-theme="maavnica"')
                matched = True
        if matched:
            kept.append(part)
        elif "data-theme" not in part:
            kept.append(part)
    if not kept:
        return None
    return ", ".join(kept)


def rewrite_not_rule(css: str) -> str:
    return css.replace(
        'body:not([data-theme|="wellness-soft"]):not([data-theme="artisan"]):not([data-theme="real-estate"])',
        'body:not([data-theme="maavnica"])',
    )


def process_css(css: str, source_themes: tuple[str, ...]) -> list[str]:
    css = rewrite_not_rule(css)
    out: list[str] = []
    pos = 0
    text = css
    while pos < len(text):
        m = re.match(r"\s*(/\*.*?\*/\s*)", text[pos:], re.DOTALL)
        if m:
            comment = m.group(1)
            if "wellness-soft-minimal uniquement" in comment:
                comment = comment.replace(
                    "wellness-soft-minimal uniquement", "maavnica uniquement"
                )
            if "Styles partagés : wellness-soft.css" in comment:
                comment = "/* Finitions proportions — maavnica uniquement. */\n"
            if "Wellness Premium — layout dédié" in comment:
                comment = "/* Layout wellness — maavnica (copie wellness-soft). */\n"
            if "Éléments wellness — masqués hors thème wellness-soft" in comment:
                comment = "/* Éléments wellness — masqués hors thème maavnica */\n"
            out.append(comment)
            pos += m.end()
            continue

        m = re.match(r"\s*@media[^{]+\{", text[pos:])
        if m:
            media_start = pos + m.end() - 1
            depth = 0
            i = media_start
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        media_block = text[pos : i + 1]
                        inner = media_block[media_block.index("{") + 1 : -1]
                        inner_out = []
                        for sm in re.finditer(r"([^{]+)(\{[^{}]*\})", inner):
                            sel = strip_to_maavnica_selectors(
                                sm.group(1).strip(), source_themes
                            )
                            if sel:
                                inner_out.append(sel + sm.group(2))
                        if inner_out:
                            prefix = media_block[: media_block.index("{") + 1]
                            out.append(
                                prefix
                                + "\n  "
                                + "\n  ".join(inner_out)
                                + "\n}\n"
                            )
                        pos = i + 1
                        break
                i += 1
            continue

        m = re.match(r"\s*@keyframes[^{]+\{", text[pos:])
        if m:
            end = text.index("}", pos)
            while text.count("{", pos, end + 1) > text.count("}", pos, end + 1):
                end = text.index("}", end + 1)
            out.append(text[pos : end + 1] + "\n")
            pos = end + 1
            continue

        m = re.match(r"([^{]+)(\{[^{}]*\})", text[pos:])
        if m:
            sel = strip_to_maavnica_selectors(m.group(1).strip(), source_themes)
            if sel:
                out.append(sel + m.group(2) + "\n")
            pos += m.end()
            continue

        pos += 1
    return out


def main() -> None:
    base = (ROOT / "wellness-soft.css").read_text(encoding="utf-8")
    minimal = (ROOT / "wellness-soft-minimal.css").read_text(encoding="utf-8")

    out = [
        "/* Maavnica — copie stricte wellness-soft + wellness-soft-minimal.\n"
        ' * Thème indépendant body[data-theme="maavnica"] — aucune personnalisation graphique. */\n\n'
    ]
    out.extend(process_css(base, ("wellness-soft-minimal",)))
    out.append("\n")
    out.extend(process_css(minimal, ("wellness-soft-minimal",)))

    (ROOT / "maavnica.css").write_text("".join(out), encoding="utf-8")
    print(f"Written {(ROOT / 'maavnica.css')} ({(ROOT / 'maavnica.css').stat().st_size} bytes)")


if __name__ == "__main__":
    main()
