import json
from pathlib import Path

r = json.loads(Path('evaluation/phase12_post_upgrade_full1134_v5.json').read_text(encoding='utf-8'))
url = 'https://act-rules.github.io/testcases/7d6734/0fd9df3029d10e81ef1e453902e8f61670939b52.html'
for c in r.get('cases', []):
    if c.get('url') == url:
        print('keys', sorted(c.keys()))
        for k in sorted(c.keys()):
            v = c[k]
            if isinstance(v, list):
                print(k, 'len=', len(v), 'sample=', v[:10])
            elif isinstance(v, dict):
                print(k, 'dict_keys=', list(v.keys())[:10])
            else:
                s = str(v)
                print(k, s[:250])
        break
