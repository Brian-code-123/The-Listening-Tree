import httpx
import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

async def test_api():
    api_key = os.environ.get('HUNYUAN_API_KEY') or os.environ.get('KIMI_API_KEY')
    if not api_key:
        print('❌ No API key found. Set HUNYUAN_API_KEY in your .env file.')
        return
    base_url = os.environ.get('HUNYUAN_BASE_URL', 'https://api.hunyuan.cloud.tencent.com/v1')
    model = os.environ.get('HUNYUAN_MODEL', 'hunyuan-turbo')
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f'{base_url}/chat/completions',
                json={
                    'model': model,
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
