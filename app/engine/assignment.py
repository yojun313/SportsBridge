"""수요 집단 → 공급 옵션 배정 (최대유량). 집단은 분할 배정 가능(인원 단위)."""

from __future__ import annotations

from collections import deque


def max_flow_assign(
    groups: list[tuple[str, int]],
    options: list[tuple[str, int | None]],
    edges: set[tuple[str, str]],
) -> tuple[int, dict[tuple[str, str], int]]:
    """groups: [(gid, size)], options: [(oid, capacity or None)], edges: 호환 쌍.
    capacity None(미확인)은 배정 불가로 취급합니다(문서 규칙: 정원 불명 = 확정 배정 제외)."""
    S, T = "S", "T"
    cap: dict[str, dict[str, int]] = {}

    def add(u, v, c):
        cap.setdefault(u, {})[v] = cap.get(u, {}).get(v, 0) + c
        cap.setdefault(v, {}).setdefault(u, 0)

    for gid, size in groups:
        add(S, f"g:{gid}", size)
    for oid, c in options:
        if c is None or c <= 0:
            continue
        add(f"o:{oid}", T, c)
    for gid, oid in edges:
        add(f"g:{gid}", f"o:{oid}", 10**9)
    flow = 0
    while True:
        parent = {S: None}
        q = deque([S])
        while q and T not in parent:
            u = q.popleft()
            for v, c in cap.get(u, {}).items():
                if c > 0 and v not in parent:
                    parent[v] = u
                    q.append(v)
        if T not in parent:
            break
        # bottleneck
        b = 10**18
        v = T
        while parent[v] is not None:
            u = parent[v]
            b = min(b, cap[u][v])
            v = u
        v = T
        while parent[v] is not None:
            u = parent[v]
            cap[u][v] -= b
            cap[v][u] += b
            v = u
        flow += b
    assigned: dict[tuple[str, str], int] = {}
    for gid, _ in groups:
        for oid, _ in options:
            back = cap.get(f"o:{oid}", {}).get(f"g:{gid}", 0)
            if back > 0:
                assigned[(gid, oid)] = back
    return flow, assigned
