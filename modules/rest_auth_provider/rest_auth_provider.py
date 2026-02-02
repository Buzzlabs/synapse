import logging
import re
import requests
import hashlib
import unicodedata

from synapse.api.errors import AuthError
from synapse.types import UserID

logger = logging.getLogger(__name__)


class RestAuthProvider:

    def __init__(self, config, account_handler):
        self.account_handler = account_handler

        self.api_base = config["api_base"]
        self.check_endpoint = "/public/authenticate"

        self.homeserver = config["homeserver"]
        self.timeout = config.get("timeout", 5)

        logger.info("RestAuthProvider carregado")

    @staticmethod
    def parse_config(config):
        for key in ("api_base", "homeserver"):
            if key not in config:
                raise Exception(f"{key} é obrigatório")
        return config

    @staticmethod
    def get_supported_login_types():
        return {
            "m.login.password": ("password",),
        }

    async def check_auth(self, username, login_type, login_dict):
        password = login_dict.get("password")
        if not password:
            raise AuthError(403, "Senha obrigatória")

        email = self._extract_email(username)
        if not email:
            raise AuthError(400, "Email obrigatório")

        logger.info("Login request email=%s", email)

        data = self._check_paywall(email, password)

        localpart = self._build_localpart_from_user(data)
        mxid = f"@{localpart}:{self.homeserver}"

        logger.info("MXID resolvido: %s", mxid)

        await self._ensure_user_exists(mxid)

        return (mxid, None)

    def _check_paywall(self, email, password):
        try:
            resp = requests.post(
                f"{self.api_base}{self.check_endpoint}",
                json={
                    "email": email,
                    "password": RestAuthProvider.hash_password(password),
                },
                timeout=self.timeout,
            )
        except Exception as e:
            logger.error("Erro chamando paywall: %s", e)
            raise AuthError(500, "Erro no serviço de autenticação")

        if resp.status_code != 200:
            raise AuthError(403, "Credenciais inválidas")

        data = resp.json()

        if not isinstance(data, dict) or "email" not in data:
            raise AuthError(403, "Resposta inválida do paywall")

        return data

 
    async def _ensure_user_exists(self, mxid: str):
        if await self.account_handler.check_user_exists(mxid):
            logger.info("Usuário %s já existe", mxid)
            return

        logger.info("Criando usuário %s", mxid)

        localpart = mxid.split(":", 1)[0][1:]

        await self.account_handler.register(
            localpart=localpart,
            displayname=None,
        )


    def _extract_email(self, username):
        
        if isinstance(username, str) and "@" in username:
            return username.strip().lower()
        return None

    def _build_localpart_from_user(self, data: dict) -> str:
        user_id = data.get("id")
        email = data.get("email")

        if not user_id:
            raise AuthError(403, "ID do usuário ausente no paywall")

        info = data.get("info") or {}
        first = info.get("first-name")
        last = info.get("last-name")

        if first and last:
            base = f"{first}_{last}"

        elif email:
            base = email.split("@", 1)[0]

        else:
            base = "user"

        base = self._normalize_localpart(base)

        # suffix = hashlib.sha256(user_id.encode()).hexdigest()[:6]

        return f"{base}" # _{suffix}

    def _normalize_localpart(self, value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("ascii")
        value = value.lower()
        return re.sub(r"[^a-z0-9._=-]", "_", value)

    @staticmethod
    def hash_password(raw: str) -> str:
        return hashlib.sha512(raw.encode("utf-8")).hexdigest()