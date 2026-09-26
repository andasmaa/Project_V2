"""
chroma_store.py — RAG bancaire AWB
- Embeddings : sentence-transformers/all-MiniLM-L6-v2 (gratuit, local)
- Store      : ChromaDB in-memory multi-collections
- Documents  : FAQ + réglements + produits AWB + PDFs externes
- Sécurité   : Multi-collections par niveau de sensibilité (public, confidentiel, secret)
"""

import chromadb
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF pour lire les PDFs
import os

# =====================================================
# CONFIGURATION DES NIVEAUX DE SENSIBILITÉ
# =====================================================
class SecurityLevel:
    PUBLIC = "public"          # Accessible à tous (tarifs, FAQ, conditions)
    CONFIDENTIAL = "confidential"  # Accessible aux agents autorisés et superviseurs
    SECRET = "secret"          # Accessible uniquement aux agents spécifiques (fraude, succession, audit)

# Mapping des agents par niveau de sensibilité (basé sur le rôle métier)
AGENT_SECURITY_LEVEL = {
    "AG01": SecurityLevel.PUBLIC,      # Modérateur
    "AG02": SecurityLevel.PUBLIC,      # Orchestrateur
    "AG03": SecurityLevel.CONFIDENTIAL, # Réclamations
    "AG04": SecurityLevel.PUBLIC,      # Info générale
    "AG05": SecurityLevel.PUBLIC,      # Incidents
    "AG06": SecurityLevel.CONFIDENTIAL, # Crédit
    "AG07": SecurityLevel.CONFIDENTIAL, # Admin
    "AG08": SecurityLevel.PUBLIC,      # Opposition carte
    "AG09": SecurityLevel.SECRET,      # Fraude
    "AG10": SecurityLevel.CONFIDENTIAL, # Clôture
    "AG11": SecurityLevel.SECRET,      # Succession
    "AG13": SecurityLevel.CONFIDENTIAL, # RGPD
    "AG14": SecurityLevel.SECRET,      # Audit
}

# =====================================================
# FONCTION POUR LIRE LES PDFs
# =====================================================
def lire_pdf(chemin_fichier):
    """Extrait le texte d'un fichier PDF"""
    try:
        doc = fitz.open(chemin_fichier)
        texte = ""
        for page in doc:
            texte += page.get_text()
        doc.close()
        if len(texte) < 100:
            print(f"⚠️ Attention: Le PDF {chemin_fichier} contient peu de texte ({len(texte)} caractères)")
        return texte[:5000]
    except Exception as e:
        print(f"❌ Erreur lecture PDF {chemin_fichier}: {e}")
        return ""

# =====================================================
# TES PDFs À CHARGER (inchangé)
# =====================================================
MES_PDFS = [
    # ... (garde tous tes PDFs existants inchangés)
]

# =====================================================
# CHARGEMENT AUTOMATIQUE DES PDFS
# =====================================================
DOCUMENTS_PDFS = []
print("📄 Chargement des PDFs...")
for pdf in MES_PDFS:
    contenu = lire_pdf(pdf["chemin"])
    if contenu and len(contenu) > 100:
        # 🔥 Ajout du niveau de sécurité basé sur l'agent
        security_level = AGENT_SECURITY_LEVEL.get(pdf["agent"], SecurityLevel.PUBLIC)
        DOCUMENTS_PDFS.append({
            "id": pdf["id"],
            "content": contenu,
            "metadata": {
                "agent": pdf["agent"],
                "topic": pdf["topic"],
                "type": "pdf",
                "nom": pdf["nom"],
                "source": os.path.basename(pdf["chemin"]),
                "security_level": security_level,  # ← Ajouté
            }
        })
        print(f"✅ PDF chargé: {pdf['nom']} ({len(contenu)} caractères) - niveau: {security_level}")
    else:
        print(f"⚠️ PDF ignoré (vide ou introuvable): {pdf['nom']}")

