import os
from pathlib import Path
base = Path('evaluation/fixtures/webaim')
base.mkdir(parents=True, exist_ok=True)
fixtures = {
    'low_contrast.html': '<html lang="en"><body><p style="color: #999; background-color: #fff;">Low contrast text</p></body></html>',
    'missing_alt.html': '<html lang="en"><body><img src="logo.png"></body></html>',
    'form_no_label.html': '<html lang="en"><body><input type="text"></body></html>',
    'empty_link.html': '<html lang="en"><body><a href="/somewhere"></a></body></html>',
    'empty_button.html': '<html lang="en"><body><button></button></body></html>',
    'no_lang.html': '<html><body>Missing lang attribute</body></html>'
}
for name, content in fixtures.items():
    (base / name).write_text(content, encoding='utf-8')
print("WebAIM fixtures seeded.")
