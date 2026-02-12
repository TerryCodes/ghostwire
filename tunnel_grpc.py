import abc
import typing
import grpclib.const
import grpclib.client
import grpclib.server
if typing.TYPE_CHECKING:
    import grpclib.metadata
import tunnel_pb2

class TunnelBase(abc.ABC):
    @abc.abstractmethod
    async def Stream(self,stream:'grpclib.server.Stream[tunnel_pb2.TunnelMessage, tunnel_pb2.TunnelMessage]') -> None:
        pass
    def __mapping__(self) -> typing.Dict[str,grpclib.const.Handler]:
        return {'/ghostwire.Tunnel/Stream':grpclib.const.Handler(self.Stream,grpclib.const.Cardinality.STREAM_STREAM,tunnel_pb2.TunnelMessage,tunnel_pb2.TunnelMessage)}

class TunnelStub:
    def __init__(self,channel:grpclib.client.Channel) -> None:
        self.Stream=grpclib.client.StreamStreamMethod(channel,'/ghostwire.Tunnel/Stream',tunnel_pb2.TunnelMessage,tunnel_pb2.TunnelMessage)
