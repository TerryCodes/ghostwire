#!/usr/bin/env python3.13
import asyncio
import subprocess
import time
import sys
import os

sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UDP_WS_SERVER_PORT=9453
UDP_RAW_SERVER_PORT=9463
UDP_WS_ECHO_PORT=9854
UDP_RAW_ECHO_PORT=9855
TOKEN="test_token_123456"

WS_SERVER_TOML=f"""
[server]
listen_host="127.0.0.1"
listen_port={UDP_WS_SERVER_PORT}
websocket_path="/ws"
ping_timeout=10
ws_pool_enabled=false
auto_update=false

[auth]
token="{TOKEN}"

[tunnels]
ports=["9080=127.0.0.1:{UDP_WS_ECHO_PORT}"]

[logging]
level="info"
file="/tmp/ghostwire-udp-ws-server.log"
"""

WS_CLIENT_TOML=f"""
[server]
url="ws://127.0.0.1:{UDP_WS_SERVER_PORT}/ws"
token="{TOKEN}"
auto_update=false

[reconnect]
initial_delay=1
max_delay=10
multiplier=2

[cloudflare]
enabled=false
ips=[]
host=""
check_interval=300

[logging]
level="info"
file="/tmp/ghostwire-udp-ws-client.log"
"""

RAW_SERVER_TOML=f"""
[server]
listen_host="127.0.0.1"
listen_port={UDP_RAW_SERVER_PORT}
protocol="udp"
ping_timeout=10
ws_pool_enabled=false
auto_update=false

[auth]
token="{TOKEN}"

[tunnels]
ports=["9081=127.0.0.1:{UDP_RAW_ECHO_PORT}"]

[logging]
level="info"
file="/tmp/ghostwire-udp-raw-server.log"
"""

RAW_CLIENT_TOML=f"""
[server]
url="ws://127.0.0.1:{UDP_RAW_SERVER_PORT}/ws"
protocol="udp"
token="{TOKEN}"
auto_update=false

[reconnect]
initial_delay=1
max_delay=10
multiplier=2

[cloudflare]
enabled=false
ips=[]
host=""
check_interval=300

[logging]
level="info"
file="/tmp/ghostwire-udp-raw-client.log"
"""

class EchoProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport=None
    def connection_made(self,transport):
        self.transport=transport
    def datagram_received(self,data,addr):
        self.transport.sendto(data,addr)

async def send_udp_and_recv(host,port,data,timeout=5):
    loop=asyncio.get_event_loop()
    recv_queue=asyncio.Queue()
    class _P(asyncio.DatagramProtocol):
        def datagram_received(self,d,a):
            recv_queue.put_nowait(d)
    transport,_=await loop.create_datagram_endpoint(_P,remote_addr=(host,port))
    transport.sendto(data)
    try:
        result=await asyncio.wait_for(recv_queue.get(),timeout=timeout)
    finally:
        transport.close()
    return result

async def test_udp_over_ws():
    print("UDP over WebSocket Test")
    print("="*40)
    with open("/tmp/test_udp_ws_server.toml","w") as f:
        f.write(WS_SERVER_TOML)
    with open("/tmp/test_udp_ws_client.toml","w") as f:
        f.write(WS_CLIENT_TOML)
    loop=asyncio.get_event_loop()
    echo_proto=EchoProtocol()
    echo_transport,_=await loop.create_datagram_endpoint(lambda: echo_proto,local_addr=("127.0.0.1",UDP_WS_ECHO_PORT))
    print(f"Echo UDP server on 127.0.0.1:{UDP_WS_ECHO_PORT}")
    server=subprocess.Popen(
        ["python3.13","server.py","-c","/tmp/test_udp_ws_server.toml"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    await asyncio.sleep(2)
    client=subprocess.Popen(
        ["python3.13","client.py","-c","/tmp/test_udp_ws_client.toml"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    await asyncio.sleep(3)
    results=[]
    for i in range(5):
        msg=f"UDP test packet {i}".encode()
        try:
            resp=await send_udp_and_recv("127.0.0.1",9080,msg,timeout=5)
            ok=resp==msg
            results.append(ok)
            print(f"  Packet {i+1}: {'OK' if ok else 'MISMATCH'} ({msg} -> {resp})")
        except asyncio.TimeoutError:
            results.append(False)
            print(f"  Packet {i+1}: TIMEOUT")
        await asyncio.sleep(0.5)
    client.terminate()
    client.wait()
    server.terminate()
    server.wait()
    echo_transport.close()
    await asyncio.sleep(1)
    success=sum(results)
    total=len(results)
    print(f"\nResult: {success}/{total} UDP packets echoed successfully")
    return success==total

async def test_udp_protocol():
    print("\nRaw UDP Protocol Test")
    print("="*40)
    with open("/tmp/test_udp_raw_server.toml","w") as f:
        f.write(RAW_SERVER_TOML)
    with open("/tmp/test_udp_raw_client.toml","w") as f:
        f.write(RAW_CLIENT_TOML)
    loop=asyncio.get_event_loop()
    echo_proto=EchoProtocol()
    echo_transport,_=await loop.create_datagram_endpoint(lambda: echo_proto,local_addr=("127.0.0.1",UDP_RAW_ECHO_PORT))
    print(f"Echo UDP server on 127.0.0.1:{UDP_RAW_ECHO_PORT}")
    server=subprocess.Popen(
        ["python3.13","server.py","-c","/tmp/test_udp_raw_server.toml"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    await asyncio.sleep(2)
    client=subprocess.Popen(
        ["python3.13","client.py","-c","/tmp/test_udp_raw_client.toml"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    await asyncio.sleep(3)
    results=[]
    for i in range(5):
        msg=f"Raw UDP test packet {i}".encode()
        try:
            resp=await send_udp_and_recv("127.0.0.1",9081,msg,timeout=5)
            ok=resp==msg
            results.append(ok)
            print(f"  Packet {i+1}: {'OK' if ok else 'MISMATCH'}")
        except asyncio.TimeoutError:
            results.append(False)
            print(f"  Packet {i+1}: TIMEOUT")
        await asyncio.sleep(0.5)
    client.terminate()
    client.wait()
    server.terminate()
    server.wait()
    echo_transport.close()
    success=sum(results)
    total=len(results)
    print(f"\nResult: {success}/{total} raw UDP packets echoed successfully")
    return success==total

async def main():
    r1=await test_udp_over_ws()
    r2=await test_udp_protocol()
    print("\n" + "="*40)
    if r1 and r2:
        print("All UDP tests PASSED")
    else:
        print(f"UDP over WS: {'PASS' if r1 else 'FAIL'}")
        print(f"Raw UDP protocol: {'PASS' if r2 else 'FAIL'}")
        sys.exit(1)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nInterrupted")
    subprocess.run(["pkill","-f","test_udp"],stderr=subprocess.DEVNULL)
