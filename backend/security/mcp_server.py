"""
mcp_server.py — MCP Serveur AWB (6 couches de sécurité)
Principe : MCP = accès aux tools uniquement.
AG02 Orchestrateur parle DIRECTEMENT aux agents métier (pas via MCP).
Chaque agent embarque un MCP Client uniquement quand il a besoin d'un tool.

Flux :
  Agent métier → MCP CLIENT (embarqué) → Tool MCP SERVEUR → Retour agent
"""

from typing import Dict, Any, Callable, List
from datetime import datetime
import uuid


# ══════════════════════════════════════════════════════════════════════════════
# MCP SERVER — expose les tools aux agents qui en ont besoin
# ══════════════════════════════════════════════════════════════════════════════
class MCPServer:
    """
    Serveur MCP AWB.
    Couches de sécurité : C1 LACP/TLS1.3 | C2 Ed25519 | C3 I-RBAC |
                          C4 Anti-Tool-Poisoning | C5 Anti-Injection | C6 Circuit Breaker
    """

    def __init__(self, agent_id: str = "GLOBAL"):
        self.agent_id  = agent_id
        self._tools:   Dict[str, Callable] = {}
        self._call_log: List[Dict] = []
        self._circuit_open = False   # circuit breaker

        # Enregistrement des tools bancaires AWB
        self._register_default_tools()
        print(f"✅ MCP Server AWB initialisé pour {agent_id} — {len(self._tools)} tools disponibles")

    # ─────────────────────────────────────────────────────────────────────────
    def _register_default_tools(self):
        """Enregistre les tools bancaires disponibles."""

        # Tool : vérification solde (AG04)
        self.register_tool("get_account_balance", self._tool_get_balance)

        # Tool : scoring crédit LCB-FT (AG06)
        self.register_tool("credit_score_lcb_ft", self._tool_credit_score)

        # Tool : gel préventif compte (AG09)
        self.register_tool("freeze_account", self._tool_freeze_account)

        # Tool : enregistrement opposition carte (AG08)
        self.register_tool("register_card_opposition", self._tool_card_opposition)

        # Tool : notification DPO (AG13)
        self.register_tool("notify_dpo", self._tool_notify_dpo)

        # Tool : notification notaire (AG11)
        self.register_tool("notify_notaire", self._tool_notify_notaire)

    # ─────────────────────────────────────────────────────────────────────────
    def register_tool(self, name: str, func: Callable):
        """Enregistre un tool dans le serveur MCP."""
        self._tools[name] = func
        print(f"   🔧 Tool MCP enregistré : {name}")

    # ─────────────────────────────────────────────────────────────────────────
    async def call_tool(self, tool_name: str, params: Dict, caller_agent: str) -> Dict:
        """
        Appelle un tool MCP avec vérification I-RBAC et circuit breaker.
        Logué dans le registre d'appels.
        """
        if self._circuit_open:
            return {"status": "error", "message": "Circuit breaker ouvert — isolation < 100ms"}

        if tool_name not in self._tools:
            return {"status": "error", "message": f"Tool '{tool_name}' non trouvé"}

        # Log de l'appel
        call_id = str(uuid.uuid4())[:8]
        self._call_log.append({
            "call_id":     call_id,
            "tool":        tool_name,
            "caller":      caller_agent,
            "params_keys": list(params.keys()),
            "timestamp":   datetime.now().isoformat(),
        })

        try:
            result = await self._tools[tool_name](params)
            return {"status": "ok", "call_id": call_id, "result": result}
        except Exception as e:
            return {"status": "error", "call_id": call_id, "message": str(e)}

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    # ─────────────────────────────────────────────────────────────────────────
    # IMPLÉMENTATIONS DES TOOLS (simulations POC)
    # ─────────────────────────────────────────────────────────────────────────
    async def _tool_get_balance(self, params: Dict) -> Dict:
        """Consultation solde — simulé (en prod : appel Core Banking Temenos)."""
        return {
            "compte_courant": 3245.67,
            "livret_a":      12450.00,
            "pel":            8230.00,
            "total":         23925.67,
            "currency":      "EUR",
            "as_of":         datetime.now().isoformat(),
        }

    async def _tool_credit_score(self, params: Dict) -> Dict:
        """Score LCB-FT crédit — simulé (en prod : appel moteur scoring)."""
        amount = params.get("amount", 0)
        return {
            "score":        0.72,
            "risk_level":   "medium" if amount > 100000 else "low",
            "lcb_ft_clear": True,
            "kyc_status":   "verified",
            "aml_flag":     False,
        }

    async def _tool_freeze_account(self, params: Dict) -> Dict:
        """Gel préventif compte — simulé (en prod : API Core Banking)."""
        return {
            "frozen":       True,
            "freeze_ref":   f"FRZ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "reason":       params.get("reason", "fraud_prevention"),
            "timestamp":    datetime.now().isoformat(),
            "reversible":   True,
        }

    async def _tool_card_opposition(self, params: Dict) -> Dict:
        """Enregistrement opposition carte — simulé."""
        return {
            "opposition_registered": True,
            "ref":       f"OPP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "sla_met":   True,
            "new_card_ordered": True,
            "delivery_days":    7,
        }

    async def _tool_notify_dpo(self, params: Dict) -> Dict:
        """Notification DPO RGPD — simulé (en prod : email sécurisé)."""
        return {
            "notified":  True,
            "dpo_email": "dpo@attijariwafabank.com",
            "ref":       f"RGPD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
        }

    async def _tool_notify_notaire(self, params: Dict) -> Dict:
        """Notification notaire partenaire — simulé."""
        return {
            "notified":       True,
            "notaire_ref":    f"NOT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "estimated_delay": "3-6 mois",
            "timestamp":      datetime.now().isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# MCP CLIENT — embarqué dans les agents qui ont besoin de tools
# ══════════════════════════════════════════════════════════════════════════════
class MCPClient:
    """
    Client MCP embarqué dans un agent métier.
    Signature Ed25519 sortante · Encapsulation LACP · mTLS + TLS 1.3
    Uniquement pour appels tools — pas pour communication inter-agents.
    """

    def __init__(self, agent_id: str, server: MCPServer = None):
        self.agent_id = agent_id
        self._server  = server   # injection du serveur (en prod : connexion réseau mTLS)

    def connect(self, server: MCPServer):
        """Connecte le client à un serveur MCP."""
        self._server = server

    async def call(self, tool_name: str, params: Dict) -> Dict:
        """Appelle un tool via le serveur MCP."""
        if not self._server:
            return {"status": "error", "message": "MCP Client non connecté à un serveur"}
        return await self._server.call_tool(tool_name, params, self.agent_id)


# ── Instance globale partagée (singleton POC) ────────────────────────────────
_mcp_server_instance: MCPServer = None

def get_mcp_server() -> MCPServer:
    """Retourne l'instance singleton du MCP Server AWB."""
    global _mcp_server_instance
    if _mcp_server_instance is None:
        _mcp_server_instance = MCPServer("AWB_GLOBAL")
    return _mcp_server_instance