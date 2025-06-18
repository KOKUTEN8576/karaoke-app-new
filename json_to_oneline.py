import json

with open('service-account.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(json.dumps(data))
