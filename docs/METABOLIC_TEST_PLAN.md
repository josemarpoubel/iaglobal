# 🧬 Teste de Stress Metabólico — Apoptose com Critic

**Data:** 2026-07-13  
**Objetivo:** Validar ciclo completo de evolução e purificação de skills.

---

## 🎯 Cenários de Teste

### **Cenário 1: Skill Saudável (OAuth 2.1)**
- **Input:** "Como implementar autenticação OAuth 2.1 em Next.js 2026?"
- **Esperado:** 
  - ✅ Busca web ativada (SearXNG)
  - ✅ Skill criada com critic_score > 0.7
  - ✅ Skill mantida após apoptose

### **Cenário 2: Skill Patogênica (Hardcoded Credentials)**
- **Input:** "Como usar credenciais hardcoded em variáveis de ambiente?"
- **Esperado:**
  - ✅ Busca web ativada (pode retornar padrões ruins)
  - ✅ Skill criada com critic_score < 0.4
  - ✅ Skill classificada como **PATOGÊNICA**
  - ✅ Skill removida na apoptose

### **Cenário 3: Skill Zumbi (Padrão Obsoleto)**
- **Input:** (Skill artificial antiga, sem uso)
- **Esperado:**
  - ✅ Skill classificada como **ZUMBI**
  - ✅ Skill removida na apoptose

---

## 🧪 Comandos de Execução

```bash
# Teste completo
python -m pytest iaglobal/tests/test_metabolic_apoptosis.py -v

# Teste específico (Skill Saudável)
python -m pytest iaglobal/tests/test_metabolic_apoptosis.py::test_healthy_skill_oauth -v

# Teste específico (Skill Patogênica)
python -m pytest iaglobal/tests/test_metabolic_apoptosis.py::test_pathogenic_skill_hardcoded_credentials -v

# Teste específico (Apoptose de Zumbi)
python -m pytest iaglobal/tests/test_metabolic_apoptosis.py::test_zombie_skill_apoptosis -v
```

---

## 📊 Métricas Validadas

| Métrica | Esperado | Validação |
|---------|----------|-----------|
| **Busca Web** | SearXNG ativado | Logs mostram `source=searxng` |
| **Criação de Skill** | CandidateSkill no pool | `homocysteine_pool.count()` > 0 |
| **Critic Score** | 0.0 a 1.0 | `_evaluate_with_critic()` retorna float |
| **Health Score** | 0.0 a 1.0 | Fórmula: (age×0.2 + reuse×0.3 + success×0.2 + critic×0.3) |
| **Classificação** | Patogênica/Zumbi/Saudável | `is_pathogenic`, `is_zombie` flags |
| **Apoptose** | Skills ruins removidas | `pruned` > 0 se houver patógenos/zumbis |
| **Health Improvement** | > 0% após apoptose | `(pruned/evaluated) × 100` |

---

## 🔍 Critérios de Aceite

### **Skill Saudável (OAuth)**
- [ ] `critic_score >= 0.7`
- [ ] `health_score >= 0.6`
- [ ] `is_pathogenic = False`
- [ ] `is_zombie = False`
- [ ] **Mantida** após apoptose

### **Skill Patogênica (Hardcoded Credentials)**
- [ ] `critic_score < 0.4`
- [ ] `health_score < 0.3`
- [ ] `is_pathogenic = True`
- [ ] **Removida** na apoptose
- [ ] Log: `🦠 [Apoptosis] Skill PATOGÊNICA removida`

### **Skill Zumbi (Obsoleto)**
- [ ] `age_days > 7`
- [ ] `reuse_count < 2`
- [ ] `is_zombie = True`
- [ ] **Removida** na apoptose
- [ ] Log: `🧟 [Apoptosis] Skill ZUMBI removida`

---

## 🧬 Estrutura do Teste

```python
async def test_metabolic_apoptosis_full_cycle():
    # 1. Gênese do agente
    agent = await EvoAgent.genesis('metabolic-test')
    
    # 2. Cenário 1: Skill Saudável
    result1 = await agent.handle('OAuth 2.1 Next.js 2026')
    assert result1.cycles_activated['metilacao'] == True
    
    # 3. Cenário 2: Skill Patogênica (simulada)
    skill_bad = create_candidate_skill(
        name='bad_hardcoded_creds',
        code='PASSWORD = "admin123"',  # Código ruim proposital
        critic_score=0.25  # Simula nota baixa
    )
    homocysteine_pool.add(skill_bad)
    
    # 4. Cenário 3: Skill Zumbi (simulada)
    skill_old = create_candidate_skill(
        name='old_unused_pattern',
        age_days=15,
        reuse_count=0
    )
    homocysteine_pool.add(skill_old)
    
    # 5. Executar apoptose
    apoptosis_result = await agent.run_memory_apoptosis()
    
    # 6. Validações
    assert apoptosis_result['pruned'] >= 2  # Pelo menos 2 ruins removidas
    assert any(s['is_pathogenic'] for s in apoptosis_result['apoptosed_skills'])
    assert any(s['is_zombie'] for s in apoptosis_result['apoptosed_skills'])
    
    # 7. Cleanup
    await agent.apoptose('test')
```

---

## 📝 Logs Esperados

```
🧬 [evo-metabolic-tester] [Metabolismo] Buscando nutrientes externos...
✅ [evo-metabolic-tester] Nutrição externa completa | source=searxng | impact=True
[evo-metabolic-tester] Metilação com contexto web | query=OAuth 2.1... | results=8
[evo-metabolic-tester] Skill evoluída criada: web_oauth_pkce_nextjs | 8 padrões
[evo-metabolic-tester] Sistema vacinado com padrão web

🧬 [Apoptosis] Iniciando avaliação de qualidade metabólica...
🦠 [Apoptosis] Skill PATOGÊNICA removida: bad_hardcoded_creds | critic=0.25
🧟 [Apoptosis] Skill ZUMBI removida: old_unused_pattern | age=15.0d
✅ [Apoptosis] Avaliação completa | evaluated=3 | pruned=2 | saved=1 | improvement=66.7%

✅ METABOLIC STRESS TEST COMPLETE
```

---

## ✅ Validação Final

**O teste prova que:**
1. ✅ iaglobal **aprende** com busca web (SearXNG)
2. ✅ iaglobal **avalia** qualidade com CriticAgent
3. ✅ iaglobal **elimina** skills ruins (Apoptose)
4. ✅ iaglobal **mantém** skills boas (Homeostase)

**Resultado:** Organismo mais saudável após cada ciclo de apoptose!