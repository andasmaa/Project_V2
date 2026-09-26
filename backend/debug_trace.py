import asyncio
import os
import sys
import traceback
from dotenv import load_dotenv

load_dotenv()

async def debug_groq():
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

        print("🟢 Test 1: Connexion à Groq...")
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Dis bonjour"}],
            max_tokens=20
        )
        print("✅ Groq OK:", response.choices[0].message.content)

    except Exception as e:
        print(f"❌ Erreur Groq: {type(e).__name__} - {e}")
        traceback.print_exc()

async def debug_chroma():
    try:
        from rag.chroma_store import ChromaStore
        chroma = ChromaStore()
        await chroma.initialize()

        print("\n🟢 Test 2: Recherche Chroma...")
        results = await chroma.similarity_search("tarifs bancaires MDM", k=3)
        print(f"✅ {len(results)} résultats trouvés")
        for r in results:
            print(f"   - {r['metadata'].get('topic', '?')} (score: {r['score']})")

    except Exception as e:
        print(f"❌ Erreur Chroma: {type(e).__name__} - {e}")
        traceback.print_exc()

async def debug_agent():
    try:
        from agents.info_agent import InfoAgent
        agent = InfoAgent()

        print("\n🟢 Test 3: Appel agent info...")
        response = await agent.get_account_info("Quels sont les tarifs bancaires MDM ?")
        print(f"✅ Réponse: {response['message'][:100]}...")

    except Exception as e:
        print(f"❌ Erreur Agent: {type(e).__name__} - {e}")
        traceback.print_exc()

async def main():
    print("=" * 50)
    print("🔍 DEBUG AWB - Test complet")
    print("=" * 50)

    await debug_groq()
    await debug_chroma()
    await debug_agent()

    print("\n" + "=" * 50)
    print("✅ Debug terminé")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())