# =====================================================
# DOCUMENTS BANCAIRES PRINCIPAUX (inchangé, on ajoute security_level)
# =====================================================
BANKING_DOCUMENTS = [
    {
        "id": "carte_001",
        "content": """Attijariwafa Bank — Opposition carte bancaire...""",
        "metadata": {"agent": "AG08", "topic": "carte_opposition", "type": "faq", "security_level": SecurityLevel.PUBLIC}
    },
    {
        "id": "carte_002",
        "content": """Attijariwafa Bank — Types de cartes bancaires...""",
        "metadata": {"agent": "AG04", "topic": "cartes_types", "type": "product", "security_level": SecurityLevel.PUBLIC}
    },
    {
        "id": "compte_001",
        "content": """Attijariwafa Bank — Consultation de compte...""",
        "metadata": {"agent": "AG04", "topic": "compte_consultation", "type": "faq", "security_level": SecurityLevel.PUBLIC}
    },
    {
        "id": "compte_002",
        "content": """Attijariwafa Bank — Virements & Paiements...""",
        "metadata": {"agent": "AG04", "topic": "virements", "type": "faq", "security_level": SecurityLevel.PUBLIC}
    },
    {
        "id": "credit_001",
        "content": """Attijariwafa Bank — Crédit immobilier...""",
        "metadata": {"agent": "AG06", "topic": "credit_immobilier", "type": "product", "security_level": SecurityLevel.CONFIDENTIAL}
    },
    {
        "id": "credit_002",
        "content": """Attijariwafa Bank — Crédit consommation & personnel...""",
        "metadata": {"agent": "AG06", "topic": "credit_conso", "type": "product", "security_level": SecurityLevel.CONFIDENTIAL}
    },
    {
        "id": "epargne_001",
        "content": """Attijariwafa Bank — Produits d'épargne et taux 2025...""",
        "metadata": {"agent": "AG04", "topic": "epargne_taux", "type": "rates", "security_level": SecurityLevel.PUBLIC}
    },
    {
        "id": "fraude_001",
        "content": """Attijariwafa Bank — Prévention et signalement fraude...""",
        "metadata": {"agent": "AG09", "topic": "fraude_prevention", "type": "security", "security_level": SecurityLevel.SECRET}
    },
    {
        "id": "fraude_002",
        "content": """Attijariwafa Bank — Usurpation identité et sécurité digitale...""",
        "metadata": {"agent": "AG09", "topic": "securite_digitale", "type": "security", "security_level": SecurityLevel.SECRET}
    },
    {
        "id": "rgpd_001",
        "content": """Attijariwafa Bank — Droits RGPD...""",
        "metadata": {"agent": "AG13", "topic": "rgpd_droits", "type": "legal", "security_level": SecurityLevel.CONFIDENTIAL}
    },
    {
        "id": "reclamation_001",
        "content": """Attijariwafa Bank — Procédure de réclamation...""",
        "metadata": {"agent": "AG03", "topic": "reclamations", "type": "faq", "security_level": SecurityLevel.CONFIDENTIAL}
    },
    {
        "id": "cloture_001",
        "content": """Attijariwafa Bank — Clôture de compte...""",
        "metadata": {"agent": "AG10", "topic": "cloture_compte", "type": "legal", "security_level": SecurityLevel.CONFIDENTIAL}
    },
    {
        "id": "succession_001",
        "content": """Attijariwafa Bank — Succession...""",
        "metadata": {"agent": "AG11", "topic": "succession", "type": "legal", "security_level": SecurityLevel.SECRET}
    },
    {
        "id": "bam_001",
        "content": """Bank Al-Maghrib — Réglementation bancaire...""",
        "metadata": {"agent": "AG06", "topic": "reglementation_bam", "type": "regulatory", "security_level": SecurityLevel.CONFIDENTIAL}
    },
]

# Ajouter les PDFs à la liste principale
BANKING_DOCUMENTS = BANKING_DOCUMENTS + DOCUMENTS_PDFS

