import logging
import os
import time

logger = logging.getLogger(__name__)


def read_secret_file(path: str | None, *, wait_seconds: int = 0) -> str | None:
    """
    Le um segredo de arquivo e devolve o conteudo sem espacos nas pontas.

    Devolve None se o caminho nao foi informado, se o arquivo nao existe
    (depois de esperar ate `wait_seconds` segundos, 1s por tentativa), se esta
    vazio ou se nao pode ser lido. So o caminho vai para o log, nunca o conteudo.
    """
    if not path:
        return None

    for attempt in range(wait_seconds + 1):
        if os.path.exists(path):
            break
        if attempt < wait_seconds:
            time.sleep(1)
    else:
        logger.warning("secret file not found: %s (waited %ss)", path, wait_seconds)
        return None

    try:
        with open(path, "r") as f:
            return f.read().strip() or None
    except OSError:
        logger.exception("cannot read secret file: %s", path)
        return None
