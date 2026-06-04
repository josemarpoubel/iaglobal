# iaglobal/graphs/policy.py

def compute_node_policy(node):
    """
    🧠 Decide evolução do node
    """

    score = node.success_rate()
    latency = node.avg_latency()

    # caso ruim → simplifica
    if score < 0.4:
        return {
            "strategy": "safe",
            "model_hint": "nvidia/meta/llama-3.3-70b-instruct"
        }

    # caso bom → acelera
    if score > 0.8 and latency < 2.0:
        return {
            "strategy": "fast",
            "model_hint": node.model_hint
        }

    # caso neutro → mantém
    return None
