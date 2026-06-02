import asyncio
import logging
import socket
import struct
from asyncio import DatagramProtocol, DatagramTransport
from typing import Optional, Tuple

from iso15118.shared.messages.timeouts import Timeouts
from iso15118.shared.messages.v2gtp import V2GTPMessage
from iso15118.shared.network import SDP_MULTICAST_GROUP, SDP_SERVER_PORT, _get_link_local_addr
from iso15118.shared.notifications import (
    ReceiveTimeoutNotification,
    UDPPacketNotification,
)

logger = logging.getLogger(__name__)


class UDPClient(DatagramProtocol):
    """
    The UDPClient makes use of asyncio and its concepts of 'transports' and
    'protocols'. A transport is an abstraction for a socket
    (how bytes are transmitted), while the protocol determines which bytes to
    transmit (and to some extent when).

    There is always a 1:1 relationship between transport and protocol objects:
    the protocol calls transport methods to send data, while the transport
    calls protocol methods to pass it data that has been received.

    asyncio implements transports for TCP, UDP, SSL, and subprocess pipes.
    We use asyncio.DatagramTransport for UDP. For more information see
    https://docs.python.org/3/library/asyncio-protocol.html
    """

    def __init__(self, session_handler_queue: asyncio.Queue, iface: str):
        self._session_handler_queue: asyncio.Queue = session_handler_queue
        # Indication whether or not the UDP client connection is open or closed
        self.started: bool = False
        self._rcv_queue: asyncio.Queue = asyncio.Queue()
        self._transport: Optional[DatagramTransport] = None
        self.iface = iface

    @staticmethod
    def _create_socket(iface: str) -> socket.socket:
        """
        This method creates an IPv6 socket configured to send multicast datagrams
        """

        # Initialise the socket for IPv6 datagrams
        # Address family (determines network layer protocol, here IPv6)
        # Socket type (datagram, determines transport layer protocol UDP)
        sock = socket.socket(family=socket.AF_INET6, type=socket.SOCK_DGRAM)

        # Allows address to be reused
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # The socket needs to be configured with a time-to-live value (TTL)
        # for messages to 1 so they do not go past the local network segment.
        ttl = struct.pack("@i", 1)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl)

        # Restrict multicast operation to the given interface
        # The IP_MULTICAST_IF or IPV6_MULTICAST_IF settings tell the socket
        # which interface it shall send its multicast packets. It can be seen
        # as the dual of bind(), in the server side, since bind() controls which
        # interface(s) the socket receives multicast packets from.
        interface_index = socket.if_nametoindex(iface)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, interface_index)

        # Bind to the interface's link-local address on an ephemeral port so
        # the kernel delivers unicast SDP responses back to this socket.
        # Without an explicit bind(), the socket only auto-binds on first
        # sendto(), and on Linux the unbound socket may not receive the unicast
        # reply because it isn't anchored to the interface. Using the
        # link-local address + scope_id avoids needing CAP_NET_RAW
        # (required by SO_BINDTODEVICE) while still anchoring to the NIC.
        link_local_addr = _get_link_local_addr(iface)
        sock.bind((str(link_local_addr), 0, 0, interface_index))

        return sock

    async def start(self):
        """
        Starts the UDP client service

        """
        # Get a reference to the event loop as we plan to use a low-level API
        # (see loop.create_datagram_endpoint())
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            protocol_factory=lambda: self,
            sock=self._create_socket(self.iface),
        )

    def connection_made(self, transport):
        """
        Callback of the lower level API, which is called when the connection to
        the socket succeeds
        """
        logger.debug("UDP client socket ready")
        self.started = True

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """
        Callback from asyncio.DatagramProtocol (which receives all packets)
        when a UDP server sent data.
        That data is put into a receiving queue that feeds into the
        communication session handler queue after.

        Args:
            data: A bytes object containing the incoming data
            addr: The address of the peer sending the data; the exact format
                  depends on the transport.
        """
        logger.info(f"Received datagram from UDP server at address {addr}")
        try:
            udp_packet = UDPPacketNotification(data, addr)
            self._rcv_queue.put_nowait((udp_packet, addr))
        except asyncio.QueueFull:
            logger.error(f"Dropped packet size {len(data)} from {addr}")

    def error_received(self, exc):
        logger.exception(f"Error received: {exc}")
        self.started = False

    def connection_lost(self, exc):
        logger.exception(f"Client closed: {exc}")
        self.started = False

    def send(self, message: V2GTPMessage):
        """
        This method will send the payload over the udp socket and right after
        will spawn a task in the event loop, awaiting for a specified time
        for an answer. Once a message is received, it is relayed to the
        Communication Session layer queue.

        If no answer arrives on time in the rcv queue, an exception is thrown
        and a ReceiveTimeout message notification is sent to the Communication
        Session layer

        if a timeout is not defined, the task will await indefinitely
        TODO: Should a None timeout be allowed? Because this way, the task
        wont ever die.

        We have to rethink/test this carefully, because of the following:
        When a task is spawned in the event loop, there are no guarantees that
        they are run sequentially, i.e., if we do
            asyncio.create_task(task_1)
            asyncio.create_task(task_2)

            There is a chance that task_2 is scheduled first than task_1
            (not sure about this)

        Consequences? We would receive a message within a time that was not
        linked with the timeout we specified when we spawned the task

        Q: Are we sure that when a message is put on the queue, that task_1
        will be the one receiving it and task_2 will still keep waiting for
        the next message?

        Solution 1: To avoid these kind of problems, the best is maybe
        to use a send queue for the UDP as well.
        A task is then reading from the queue the payload to be sent and the
        time out. We will await for the message until the specified timeout
        and we do not send any other message until we receive a message
        or the timeout expires. Since we are not forced to do multiplexing of
        messages, maybe this is the best way

        Solution 2: We check if the message just received is in fact an
        answer for the message requested/sent. If not, we put the message
        back into the queue and we restart the wait_for with the reamining
        time. Q: Do we endageour ourselves of entering in a deadloop of
        getting a message from the queue and putting it back over and over
        until the time expires? We have to test that
        """
        self._transport.sendto(
            message.to_bytes(), (SDP_MULTICAST_GROUP, SDP_SERVER_PORT)
        )

        logger.debug(f"Message sent: {message}")

    async def receive(self):
        try:
            udp_packet, _ = await asyncio.wait_for(
                self._rcv_queue.get(), timeout=Timeouts.SDP_REQ
            )
            self._session_handler_queue.put_nowait(udp_packet)
        except asyncio.TimeoutError as e:
            logger.warning(
                f"A {e.__class__.__name__} occurred. Waited "
                f"for {Timeouts.SDP_REQ} s after sending an "
                f"SDPRequest"
            )
            self._session_handler_queue.put_nowait(ReceiveTimeoutNotification())

    async def send_and_receive(self, message: V2GTPMessage):
        self.send(message)
        await self.receive()
