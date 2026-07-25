import httpx, json, time
time.sleep(2)

r = httpx.get('http://localhost:8000/health', timeout=5)
print('health:', r.json())

stats = httpx.get('http://localhost:8000/api/stats', timeout=5).json()
print('stats:', json.dumps(stats, indent=2))

incs = httpx.get('http://localhost:8000/api/incidents', timeout=5).json()
print(f'incidents: {len(incs)} found')
if incs:
    print('first id:', incs[0]['id'])

html = httpx.get('http://localhost:8000/', timeout=5)
print('html status:', html.status_code, '— bytes:', len(html.content))
