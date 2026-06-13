import pytest
import tempfile
from pathlib import Path

from iaglobal.evolution.meta_evolver import MetaEvolver, EvolutionParams, MetaTrial


class TestMetaEvolver:

    def _make_isolated(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        return MetaEvolver(path=Path(tmp.name)), Path(tmp.name)

    def test_default_params(self):
        m, _ = self._make_isolated()
        assert m.current_params.mutation_rate == 0.1
        assert m.current_params.crossover_rate == 0.3

    def test_record_trial_increases_count(self):
        m, path = self._make_isolated()
        try:
            count_before = len(m.trials)
            m.record_trial(EvolutionParams(), 20)
            assert len(m.trials) == count_before + 1
        finally:
            path.unlink(missing_ok=True)

    def test_improvement_calculated(self):
        m, path = self._make_isolated()
        try:
            m.record_trial(EvolutionParams(), 30)
            assert m.trials[-1].improvement == 30
        finally:
            path.unlink(missing_ok=True)

    def test_best_improvement_tracked(self):
        m, path = self._make_isolated()
        try:
            m.record_trial(EvolutionParams(), 10)
            m.record_trial(EvolutionParams(), 40)
            assert m._best_improvement == 40
        finally:
            path.unlink(missing_ok=True)

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            m1 = MetaEvolver(path=path)
            m1.record_trial(EvolutionParams(), 40)
            m2 = MetaEvolver(path=path)
            assert len(m2.trials) >= 1
            assert m2.trials[-1].improvement == 40
        finally:
            path.unlink(missing_ok=True)

    def test_params_adjust_on_negative_improvement(self):
        m, path = self._make_isolated()
        try:
            m.current_params.mutation_rate = 0.1
            for _ in range(4):
                m.record_trial(EvolutionParams(), -10)
            assert m.current_params.mutation_rate < 0.1  # algoritmo reduz mutação em estagnação
        finally:
            path.unlink(missing_ok=True)

    def test_get_stats_structure(self):
        m, path = self._make_isolated()
        try:
            stats = m.get_stats()
            assert "current_params" in stats
            assert "trials_count" in stats
            assert "avg_improvement" in stats
        finally:
            path.unlink(missing_ok=True)

    def test_evolution_params_roundtrip(self):
        p1 = EvolutionParams(mutation_rate=0.25, crossover_rate=0.5)
        d = p1.to_dict()
        p2 = EvolutionParams.from_dict(d)
        assert p1.mutation_rate == p2.mutation_rate
        assert p1.crossover_rate == p2.crossover_rate
