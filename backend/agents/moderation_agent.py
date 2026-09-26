# agents/moderation_agent.py
from agents.base_agent import BaseAgent
from typing import Dict

class ModerationAgent(BaseAgent):
    def __init__(self):
        super().__init__("AG01", model="mixtral-8x7b-32768")
        
    async def process(self, message: str, context: Dict = None) -> Dict:
        toxicity = await self.check_toxicity(message)
        return {"is_toxic": toxicity["is_toxic"], "score": toxicity["score"]}
    
    async def check_toxicity(self, message: str) -> Dict:
        """
        Utilise Groq LLM pour détecter la toxicité
        Retourne un score entre 0 et 1
        """
        prompt = f"""Analyse le message suivant d'un client bancaire et évalue sa toxicité.

Message: "{message}"

Règles d'analyse:
- Toxicité élevée (score 0.8-1.0): insultes graves, menaces, harcèlement, langage très agressif
- Toxicité modérée (score 0.4-0.7): frustration excessive, mots grossiers, ton agressif
- Toxicité faible (score 0.1-0.3): légère impatience, ton un peu sec
- Non toxique (score 0.0): message normal, poli, professionnel

IMPORTANT: 
- Un client frustré qui signale un problème N'EST PAS toxique automatiquement
- Distingue "colère légitime" vs "toxicité réelle"
- Les mots comme "arnaque", "piratage", "fraude", "vol", "non autorisé", "supprimer", "données personnelles", "litige", "virement frauduleux" sont des signalements légitimes, PAS de la toxicité
- Une demande légitime de clôture de compte ou de suppression de données n'est PAS toxique
- TOUTES les demandes bancaires légitimes sont NON toxiques, même si elles expriment de la frustration

Réponds UNIQUEMENT au format JSON:
{{"score": 0.00, "reason": "Demande bancaire légitime", "is_toxic": false}}

Où is_toxic = True UNIQUEMENT pour les insultes graves et menaces explicites."""

        try:
            response = await self.call_llm(prompt, max_tokens=150)
            
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = min(max(result.get("score", 0.0), 0.0), 1.0)
                return {
                    "is_toxic": result.get("is_toxic", score >= 0.5),
                    "score": score,
                    "reason": result.get("reason", "")
                }
        except Exception as e:
            print(f"⚠️ Erreur modération LLM: {e}, fallback sur règles simples")
        
        return await self._fallback_toxicity_check(message)
    
    async def _fallback_toxicity_check(self, message: str) -> Dict:
        """Détection basique de toxicité (fallback très permissif)"""
        msg_lower = message.lower()
        
        # 🔥 SEULES les vraies insultes sont bloquées
        true_insults = ["connard", "merde", "ta gueule", "idiot", "stupide", "crétin", "nul", "incompétent", "fils de pute", "enculé"]
        
        # 🔥 Ne plus bloquer ces mots (maintenant autorisés)
        # "litige", "frauduleux", "dab", "avalé", etc. ne sont pas dans true_insults
        
        score = 0.0
        for word in true_insults:
            if word in msg_lower:
                score += 0.5
        
        # 🔥 Si le message contient un mot de signalement légitime, score forcé à 0
        legit_keywords = [
            "litige", "frauduleux", "virement", "carte", "dab", "avalé", 
            "compte", "clôture", "succession", "rgpd", "données", 
            "fraude", "piratage", "arnaque", "transaction"
        ]
        
        if any(kw in msg_lower for kw in legit_keywords):
            score = 0.0
        
        score = min(score, 1.0)
        
        return {
            "is_toxic": score >= 0.5,
            "score": score,
            "reason": "Détection par règles (fallback)"
        }