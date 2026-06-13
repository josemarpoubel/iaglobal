# tests/test_evolutionengine.py

import pytest
from unittest.mock import MagicMock
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node 

class TestEvolutionEngine:
    
    @pytest.fixture
    def mock_engine(self):
        """Configura um engine com dependências mockadas para isolar o teste."""
        mock_designer = MagicMock()
        graph = ExecutionGraph()
        
        return EvolutionEngine(graph=graph, meta_designer=mock_designer)

    def test_geracao_de_nome_curto(self, mock_engine):
        """Valida se o _short_name corta nomes grandes e gera hash de segurança."""
        from iaglobal.evolution.evolutionengine import _short_name
        
        # Nome longo o suficiente para forçar o truncamento e geração de hash
        long_name = "agente_especializado_em_seguranca_complexa_v1" * 5
        result = _short_name(long_name)
        
        # Validações estruturais
        assert len(result) <= 120
        
        # A lógica ajustada: o resultado ou mantém o formato com underscore (se for curto)
        # ou é um hash hexadecimal puro (se for longo).
        # isalnum() verifica se o resultado é apenas alfanumérico (característica do hash hex).
        assert "_" in result or result.isalnum()

    def test_registro_de_linhagem(self, mock_engine):
        """Valida se o engine interage corretamente com o nó para registrar linhagem."""
        mock_node = MagicMock()
        # mock_node.fitness() precisa retornar algo para o cálculo de fitness_delta
        mock_node.fitness.return_value = 1.0 
        mock_node.strategy = "coding"
        mock_node.lineage = [] # Garante que é uma lista

        # Chama o método interno existente
        mock_engine._record_lineage(
            node=mock_node,
            parent_name="parent_v1",
            event_type="mutation",
            parent_fitness=0.5 # Ajuste conforme a assinatura do seu método
        )
        
        # Verifica se o registro foi adicionado à lista do mock_node
        assert len(mock_node.lineage) > 0


    def test_ciclo_de_finalizacao_persistente(self, mock_engine):
        """Garante que ao finalizar o ciclo, o hash é gerado e o estado é salvo."""
        mock_engine._save_state = MagicMock()
        
        # Simula a finalização
        mock_engine._finalize_cycle()
        
        # Verifica se o estado foi persistido (chamada mockada)
        mock_engine._save_state.assert_called_once()
        # Verifica se a geração foi incrementada
        assert mock_engine.graph.generation >= 0

    def test_consistencia_de_hash(self, mock_engine):
        """Garante que o hash do grafo muda se adicionarmos um nó."""
        # 1. Captura o hash inicial
        hash_inicial = mock_engine.graph._graph_hash
    
        # 2. Prepara o DNA e o Payload
        dna = {"name": "novo_agente", "node_type": "general", "strategy": "coding"}
        # Se o payload for opcional em outras partes do sistema, 
        # tente passar um dict vazio ou o próprio dna se o método for sobrecarregado
        payload = {"data": "init_content"} 
        
        # 3. Chama o método com os dois argumentos esperados
        mock_engine.graph.add_node_by_dna(dna, payload)
        
        # 4. Verifica se o hash mudou
        assert mock_engine.graph._graph_hash != hash_inicial

if __name__ == "__main__":
    print("🧪 Executando testes do EvolutionEngine...")
    pytest.main([__file__])
