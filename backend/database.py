# database.py
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import os

from security.encryption import (
    encrypt_sensitive_data,
    decrypt_sensitive_data,
)

# =====================================================
# CHEMIN BASE DE DONNÉES (Vault ou local)
# =====================================================
try:
    from security.vault_loader import get_database_config
    _db_cfg = get_database_config()
    _db_path = _db_cfg.get("sqlite_path")
except Exception:
    _db_path = None

if _db_path:
    if not os.path.isabs(_db_path):
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _db_path)
    else:
        DB_PATH = _db_path
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "awb_bank.db")

print(f"📁 Base SQLite : {DB_PATH}")


# =====================================================
# HELPERS CHIFFREMENT
# =====================================================
def _safe_encrypt(value: str) -> str:
    """Chiffre une valeur en toute sécurité (retourne '' si vide)"""
    if not value:
        return value
    try:
        return encrypt_sensitive_data(value)
    except Exception as e:
        print(f"⚠️ Erreur chiffrement: {e}")
        return value  # fallback : on stocke en clair (à éviter en prod)


def _safe_decrypt(value: str) -> str:
    """Déchiffre une valeur en toute sécurité"""
    if not value:
        return value
    try:
        return decrypt_sensitive_data(value)
    except Exception:
        # Si la donnée n'était pas chiffrée, on la retourne telle quelle
        return value


