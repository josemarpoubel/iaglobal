"""
Autoimunidade Arquitetural Detector (Passo 120)

Detecta quando o sistema imunológico ataca componentes saudáveis do sistema,
causando degradação desnecessária de performance ou funcionalidade.

Princípio: Assim como doenças autoimunes biológicas, o sistema pode desenvolver
"anticorpos" contra padrões legítimos, causando falsos positivos crônicos.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics


@dataclass
class AutoimmunityMarker:
    """Marca de evento autoimune potencial"""
    component_id: str
    trigger_count: int = 0
    false_positive_count: int = 0
    last_trigger_time: float = 0.0
    sensitivity_level: float = 0.5  # 0.0-1.0
    health_score: float = 1.0  # 1.0 = saudável, 0.0 = comprometido
    pattern_hash: str = ""
    
    def calculate_autoimmunity_risk(self) -> float:
        """Calcula risco de autoimunidade (0.0-1.0)"""
        if self.trigger_count == 0:
            return 0.0
        
        fp_rate = self.false_positive_count / max(self.trigger_count, 1)
        recency_factor = max(0.0, 1.0 - (time.time() - self.last_trigger_time) / 3600)
        
        # Alto risco = muitos falsos positivos + alta sensibilidade + recente
        risk = (fp_rate * 0.5 + self.sensitivity_level * 0.3 + recency_factor * 0.2)
        return min(1.0, risk)


class AutoimmunityDetector:
    """
    Detecta e previne respostas autoimunes do sistema imunológico
    
    Monitora:
    - Trigger rates anormais de circuit breakers
    - Falsos positivos em detectores de patógenos
    - Sensibilidade excessiva em pruning metabólico
    - Apoptose prematura de componentes saudáveis
    """
    
    def __init__(self):
        self.markers: Dict[str, AutoimmunityMarker] = {}
        self.trigger_history: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)  # timestamp, was_false_positive
        self.component_health: Dict[str, float] = {}
        self.autoimmune_events: List[Dict] = []
        
        # Thresholds configuráveis
        self.fp_rate_threshold = 0.3  # 30% de falsos positivos = alerta
        self.trigger_rate_threshold = 10  # triggers/hora = alerta
        self.sensitivity_reduction_step = 0.1
        self.min_sensitivity = 0.1
        self.max_sensitivity = 0.9
        
    def register_component(self, component_id: str, initial_sensitivity: float = 0.5):
        """Registra componente para monitoramento"""
        if component_id not in self.markers:
            self.markers[component_id] = AutoimmunityMarker(
                component_id=component_id,
                sensitivity_level=initial_sensitivity
            )
            self.component_health[component_id] = 1.0
            self.trigger_history[component_id] = []
    
    def record_trigger(self, component_id: str, was_false_positive: bool = False):
        """Registra trigger de detector/circuit breaker"""
        self.register_component(component_id)
        
        marker = self.markers[component_id]
        marker.trigger_count += 1
        marker.last_trigger_time = time.time()
        
        if was_false_positive:
            marker.false_positive_count += 1
        
        # Mantém histórico das últimas 100 ocorrências
        history = self.trigger_history[component_id]
        history.append((time.time(), was_false_positive))
        if len(history) > 100:
            history.pop(0)
        
        # Atualiza saúde do componente
        self._update_component_health(component_id)
        
        # Verifica se precisa ajustar sensibilidade
        self._adjust_sensitivity(component_id)
    
    def _update_component_health(self, component_id: str):
        """Atualiza score de saúde baseado em histórico"""
        history = self.trigger_history[component_id]
        if not history:
            self.component_health[component_id] = 1.0
            return
        
        # Calcula taxa de falsos positivos recente (últimas 20 ocorrências)
        recent = history[-20:] if len(history) >= 20 else history
        fp_rate = sum(1 for _, fp in recent if fp) / len(recent)
        
        # Saúde diminui com falsos positivos
        health = max(0.0, 1.0 - (fp_rate * 1.5))  # Penalidade forte
        self.component_health[component_id] = health
        
        # Atualiza marker
        self.markers[component_id].health_score = health
    
    def _adjust_sensitivity(self, component_id: str):
        """Ajusta automaticamente sensibilidade baseado em falsos positivos"""
        marker = self.markers[component_id]
        risk = marker.calculate_autoimmunity_risk()
        
        if risk > self.fp_rate_threshold:
            # Reduz sensibilidade para diminuir falsos positivos
            marker.sensitivity_level = max(
                self.min_sensitivity,
                marker.sensitivity_level - self.sensitivity_reduction_step
            )
            
            # Registra evento autoimune
            self.autoimmune_events.append({
                'timestamp': time.time(),
                'component': component_id,
                'action': 'SENSITIVITY_REDUCED',
                'old_sensitivity': marker.sensitivity_level + self.sensitivity_reduction_step,
                'new_sensitivity': marker.sensitivity_level,
                'risk_score': risk
            })
    
    def get_autoimmunity_status(self, component_id: str) -> Dict:
        """Retorna status completo de autoimunidade do componente"""
        if component_id not in self.markers:
            return {'status': 'UNKNOWN', 'message': 'Componente não registrado'}
        
        marker = self.markers[component_id]
        risk = marker.calculate_autoimmunity_risk()
        
        status = 'HEALTHY'
        if risk > 0.7:
            status = 'CRITICAL_AUTOIMMUNITY'
        elif risk > 0.4:
            status = 'WARNING_AUTOIMMUNITY'
        elif risk > 0.2:
            status = 'MONITORING'
        
        return {
            'status': status,
            'component': component_id,
            'trigger_count': marker.trigger_count,
            'false_positive_count': marker.false_positive_count,
            'fp_rate': marker.false_positive_count / max(marker.trigger_count, 1),
            'sensitivity': marker.sensitivity_level,
            'health_score': marker.health_score,
            'autoimmunity_risk': risk,
            'last_trigger': marker.last_trigger_time
        }
    
    def should_block_component(self, component_id: str) -> Tuple[bool, str]:
        """
        Decide se componente deve ser bloqueado temporariamente
        
        Retorna: (should_block, reason)
        """
        if component_id not in self.markers:
            return False, ""
        
        marker = self.markers[component_id]
        risk = marker.calculate_autoimmunity_risk()
        
        # Bloqueia se risco crítico E saúde muito baixa
        if risk > 0.8 and marker.health_score < 0.3:
            return True, f"Autoimunidade crítica (risco={risk:.2f}, saúde={marker.health_score:.2f})"
        
        # Bloqueia se muitos falsos positivos consecutivos
        history = self.trigger_history[component_id]
        if len(history) >= 10:
            recent_fps = sum(1 for _, fp in history[-10:] if fp)
            if recent_fps >= 8:  # 80% de falsos positivos
                return True, f"Falsos positivos consecutivos ({recent_fps}/10)"
        
        return False, ""
    
    def reset_component(self, component_id: str):
        """Reseta marcador de componente (após intervenção manual)"""
        if component_id in self.markers:
            marker = self.markers[component_id]
            marker.trigger_count = 0
            marker.false_positive_count = 0
            marker.sensitivity_level = 0.5  # Reset para padrão
            marker.health_score = 1.0
            self.trigger_history[component_id] = []
            
            self.autoimmune_events.append({
                'timestamp': time.time(),
                'component': component_id,
                'action': 'MANUAL_RESET'
            })
    
    def get_system_autoimmunity_report(self) -> Dict:
        """Relatório geral de autoimunidade do sistema"""
        if not self.markers:
            return {'status': 'NO_DATA', 'components': []}
        
        critical_components = []
        warning_components = []
        healthy_components = []
        
        for component_id in self.markers:
            status = self.get_autoimmunity_status(component_id)
            if status['status'] == 'CRITICAL_AUTOIMMUNITY':
                critical_components.append(status)
            elif status['status'] == 'WARNING_AUTOIMMUNITY':
                warning_components.append(status)
            else:
                healthy_components.append(status)
        
        avg_health = statistics.mean([m.health_score for m in self.markers.values()]) if self.markers else 1.0
        avg_risk = statistics.mean([m.calculate_autoimmunity_risk() for m in self.markers.values()]) if self.markers else 0.0
        
        return {
            'status': 'CRITICAL' if critical_components else ('WARNING' if warning_components else 'HEALTHY'),
            'total_components': len(self.markers),
            'critical_count': len(critical_components),
            'warning_count': len(warning_components),
            'healthy_count': len(healthy_components),
            'average_health': avg_health,
            'average_risk': avg_risk,
            'critical_components': critical_components,
            'warning_components': warning_components,
            'recent_events': self.autoimmune_events[-20:]
        }
    
    def integrate_with_immune_orchestrator(self, orchestrator) -> None:
        """
        Integra com ImmuneOrchestrator para ajuste dinâmico
        
        Aplica fatores de supressão em detectores com autoimunidade
        """
        report = self.get_system_autoimmunity_report()
        
        for component_status in report.get('critical_components', []) + report.get('warning_components', []):
            component_id = component_status['component']
            risk = component_status['autoimmunity_risk']
            
            # Aplica supressão proporcional ao risco
            suppression_factor = 1.0 - (risk * 0.5)  # Até 50% de supressão
            
            # Notifica orchestrator para ajustar thresholds
            if hasattr(orchestrator, 'adjust_detector_sensitivity'):
                orchestrator.adjust_detector_sensitivity(component_id, suppression_factor)


# Singleton global
_autoimmunity_detector: Optional[AutoimmunityDetector] = None

def get_autoimmunity_detector() -> AutoimmunityDetector:
    """Singleton getter"""
    global _autoimmunity_detector
    if _autoimmunity_detector is None:
        _autoimmunity_detector = AutoimmunityDetector()
    return _autoimmunity_detector


if __name__ == "__main__":
    print("=== Teste Autoimmunidade Arquitetural ===\n")
    
    detector = get_autoimmunity_detector()
    
    # Simula componente saudável
    print("1. Componente saudável (poucos triggers, sem FPs):")
    for i in range(5):
        detector.record_trigger("loop_detector", was_false_positive=False)
    status = detector.get_autoimmunity_status("loop_detector")
    print(f"   Status: {status['status']}, Saúde: {status['health_score']:.2f}, Risco: {status['autoimmunity_risk']:.2f}")
    
    # Simula componente com autoimunidade
    print("\n2. Componente com autoimunidade (muitos FPs):")
    for i in range(15):
        detector.record_trigger("apoptosis_engine", was_false_positive=(i < 12))  # 80% FPs
    status = detector.get_autoimmunity_status("apoptosis_engine")
    print(f"   Status: {status['status']}")
    print(f"   Saúde: {status['health_score']:.2f}")
    print(f"   Risco: {status['autoimmunity_risk']:.2f}")
    print(f"   Sensibilidade ajustada: {status['sensitivity']:.2f}")
    
    should_block, reason = detector.should_block_component("apoptosis_engine")
    print(f"   Bloquear? {should_block} - {reason}")
    
    # Relatório do sistema
    print("\n3. Relatório do Sistema:")
    report = detector.get_system_autoimmunity_report()
    print(f"   Status: {report['status']}")
    print(f"   Componentes: {report['total_components']}")
    print(f"   Críticos: {report['critical_count']}")
    print(f"   Alertas: {report['warning_count']}")
    print(f"   Saúde média: {report['average_health']:.2f}")
    print(f"   Risco médio: {report['average_risk']:.2f}")
    
    # Testa reset
    print("\n4. Reset manual do componente problemático:")
    detector.reset_component("apoptosis_engine")
    status = detector.get_autoimmunity_status("apoptosis_engine")
    print(f"   Status após reset: {status['status']}")
    print(f"   Saúde: {status['health_score']:.2f}")
    print(f"   Sensibilidade: {status['sensitivity']:.2f}")
    
    print("\n✅ Teste Autoimmunidade concluído!")
