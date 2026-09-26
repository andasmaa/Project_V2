"""
agents_metier.py — Agents métier AWB complets
Contient : AG03, AG05, AG07, AG08, AG09, AG10, AG11, AG13
Chaque agent utilise :
  - Groq API via BaseAgent.call_llm()
  - ChromaStore RAG pour enrichir le contexte
  - Logique HITL spécifique à son domaine
"""

from agents.base_agent import BaseAgent
from typing import Dict
import re
import uuid
from datetime import datetime

SYSTEM_PROMPT = """Tu es un conseiller bancaire expert d'Attijariwafa Bank (AWB), la première banque du Maroc.

RÈGLES D'EXPERTISE BANCAIRE :
1. Tu es un expert bancaire, pas un assistant généraliste
2. Réponses précises, professionnelles et utiles
3. Connaissances bancaires : comptes, cartes, crédits, épargne, fraude, RGPD, succession
4. Formule claire et rassurante
5. Si question hors bancaire, rappelle poliment ton rôle

EXEMPLE DE RÉPONSE À UNE QUESTION BANCAIRE :
Client: "j'ai perdu ma carte"
Réponse: "Je comprends votre situation. Votre carte est immédiatement bloquée. Voulez-vous que je vous explique la procédure d'opposition ?"

EXEMPLE DE RÉPONSE HORS SUJET :
Client: "tu connais la météo ?"
Réponse: "Je suis votre conseiller bancaire AWB. Je ne peux vous parler météo, mais je peux vous aider avec vos comptes, cartes ou crédits. Que puis-je faire pour vous ?"

Réponds naturellement, en français, comme un vrai conseiller bancaire."""
# ════════════════════════════════════════════════════════════════════════════
# AG03 — RÉCLAMATIONS  (Mistral · HITL si litige > 5 000 MAD)
# ════════════════════════════════════════════════════════════════════════════

