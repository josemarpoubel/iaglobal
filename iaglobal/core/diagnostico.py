# iaglobal/core/diagnostico.py

import sys

class AnalisadorRotas:
    @staticmethod
    def diagnosticar(provedor: str, modelo: str, erro: Exception) -> dict:
        """
        Analisa a exceção capturada e gera um relatório de Causa Raiz (RCA).
        """
        erro_str = str(erro).lower()
        causa = "Causa desconhecida"
        acao = "Contatar suporte do framework"
        status_code = "Desconhecido"

        # 1. Identificação de Estouro de Cota (HTTP 429 / Rate Limit)
        if "429" in erro_str or "quotaed" in erro_str or "exceeded" in erro_str or "rate_limit" in erro_str:
            status_code = "HTTP 429 (Too Many Requests)"
            causa = f"A rota do provedor '{provedor}' atingiu o teto máximo de requisições permitidas no plano gratuito."
            acao = "Rotacionar imediatamente para um provedor alternativo ou aguardar a janela de tempo (Retry-After) expirar."
            
        # 2. Identificação de Chave de API Inválida (HTTP 401 / Autenticação)
        elif "401" in erro_str or "invalid" in erro_str or "unauthorized" in erro_str or "api key" in erro_str:
            status_code = "HTTP 401 (Unauthorized)"
            causa = f"A chave de API configurada no seu arquivo .env para o provedor '{provedor}' é inválida ou expirou."
            acao = "Verifique o seu arquivo .env na raiz do projeto e certifique-se de que colou a chave correta sem espaços."

        # 3. Identificação de Erro de Modelo Inexistente (HTTP 404 / Not Found)
        elif "404" in erro_str or "not found" in erro_str or "unknown model" in erro_str:
            status_code = "HTTP 404 (Not Found)"
            causa = f"O modelo '{modelo}' não foi localizado no catálogo oficial do provedor '{provedor}'."
            acao = "Corrija o mapeamento de strings dentro do arquivo 'iaglobal/core/router.py'. Remova espaços invisíveis."

        # 4. Identificação de Timeout ou Rede Offline
        elif "timeout" in erro_str or "connection timed out" in erro_str or "read timeout" in erro_str:
            status_code = "Network Timeout"
            causa = "A requisição demorou mais de 120 segundos para responder, indicando sobrecarga ou falta de internet."
            acao = "Se for local (Ollama), certifique-se de que a RAM está limpa. Se for nuvem, verifique a conexão de rede."

        # Monta o relatório estruturado de RCA
        relatorio = {
            "PROVEDOR_AFETADO": provedor.upper(),
            "MODELO_ALVO": modelo,
            "CLASSIFICACAO": status_code,
            "DIAGNOSTICO_RCA": causa,
            "PROXIMO_PASSO": acao
        }

        # Imprime um painel visual explicativo no console para o desenvolvedor
        print("\n" + "🚨" + "="*58)
        print(f" PANEL DE DIAGNÓSTICO DE FALHA EM ROTA (RCA)")
        print("="*60)
        for chave, valor in relatorio.items():
            print(f"👉 {chave:<18}: {valor}")
        print("="*60 + "\n")

        return relatorio

