import asyncio, httpx, os, base64
from dotenv import load_dotenv

load_dotenv()
async def test():
    key = os.environ.get("ZHIPU_API_KEY")
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    # Try a public URL first to see if payload is accepted
    data = "https://www.w3schools.com/w3images/lights.jpg"
    
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": data}}
        ]}
    ]
    
    payload = {
        "model": "glm-4v",
        "messages": messages,
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {key}"})
        print("URL test:", resp.status_code, resp.json())
        
if __name__ == "__main__":
    asyncio.run(test())
