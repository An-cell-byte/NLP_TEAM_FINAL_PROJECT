"""Reúne la documentación del demo en un HTML que se puede abrir sin conexión."""

from html import escape
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'Documentacion.html'


def slug(text):
    return re.sub(r'[^\w -]', '', text.lower()).replace(' ', '-').replace('_', '-')


def main():
    sources = [
        ROOT / name for name in (
            'README.md', 'README_WINDOWS.md', 'README_CONSTRUCCION.md', 'PREGUNTAS_FRECUENTES.md'
        )
    ]
    sources.extend(sorted((ROOT / 'docs').glob('*.md')))
    anchors = {
        source: 'guia-' + slug(source.relative_to(ROOT).with_suffix('').as_posix().replace('/', '-'))
        for source in sources
    }
    markdown = MarkdownIt('commonmark', {'html': False}).enable('table')
    index = []
    sections = []

    for source in sources:
        anchor = anchors[source]
        tokens = markdown.parse(source.read_text(encoding='utf-8'))
        title = tokens[1].content if tokens and tokens[0].type == 'heading_open' else source.stem
        index.append(f'<li><a href="#{anchor}">{escape(title)}</a></li>')
        for position, token in enumerate(tokens):
            if token.type == 'heading_open':
                token.attrSet('id', f'{anchor}-{slug(tokens[position + 1].content)}')
            for child in token.children or []:
                if child.type != 'link_open':
                    continue
                href = urlsplit(child.attrGet('href'))
                if href.scheme or href.netloc or not href.path:
                    continue
                destination = (source.parent / unquote(href.path)).resolve()
                if destination in anchors:
                    fragment = '-' + unquote(href.fragment) if href.fragment else ''
                    child.attrSet('href', '#' + anchors[destination] + fragment)
                elif destination == OUTPUT:
                    child.attrSet('href', '#indice')
        rendered = markdown.renderer.render(tokens, markdown.options, {})
        sections.append(f'<section id="{anchor}"><p><a href="#indice">Volver al índice</a></p>{rendered}</section>')

    page = '''<!doctype html>
<html lang="es">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guías de Qwerty</title>
<style>
  body { max-width: 72ch; margin: 2rem auto; padding: 0 1.25rem;
         font: 1rem/1.6 system-ui, sans-serif; color: #172033; }
  a { color: #075b9b; }
  pre, table { overflow-x: auto; }
  pre { padding: 1rem; background: #f0f4f8; }
  table { display: block; border-collapse: collapse; }
  th, td { padding: .45rem .6rem; border: 1px solid #cbd5e1; text-align: left; }
  section { padding-top: 1.5rem; margin-top: 2rem; border-top: 1px solid #cbd5e1; }
</style>
<main>
<h1 id="indice">Guías de Qwerty</h1>
<p>Elige la guía que quieres consultar.</p>
'''
    page += '<nav aria-label="Guías"><ul>' + ''.join(index) + '</ul></nav>'
    page += '\n'.join(sections) + '</main>\n</html>\n'
    OUTPUT.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
