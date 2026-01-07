import json
import logging
from urllib.parse import quote

from zope.interface import implementer

from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import ensureDeferred, succeed
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from synapse.module_api import ModuleApi
from synapse.http.server import respond_with_json
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)

class InviteModule:
    def __init__(self, config, api: ModuleApi):
        logger.warning("InviteModule loaded")
        module_config = InviteModuleConfig(config)
        api.register_web_resource(
            path="/_matrix/invite",
            resource=InviteResource(api, module_config),
        )

class InviteResource(Resource):
    isLeaf = True

    def __init__(self, api: ModuleApi, config: "InviteModuleConfig"):
        super().__init__()
        self.api = api
        self.config = config
        self.agent = Agent(api._hs.get_reactor())

    def render_POST(self, request):
        ensureDeferred(self._handle(request))
        return NOT_DONE_YET

    async def _handle(self, request):
        try:
            logger.info("invite: request received")

            requester = await self.api.get_user_by_req(request)
            user_id = requester.user.to_string()
            logger.info("invite: requester user_id=%s", user_id)

            body = parse_json_object_from_request(request)
            logger.info("invite: payload=%s", body)

            community = body.get("community")
            if not community:
                logger.warning("invite: missing community")
                raise SynapseError(400, "missing community")

            if community not in self.config.communities:
                logger.warning("invite: unknown community=%s", community)
                raise SynapseError(404, "unknown community")

            room_id = self.config.communities[community]

            logger.info(
                "invite: community=%s resolved to room_id=%s",
                community,
                room_id,
            )

            url = (
                f"{self.config.homeserver}/_synapse/admin/v1/join/"
                f"{quote(room_id)}"
            )

            logger.info("invite: calling admin join endpoint %s", url)

            payload = json.dumps({"user_id": user_id}).encode()

            response = await self.agent.request(
                b"POST",
                url.encode(),
                Headers({
                        b"Authorization": [f"Bearer {self.config.admin_token}".encode()],
                        b"Content-Type": [b"application/json"],
                    }
                ),
                bodyProducer=_BodyProducer(payload),
            )

            response_body = await readBody(response)

            logger.info(
                "invite: admin join response code=%s body=%s",
                response.code,
                response_body.decode(errors="ignore"),
            )

            if response.code != 200:
                logger.error("invite: admin join failed")
                raise SynapseError(500, "admin join failed")

            logger.info(
                "invite: success user=%s room=%s",
                user_id,
                room_id,
            )

            respond_with_json(request, 200, {"ok": True})

        except SynapseError as e:
            logger.warning(
                "invite: synapse error code=%s msg=%s",
                e.code,
                e.msg,
            )
            respond_with_json(request, e.code, {"error": e.msg})

        except Exception:
            logger.exception("invite: unexpected failure")
            respond_with_json(request, 500, {"error": "internal"})


@implementer(IBodyProducer)
class _BodyProducer:
    def __init__(self, body: bytes):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class InviteModule:
    def __init__(self, config, api: ModuleApi):
        logger.warning("InviteModule loaded")
        module_config = InviteModuleConfig(config)
        api.register_web_resource(
            path="/_matrix/invite",
            resource=InviteResource(api, module_config),
        )

class InviteModuleConfig:
    def __init__(self, config: dict):
        try:
            self.admin_token = config["admin_token"]
            self.homeserver = config["homeserver"]
            self.communities = config["communities"]
        except KeyError as e:
            raise Exception(f"Missing InviteModule config key: {e}")
