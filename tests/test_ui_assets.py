import re
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / 'ui'

ATTR_RE = re.compile(r'''\b(?:href|src)="([^"]*)"''')
CSS_URL_RE = re.compile(r'''url\(\s*(?:'([^']*)'|"([^"]*)")\s*\)''')
IMPORT_RE = re.compile(r'''import\s*\{([^}]*)\}\s*from\s*['"](\./[^'"]+)['"]''')


def _rel(path):
    return path.relative_to(UI.parent)


def _is_exported(source, name):
    pattern = r'export\s+(?:async\s+function|function|const|let|class)\s+' + re.escape(name) + r'(?![\w$])'
    return re.search(pattern, source) is not None


class UiAssetsTest(unittest.TestCase):
    def test_index_html_resources_exist(self):
        index = UI / 'index.html'
        refs = ATTR_RE.findall(index.read_text(encoding='utf-8'))
        for ref in refs:
            if ref.startswith(('data:', 'http', '#')):
                continue
            with self.subTest(ref=ref):
                self.assertTrue((UI / ref).is_file(), f'{_rel(index)}: missing resource {ref}')

    def test_css_urls_exist(self):
        for css in sorted(UI.rglob('*.css')):
            text = css.read_text(encoding='utf-8')
            for single, double in CSS_URL_RE.findall(text):
                ref = single or double
                if ref.startswith(('data:', 'http')):
                    continue
                with self.subTest(css=str(_rel(css)), ref=ref):
                    self.assertTrue((css.parent / ref).is_file(), f'{_rel(css)}: missing url {ref}')

    def test_js_imports_resolve(self):
        for js in sorted(UI.glob('*.js')):
            text = js.read_text(encoding='utf-8')
            for names, ref in IMPORT_RE.findall(text):
                target = UI / ref
                with self.subTest(js=str(_rel(js)), ref=ref):
                    self.assertTrue(target.is_file(), f'{_rel(js)}: missing imported file {ref}')
                    source = target.read_text(encoding='utf-8')
                    for item in names.split(','):
                        item = item.strip()
                        if not item:
                            continue
                        name = item.split(' as ')[0].strip()
                        self.assertTrue(_is_exported(source, name),
                                        f'{_rel(js)}: {ref} does not export {name}')


if __name__ == '__main__':
    unittest.main()
