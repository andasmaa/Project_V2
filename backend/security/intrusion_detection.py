# security/intrusion_detection.py
from collections import defaultdict
from datetime import datetime, timedelta
import re

class IntrusionDetector:
    def __init__(self):
        self.failed_logins = defaultdict(list)
        self.suspicious_patterns = [
            r"union.*select",
            r"or\s+1=1",
            r"drop\s+table",
            r"';.*--",
            r"xp_cmdshell",
        ]
        self.blocked_ips = set()
    
    def check_failed_login(self, email: str, ip: str):
        now = datetime.now()
        cutoff = now - timedelta(minutes=15)
        self.failed_logins[email] = [t for t in self.failed_logins[email] if t > cutoff]
        self.failed_logins[email].append(now)
        
        if len(self.failed_logins[email]) >= 5:
            self.blocked_ips.add(ip)
            raise Exception(f"IP {ip} bloquée après 5 tentatives échouées")
    
    def check_sql_injection(self, message: str) -> bool:
        for pattern in self.suspicious_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False

intrusion_detector = IntrusionDetector()