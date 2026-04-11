import httpx
url='https://act-rules.github.io/testcases/efbfc7/9930d3f2863fb8d1a18b75a472ffad5348f5e306.html'
with httpx.Client(follow_redirects=True, timeout=15.0) as c:
    r=c.get(url)
print('status', r.status_code, 'len', len(r.text))
text=r.text
print(text[:1200])
print('contains_iframe', '<iframe' in text.lower())
print('contains_style_attr', 'style=' in text.lower())
print('contains_style_tag', '<style' in text.lower())
