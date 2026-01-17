"""Tests for WorkingMemoryGraph - ported from deprecated repo."""
import pytest
from src.personal_assistant.working_memory import WorkingMemoryGraph


def test_link_creates_edge_with_seed_weight():
    wm = WorkingMemoryGraph(reinforce_delta=2.0, max_weight=10.0)
    weight = wm.link("a", "b", seed_weight=1.0)
    assert weight == 1.0
    assert wm.get_weight("a", "b") == 1.0


def test_link_reinforces_existing_edge():
    wm = WorkingMemoryGraph(reinforce_delta=2.0, max_weight=10.0)
    wm.link("a", "b", seed_weight=1.0)
    weight = wm.link("a", "b")  # Reinforce
    assert weight == 3.0  # 1.0 + 2.0


def test_link_respects_max_weight():
    wm = WorkingMemoryGraph(reinforce_delta=5.0, max_weight=3.0)
    wm.link("a", "b", seed_weight=1.0)
    weight = wm.link("a", "b")  # Would be 6.0 without cap
    assert weight == 3.0


def test_access_reinforces_edge():
    wm = WorkingMemoryGraph(reinforce_delta=1.0, max_weight=100.0)
    wm.link("a", "b", seed_weight=5.0)
    weight = wm.access("a", "b")
    assert weight == 6.0


def test_access_returns_none_for_missing_edge():
    wm = WorkingMemoryGraph()
    assert wm.access("missing", "edge") is None


def test_get_weight_no_side_effects():
    wm = WorkingMemoryGraph(reinforce_delta=1.0)
    wm.link("a", "b", seed_weight=5.0)
    assert wm.get_weight("a", "b") == 5.0
    assert wm.get_weight("a", "b") == 5.0  # Still 5.0, no reinforcement


def test_get_activation_boost():
    wm = WorkingMemoryGraph()
    wm.link("x", "target", seed_weight=3.0)
    wm.link("y", "target", seed_weight=2.0)
    assert wm.get_activation_boost("target") == 5.0


def test_get_activation_boost_missing_node():
    wm = WorkingMemoryGraph()
    assert wm.get_activation_boost("nonexistent") == 0.0
    assert wm.get_activation_boost("nonexistent", default=1.5) == 1.5


def test_decay_all():
    wm = WorkingMemoryGraph()
    wm.link("a", "b", seed_weight=10.0)
    wm.decay_all(decay_factor=0.5)
    assert wm.get_weight("a", "b") == 5.0


def test_decay_all_multiple_edges():
    wm = WorkingMemoryGraph()
    wm.link("a", "b", seed_weight=10.0)
    wm.link("b", "c", seed_weight=20.0)
    wm.decay_all(decay_factor=0.5)
    assert wm.get_weight("a", "b") == 5.0
    assert wm.get_weight("b", "c") == 10.0


def test_clear():
    wm = WorkingMemoryGraph()
    wm.link("a", "b", seed_weight=10.0)
    wm.link("c", "d", seed_weight=5.0)
    wm.clear()
    assert wm.get_weight("a", "b") is None
    assert wm.get_weight("c", "d") is None


def test_get_top_activated():
    wm = WorkingMemoryGraph()
    wm.link("query", "proc1", seed_weight=5.0)
    wm.link("query", "proc2", seed_weight=2.0)
    wm.link("other", "proc1", seed_weight=3.0)  # proc1 gets 5+3=8 total
    
    top = wm.get_top_activated(top_k=2)
    assert len(top) == 2
    assert top[0][0] == "proc1"  # Highest activation
    assert top[0][1] == 8.0
    assert top[1][0] == "proc2"
    assert top[1][1] == 2.0


def test_seed_weight_capped_at_creation():
    wm = WorkingMemoryGraph(max_weight=5.0)
    weight = wm.link("a", "b", seed_weight=100.0)
    assert weight == 5.0


def test_multiple_reinforcements():
    wm = WorkingMemoryGraph(reinforce_delta=1.0, max_weight=100.0)
    wm.link("a", "b", seed_weight=0.0)
    for _ in range(10):
        wm.link("a", "b")
    assert wm.get_weight("a", "b") == 10.0
