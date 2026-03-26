"""Test JoinGraph paths for the two-layer measurement model."""
import networkx as nx
from app.ontology.mapping import MappingDictionary
from app.ontology.join_graph import JoinGraph

m = MappingDictionary('app/ontology/data/mapping_prod.json')
g = JoinGraph()
g.build(m)

paths = [
    ('semi:WaferMeasurementSnapshot', 'semi:Wafer'),
    ('semi:WaferMeasurementSnapshot', 'semi:ProductionLot'),
    ('semi:WaferMeasurementSnapshot', 'semi:ProcessStation'),
    ('semi:WaferMeasurementSnapshot', 'semi:Equipment'),
    ('semi:WaferMeasurementSnapshot', 'semi:ParamDefinition'),
    ('semi:Wafer', 'semi:WaferMeasurementSnapshot'),
    ('semi:ProductionLot', 'semi:WaferMeasurementSnapshot'),
    ('semi:MeasurementPassRecord', 'semi:Wafer'),
    ('semi:MeasurementPassRecord', 'semi:ProductionLot'),
]

print("=== JoinGraph Path Reachability ===\n")
for src, tgt in paths:
    try:
        p = nx.shortest_path(g._g, src, tgt)
        hops = ' -> '.join([n.replace('semi:', '') for n in p])
        print(f"  [{len(p)-1} hop] {hops}")
    except nx.NetworkXNoPath:
        print(f"  NO PATH: {src} -> {tgt}")
