# iaglobal/graphs/evolutionmonitor.py

import networkx as nx
import logging

logger = logging.getLogger("EvolutionMonitor")

class EvolutionMonitor:
    def __init__(self):
        self.tree = nx.DiGraph()

    def on_event_recorded(self, node_name: str, entry):
        """Atualiza a árvore de linhagem de forma segura."""
        # Se for um crossover, parent_name pode conter "a x b"
        parents = [p.strip() for p in entry.parent_name.split(" x ")] if entry.parent_name else []
        
        for p in parents:
            self.tree.add_edge(p, node_name, event=entry.event_type)
        
        # Garante que o nó exista no grafo antes de atualizar os atributos
        if not self.tree.has_node(node_name):
            self.tree.add_node(node_name)
            
        # Atualiza atributos do nó
        self.tree.nodes[node_name].update({
            'fitness': entry.fitness_delta,
            'strategy': entry.strategy,
            'gen': entry.generation
        })
        
        logger.debug(f"Monitor: Linhagem registrada para {node_name}")
        print(f"👁️ Monitor: Agente {node_name} evoluiu via {entry.event_type} (Fitness: {entry.fitness_delta:.2f})")

    def get_json_structure(self):
        """Exporta para um formato leve (ideal para dashboards web)."""
        return nx.node_link_data(self.tree)
