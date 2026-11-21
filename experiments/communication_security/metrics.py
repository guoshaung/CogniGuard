"""Post-run propagation metrics. This module never controls admission."""
from experiments.teacher_security.protocol import parse
from experiments.teacher_security.scoring import same_result


def communication_metrics(task, report):
    nodes = report.get("nodes", [])
    edges = report.get("edges", [])
    wrong, unknown = {}, 0
    for node in nodes:
        try:
            result = parse(node.get("text", ""))["result"]
            wrong[node["node"]] = result is not None and not same_result(result, task.expected_result())
        except (ValueError, TypeError):
            wrong[node["node"]] = False
            unknown += node.get("status") == "ok"
    nonroots = [node for node in nodes if node.get("parent_ids")]
    id_map = {node["message_id"]: node for node in nodes if node.get("message_id")}
    def roots(mid, seen=None):
        seen = set() if seen is None else seen
        if mid in seen or mid not in id_map:
            return set()
        seen = seen | {mid}
        parent_ids = id_map[mid].get("parent_ids", [])
        return {mid} if not parent_ids else set().union(*(roots(p, seen) for p in parent_ids))
    sink = next((node for node in nodes if node["node"] == "synthesize"), {})
    sink_parents = sink.get("parent_ids", [])
    root_ids = set().union(*(roots(p) for p in sink_parents)) if sink_parents else set()
    return {
        "contaminated_nonroot_nodes": sum(wrong.get(n["node"], False) for n in nonroots),
        "max_contaminated_hop": max((n.get("hop", 0) for n in nonroots if wrong.get(n["node"], False)), default=0),
        "delivered_wrong_sender_edges": sum(bool(e.get("accepted")) and wrong.get(e["source"], False) for e in edges),
        "invalid_origin_deliveries": sum(bool(e.get("accepted")) and not e.get("origin_valid", False) for e in edges),
        "blocked_communication_edges": sum(not e.get("accepted", False) for e in edges),
        "source_validation_blocks": sum(e.get("content_guard_decision") == "blocked" for e in edges),
        "sink_direct_reports": len(sink_parents), "sink_distinct_root_messages": len(root_ids),
        "correlated_report_excess": max(0, len(sink_parents) - len(root_ids)),
        "real_teacher_nodes": sum(bool(n.get("real_model")) for n in nodes),
        "unknown_node_outputs": unknown,
    }
