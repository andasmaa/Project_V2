import asyncio
from rag.chroma_store import ChromaStore

async def test():
    print("🔄 Initialisation de ChromaDB...")
    chroma = ChromaStore()
    await chroma.initialize()
    
    print("\n📚 Test 1: Recherche 'tarifs bancaires'")
    results = await chroma.similarity_search("tarifs bancaires", k=3)
    print(f"   Résultats trouvés: {len(results)}")
    for r in results:
        print(f"   - {r['metadata'].get('topic', '?')} (score: {r['score']})")
        print(f"     Extrait: {r['content'][:100]}...")
    
    print("\n📚 Test 2: Recherche 'opposition carte'")
    results = await chroma.similarity_search("opposition carte", k=3)
    print(f"   Résultats trouvés: {len(results)}")
    for r in results:
        print(f"   - {r['metadata'].get('topic', '?')} (score: {r['score']})")
    
    print("\n📚 Test 3: Recherche 'crédit immobilier'")
    results = await chroma.similarity_search("crédit immobilier", k=3)
    print(f"   Résultats trouvés: {len(results)}")

asyncio.run(test())