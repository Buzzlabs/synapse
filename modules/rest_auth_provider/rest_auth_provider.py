import logging
import re
import requests
import hashlib
import unicodedata

try:
    from synapse.api.errors import AuthError
except ImportError:
    class AuthError(Exception):
        def __init__(self, code, msg):
            super().__init__(msg)
            self.code = code


logger = logging.getLogger(__name__)


class RestAuthProvider:

    def __init__(self, config, account_handler):
        self.account_handler = account_handler

        self.api_base = config["api_base"]
        self.check_endpoint = "/public/authenticate"

        self.timeout = config.get("timeout", 5)

        logger.info("RestAuthProvider loaded")

    @staticmethod
    def parse_config(config):
        for key in ("api_base",):
            if key not in config:
                raise Exception(f"{key} is necessary")
        return config

    @staticmethod
    def get_supported_login_types():
        return {
            "m.login.password": ("password",),
        }

    async def check_auth(self, username, login_type, login_dict):
        password = login_dict.get("password")
        if not password:
            raise AuthError(403, "password is necessary")

        email = self._extract_email(username)
        if not email:
            raise AuthError(400, "Email is necessary")

        logger.info("Login request email=%s", email)

        data = self._check_paywall(email, password)

        localpart = self._build_localpart_from_user(data)
        server_name = self.account_handler._hs.hostname
        mxid = f"@{localpart}:{server_name}"


        logger.info("MXID resolved: %s", mxid)

        await self._ensure_user_exists(mxid)

        return (mxid, None)

    def _check_paywall(self, email, password):
        try:
            resp = requests.post(
                f"{self.api_base}{self.check_endpoint}",
                json={
                    "subscriber-user/email": email,
                    "subscriber-user/password": RestAuthProvider.hash_password(password),
                },

                timeout=self.timeout,
            )
        except Exception as e:
            logger.error("Error calling paywall: %s", e)
            raise AuthError(500, "Authentication service error")

        if resp.status_code != 200:
            raise AuthError(403, "Invalid credentials")

        data = resp.json()

        if not isinstance(data, dict) or "email" not in data:
            raise AuthError(403, "Invalid response from the paywall")

        return data

 
    async def _ensure_user_exists(self, mxid: str):
        if await self.account_handler.check_user_exists(mxid):
            logger.info("User %s already exists", mxid)
            return

        logger.info("Creating user %s", mxid)

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
            raise AuthError(403, "User ID missing from the paywall response")

        info = data.get("info") or {}
        first = info.get("first-name")
        last = info.get("last-name")

        if first and last:
            base = f"{first}_{last}"

        elif email:
            base = email.split("@", 1)[0]

        else:
            raise AuthError(
                403,
                "Insufficient user data to build Matrix localpart"
            )


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