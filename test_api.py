import httpx
import asyncio

async def test_api():
    api_key = 'sk-3Z0dKq6LvBjatHBfj1soXSgRxhvjqQHuDS6sIxwwI6t3xiel'
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                'https://api.moonshot.cn/v1/chat/completions',
                json={
                    'model': 'moonshot-v1-8k',
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 10
                },
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            )
            print(f'HTTP Status: {resp.status_code}')
            if resp.status_code != 200:
                print(f'❌ Error:\n{resp.text}')
            else:
                print('✅ API Key VALID! AI will respond naturally now.')
        except Exception as e:
            print(f'❌ Connection Error: {e}')

asyncio.run(test_api())
