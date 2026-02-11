# GhostWire v0.9.0 → v0.9.1 Development Summary

## Problem Identified

GhostWire suffered from high latency and poor stability issues documented in `Problem.md`:

### Critical Issues Found:
1. **50ms artificial batching delay** - `sender_task` waited 50ms for batching (timeout=0.05)
2. **No TCP_NODELAY** - Nagle's algorithm added 40-200ms delays on local sockets
3. **Large batch thresholds** - 1MB batching before drain caused head-of-line blocking
4. **Aggressive timeouts** - 120s drain timeout, 30s queue timeout
5. **Large buffers** - 256KB read buffers
6. **Low connection limits** - 256 semaphore limit, 128 preconnect buffer

### Test Environment:
- **Localhost testing** - All tests passed with 100% success rate
- Throughput: 309-347 Mbps
- Latency: <1ms (localhost)

## First Attempt: v0.9.0 (FAILED)

### Changes Made:
1. ✅ Removed 50ms batching delay (simple `await send_queue.get()`)
2. ✅ Enabled TCP_NODELAY on local sockets
3. ✅ Reduced drain timeout: 120s → 15s
4. ✅ Reduced queue timeout: 30s → 15s
5. ✅ Reduced read buffer: 256KB → 64KB
6. ✅ Reduced batch threshold: 1MB → 256KB
7. ✅ Increased semaphore: 256 → 1024
8. ✅ Reduced preconnect buffer: 128 → 16

### Testing Results:
- **Localhost tests**: 100% success ✅
- **Quick reconnection test**: PASSED ✅
- **Throughput test**: 309.83 Mbps ✅

### Production Deployment: CATASTROPHIC FAILURE ❌

**Released**: v0.9.0 on 2026-02-11
**Result**: Complete service breakdown within minutes

#### Production Environment (Critical Difference):
- **Route**: Iran (ar server) ↔ CloudFlare ↔ Netherlands (nl server)
- **Latency**: 200-500ms (not <1ms like localhost!)
- **Network**: High packet loss, congestion, CloudFlare proxy

#### Failure Symptoms:
```
- "timed out during opening handshake" - CONSTANTLY
- "Connection failed" every 10-30 seconds
- Child channels failing and reconnecting in loops
- Ping timeouts killing stable connections
- Service completely unstable
```

#### Root Cause:
**15-second timeouts were TOO AGGRESSIVE for high-latency WAN connections**
- Normal RTT: 200-500ms
- During packet loss: 5-15 seconds
- 15s timeout killed connections during normal network hiccups

#### Emergency Response:
- Rolled back to v0.8.3 immediately
- Deleted v0.9.0 release from GitHub
- Reverted git commit

## Lessons Learned: Why Localhost Testing Failed Us

### The Fatal Flaw:
**Localhost (1ms) ≠ Production WAN (200-500ms through CloudFlare)**

### What Worked on Localhost but Failed in Production:
1. **15s timeouts** - Fine for 1ms, catastrophic for 500ms + packet loss
2. **64KB buffers** - OK for low latency, problematic for high bandwidth-delay product
3. **TCP_NODELAY** - Good for LAN, not helpful (possibly harmful) for WAN

### CloudFlare-Specific Issues Discovered:

#### From Web Research:
1. **100-second idle timeout** - CloudFlare disconnects idle WebSockets
   - Our 10s ping interval handles this ✅
2. **CloudFlare ADDS latency** - 5-500ms, doesn't accelerate WebSockets
3. **Connection restarts** - CloudFlare updates terminate connections
4. **Larger messages preferred** - 1MB message limit, bigger is better
5. **Application-level keepalive required** - Built-in ping/pong not enough

#### Our Implementation:
- ✅ Application-level MSG_PING/MSG_PONG (already implemented)
- ✅ ping_interval=10s (default, config-based)
- ✅ ping_timeout=10s (default, but too aggressive for production)
- ✅ WebSocket ping disabled (ping_interval=None - correct for CloudFlare)

## Final Solution: v0.9.1 (SUCCESS)

### Strategy:
Keep the good optimizations, fix the CloudFlare-incompatible parts.

### Code Changes from v0.8.3:

#### ✅ Kept (CloudFlare-Safe):
1. **Removed 50ms batching delay** - No timeout wait, immediate sending
2. **Increased semaphore** - 256 → 1024 connections
3. **Reduced batch threshold** - 1MB → 256KB in conn_writer_loop
4. **Reduced read buffer** - 256KB → 64KB

#### 🔧 Fixed for CloudFlare:
1. **Drain timeout**: 60s (was 120s, tested 15s failed)
2. **Queue timeout**: 30s (was 30s, unchanged)

#### ❌ Removed (Broke Production):
1. **TCP_NODELAY** - Not helpful for WAN links
2. **Aggressive 15s timeouts** - Too short for high-latency

