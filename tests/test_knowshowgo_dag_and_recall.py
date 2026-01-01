import pytest

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.ksg import KSGStore
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance


def test_create_and_recall_prototype_and_concept():
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory)
    prov = Provenance("user", "now", 1.0, "ksg-test")

    proto_uuid = ksg.create_prototype(
        name="ProcedureProto",
        description="Prototype for procedures",
        context="workflow",
        labels=["Prototype", "Procedure"],
        embedding=[1.0, 0.0],
        provenance=prov,
        base_prototype_uuid=None,
    )
    concept_uuid = ksg.create_concept(
        prototype_uuid=proto_uuid,
        json_obj={"name": "DemoProc", "steps": ["a", "b", "c"]},
        embedding=[0.5, 0.1],
        provenance=prov,
    )

    # Prototype and concept stored
    assert proto_uuid in memory.nodes
    assert concept_uuid in memory.nodes
    concept = memory.nodes[concept_uuid]
    assert concept.props["prototype_uuid"] == proto_uuid
    # Inheritance edge or instantiates exists
    edges = list(memory.edges.values())
    rels = {(e.from_node, e.to_node, e.rel) for e in edges}
    assert any(e[0] == concept_uuid and e[2] == "instantiates" for e in rels)


def test_dag_like_list_recall():
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory)
    prov = Provenance("user", "now", 1.0, "ksg-test")

    list_proto = ksg.create_prototype(
        name="ListProto",
        description="Prototype for list-like concept",
        context="collection",
        labels=["Prototype", "List"],
        embedding=[0.2, 0.2],
        provenance=prov,
        base_prototype_uuid=None,
    )
    dag_concept = ksg.create_concept(
        prototype_uuid=list_proto,
        json_obj={"name": "StepList", "items": ["step1", "step2", "step3"]},
        embedding=[0.3, 0.3],
        provenance=prov,
    )

    # Simple recall via search should return the concept
    results = memory.search("StepList", top_k=1, query_embedding=[0.3, 0.3])
    assert results
    assert results[0]["uuid"] == dag_concept


def test_create_typed_concepts_from_seeded_prototypes():
    memory = MockMemoryTools()
    ksg_store = KSGStore(memory)

    def embed(text: str):
        return [float(len(text)), 0.2]

    ksg_store.ensure_seeds(embedding_fn=embed)

    dag = ksg_store.create_concept("DAG", "DagConcept", ["dag"], {"steps": ["one", "two"]})
    tag = ksg_store.create_concept("Tag", "TagConcept", ["tag"], {"tags": ["x"]})
    task = ksg_store.create_concept("Task", "TaskConcept", ["task"], {"status": "open"})
    event = ksg_store.create_concept("Event", "EventConcept", ["event"], {"location": "here"})
    obj = ksg_store.create_concept("Object", "ObjectConcept", ["object"], {"properties": [{"name": "foo", "value": "bar"}]})

    for name, kind, node in [
        ("DagConcept", "DAG", dag),
        ("TagConcept", "Tag", tag),
        ("TaskConcept", "Task", task),
        ("EventConcept", "Event", event),
        ("ObjectConcept", "Object", obj),
    ]:
        assert node.kind == kind
        results = memory.search(name, top_k=50, filters={"kind": kind}, query_embedding=[len(name), 0.2])
        assert any(r.get("uuid") == node.uuid for r in results)
