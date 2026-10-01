import asyncio
import logging
import socket
from ipaddress import IPv6Address

from iso15118.shared.security import get_ssl_context

logger = logging.getLogger(__name__)

SLEEP = 10


class TCPClient(asyncio.Protocol):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, session_handler_queue, port, is_tls):
        self._closed = False
        self.reader = None
        self.writer = None
        self.port = port
        self._session_handler_queue = session_handler_queue
        self._rcv_queue: asyncio.Queue = asyncio.Queue()
        self._last_message_sent = None
        self.ssl_context = None
        if is_tls:
            self.ssl_context = get_ssl_context(False)

    @staticmethod
    async def create(
        host: IPv6Address,
        port: int,
        session_handler_queue: asyncio.Queue,
        is_tls: bool,
        iface: str,
    ) -> "TCPClient":
        """
        TCPClient setup
        """
        self = TCPClient(session_handler_queue, port, is_tls)

        # When using IPv6 addresses, the interface must be specified in the
        # host IP string or we need to connect using the full socket address,
        # which includes the scope id. This is why, in the next line,
        # we concatenate the host IP with the NIC defined with the
        # NETWORK_INTERFACE env
        full_host_address = host.compressed + f"%{iface}"

        try:
            self.reader, self.writer = await asyncio.open_connection(
                host=full_host_address,
                port=port,
                family=socket.AF_INET6,
                ssl=self.ssl_context,
                server_hostname='' if self.ssl_context else None,
            )
        except ConnectionRefusedError as exc:
            raise exc
        except Exception as exc:
            raise exc

        return self