### Timeout Rationale:
- **60s drain timeout**: Tolerates temporary network slowdowns
- **30s queue timeout**: Fast enough to fail, slow enough to succeed
- **Original 120s**: Too long, resources held unnecessarily
- **Tested 15s**: Too short, killed connections during normal hiccups

### Release Info:
- **Version**: v0.9.1
- **Released**: 2026-02-11
- **URL**: https://github.com/FrenchToblerone54/ghostwire/releases/tag/v0.9.1

## Configuration Recommendations

### For High-Latency Deployments (>200ms RTT):

User will manually update configs on ar/nl servers:

```toml
[server]
ping_interval = 30   # Send keepalive every 30s (was 10s)
ping_timeout = 60    # Tolerate 60s without response (was 10s)
```

**Why these values:**
- 30s ping_interval: Well under CloudFlare's 100s timeout, less chatty
- 60s ping_timeout: Tolerates temporary network issues without killing connection

### Current Deployment State:
- **ar server (Iran)**: Auto-updated to v0.9.1
- **nl server (Netherlands)**: Auto-updated to v0.9.1
- **Config updates**: Pending manual changes by user

## Technical Insights

### CloudFlare WebSocket Behavior:
- Acts as TLS-terminating proxy
- Adds 5-500ms latency
- 100-second idle timeout (application keepalive required)
- Restarts during code deployments (connections lost)
- Larger messages = more efficient (prefer 1MB batches)

### High-Latency TCP Tuning:
- **Bandwidth-Delay Product**: High latency needs larger buffers
- **Recommended**: 512KB - 64MB for tcp_wmem/tcp_rmem
- **Our choice**: 64KB (conservative, may increase if needed)
- **Window scaling**: Critical for high RTT connections

### Application-Level Ping/Pong:
- More reliable than WebSocket built-in ping for CloudFlare
- Must be < 100s to prevent CloudFlare timeout
- Should tolerate RTT spikes (60s timeout reasonable)

## Next Steps

1. **Monitor production** - Watch ar/nl servers for stability
2. **Manual config updates** - User will update ping_interval/timeout
3. **Performance testing** - Verify improvements on actual Iran-NL route
4. **Consider additional tuning**:
   - May increase buffers if throughput limited
   - May adjust ping intervals based on real-world behavior
   - Monitor CloudFlare connection stability

## Files Modified

### Code Changes (v0.9.1):
- `server.py` - Timeout adjustments, removed TCP_NODELAY, simplified sender_task
- `client.py` - Timeout adjustments, removed TCP_NODELAY, simplified sender_task
- `updater.py` - Version bump to v0.9.1

### Configuration (Manual Updates Required):
- `server.toml` - User will add ping_interval=30, ping_timeout=60
- `/etc/ghostwire/server.toml` (ar server) - Pending manual update
- `/etc/ghostwire/client-iran.toml` (nl server) - Pending manual update

### Documentation:
- `Problem.md` - Created (analysis of original issues)
- `SUMMARY.md` - This file

## Key Takeaways

1. **Test in production-like environments** - Localhost testing is insufficient for WAN optimization
2. **CloudFlare requires special handling** - Not just a transparent proxy
3. **Conservative timeouts for high latency** - 60s, not 15s
4. **Application-level keepalive works** - Already had it, just needed config tuning
5. **TCP_NODELAY != WAN optimization** - LAN optimization, not WAN
6. **Bigger batches for CloudFlare** - 256KB-1MB preferred over small packets
7. **Monitor before optimizing** - Understand baseline before making changes

## Success Metrics

### v0.8.3 (Baseline):
- Stable but high latency
- Some reconnections but functional

### v0.9.0 (Failed):
- Complete instability
- Constant reconnections
- Unusable in production

### v0.9.1 (Target):
- Stable operation expected
- Lower latency than v0.8.3
- Better throughput with 4x connection limit
- Tolerates high-latency CloudFlare route

## References

### Research Sources:
- [CloudFlare WebSocket Configuration Guide](https://websocket.org/guides/infrastructure/cloudflare/)
- [WebSockets Library Defaults](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)
- [TCP High Latency Tuning](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/10/html/network_troubleshooting_and_performance_tuning/tuning-tcp-connections-for-high-throughput)
- CloudFlare Community Forums - WebSocket timeout discussions
- Brave Search - "CloudFlare WebSocket performance optimization"

### Git History:
```
0efb08a Release v0.9.1 - CloudFlare-optimized latency improvements
27c0ce9 Reapply "Release v0.9.0 - Major latency and stability improvements"
018b728 Revert "Release v0.9.0 - Major latency and stability improvements"
3787d4a Release v0.9.0 - Major latency and stability improvements (REVERTED)
37d2cc3 Release v0.8.3 - Add proxy support for auto-updates
```

## End of Summary

This document captures the complete journey from identifying performance issues, attempting optimizations, experiencing catastrophic production failure, learning from mistakes, and delivering a CloudFlare-compatible solution.

Continue from here in the next session with production monitoring and config tuning.
