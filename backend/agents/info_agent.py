# agents/info_agent.py
from agents.base_agent import BaseAgent
from typing import Dict
from datetime import datetime
import sqlite3
import os
import traceback

# Chemin vers la base de données
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'awb_bank.db')

class InfoAgent(BaseAgent):
    def __init__(self):
        super().__init__("AG04", "mistral:7b")

    async def process(self, message: str, context: Dict = None) -> Dict:
        return await self.get_account_info(message, context)

    async def get_account_info(self, message: str, context: Dict = None) -> Dict:
        rag_context = (context or {}).get("rag_context", "")
        rag_results = (context or {}).get("rag_results", [])
        session_id = (context or {}).get("session_id")
        
        print("=" * 60)
        print(f"📚 INFO_AGENT - Message: {message[:80]}")
        print(f"🔑 Session ID reçu: {session_id}")
        print(f"📊 Type de session_id: {type(session_id)}")
        print("=" * 60)
        
        msg_lower = message.lower()
        
        # 🔥 Vérifier si l'utilisateur demande ses soldes
        if any(kw in msg_lower for kw in ["solde", "compte", "argent", "avoir", "patrimoine"]):
            print("🔍 Demande de solde détectée")
            
            if not session_id:
                print("❌ ERREUR: Pas de session_id - impossible d'accéder à la BD")
                return {
                    "message": "Veuillez vous reconnecter pour accéder à vos informations bancaires.",
                    "confidence": 0.4
                }
            
            try:
                comptes = self._get_comptes_from_db(session_id)
                print(f"📊 Résultat BD: {len(comptes) if comptes else 0} comptes")
                
                if comptes:
                    response = self._format_soldes_response(comptes)
                    return {"message": response, "confidence": 0.95}
                else:
                    return {
                        "message": "Aucun compte trouvé pour cette session. Veuillez vous reconnecter.",
                        "confidence": 0.5
                    }
            except Exception as e:
                print(f"❌ Exception dans get_account_info: {e}")
                traceback.print_exc()
                return {
                    "message": "Désolé, une erreur technique est survenue. Veuillez réessayer.",
                    "confidence": 0.3
                }
        
        # 🔥 Vérifier si l'utilisateur demande ses transactions
        if any(kw in msg_lower for kw in ["transaction", "operation", "historique", "virement", "paiement"]):
            print("🔍 Demande de transactions détectée")
            
            if not session_id:
                return {
                    "message": "Veuillez vous reconnecter pour accéder à vos transactions.",
                    "confidence": 0.4
                }
            
            try:
                transactions = self._get_transactions_from_db(session_id)
                if transactions:
                    response = self._format_transactions_response(transactions)
                    return {"message": response, "confidence": 0.95}
                else:
                    return {
                        "message": "Aucune transaction récente trouvée.",
                        "confidence": 0.5
                    }
            except Exception as e:
                print(f"❌ Exception dans get_account_info transactions: {e}")
                return {
                    "message": "Désolé, une erreur technique est survenue.",
                    "confidence": 0.3
                }
        
        # 🔥 Prompt système pour les autres questions
        system_prompt = """Tu es un conseiller bancaire professionnel d'Attijariwafa Bank (AWB) au Maroc.

TON RÔLE :
- Tu es un expert bancaire, pas un robot
- Tu donnes des réponses naturelles, humaines et professionnelles
- Tu utilises un langage bancaire clair sans jargon inutile
- Tu n'utilises JAMAIS d'émojis
- Tu ne donnes jamais d'informations confidentielles

N'utilise JAMAIS les expressions '[votre nom]' ou '[nom]'. Utilise 'je' directement.
Réponds dans la langue du client (français, anglais ou arabe)."""

        user_prompt = f"Client: {message}\n\nEn tant que conseiller bancaire AWB, réponds de manière naturelle, précise et utile."

        try:
            response = await self.call_llm(user_prompt, system=system_prompt, max_tokens=300, temperature=0.7)
        except Exception as e:
            print(f"⚠️ Erreur LLM info_agent: {e}")
            response = "Je suis votre conseiller bancaire AWB. Comment puis-je vous aider aujourd'hui ?"
        
        return {
            "message": response,
            "confidence": 0.90
        }
    
    def _get_comptes_from_db(self, session_id: str) -> list:
        """Récupère les comptes d'un client depuis la base de données"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Récupérer le client_id depuis la session
            cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
            session = cursor.fetchone()
            
            if not session:
                print(f"❌ Session non trouvée: {session_id}")
                conn.close()
                return []
            
            # Récupérer les comptes
            cursor.execute('''
                SELECT type_compte, solde, iban, decouvert_autorise 
                FROM comptes 
                WHERE client_id = ? AND statut = 'ACTIF'
            ''', (session["client_id"],))
            
            comptes = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            print(f"✅ {len(comptes)} comptes trouvés pour client {session['client_id']}")
            for c in comptes:
                print(f"   - {c['type_compte']}: {c['solde']} MAD")
            
            return comptes
        except Exception as e:
            print(f"❌ Erreur BD comptes: {e}")
            traceback.print_exc()
            return []
    
    def _get_transactions_from_db(self, session_id: str, limit: int = 5) -> list:
        """Récupère les dernières transactions d'un client"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Récupérer le client_id depuis la session
            cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
            session = cursor.fetchone()
            
            if not session:
                conn.close()
                return []
            
            # Récupérer les transactions
            cursor.execute('''
                SELECT t.date_transaction, t.type_transaction, t.montant, t.description, t.beneficiaire, c.type_compte
                FROM transactions t
                JOIN comptes c ON t.compte_id = c.compte_id
                WHERE c.client_id = ?
                ORDER BY t.date_transaction DESC 
                LIMIT ?
            ''', (session["client_id"], limit))
            
            transactions = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return transactions
        except Exception as e:
            print(f"❌ Erreur BD transactions: {e}")
            return []
    
    def _format_soldes_response(self, comptes: list) -> str:
        """Formate la réponse des soldes"""
        if not comptes:
            return "Je n'ai pas pu récupérer vos informations de compte. Veuillez réessayer."
        
        total = sum(c["solde"] for c in comptes)
        
        response = "**Résumé de vos comptes**\n\n"
        
        for compte in comptes:
            type_compte = compte["type_compte"]
            solde = compte["solde"]
            decouvert = compte.get("decouvert_autorise", 0)
            
            response += f"• **{type_compte}**: {solde:,.0f} MAD"
            if decouvert > 0:
                response += f" (découvert autorisé: {decouvert:,.0f} MAD)"
            response += "\n"
        
        response += f"\n**Solde total**: {total:,.0f} MAD"
        
        return response
    
    def _format_transactions_response(self, transactions: list) -> str:
        """Formate la réponse des transactions"""
        if not transactions:
            return "Aucune transaction récente trouvée sur vos comptes."
        
        response = "**Dernières transactions**\n\n"
        
        for t in transactions:
            date = t["date_transaction"][:10] if t["date_transaction"] else "Date inconnue"
            montant = t["montant"]
            type_transaction = t["type_transaction"]
            description = t["description"]
            beneficiaire = t.get("beneficiaire", "")
            
            signe = "+" if montant > 0 else ""
            
            response += f"• **{date}** - {type_transaction}: {signe}{montant:,.0f} MAD"
            if description:
                response += f" ({description})"
            if beneficiaire:
                response += f" - {beneficiaire}"
            response += "\n"
        
        return response