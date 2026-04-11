import httpx
urls=[
 'https://act-rules.github.io/testcases/afb423/5b0d73b16341a9d74ffa8f448a03893a6f816d4a.html',
 'https://act-rules.github.io/testcases/cc0f0a/0ed8074a5bee7052a1a28f9fd718b7d35a645cfd.html',
]
for url in urls:
    with httpx.Client(follow_redirects=True, timeout=15.0) as c:
        r=c.get(url)
    t=r.text
    print('\nURL',url)
    print('status',r.status_code,'len',len(t),'video',('<video' in t.lower()),'audio',('<audio' in t.lower()),'label',('<label' in t.lower()),'input',('<input' in t.lower()))
    print(t[:800])
