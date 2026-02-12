# HTTP/2 Implementation - Session Summary

## Problem
CloudFlare forces HTTP/2 which breaks WebSocket upgrade:
```
* using HTTP/2
* Invalid HTTP header: [upgrade], [websocket]
< HTTP/2 426
```

## What We Tried
Implemented HTTP/2 bidirectional streaming transport in `http2_transport.py` using `httpx` library.

## Current Status
**WebSocket**: ✅ WORKS PERFECTLY (3562 Mbps throughput)
**HTTP/2**: ❌ BROKEN - Architectural issue

## Why HTTP/2 Failed
Fatal flaw in `http2_transport.py`:
- Used `httpx.AsyncClient.post()` for bidirectional streaming
- `httpx` can't read response while still writing request body
- Creates deadlock: server sends pubkey → client reads → client sends auth → server reads
- HTTP/2 POST doesn't support this pattern

**Error manifestations:**
- Client: `'NoneType' object has no attribute 'public_bytes'`
- Server: `Auth message too large`
- Root cause: Streaming request/response incompatibility

## Code Locations
- `http2_transport.py` - Broken implementation
- `grpc-implementation` branch - Partial gRPC attempt (incomplete)
- `test_concurrent_speed.py` - Test suite (works with WebSocket)
- Default protocol in `config.py`: Currently `websocket`

## Technical Details

### What Works
```python
# WebSocket (protocol.py has all crypto functions)
from protocol import *  # Has generate_rsa_keypair, serialize_public_key, etc.
```

### What's Broken
```python
# http2_transport.py line 187-223
# Tries bidirectional streaming with httpx.post() - won't work
async def connect(self):
    self.response = await self.client.post(...)  # Blocks until request completes
    # Can't read response here while request is streaming
```

### Auth Handshake (correct flow)
1. Server → Client: MSG_PUBKEY (server's RSA public key)
2. Client → Server: MSG_AUTH (token encrypted with server's pubkey)
3. Client → Server: MSG_PUBKEY (client's RSA public key)
4. Server → Client: MSG_SESSION_KEY (AES key encrypted with client's pubkey)
5. Both: Derive AES-256-GCM key for data encryption

## Next Steps for HTTP/2 Rewrite

### Option 1: Use h2 library directly (recommended)
```python
import h2.connection
import h2.events
# Full control over HTTP/2 frames
# Can do proper bidirectional streaming
```

### Option 2: Finish gRPC (on branch)
- Already has protobuf definitions
- Native bidirectional streaming
- More overhead but proven solution

### Option 3: Different HTTP/2 client
- Not `httpx` - need one supporting concurrent read/write
- `hyper` library? (deprecated)
- Or implement custom with `h2`

## Key Insights
1. CloudFlare HTTP/2 issue might just be nginx config (not tested properly)
2. WebSocket works great - HTTP/2 may not be necessary
3. If HTTP/2 needed: must use library with true bidirectional streaming support
4. Current `httpx` approach is fundamentally incompatible

## Files to Review
- `http2_transport.py` - Delete or rewrite completely
- `protocol.py` - All crypto functions here (not in auth.py or crypto.py)
- `server.py:539` - Protocol switch: `if self.config.protocol=="http2"`
- `client.py:277` - Protocol switch in connect method

## Version Status
- v0.10.2: Released (but HTTP/2 broken)
- WebSocket as default is correct choice
- HTTP/2 marked experimental but doesn't work

## For Next Session
1. Option: Try fixing CloudFlare with WebSocket + proper nginx config first
2. Option: Rewrite HTTP/2 with `h2` library for true bidirectional streaming
3. Option: Finish gRPC implementation (cleaner, more standard)

**Recommendation**: Test WebSocket with CloudFlare properly first. The HTTP 426 error might be solvable with correct nginx config. If not, then invest in proper HTTP/2 with `h2` library.
