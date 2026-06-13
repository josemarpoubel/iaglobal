# training/auto_trainer.py

import subprocess
import tempfile
import os
import re
import torch
from pathlib import Path
from typing import Tuple, Optional
# Imports internos ajustados para respeitar o mapeamento de pacotes da lib
from iaglobal.core.assistant import executar
from iaglobal.utils.logger import logger

MAX_ITERS = 5

def executar_codigo(codigo: str) -> Tuple[int, str, str]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as f:
        f.write(codigo.encode('utf-8'))
        path = f.name

    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def extrair_codigo(texto: str) -> str:
    match = re.search(r"```python(.*?)```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    return texto.strip()

def disparar_fine_tuning_local(prompt_treino: str, resposta_perfeita: str):
    """
    Motor de Treinamento preparado para GPU.
    Ajusta os pesos neurais do modelo local de forma permanente usando LoRA.
    """
    # DETECÇÃO AUTOMÁTICA DE HARDWARE
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"⚙️ [AUTO TRAINER]: Inicializando motor de pesos. Hardware ativo: {device.upper()}")

    try:
        # Importações lazy-loading para não quebrar o sistema caso a venv atual não tenha instalado
        from iaglobal._paths import DATA_ROOT
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import SFTTrainer
        from peft import LoraConfig, get_peft_model
        
        modelo_base = "sentence-transformers/all-MiniLM-L6-v2" # Substitua pelo path do seu modelo de código se necessário
        models_dir = str(DATA_ROOT / "models" / "pesos_ajustados")
        
        tokenizer = AutoTokenizer.from_pretrained(modelo_base)
        # Configuração para evitar estouro de memória VRAM (carrega em 8-bits se for GPU)
        model = AutoModelForCausalLM.from_pretrained(
            modelo_base,
            device_map="auto" if device == "cuda" else None,
            load_in_8bit=True if device == "cuda" else False
        )

        # CONFIGURAÇÃO LORA (Ajuste fino de baixo escalonamento para economizar VRAM)
        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"], # Padrão para arquiteturas baseadas em Llama/Mistral
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )
        
        # Cria a estrutura de par estruturado (Prompt -> Resposta) que o modelo precisa internalizar
        dados_treino = [{"text": f"### Instrução:\n{prompt_treino}\n\n### Resposta Perfeita:\n{resposta_perfeita}"}]
        
        training_args = TrainingArguments(
            output_dir=models_dir,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            logging_steps=1,
            max_steps=10 if device == "cpu" else 100, # Treino curto se for CPU apenas para validar sintaxe
            fp16=True if device == "cuda" else False
        )

        trainer = SFTTrainer(
            model=model,
            train_dataset=dados_treino,
            peft_config=peft_config,
            dataset_text_field="text",
            args=training_args,
            max_seq_length=512
        )
        
        logger.info("🏋️ [AUTO TRAINER]: Iniciando otimização dos tensores e retropropagação...")
        trainer.train()
        trainer.model.save_pretrained(models_dir)
        logger.info("✅ [AUTO TRAINER]: O modelo aprendeu o comportamento de forma nativa e permanente!")

    except ImportError:
        logger.warning("⚠️ [AUTO TRAINER SIMULADO]: Módulos 'transformers/peft' não localizados na venv. Pulando treino real.")
    except Exception as e:
        logger.error(f"❌ Falha crítica no ciclo de backpropagation: {e}")

def auto_train(task: str) -> Tuple[Optional[str], str]:
    modelo = escolher_modelo(task)
    prompt = f"Você é um engenheiro Python.\n\nResolva o problema abaixo gerando APENAS código executável:\n\nPROBLEMA:\n{task}\n"

    codigo_cru = executar(modelo, prompt)
    code = extrair_codigo(codigo_cru)

    for i in range(MAX_ITERS):
        status, out, err = executar_codigo(code)

        if status == 0:
            logger.info(f"✔ Código validado com sucesso na iteração {i+1}. Acionando aprendizado de máquina...")
            # >>> CONEXÃO COM O MOTOR DE TREINO
            # Se o código deu certo, enviamos a tarefa e a resposta perfeita para fixar nos pesos neurais
            disparar_fine_tuning_local(prompt_treino=task, resposta_perfeita=code)
            return code, out

        fix_prompt = f"O código falhou.\n\nERRO:\n{err}\n\nCÓDIGO:\n{code}\n\nCorrija e devolva apenas o código completo funcionando.\n"
        codigo_cru = executar(modelo, fix_prompt)
        code = extrair_codigo(codigo_cru)

    # Registro de erro se esgotar as tentativas (Movido para fora do unreachable code antigo)
    try:
        from iaglobal.memory.memory_error import store_error
        store_error(
            prompt=task,
            response=code,
            critique=err if 'err' in locals() else "Timeout/Erro Desconhecido",
            corrected="failed-all-iters"
        )
    except Exception:
        pass

    return None, "falhou após tentativas"

