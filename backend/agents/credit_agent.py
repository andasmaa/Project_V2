# agents/credit_agent.py
from agents.base_agent import BaseAgent
from typing import Dict
import re
from datetime import datetime

class CreditAgent(BaseAgent):
    def __init__(self):
        super().__init__("AG06", "qwen:7b")
        self.hitl_threshold = 100000

    async def process_credit_request(self, message: str, user_id: str, context: Dict = None) -> Dict:
        amount = self._extract_amount(message)
        credit_ref = f"CRD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        msg_lower = message.lower()
        
        print(f"💰 CREDIT - Message: '{message[:80]}'")
        print(f"💰 CREDIT - Montant extrait: {amount} MAD")
        
        # 🔥 PRIORITÉ 1: Répondre aux questions sans montant
        if amount == 0:
            # Question sur les taux
            if "taux" in msg_lower or "intérêt" in msg_lower:
                response = """**Taux d'intérêt crédit immobilier AWB (Maroc)**

Taux à partir de 4.5% (fixe) sur 25 ans maximum.
Taux variable à partir de 4.0%.

Les taux sont donnés à titre indicatif et peuvent varier selon votre profil.
Une simulation personnalisée est disponible en agence.

 Service crédit : 0801 00 22 22"""
                return {
                    "message": response,
                    "confidence": 0.90,
                    "requires_hitl": False,
                    "credit_ref": credit_ref,
                }
            
            # Question sur les documents
            elif "document" in msg_lower or "papier" in msg_lower or "justificatif" in msg_lower:
                response = """**Documents nécessaires pour un crédit consommation AWB**

1. Carte d'identité nationale (CIN) en cours de validité
2. 3 derniers bulletins de salaire
3. Relevés bancaires des 3 derniers mois
4. Justificatif de domicile (facture d'électricité, eau, etc.)
5. Contrat de travail ou attestation d'emploi

Délai de traitement : 5 à 10 jours ouvrés.

 Service crédit : 0801 00 22 22"""
                return {
                    "message": response,
                    "confidence": 0.90,
                    "requires_hitl": False,
                    "credit_ref": credit_ref,
                }
            
            # Question sur les conditions/durées
            elif "condition" in msg_lower or "durée" in msg_lower or "délai" in msg_lower:
                response = """**Conditions générales des crédits AWB**

- Durée maximale : 25 ans pour crédit immobilier
- Délai de traitement : 5 à 15 jours ouvrés
- Apport minimum : 10% pour crédit immobilier
- Assurance obligatoire incluse

 Service crédit : 0801 00 22 22"""
                return {
                    "message": response,
                    "confidence": 0.90,
                    "requires_hitl": False,
                    "credit_ref": credit_ref,
                }
            
            # Demande de crédit sans montant
            elif any(kw in msg_lower for kw in ["credit", "crédit", "pret", "prêt", "emprunt", "financement"]):
                response = """**Demande de crédit**

Pour traiter votre demande, merci de préciser :
- Le type de crédit souhaité (immobilier, auto, consommation)
- Le montant en MAD (Dirhams Marocains)

Exemple : "Crédit immobilier de 150 000 MAD"

 Service crédit : 0801 00 22 22"""
                return {
                    "message": response,
                    "confidence": 0.85,
                    "requires_hitl": False,
                    "credit_ref": credit_ref,
                }
        
        # 🔥 PRIORITÉ 2: Montant détecté
        if amount > 0:
            requires_hitl = amount > self.hitl_threshold
            
            if requires_hitl:
                response = f"""**Demande de crédit de {amount:,.0f} MAD**

 Votre demande nécessite une validation par un superviseur (montant > {self.hitl_threshold:,.0f} MAD).
Un conseiller vous contactera sous 2h ouvrées.

 Service crédit : 0801 00 22 22"""
            else:
                response = f"""**Demande de crédit de {amount:,.0f} MAD**

 Votre demande a été enregistrée. Un conseiller vous contactera sous 24h.

 Service crédit : 0801 00 22 22"""
            
            return {
                "message": f"**Demande de crédit**\nRéférence : {credit_ref}\n\n{response}",
                "confidence": 0.90,
                "requires_hitl": requires_hitl,
                "hitl_reason": f"Crédit {amount:,.0f} MAD > {self.hitl_threshold:,.0f} MAD" if requires_hitl else "",
                "credit_ref": credit_ref,
            }
        
        # 🔥 PRIORITÉ 3: Réponse par défaut
        response = """**Crédits AWB (Maroc)**

Nous proposons plusieurs types de crédits :
- Crédit immobilier : à partir de 4.5%
- Crédit auto : à partir de 5.5%
- Crédit consommation : à partir de 6.5%

Pour une simulation, contactez le 0801 00 22 22
Ou rendez-vous dans votre agence AWB

Pouvez-vous me préciser le montant souhaité en MAD ?"""
        
        return {
            "message": f"{response}\n\nRéférence : {credit_ref}",
            "confidence": 0.85,
            "requires_hitl": False,
            "credit_ref": credit_ref,
        }

    async def process(self, message: str, context: Dict = None) -> Dict:
        user_id = (context or {}).get("user_id", "unknown")
        return await self.process_credit_request(message, user_id, context)

    def _extract_amount(self, text: str) -> float:
        """Extrait le montant mentionné dans le texte."""
        text_clean = re.sub(r'[ ,]', '', text)
        
        match_mad = re.search(r'(\d+)\s*(?:mad|dh|dirham)', text_clean, re.IGNORECASE)
        if match_mad:
            return float(match_mad.group(1))
        
        match_eur = re.search(r'(\d+)\s*(?:€|eur)', text_clean, re.IGNORECASE)
        if match_eur:
            return float(match_eur.group(1)) * 11
        
        numbers = re.findall(r'(\d{4,})', text_clean)
        if numbers:
            amounts = [float(n) for n in numbers]
            return max(amounts)
        
        return 0