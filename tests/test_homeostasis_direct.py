import pytest
from iaglobal.evolution.homeostasis_controller import HomeostasisController

def test_apply_adjustments_is_functional():
    controller = HomeostasisController.get_instance()
    
    # Mock completo seguindo o contrato esperado pelo loop de violações
    mock_sla = {
        "in_compliance": False,
        "violations": [
            {
                "type": "latency", 
                "value": 6000.0, 
                "threshold": 5000.0
            }
        ]
    }
    
    adjustments = controller.apply_adjustments(mock_sla)
    
    assert adjustments["adjusted"] is True
    assert "epsilon_after" in adjustments
    print(f"\nAjustes validados: {adjustments}")