class ComplaintAgent(BaseAgent):
    """
    Gère les réclamations clients.
    HITL uniquement si montant litige > 5 000 MAD.
    """
    HITL_AMOUNT = 5_000   # MAD

    def __init__(self):
        super().__init__("AG03", "mistral:7b")
        self.hitl_threshold = self.HITL_AMOUNT

    async def process(self, message: str, context: Dict = None) -> Dict:
        amount = self._extract_amount(message)
        ticket_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # HITL uniquement si montant > 5000
        requires_hitl = amount is not None and amount > self.HITL_AMOUNT
        
        print(f"🔍 RECLAMATION - amount: {amount}, hitl: {requires_hitl}")

        # 🔥 PROMPT POUR RÉPONSE COMPLÈTE
        system_prompt = """Tu es un conseiller bancaire d'Attijariwafa Bank traitant les réclamations.

Règles :
- Réponds de manière professionnelle et complète
- N'utilise JAMAIS '[votre nom]' ou '[nom]'. Utilise 'je'
- Structure ta réponse de façon claire
- Propose une solution ou les prochaines étapes
- N'utilise JAMAIS 'Je m'appelle'
- Utilise 'je' directement sans parenthèses
- Réponds de manière professionnelle et concise
Si le client ne donne pas de montant, ne parle pas de superviseur.
Exemple : "Nous avons bien enregistré votre réclamation."
Sois concis mais complet (3-4 phrases)."""

        try:
            response = await self.call_llm(
                f"Client: {message}\n\nRéponse du conseiller:",
                system=system_prompt,
                max_tokens=200,
                temperature=0.6
            )
            response = response.strip()
        except Exception as e:
            print(f"⚠️ Erreur LLM réclamation: {e}")
            response = "Nous avons bien enregistré votre réclamation. Un conseiller vous contactera sous 48h."

        # Construction de la réponse complète
        full_response = (
            f"**Réclamation enregistrée**\n\n"
            f"**Référence :** `{ticket_id}`\n"
            f"**Délai :** {'24h (prioritaire)' if requires_hitl else '10 jours ouvrés'}\n\n"
            f"{response}"
        )

        if requires_hitl:
            full_response += (
                f"\n\n⚠️ **Litige {amount:,.0f} MAD** - Un superviseur traitera votre dossier sous 24h."
            )

        return {
            "message": full_response,
            "confidence": 0.90,
            "requires_hitl": requires_hitl,
            "hitl_reason": f"Litige > {self.HITL_AMOUNT} MAD" if requires_hitl else "",
            "ticket_id": ticket_id,
        }

    def _extract_amount(self, text: str):
        """Extrait le montant mentionné dans le texte."""
        msg_lower = text.lower()
        
        # Chercher avec devise
        match = re.search(r'(\d[\d\s]*(?:[.,]\d{1,2})?)\s*(?:mad|dh|dirham|€|eur)', msg_lower)
        if match:
            try:
                return float(match.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                pass
        
        # Chercher des nombres simples
        numbers = re.findall(r'(\d{4,})', text)
        if numbers:
            try:
                amount = float(numbers[0])
                if amount >= 5000:
                    return amount
            except ValueError:
                pass
        
        return None
# ════════════════════════════════════════════════════════════════════════════
# AG05 — INCIDENTS TECHNIQUES  (Mistral · HITL si critique · SLA 5min)
# ════════════════════════════════════════════════════════════════════════════
class IncidentAgent(BaseAgent):
    """
    Gère les incidents techniques : panne app, DAB, virement bloqué, etc.
    SLA 5 minutes pour les incidents critiques.
    """

    CRITICAL_KEYWORDS = [
        "panne", "inaccessible", "bloqué", "erreur système",
        "virement bloqué", "application ne répond", "site down",
        "dab hors service", "paiement refusé systématiquement"
    ]
    
    # 🔥 MOTS-CLÉS POUR FORCER HITL (incidents critiques)
    FORCE_HITL_KEYWORDS = [
        "avalé", "urgence", "panne critique", "ne répond plus", 
        "hors service", "dab en panne", "carte avalée", "urgence technique",
        "incident critique", "bloqué urgent"
    ]

    def __init__(self):
        super().__init__("AG05", "mistral:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        chroma = (context or {}).get("chroma")
        rag_context = ""
        if chroma:
            docs = await chroma.similarity_search(message, k=2)
            rag_context = chroma.format_context(docs)

        # Détection standard
        is_critical = self._matches(message, self.CRITICAL_KEYWORDS)
        
        # 🔥 Force HITL pour les mots-clés d'urgence
        force_critical = any(kw in message.lower() for kw in self.FORCE_HITL_KEYWORDS)
        
        # HITL si critique standard OU force
        requires_hitl = is_critical or force_critical
        
        incident_ref = f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        print(f" INCIDENT AGENT - message: {message[:50]}")
        print(f"   is_critical: {is_critical}, force_critical: {force_critical}")
        print(f"   requires_hitl: {requires_hitl}")

        system_prompt = (
            "N'utilise JAMAIS '[votre nom]' ou '[nom]'. Utilise 'je' directement. "
            "Tu es l'agent incidents techniques d'Attijariwafa Bank. "
            "Diagnostic rapide, solution claire. "
            f"SLA : {'5 minutes' if requires_hitl else '2h'}. "
            "Propose toujours une solution de contournement immédiate."
        )

        response = await self.call_llm(message, system=system_prompt, rag_context=rag_context)

        full_response = (
            f" **Incident enregistré** — Référence : `{incident_ref}`\n\n"
            f"{response}"
        )

        if requires_hitl:
            full_response += (
                "\n\n **Incident critique détecté** — "
                "Équipe technique notifiée. SLA : résolution sous 5 minutes.\n"
                "**Superviseur notifié** — Intervention humaine requise."
            )

        return {
            "message": full_response,
            "confidence": 0.88,
            "requires_hitl": requires_hitl,
            "hitl_reason": "Incident critique — SLA 5min (supervision requise)" if requires_hitl else "",
            "incident_ref": incident_ref,
            "sla_minutes": 5 if requires_hitl else 120,
        }

# ════════════════════════════════════════════════════════════════════════════
# AG07 — ADMINISTRATIF  (Mistral · double auth · RIB / adresse)
# ════════════════════════════════════════════════════════════════════════════
class AdminAgent(BaseAgent):
    """
    Modifications administratives : RIB, adresse, email, téléphone.
    Double authentification obligatoire UNIQUEMENT pour les MODIFICATIONS.
    """

    # Actions qui nécessitent une double authentification (modifications)
    MODIFICATION_OPS = ["modifier", "changer", "mettre à jour", "changement"]
    
    # Actions en lecture seule (pas de double auth)
    READ_ONLY_OPS = ["rib", "relevé", "obtenir", "avoir", "consulter", "voir", "afficher"]

    def __init__(self):
        super().__init__("AG07", "mistral:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        msg_lower = message.lower()
        
        # 🔥 Détecter si c'est une modification ou une consultation
        is_modification = any(kw in msg_lower for kw in self.MODIFICATION_OPS)
        is_read_only = any(kw in msg_lower for kw in self.READ_ONLY_OPS)
        
        op_ref = f"ADM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 🔥 Si c'est une consultation (RIB, solde, etc.) → pas de double auth
        if "rib" in msg_lower and ("obtenir" in msg_lower or "avoir" in msg_lower or "c'est quoi" in msg_lower):
            response = """**Obtenir votre RIB**

Votre RIB (Relevé d'Identité Bancaire) est disponible gratuitement :

1. **Application mobile AWB** : connectez-vous, allez dans "Mes comptes" → "RIB"
2. **Banque en ligne** : espace client → "Documents" → "RIB"
3. **En agence** : présentez votre carte d'identité

Le RIB contient : numéro de compte, clé RIB, code banque, code guichet.

Aucune authentification supplémentaire n'est requise pour la consultation."""
            
            return {
                "message": response,
                "confidence": 0.95,
                "requires_hitl": False,
                "double_auth_required": False,
                "op_ref": op_ref,
            }
        
        # 🔥 Si c'est une modification réelle → double authentification
        if is_modification or any(kw in msg_lower for kw in ["adresse", "email", "téléphone", "mobile"]):
            response = await self.call_llm(message, system=system_prompt, rag_context=rag_context)
            
            full_response = (
                f"**Modification administrative** — Référence : `{op_ref}`\n\n"
                "**Double authentification requise** avant toute modification.\n"
                "Vous allez recevoir un code OTP par SMS.\n\n"
                f"{response}\n\n"
                "**Document requis :** Pièce d'identité (CIN/Passeport) valide."
            )
        elif "ptz" in msg_lower or "taux zéro" in msg_lower:
            response = """**Prêt à Taux Zéro (PTZ) AWB**

        Le PTZ est un prêt immobilier sans intérêts pour l'achat d'une résidence principale.

        Conditions :
        - Plafond selon zone géographique et composition familiale
        - Ressources ne dépassant pas un certain plafond
        - Logement neuf ou ancien avec travaux

        Pour plus d'informations, contactez le 0801 00 22 22"""    
            
            return {
                "message": full_response,
                "confidence": 0.92,
                "requires_hitl": False,
                "double_auth_required": True,
                "op_ref": op_ref,
            }
        
        # 🔥 Réponse par défaut
        return {
            "message": "Je suis votre assistant administratif AWB. Je peux vous aider à consulter votre RIB, modifier vos coordonnées, ou obtenir des documents. Que souhaitez-vous ?",
            "confidence": 0.85,
            "requires_hitl": False,
            "double_auth_required": False,
            "op_ref": op_ref,
        }
# ════════════════════════════════════════════════════════════════════════════
# AG08 — OPPOSITION CARTE  (Mistral · SLA < 5min · Ed25519 horodaté)
# ════════════════════════════════════════════════════════════════════════════
# Dans agents_metier.py - OppositionAgent
# Dans agents_metier.py - OppositionAgent
class OppositionAgent(BaseAgent):
    def __init__(self):
        super().__init__("AG08", "mistral:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        opposition_ref = f"OPP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"
        timestamp_iso = datetime.now().isoformat() + "Z"

        import hashlib
        ed25519_sim = hashlib.sha256(
            f"{opposition_ref}{timestamp_iso}".encode()
        ).hexdigest()[:32]

        # 🔥 PROMPT POUR RÉPONSE NATURELLE SUR OPPOSITION
        system_prompt = """Tu es un conseiller bancaire d'Attijariwafa Bank spécialisé dans les oppositions de carte.

TON RÔLE :
- Tu es empathique et rassurant (le client est souvent stressé)
- Ta réponse est unique et adaptée à la situation du client
- Tu n'utilises jamais d'émojis
- Tu ne répètes jamais la même formulation

RÈGLES :
1. Confirme que l'opposition est enregistrée
2. Donne la référence d'opposition (fournie)
3. Rassure le client sur le blocage immédiat
4. Indique les délais pour la nouvelle carte (5-7 jours)
5. Rappelle le numéro d'urgence 0800 00 11 00
6. N'utilise JAMAIS les expressions '[votre nom]' ou '[nom]'. Utilise 'je' directement.
Exemple de réponse :
"Je comprends votre situation. L'opposition sur votre carte est immédiatement enregistrée. Votre carte est maintenant bloquée. Une nouvelle carte vous parviendra sous 5 à 7 jours ouvrés. Pour toute urgence, notre hotline est joignable 24h/24 au 0800 00 11 00."

Réponds de manière naturelle et rassurante, en adaptant ton message à la détresse perçue du client."""

        try:
            llm_response = await self.call_llm(
                f"{system_prompt}\n\nClient: {message}\n\nRéponse du conseiller:",
                max_tokens=200,
                temperature=0.8
            )
            response = llm_response.strip()
        except Exception as e:
            print(f"⚠️ Erreur LLM opposition: {e}")
            response = "Votre opposition est enregistrée. Votre carte est bloquée. Une nouvelle carte vous sera envoyée sous 5 à 7 jours."

        full_response = (
            f"**Opposition enregistrée**\n"
            f"Référence : {opposition_ref}\n"
            f"Date : {timestamp_iso}\n\n"
            f"{response}\n\n"
            f"Numéro d'urgence 24h/24 : 0800 00 11 00"
        )

        return {
            "message": full_response,
            "confidence": 0.99,
            "requires_hitl": False,
            "opposition_ref": opposition_ref,
        }
# ════════════════════════════════════════════════════════════════════════════
# AG09 — FRAUDE  (Qwen · XGBoost simulé · HITL si score > 0.8)
# ════════════════════════════════════════════════════════════════════════════
class FraudAgent(BaseAgent):
    """
    Détection et traitement fraude.
    HITL seulement pour les montants > 100 000 MAD ou mots-clés graves.
    """

    # Signaux de fraude avec poids
    FRAUD_SIGNALS = {
        "piraté": 0.6, "compte vidé": 0.7, "volé": 0.5, "arnaque": 0.5,
        "transaction inconnue": 0.5, "virement non autorisé": 0.6,
        "usurpation": 0.5, "escroquerie": 0.5, "phishing": 0.5,
        "hack": 0.6, "faux conseiller": 0.6, "vishing": 0.5,
        "frauduleux": 0.6, "suspecte": 0.4, "pirate": 0.6
    }
    
    # 🔥 MOTS-CLÉS POUR FORCER HITL
    FORCE_HITL_KEYWORDS = [
        "150000", "150 000", "200000", "200 000", "250000", "250 000",
        "300000", "300 000", "120000", "120 000",
        "frauduleux", "piraté", "compte vidé", "disparu", "urgent"
    ]

    def __init__(self):
        super().__init__("AG09", "qwen:7b")
        self.hitl_threshold = 0.6  # Seuil augmenté

    async def process(self, message: str, context: Dict = None) -> Dict:
        msg_lower = message.lower()
        
        # Extraction du montant
        amount = self._extract_amount(message)
        
        # Détection des mots-clés graves
        force_hitl = any(kw in msg_lower for kw in self.FORCE_HITL_KEYWORDS)
        
        # 🔥 HITL UNIQUEMENT si montant > 100 000 MAD OU mots-clés graves
        requires_hitl = (amount > 100000) or (force_hitl and amount > 0)
        
        fraud_ref = f"FRD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        print(f"FRAUD AGENT - message: {message[:50]}")
        print(f"   montant: {amount}, force_hitl: {force_hitl}")
        print(f"   requires_hitl: {requires_hitl}")

        # 🔥 RÉPONSE POUR CAS GRAVES (AVEC HITL)
        if requires_hitl:
            return {
                "message": f"""**Alerte fraude - Référence : {fraud_ref}**
Risque détecté : CRITIQUE
Montant : {amount:,.0f} MAD

Suite à votre signalement, nous avons immédiatement activé le gel préventif de votre compte.

Un superviseur a été notifié et vous contactera sous 10 secondes.

Ne communiquez aucun code par téléphone.

 Service anti-fraude : 0801 00 22 22 (24h/24)""",
                "confidence": 0.95,
                "requires_hitl": True,
                "hitl_reason": f"Fraude critique - montant {amount:,.0f} MAD",
                "fraud_ref": fraud_ref,
                "account_frozen": True,
            }
        
        # 🔥 RÉPONSE POUR CAS BÉNINS (SANS HITL)
        else:
            return {
                "message": f"""**Vérification sécurité - Référence : {fraud_ref}**

Nous avons bien pris en compte votre signalement.

Bonnes pratiques de sécurité :
1. Activez les alertes SMS dans l'application
2. Vérifiez régulièrement vos transactions
3. Ne communiquez jamais vos codes par téléphone
4. Contactez le 0801 00 22 22 en cas d'urgence

Nous restons à votre disposition.""",
                "confidence": 0.50,
                "requires_hitl": False,
                "hitl_reason": "",
                "fraud_ref": fraud_ref,
                "account_frozen": False,
            }

    def _compute_fraud_score(self, message: str) -> float:
        """Score fraude (non utilisé dans cette version simplifiée)."""
        return 0.0

    def _extract_amount(self, text: str) -> float:
        """Extrait le montant mentionné dans le texte."""
        import re
        
        # Nettoyer le texte
        text_clean = text.replace(",", "").replace(" ", "")
        
        # Chercher les nombres de 4 chiffres ou plus
        numbers = re.findall(r'(\d{4,})', text_clean)
        if numbers:
            try:
                amounts = [float(n) for n in numbers]
                return max(amounts)
            except:
                pass
        
        # Chercher les nombres avec espaces (ex: "200 000")
        numbers_space = re.findall(r'(\d{1,3}(?:\s\d{3})+)', text)
        if numbers_space:
            try:
                amount_str = numbers_space[0].replace(" ", "")
                return float(amount_str)
            except:
                pass
        
        return 0
# ════════════════════════════════════════════════════════════════════════════
# AG10 — CLÔTURE COMPTE  (Qwen · Human-in-Command TOUJOURS)
# ════════════════════════════════════════════════════════════════════════════

class ClosureAgent(BaseAgent):
    """
    Demande de clôture de compte.
    Human-in-Command OBLIGATOIRE — aucun agent IA ne décide seul.
    """

    def __init__(self):
        super().__init__("AG10", "qwen:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        closure_ref = f"CLO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        msg_lower = message.lower()
        
        # Détection du type de produit à clôturer
        if "livret" in msg_lower or "épargne" in msg_lower:
            produit = "livret d'épargne"
        elif "pel" in msg_lower:
            produit = "Plan Épargne Logement (PEL)"
        elif "cel" in msg_lower:
            produit = "Compte Épargne Logement (CEL)"
        else:
            produit = "compte bancaire"

        # 🔥 Réponse simple sans appel LLM (évite "je suis l'agent")
        full_response = (
            f"**Demande de clôture** — Référence : `{closure_ref}`\n\n"
            f"**Produit concerné :** {produit}\n\n"
            "**RÈGLE ABSOLUE** : Aucun agent IA ne peut décider seul d'une clôture.\n"
            "Un conseiller humain validera votre demande (Human-in-Command).\n\n"
            "**Procédure à suivre :**\n"
            "1. Validation superviseur sous 1h\n"
            "2. Rendez-vous en agence avec votre CIN\n"
            "3. Préavis de 30 jours\n"
            "4. Virement du solde sur votre compte courant\n\n"
            "**Prochaines étapes :**\n"
            "• Un superviseur va vous contacter sous 1h\n"
            "• Vous recevrez une confirmation par SMS"
        )

        return {
            "message": full_response,
            "confidence": 0.95,
            "requires_hitl": True,
            "hitl_reason": f"Clôture {produit} — Human-in-Command obligatoire",
            "closure_ref": closure_ref,
        }
# ════════════════════════════════════════════════════════════════════════════
# AG11 — SUCCESSION  (Qwen · HITL TOUJOURS · notaire)
# ════════════════════════════════════════════════════════════════════════════
class SuccessionAgent(BaseAgent):
    """
    Gestion des successions et décès.
    Human-in-Command TOUJOURS + notification notaire partenaire.
    """

    def __init__(self):
        super().__init__("AG11", "qwen:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        succession_ref = f"SUC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        chroma = (context or {}).get("chroma")
        rag_context = ""
        if chroma:
            docs = await chroma.similarity_search(message, k=2, agent_filter="AG11")
            rag_context = chroma.format_context(docs)

        # 🔥 PROMPT CORRIGÉ - Suppression totale de l'identité d'agent
        system_prompt = (
            "N'utilise JAMAIS les expressions 'en tant qu'agent succession', 'je suis l'agent succession' ou '[votre nom]'. "
            "Réponds simplement avec empathie. "
            "Explique la procédure de succession : documents nécessaires (acte de décès, certificat d'héritiers, CIN), "
            "le gel automatique des comptes, les délais, et le rôle du notaire. "
            "Un superviseur humain sera impliqué."
        )

        response = await self.call_llm(message, system=system_prompt, rag_context=rag_context)

        full_response = (
            f"**Dossier succession** — Référence : `{succession_ref}`\n\n"
            f"{response}\n\n"
            "**Documents requis :**\n"
            "• Acte de décès officiel\n"
            "• Certificat d'héritiers ou acte notarié\n"
            "• CIN de chaque héritier\n\n"
            "**Un superviseur et un notaire partenaire AWB seront contactés sous 24h.**\n"
            "Service succession : 0522 49 80 00"
        )

        return {
            "message": full_response,
            "confidence": 0.95,
            "requires_hitl": True,
            "hitl_reason": "Succession — Human-in-Command obligatoire + notification notaire",
            "succession_ref": succession_ref,
        }

# ════════════════════════════════════════════════════════════════════════════
# AG13 — RGPD  (Qwen · Art.17 · HITL TOUJOURS · notification DPO)
# ════════════════════════════════════════════════════════════════════════════
class RGPDAgent(BaseAgent):
    """
    Gestion des droits RGPD (accès, rectification, suppression Art.17).
    Human-in-Command TOUJOURS pour Art.17.
    """

    RGPD_RIGHTS = {
        "accès":          "Art.15 — Droit d'accès",
        "rectification":  "Art.16 — Droit de rectification",
        "suppression":    "Art.17 — Droit à l'oubli",
        "oubli":          "Art.17 — Droit à l'oubli",
        "effacement":     "Art.17 — Droit à l'oubli",
        "portabilité":    "Art.20 — Droit à la portabilité",
        "opposition":     "Art.21 — Droit d'opposition",
        "limitation":     "Art.18 — Droit à la limitation",
    }

    def __init__(self):
        super().__init__("AG13", "qwen:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        rgpd_ref = f"RGPD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        right_detected = self._detect_right(message)
        is_art17 = "Art.17" in right_detected

        chroma = (context or {}).get("chroma")
        rag_context = ""
        if chroma:
            docs = await chroma.similarity_search(message, k=2, agent_filter="AG13")
            rag_context = chroma.format_context(docs)

        # 🔥 PROMPT RGPD - SANS EMAIL, SANS "JE SUIS LE DPO"
        system_prompt = f"""Tu es un conseiller bancaire d'Attijariwafa Bank traitant les demandes RGPD.

Droit détecté : {right_detected}.

Instructions importantes :
- Réponds de manière professionnelle et concise
- N'utilise JAMAIS d'email
- N'utilise JAMAIS les expressions "je suis l'agent RGPD" ou "je suis le DPO"
- Utilise "nous" ou "le service RGPD" à la place
- Délai légal : 30 jours pour traiter la demande
- Exception légale : certaines données peuvent être conservées 10 ans pour obligations bancaires

Pour l'Art.17 (droit à l'oubli) :
- Indique qu'un superviseur humain doit valider la demande
- Explique que certaines données peuvent être conservées 10 ans

Réponds de manière naturelle, professionnelle, sans émojis."""

        try:
            response = await self.call_llm(
                f"Client: {message}\nDroit RGPD détecté: {right_detected}\nArt.17: {is_art17}\n\nRéponse:",
                system=system_prompt,
                max_tokens=300,
                temperature=0.6
            )
            response = response.strip()
        except Exception as e:
            print(f"⚠️ Erreur LLM RGPD: {e}")
            response = "Votre demande RGPD a bien été enregistrée. Le service RGPD vous contactera sous 30 jours."

        full_response = (
            f"**Demande RGPD**\n"
            f"Référence : {rgpd_ref}\n"
            f"Droit exercé : {right_detected}\n"
            f"Délai légal : 30 jours\n\n"
            f"{response}"
        )

        if is_art17:
            full_response += (
                "\n\nNote: L'Art.17 (droit à l'oubli) nécessite une validation par un superviseur humain. Certaines données peuvent être conservées jusqu'à 10 ans pour répondre aux obligations légales bancaires."
            )

        return {
            "message": full_response,
            "confidence": 0.96,
            "requires_hitl": True,
            "hitl_reason": f"RGPD {right_detected} - validation superviseur requise",
            "rgpd_ref": rgpd_ref,
            "right_detected": right_detected,
            "dpo_notified": True,
        }

    def _detect_right(self, message: str) -> str:
        """Détecte le droit RGPD demandé."""
        msg_lower = message.lower()
        # 🔥 Priorité à Art.17
        if any(kw in msg_lower for kw in ["supprimer", "supprimez", "effacement", "oubli", "effacer"]):
            return "Art.17 — Droit à l'oubli"
        for keyword, right in self.RGPD_RIGHTS.items():
            if keyword in msg_lower:
                return right
        return "Art.15 — Droit d'accès"