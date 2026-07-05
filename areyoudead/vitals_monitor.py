#!/usr/bin/env python3
"""Live monitor for RuView feature-state packets (0xC5110006, 60 B, ~5 Hz).

Usage: python3 vitals_monitor.py [seconds]
Prints one summary line per node per second.
"""
import socket, struct, sys, time

FEAT_MAGIC = 0xC5110006
FMT = "<IBBHQ9fHHI"  # magic,node,mode,seq,ts_us,9 floats,qflags,resv,crc

QF_CAL = 1 << 6
QF_PRES_VALID = 1 << 0
QF_RESP_VALID = 1 << 1
QF_DEGRADED = 1 << 5

duration = float(sys.argv[1]) if len(sys.argv) > 1 else 15
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))
sock.settimeout(0.5)

nodes = {}
counts = {}
end = time.time() + duration
last_print = 0.0

while time.time() < end:
    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        data = None
    if data and len(data) == 60:
        f = struct.unpack(FMT, data)
        if f[0] == FEAT_MAGIC:
            (m, node, mode, seq, ts, motion, presence, resp, resp_c,
             hb, hb_c, anom, env, coher, qf, _r, _crc) = f
            nodes[node] = (motion, presence, resp, resp_c, hb, hb_c, anom, qf)
            counts[node] = counts.get(node, 0) + 1
    now = time.time()
    if now - last_print >= 1.0 and nodes:
        last_print = now
        for node in sorted(nodes):
            motion, presence, resp, resp_c, hb, hb_c, anom, qf = nodes[node]
            state = "CALIBRATING" if qf & QF_CAL else (
                "degraded" if qf & QF_DEGRADED else "ok")
            print(f"t={duration-(end-now):3.0f}s n{node} [{state:11s}] "
                  f"presence={presence:5.2f} motion={motion:5.2f} "
                  f"breath={resp:5.1f}bpm(c{resp_c:.2f}) "
                  f"heart={hb:5.1f}bpm(c{hb_c:.2f}) anomaly={anom:4.2f}",
                  flush=True)

print("---")
for node in sorted(counts):
    print(f"node {node}: {counts[node]} packets in {duration:.0f}s")