# =====================================================
# CLASSE CHROMASTORE MULTI-COLLECTIONS
# =====================================================
class ChromaStore:
    """
    Store vectoriel RAG multi-collections avec isolation par niveau de sensibilité.
    - PUBLIC : accessible par tous
    - CONFIDENTIAL : accessible par agents autorisés + superviseurs
    - SECRET : accessible uniquement par agents spécifiques (AG09, AG11, AG14)
    """

    COLLECTIONS = {
        SecurityLevel.PUBLIC: "awb_public_knowledge",
        SecurityLevel.CONFIDENTIAL: "awb_confidential_knowledge",
        SecurityLevel.SECRET: "awb_secret_knowledge",
    }

    def __init__(self):
        self.client = None
        self.collections = {}
        self.embedder = None
        self._initialized = False
        self.user_role = "client"  # Par défaut: client

    def set_user_role(self, role: str):
        """Définit le rôle de l'utilisateur (client, supervisor, admin)"""
        self.user_role = role

    async def initialize(self):
        """Initialise ChromaDB avec toutes les collections"""
        if self._initialized:
            return

        print("🔄 Initialisation du RAG ChromaDB multi-collections...")
        
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.client = chromadb.Client()

        # Créer les collections par niveau de sensibilité
        for level, collection_name in self.COLLECTIONS.items():
            self.collections[level] = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine", "security_level": level}
            )
            print(f"   ✅ Collection {collection_name} prête")

        # Charger les documents si les collections sont vides
        if self.collections[SecurityLevel.PUBLIC].count() == 0:
            await self._load_documents_by_level()

        self._initialized = True
        
        total_docs = sum(c.count() for c in self.collections.values())
        print(f"✅ ChromaDB AWB initialisé — {total_docs} documents dans {len(self.collections)} collections")

    def _get_allowed_collections(self, agent_filter: str = None) -> List[str]:
        """Retourne la liste des collections accessibles selon le rôle et l'agent"""
        allowed = [SecurityLevel.PUBLIC]  # Tout le monde a accès au public
        
        # Superviseur et Admin ont accès au confidentiel
        if self.user_role in ["supervisor", "admin"]:
            allowed.append(SecurityLevel.CONFIDENTIAL)
        
        # Admin a accès au secret
        if self.user_role == "admin":
            allowed.append(SecurityLevel.SECRET)
        
        # Certains agents ont accès au confidentiel même pour un client
        if agent_filter and AGENT_SECURITY_LEVEL.get(agent_filter) == SecurityLevel.CONFIDENTIAL:
            allowed.append(SecurityLevel.CONFIDENTIAL)
        
        # Agents de fraude, succession, audit ont accès au secret
        if agent_filter and AGENT_SECURITY_LEVEL.get(agent_filter) == SecurityLevel.SECRET:
            allowed.append(SecurityLevel.SECRET)
        
        return list(set(allowed))

    async def _load_documents_by_level(self):
        """Charge les documents dans les collections appropriées selon leur niveau de sécurité"""
        print(f"📄 Chargement de {len(BANKING_DOCUMENTS)} documents par niveau de sensibilité...")
        
        # Organiser les documents par niveau
        docs_by_level = {
            SecurityLevel.PUBLIC: [],
            SecurityLevel.CONFIDENTIAL: [],
            SecurityLevel.SECRET: [],
        }
        
        for doc in BANKING_DOCUMENTS:
            security_level = doc["metadata"].get("security_level", SecurityLevel.PUBLIC)
            docs_by_level[security_level].append(doc)
        
        # Charger chaque collection
        for level, docs in docs_by_level.items():
            if not docs:
                continue
                
            contents = [doc["content"] for doc in docs]
            ids = [doc["id"] for doc in docs]
            metadatas = [doc["metadata"] for doc in docs]
            
            embeddings = self.embedder.encode(
                contents,
                batch_size=16,
                show_progress_bar=True
            ).tolist()
            
            self.collections[level].add(
                documents=contents,
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas,
            )
            
            print(f"   ✅ {len(contents)} documents chargés dans {level}")
        
        # Statistiques
        for level, collection in self.collections.items():
            print(f"   📊 {level}: {collection.count()} documents")

    async def similarity_search(
        self,
        query: str,
        k: int = 3,
        agent_filter: str = None,
        security_level: str = None,
    ) -> List[Dict]:
        """
        Recherche sémantique dans les collections autorisées.
        
        Args:
            query: Question du client
            k: Nombre de documents à retourner
            agent_filter: Filtrer par agent (AG04, AG06, etc.)
            security_level: Niveau de sécurité spécifique (si None, utilise les permissions)
        """
        if not self._initialized or not self.collections:
            await self.initialize()

        # Déterminer les collections autorisées
        if security_level:
            allowed_levels = [security_level]
        else:
            allowed_levels = self._get_allowed_collections(agent_filter)
        
        all_results = []
        
        for level in allowed_levels:
            if level not in self.collections:
                continue
                
            collection = self.collections[level]
            if collection.count() == 0:
                continue
            
            where_filter = {"agent": agent_filter} if agent_filter else None
            
            try:
                query_embedding = self.embedder.encode([query]).tolist()
                results = collection.query(
                    query_embeddings=query_embedding,
                    n_results=min(k, collection.count()),
                    where=where_filter,
                )
                
                for i, doc_content in enumerate(results["documents"][0]):
                    score = 1.0 - results["distances"][0][i]
                    if score > 0.25:
                        all_results.append({
                            "content": doc_content,
                            "metadata": results["metadatas"][0][i],
                            "score": round(score, 3),
                            "id": results["ids"][0][i],
                            "security_level": level,
                        })
            except Exception as e:
                print(f"⚠️ Erreur recherche dans {level}: {e}")
                continue
        
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:k]

    async def search_by_agent(self, query: str, agent_id: str, k: int = 3) -> List[Dict]:
        """Recherche spécifique pour un agent (tient compte de ses droits d'accès)"""
        return await self.similarity_search(query, k=k, agent_filter=agent_id)

    async def search_for_client(self, query: str, k: int = 3) -> List[Dict]:
        """Recherche pour un client standard (accès public uniquement)"""
        return await self.similarity_search(query, k=k, security_level=SecurityLevel.PUBLIC)

    def format_context(self, docs: List[Dict], max_chars: int = 1500) -> str:
        """Formate les documents récupérés en contexte pour le LLM"""
        if not docs:
            return ""

        lines = ["[Documents AWB pertinents]"]
        total = 0

        for i, doc in enumerate(docs, 1):
            source = doc['metadata'].get('nom', doc['metadata'].get('topic', '?'))
            level = doc.get('security_level', 'public')
            entry = f"\n--- Document {i} (score={doc['score']}, niveau={level}, source={source}) ---\n{doc['content']}\n"
            if total + len(entry) > max_chars:
                break
            lines.append(entry)
            total += len(entry)

        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """Retourne les statistiques des collections"""
        if not self.collections:
            return {"status": "non initialisé", "documents": 0}
        
        stats = {"status": "actif", "collections": {}}
        for level, collection in self.collections.items():
            stats["collections"][level] = collection.count()
        stats["total_documents"] = sum(stats["collections"].values())
        stats["model"] = "all-MiniLM-L6-v2"
        
        return stats
    # =====================================================
    # MÉTHODES POUR L'INTERFACE D'ADMINISTRATION RAG
    # =====================================================

    def get_collections_detail(self) -> Dict:
        """Retourne le détail complet de chaque collection (docs + metadata)"""
        if not self._initialized:
            return {"status": "non initialisé", "collections": {}}

        detail = {"status": "actif", "collections": {}}

        for level, collection in self.collections.items():
            count = collection.count()
            docs = []
            if count > 0:
                # Récupérer tous les documents (avec metadata, sans embeddings pour la légèreté)
                raw = collection.get(include=["documents", "metadatas"])
                for i, doc_id in enumerate(raw["ids"]):
                    docs.append({
                        "id": doc_id,
                        "content": raw["documents"][i][:400] + ("..." if len(raw["documents"][i]) > 400 else ""),
                        "content_length": len(raw["documents"][i]),
                        "metadata": raw["metadatas"][i],
                    })
            detail["collections"][level] = {
                "name": self.COLLECTIONS[level],
                "count": count,
                "documents": docs,
            }

        return detail

    def get_agents_permissions(self) -> Dict:
        """Retourne la matrice agents × niveaux d'accès"""
        result = []
        for agent_id, level in AGENT_SECURITY_LEVEL.items():
            # Calculer les collections réellement accessibles
            allowed = self._get_allowed_collections(agent_filter=agent_id)
            result.append({
                "agent_id": agent_id,
                "security_level": level,
                "allowed_collections": allowed,
            })
        return {"agents": result}

    async def debug_search(self, query: str, k: int = 3, agent_filter: str = None,
                           user_role: str = "client") -> Dict:
        """
        Recherche sémantique détaillée pour l'interface d'admin.
        Retourne les résultats + les collections interrogées + le rôle simulé.
        """
        # Sauvegarder le rôle actuel et appliquer celui du debug
        old_role = self.user_role
        self.user_role = user_role

        try:
            if not self._initialized:
                await self.initialize()

            allowed_levels = self._get_allowed_collections(agent_filter)
            all_results = []

            for level in allowed_levels:
                if level not in self.collections:
                    continue
                collection = self.collections[level]
                if collection.count() == 0:
                    continue

                where_filter = {"agent": agent_filter} if agent_filter else None

                try:
                    query_embedding = self.embedder.encode([query]).tolist()
                    results = collection.query(
                        query_embeddings=query_embedding,
                        n_results=min(k, collection.count()),
                        where=where_filter,
                    )
                    for i, doc_content in enumerate(results["documents"][0]):
                        distance = results["distances"][0][i]
                        score = 1.0 - distance
                        all_results.append({
                            "content": doc_content,
                            "metadata": results["metadatas"][0][i],
                            "score": round(score, 3),
                            "distance": round(distance, 3),
                            "id": results["ids"][0][i],
                            "security_level": level,
                            "kept": score > 0.25,  # Le seuil utilisé dans similarity_search
                        })
                except Exception as e:
                    print(f"⚠️ Erreur debug_search dans {level}: {e}")
                    continue

            all_results.sort(key=lambda x: x["score"], reverse=True)

            return {
                "query": query,
                "user_role": user_role,
                "agent_filter": agent_filter,
                "allowed_collections": allowed_levels,
                "threshold": 0.25,
                "results": all_results[:k * 2],  # On retourne un peu plus pour voir les rejetés
            }
        finally:
            self.user_role = old_role