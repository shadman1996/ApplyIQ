import os
import sys
import json
import getpass
from typing import Dict, Any, Optional

CRED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "credentials.json")

class CredentialVault:
    """
    Secure local credential manager. Prompts user in chat ONCE per platform,
    saves locally on laptop, and automatically reuses for 24/7 background applications.
    """
    def __init__(self):
        os.makedirs(os.path.dirname(CRED_PATH), exist_ok=True)
        self.credentials = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(CRED_PATH):
            try:
                with open(CRED_PATH, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        with open(CRED_PATH, 'w') as f:
            json.dump(self.credentials, f, indent=2)

    def get_credential(self, platform_key: str) -> Optional[Dict[str, str]]:
        return self.credentials.get(platform_key)

    def get_gemini_api_key(self) -> Optional[str]:
        """Retrieves Gemini API Key from environment, .env file, or credentials vault."""
        key = os.environ.get("GEMINI_API_KEY")
        if key and len(key.strip()) > 5:
            return key.strip()

        # Check .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY=") and len(line) > 15:
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["GEMINI_API_KEY"] = val
                                return val
            except Exception:
                pass

        # Check credentials.json
        gem_cred = self.credentials.get("gemini")
        if isinstance(gem_cred, dict):
            k = gem_cred.get("api_key") or gem_cred.get("password")
            if k and len(k.strip()) > 5:
                os.environ["GEMINI_API_KEY"] = k.strip()
                return k.strip()
        elif isinstance(gem_cred, str) and len(gem_cred.strip()) > 5:
            os.environ["GEMINI_API_KEY"] = gem_cred.strip()
            return gem_cred.strip()

        raw_key = self.credentials.get("gemini_api_key")
        if raw_key and isinstance(raw_key, str) and len(raw_key.strip()) > 5:
            os.environ["GEMINI_API_KEY"] = raw_key.strip()
            return raw_key.strip()

        return None

    def set_gemini_api_key(self, api_key: str):
        """Stores the Gemini API key in credentials vault and updates .env."""
        api_key = api_key.strip()
        self.credentials["gemini"] = {"api_key": api_key, "username": "gemini_user"}
        self.credentials["gemini_api_key"] = api_key
        self._save()
        os.environ["GEMINI_API_KEY"] = api_key

        # Update .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        try:
            lines = []
            replaced = False
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for i, l in enumerate(lines):
                    if l.strip().startswith("GEMINI_API_KEY="):
                        lines[i] = f"GEMINI_API_KEY={api_key}\n"
                        replaced = True
            if not replaced:
                lines.insert(0, f"GEMINI_API_KEY={api_key}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass

    def prompt_user_for_credential(self, platform_name: str, domain: str) -> Dict[str, str]:
        """
        Interactive chat prompt when agent encounters a new platform for the first time.
        """
        print("\n" + "="*60)
        print(f"🤖 [AGENT REQUEST] One-Time Login Needed for: {platform_name} ({domain})")
        print("="*60)
        print(f"I found a high-matching cybersecurity job on {platform_name}.")
        print("Please enter your login details ONCE. I will save them locally and never ask again.\n")
        
        username = input(f"Enter username/email for {platform_name}: ").strip()
        if sys.stdin.isatty():
            password = getpass.getpass(f"Enter password for {platform_name}: ").strip()
        else:
            print(f"Enter password for {platform_name}: ", end="", flush=True)
            password = sys.stdin.readline().strip()
        
        creds = {"username": username, "password": password}
        self.credentials[domain] = creds
        self.credentials[platform_name.lower()] = creds
        self._save()
        
        print(f"✅ Credentials for {platform_name} saved securely in local vault.\n")
        return creds
