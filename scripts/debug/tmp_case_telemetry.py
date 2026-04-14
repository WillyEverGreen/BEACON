import json
from pathlib import Path

r = json.loads(Path('evaluation/phase12_post_upgrade_full1134_v5.json').read_text(encoding='utf-8'))
url='https://act-rules.github.io/testcases/7d6734/0fd9df3029d10e81ef1e453902e8f61670939b52.html'
c = next(x for x in r.get('cases',[]) if x.get('url')==url)
import pprint
pprint.pp(c.get('precision_profile_telemetry'))