# =====================================================
# INITIALISATION
# =====================================================
def init_db():
    """Initialise la base de données avec toutes les tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table clients
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telephone TEXT,
            adresse TEXT,
            password_hash TEXT NOT NULL,
            date_naissance DATE,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table comptes bancaires
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comptes (
            compte_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            iban TEXT UNIQUE NOT NULL,
            type_compte TEXT CHECK(type_compte IN ('COURANT', 'LIVRET_A', 'PEL', 'EPARGNE', 'JEUNE', 'PREMIUM')),
            solde REAL DEFAULT 0,
            statut TEXT DEFAULT 'ACTIF' CHECK(statut IN ('ACTIF', 'BLOQUE', 'FERME')),
            date_ouverture TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            decouvert_autorise REAL DEFAULT 0,
            plafond_retrait_journalier REAL DEFAULT 5000,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
    ''')

    # Table transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            compte_id TEXT NOT NULL,
            type_transaction TEXT CHECK(type_transaction IN ('VIREMENT', 'RETRAIT', 'DEPOT', 'FRAIS', 'INTERETS', 'CARTE', 'CHEQUE')),
            montant REAL NOT NULL,
            date_transaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            reference TEXT,
            beneficiaire TEXT,
            statut TEXT DEFAULT 'COMPLETEE' CHECK(statut IN ('COMPLETEE', 'EN_ATTENTE', 'ANNULEE')),
            FOREIGN KEY (compte_id) REFERENCES comptes(compte_id)
        )
    ''')

    # Table sessions utilisateur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            client_name TEXT NOT NULL,
            login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
    ''')

    # Table auth_events (SIEM)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auth_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            email TEXT,
            client_id TEXT,
            event_type TEXT CHECK(event_type IN ('LOGIN_SUCCESS','LOGIN_FAILED','LOGOUT','SESSION_EXPIRED','TOKEN_REFRESH')),
            ip_address TEXT,
            user_agent TEXT,
            session_id TEXT,
            details TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée")


# =====================================================
# MOTS DE PASSE
# =====================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# =====================================================
# SIEM — AUTH EVENTS
# =====================================================
def log_auth_event(event_type: str, email: str = None, client_id: str = None,
                   session_id: str = None, ip_address: str = None,
                   user_agent: str = None, details: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO auth_events (event_type, email, client_id, session_id,
                                 ip_address, user_agent, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (event_type, email, client_id, session_id, ip_address, user_agent, details))
    conn.commit()
    conn.close()


def get_auth_events(limit: int = 100) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM auth_events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_auth_stats_24h() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT event_type, COUNT(*) FROM auth_events
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY event_type
    ''')
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return stats


# =====================================================
# LECTURE CLIENT
# =====================================================
def get_client_by_email(email: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE email = ?", (email,))
    client = cursor.fetchone()
    conn.close()
    if not client:
        return None
    client_dict = dict(client)
    # 🔓 Déchiffre le téléphone
    if client_dict.get("telephone"):
        client_dict["telephone"] = _safe_decrypt(client_dict["telephone"])
    return client_dict


# =====================================================
# LECTURE COMPTES
# =====================================================
def get_comptes_by_client(client_id: str) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comptes WHERE client_id = ? AND statut = 'ACTIF'", (client_id,))
    comptes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    # 🔓 Déchiffre les IBAN
    for c in comptes:
        if c.get("iban"):
            c["iban"] = _safe_decrypt(c["iban"])
    return comptes


# =====================================================
# LECTURE TRANSACTIONS
# =====================================================
def get_transactions_by_compte(compte_id: str, limit: int = 10) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM transactions 
        WHERE compte_id = ? 
        ORDER BY date_transaction DESC 
        LIMIT ?
    ''', (compte_id, limit))
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return transactions


def get_all_transactions_by_client(client_id: str, limit: int = 20) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, c.type_compte, c.iban 
        FROM transactions t
        JOIN comptes c ON t.compte_id = c.compte_id
        WHERE c.client_id = ?
        ORDER BY t.date_transaction DESC 
        LIMIT ?
    ''', (client_id, limit))
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    # 🔓 Déchiffre l'IBAN joint
    for t in transactions:
        if t.get("iban"):
            t["iban"] = _safe_decrypt(t["iban"])
    return transactions


def get_solde_total(client_id: str) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(solde) FROM comptes WHERE client_id = ?", (client_id,))
    result = cursor.fetchone()[0]
    conn.close()
    return result or 0.0


# =====================================================
# SESSIONS
# =====================================================
def create_session(session_id: str, client_id: str, client_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (session_id, client_id, client_name, last_activity)
        VALUES (?, ?, ?, ?)
    ''', (session_id, client_id, client_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_session(session_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    conn.close()
    return dict(session) if session else None


def update_session_activity(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET last_activity = ? WHERE session_id = ?",
                   (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()


# =====================================================
# INFOS CLIENT COMPLET
# =====================================================
def get_client_full_info(client_id: str) -> Dict:
    comptes = get_comptes_by_client(client_id)
    solde_total = get_solde_total(client_id)
    transactions = get_all_transactions_by_client(client_id, 10)
    return {
        "comptes": comptes,
        "solde_total": solde_total,
        "transactions": transactions,
        "nb_comptes": len(comptes)
    }


# =====================================================
# CHARGEMENT DES DONNÉES (avec chiffrement)
# =====================================================
def load_sample_data():
    """Charge des données clients simulées (9 fixes + 100 générés)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Vérifie si des données existent déjà
    cursor.execute("SELECT COUNT(*) FROM clients")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return

    # =====================================================
    # 9 CLIENTS FIXES
    # =====================================================
    clients = [
        ("C001", "BENALI", "Farid", "farid@awb.ma", "0612345678", "12 Rue de la Liberté, Casablanca", hash_password("farid20"), "1990-05-15"),
        ("C002", "EL MANSOURI", "Ahmed", "ahmed@awb.ma", "0612345679", "45 Avenue Hassan II, Rabat", hash_password("ahmed123"), "1985-08-22"),
        ("C003", "ALAOUI", "Fatima", "fatima@awb.ma", "0612345680", "78 Boulevard Mohammed V, Marrakech", hash_password("fatima456"), "1992-11-30"),
        ("C004", "TOUMI", "Karim", "karim@awb.ma", "0612345681", "23 Rue Oued Fès, Fès", hash_password("karim789"), "1988-03-10"),
        ("C005", "BENJELLOUN", "Sofia", "sofia@awb.ma", "0612345682", "67 Avenue des FAR, Tanger", hash_password("sofia123"), "1995-07-20"),
        ("C006", "OUAZZANI", "Hassan", "hassan@awb.ma", "0612345683", "34 Rue Moulay Ismail, Meknès", hash_password("hassan456"), "1982-12-05"),
        ("C007", "CHAKIB", "Leila", "leila@awb.ma", "0612345684", "89 Avenue de l'Afrique, Agadir", hash_password("leila789"), "1993-09-18"),
        ("C008", "BENABDELJALIL", "Youssef", "youssef@awb.ma", "0612345685", "56 Rue de la Gare, Tétouan", hash_password("youssef123"), "1987-04-12"),
        ("C009", "IMOUZAZ", "Nabila", "nabila.imouzaz@awb.ma", "0612345688", "15 Rue des Oliviers, Casablanca", hash_password("nabila20"), "1995-08-25"),
    ]

    # 100 USERS GÉNÉRÉS
    prenoms_marocains = [
        "Mohamed", "Ahmed", "Youssef", "Omar", "Ali", "Hassan", "Ibrahim", "Karim", "Rachid", "Samir",
        "Fatima", "Aicha", "Khadija", "Zineb", "Salma", "Nadia", "Leila", "Sanaa", "Imane", "Houda",
        "Amine", "Mehdi", "Anas", "Yassine", "Bilal", "Hamza", "Adil", "Khalid", "Mounir", "Nizar",
        "Aya", "Yasmine", "Rania", "Sofia", "Ines", "Lina", "Sara", "Malak", "Meryem", "Chaimae",
    ]
    noms_marocains = [
        "EL AMRANI", "BENALI", "ALAOUI", "EL FASSI", "BENNANI", "IDRISSI", "Tazi", "BERADA", "CHRAIBI",
        "SEBTI", "LAHLOU", "BENJELLOUN", "MANSOURI", "ZEROUAL", "BOUAZZA", "KETTANI", "BERRADA",
        "OUAZZANI", "CHAKIB", "TOUMI", "BENABDELJALIL", "IMOUZAZ", "GUESSOUS", "LARAICHI", "MEKOUAR",
    ]
    villes = ["Casablanca", "Rabat", "Marrakech", "Fès", "Tanger", "Agadir", "Meknès", "Oujda", "Tétouan", "Kénitra"]

    random.seed(42)

    for i in range(10, 110):
        prenom = random.choice(prenoms_marocains)
        nom = random.choice(noms_marocains)
        ville = random.choice(villes)
        username = f"{prenom.lower()}.{nom.lower().replace(' ', '')}{i}"
        email = f"{username}@awb.ma"
        password = f"pass{i}"
        telephone = f"06{random.randint(10000000, 99999999)}"
        adresse = f"{random.randint(1, 200)} Rue {random.choice(['des Fleurs', 'de la Paix', 'Mohammed V', 'Hassan II', 'des Roses', 'Al Massira'])}"
        date_naissance = f"{random.randint(1960, 2000)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"

        clients.append((
            f"C{i:03d}", nom, prenom, email, telephone,
            f"{adresse}, {ville}", hash_password(password), date_naissance
        ))

    # 🔐 Chiffre les téléphones AVANT insertion
    clients_encrypted = []
    for c in clients:
        client_id, nom, prenom, email, telephone, adresse, pwd_hash, date_naiss = c
        clients_encrypted.append((
            client_id, nom, prenom, email,
            _safe_encrypt(telephone),   # 🔐 chiffré
            adresse, pwd_hash, date_naiss
        ))

    cursor.executemany('''
        INSERT INTO clients (client_id, nom, prenom, email, telephone, adresse, password_hash, date_naissance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', clients_encrypted)
    print(f"   ✅ {len(clients_encrypted)} clients insérés (téléphones chiffrés)")

    # =====================================================
    # COMPTES BANCAIRES
    # =====================================================
    comptes = [
        ("CPT001", "C001", "FR7612345678901234567890123", "COURANT", 125000, "ACTIF", -5000, 10000),
        ("CPT002", "C001", "FR7612345678901234567890124", "LIVRET_A", 45000, "ACTIF", 0, 5000),
        ("CPT003", "C001", "FR7612345678901234567890125", "PEL", 30000, "ACTIF", 0, 0),
        ("CPT004", "C002", "FR7612345678901234567890126", "COURANT", 85000, "ACTIF", -3000, 8000),
        ("CPT005", "C002", "FR7612345678901234567890127", "EPARGNE", 12000, "ACTIF", 0, 5000),
        ("CPT006", "C003", "FR7612345678901234567890128", "COURANT", 250000, "ACTIF", -10000, 15000),
        ("CPT007", "C004", "FR7612345678901234567890129", "COURANT", 45000, "ACTIF", -2000, 5000),
        ("CPT008", "C005", "FR7612345678901234567890130", "COURANT", 180000, "ACTIF", -8000, 12000),
        ("CPT009", "C005", "FR7612345678901234567890131", "LIVRET_A", 75000, "ACTIF", 0, 5000),
        ("CPT010", "C006", "FR7612345678901234567890132", "COURANT", 95000, "ACTIF", -5000, 8000),
        ("CPT011", "C007", "FR7612345678901234567890133", "COURANT", 32000, "ACTIF", -1000, 5000),
        ("CPT012", "C008", "FR7612345678901234567890134", "COURANT", 150000, "ACTIF", -7000, 10000),
        ("CPT013", "C009", "FR7612345678901234567890140", "COURANT", 157500, "ACTIF", -8000, 15000),
        ("CPT014", "C009", "FR7612345678901234567890141", "LIVRET_A", 68000, "ACTIF", 0, 5000),
        ("CPT015", "C009", "FR7612345678901234567890142", "EPARGNE", 25000, "ACTIF", 0, 5000),
        ("CPT016", "C009", "FR7612345678901234567890143", "PREMIUM", 500000, "ACTIF", -20000, 25000),
    ]

    compte_counter = 17
    types = ["COURANT", "LIVRET_A", "EPARGNE", "PREMIUM", "JEUNE"]

    for i in range(10, 110):
        client_id = f"C{i:03d}"
        nb_comptes = random.choice([1, 1, 1, 2])
        for j in range(nb_comptes):
            type_compte = random.choice(types)
            solde = round(random.uniform(1000, 500000), 2)
            iban = f"FR7612345678901234567{compte_counter:06d}"
            decouvert = random.choice([0, -1000, -3000, -5000])
            plafond = random.choice([3000, 5000, 8000, 10000, 15000])
            comptes.append((
                f"CPT{compte_counter:03d}", client_id, iban, type_compte,
                solde, "ACTIF", decouvert, plafond
            ))
            compte_counter += 1

    # 🔐 Chiffre les IBAN AVANT insertion
    comptes_encrypted = []
    for c in comptes:
        compte_id, client_id, iban, type_c, solde, statut, decouvert, plafond = c
        comptes_encrypted.append((
            compte_id, client_id,
            _safe_encrypt(iban),  # 🔐 chiffré
            type_c, solde, statut, decouvert, plafond
        ))

    cursor.executemany('''
        INSERT INTO comptes (compte_id, client_id, iban, type_compte, solde, statut, decouvert_autorise, plafond_retrait_journalier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', comptes_encrypted)
    print(f"   ✅ {len(comptes_encrypted)} comptes insérés (IBAN chiffrés)")

    # =====================================================
    # TRANSACTIONS
    # =====================================================
    now = datetime.now()
    transactions = [
        ("TRX001", "CPT001", "VIREMENT", -5000, now - timedelta(days=5), "Virement vers BENALI", "REF123456", "Mohamed BENALI"),
        ("TRX002", "CPT001", "DEPOT", 10000, now - timedelta(days=10), "Virement reçu", "REF123457", "Saïd EL MANSOURI"),
        ("TRX003", "CPT001", "RETRAIT", -2000, now - timedelta(days=15), "Retrait DAB", "REF123458", ""),
        ("TRX004", "CPT001", "FRAIS", -150, now - timedelta(days=30), "Frais de tenue de compte", "REF123459", ""),
        ("TRX005", "CPT002", "INTERETS", 450, now - timedelta(days=60), "Intérêts Livret A", "REF123460", ""),
        ("TRX006", "CPT004", "VIREMENT", -20000, now - timedelta(days=3), "Virement", "REF123461", "Fatima ALAOUI"),
        ("TRX007", "CPT004", "CARTE", -850, now - timedelta(days=2), "Paiement Carrefour", "REF123462", "Carrefour"),
        ("TRX008", "CPT006", "DEPOT", 50000, now - timedelta(days=8), "Virement reçu", "REF123463", "Karim TOUMI"),
        ("TRX009", "CPT006", "RETRAIT", -10000, now - timedelta(days=12), "Retrait DAB", "REF123464", ""),
        ("TRX010", "CPT013", "DEPOT", 25000, now - timedelta(days=2), "Virement reçu", "REF123470", "Hassan OUAZZANI"),
        ("TRX011", "CPT013", "VIREMENT", -8500, now - timedelta(days=5), "Virement", "REF123471", "Leila CHAKIB"),
        ("TRX012", "CPT013", "CARTE", -1200, now - timedelta(days=1), "Paiement Marjane", "REF123472", "Marjane"),
        ("TRX013", "CPT013", "RETRAIT", -3000, now - timedelta(days=7), "Retrait DAB", "REF123473", ""),
        ("TRX014", "CPT013", "VIREMENT", -15000, now - timedelta(days=12), "Virement", "REF123474", "Youssef BENABDELJALIL"),
        ("TRX015", "CPT013", "DEPOT", 35000, now - timedelta(days=20), "Virement reçu", "REF123475", "Mohamed BENALI"),
        ("TRX016", "CPT013", "FRAIS", -200, now - timedelta(days=30), "Frais de tenue de compte", "REF123476", ""),
        ("TRX017", "CPT013", "CARTE", -350, now - timedelta(days=4), "Paiement Zara", "REF123477", "Zara"),
        ("TRX018", "CPT014", "INTERETS", 680, now - timedelta(days=60), "Intérêts Livret A", "REF123478", ""),
        ("TRX019", "CPT014", "DEPOT", 10000, now - timedelta(days=15), "Alimentation livret", "REF123479", ""),
        ("TRX020", "CPT016", "DEPOT", 100000, now - timedelta(days=45), "Dépôt initial", "REF123480", ""),
        ("TRX021", "CPT016", "VIREMENT", -25000, now - timedelta(days=10), "Virement", "REF123481", "Sofia BENJELLOUN"),
        ("TRX022", "CPT016", "CARTE", -5000, now - timedelta(days=3), "Paiement Voyage", "REF123482", "Royal Air Maroc"),
    ]

    types_tx = ["VIREMENT", "RETRAIT", "DEPOT", "CARTE", "FRAIS"]
    trx_counter = 23

    for compte_id in [c[0] for c in comptes if int(c[0].replace("CPT", "")) > 16][:50]:
        nb_tx = random.randint(2, 6)
        for _ in range(nb_tx):
            type_tx = random.choice(types_tx)
            montant = round(random.uniform(50, 20000), 2)
            if type_tx in ["VIREMENT", "RETRAIT", "CARTE", "FRAIS"]:
                montant = -montant
            transactions.append((
                f"TRX{trx_counter:04d}", compte_id, type_tx, montant,
                now - timedelta(days=random.randint(1, 90)),
                f"{type_tx.lower().capitalize()} automatique",
                f"REF{trx_counter:06d}",
                random.choice(["Marjane", "Carrefour", "Zara", "Royal Air Maroc", ""])
            ))
            trx_counter += 1

    cursor.executemany('''
        INSERT INTO transactions (transaction_id, compte_id, type_transaction, montant, date_transaction, description, reference, beneficiaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', transactions)

    conn.commit()
    conn.close()

    print(f"   ✅ {len(transactions)} transactions insérées")
    print("=" * 60)
    print("📊 RÉSUMÉ DES DONNÉES (🔐 chiffrées avec Vault)")
    print("=" * 60)
    print(f"   👥 Clients : {len(clients)} (9 fixes + 100 générés)")
    print(f"   💳 Comptes : {len(comptes)}")
    print(f"   💸 Transactions : {len(transactions)}")
    print("=" * 60)
    print("🔑 COMPTES DE DÉMO :")
    print("   nabila.imouzaz@awb.ma / nabila20")
    print("   farid@awb.ma / farid20")
    print("   + 100 users générés")
    print("=" * 60)


# =====================================================
# LECTURE PAR SESSION
# =====================================================
def get_client_by_session(session_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return None
    cursor.execute("SELECT * FROM clients WHERE client_id = ?", (session["client_id"],))
    client = cursor.fetchone()
    conn.close()
    if not client:
        return None
    client_dict = dict(client)
    # 🔓 Déchiffre le téléphone
    if client_dict.get("telephone"):
        client_dict["telephone"] = _safe_decrypt(client_dict["telephone"])
    return client_dict


def get_comptes_by_session(session_id: str) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return []
    cursor.execute("SELECT * FROM comptes WHERE client_id = ? AND statut = 'ACTIF'", (session["client_id"],))
    comptes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    # 🔓 Déchiffre les IBAN
    for c in comptes:
        if c.get("iban"):
            c["iban"] = _safe_decrypt(c["iban"])
    return comptes


def get_solde_total_by_session(session_id: str) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return 0.0
    cursor.execute("SELECT SUM(solde) FROM comptes WHERE client_id = ?", (session["client_id"],))
    result = cursor.fetchone()[0]
    conn.close()
    return result or 0.0


def get_dernieres_transactions_by_session(session_id: str, limit: int = 5) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return []
    cursor.execute('''
        SELECT t.*, c.type_compte 
        FROM transactions t
        JOIN comptes c ON t.compte_id = c.compte_id
        WHERE c.client_id = ?
        ORDER BY t.date_transaction DESC 
        LIMIT ?
    ''', (session["client_id"], limit))
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return transactions


def get_resume_client(session_id: str) -> Dict:
    comptes = get_comptes_by_session(session_id)
    solde_total = get_solde_total_by_session(session_id)
    transactions = get_dernieres_transactions_by_session(session_id, 5)

    comptes_detail = []
    for compte in comptes:
        comptes_detail.append({
            "type": compte["type_compte"],
            "solde": compte["solde"],
            "iban": compte["iban"][-6:] if compte.get("iban") else None,
            "decouvert_autorise": compte.get("decouvert_autorise", 0),
            "plafond_retrait": compte.get("plafond_retrait_journalier", 5000)
        })

    transactions_detail = []
    for t in transactions:
        transactions_detail.append({
            "date": t["date_transaction"],
            "type": t["type_transaction"],
            "montant": t["montant"],
            "description": t["description"],
            "beneficiaire": t.get("beneficiaire", "")
        })

    return {
        "solde_total": solde_total,
        "nombre_comptes": len(comptes),
        "comptes": comptes_detail,
        "dernieres_transactions": transactions_detail,
        "a_une_premium": any(c["type_compte"] == "PREMIUM" for c in comptes)
    }


def check_solde_suffisant(session_id: str, montant: float, type_compte: str = "COURANT") -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT client_id FROM sessions WHERE session_id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return False
    cursor.execute('''
        SELECT solde, decouvert_autorise 
        FROM comptes 
        WHERE client_id = ? AND type_compte = ? AND statut = 'ACTIF'
    ''', (session["client_id"], type_compte))
    compte = cursor.fetchone()
    conn.close()
    if not compte:
        return False
    solde_disponible = compte[0] + compte[1]
    return solde_disponible >= montant


# =====================================================
# INITIALISATION AU CHARGEMENT
# =====================================================
init_db()
load_sample_data()