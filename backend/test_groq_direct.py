import asyncio
import os
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

async def test():
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Dis bonjour en français"}],
            max_tokens=50
        )
        print("✅ Groq fonctionne:", response.choices[0].message.content)
    except Exception as e:
        print("❌ Erreur Groq:", e)

asyncio.run(test())