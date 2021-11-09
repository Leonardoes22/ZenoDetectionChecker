import xml.etree.ElementTree as ET
import networkx as nx
import matplotlib.pyplot as plt

class Component:
    def __init__(self, compElement):
        self.locations = self.load_locations(compElement)
        self.initial = compElement.find("init").attrib["ref"]
        self.transitions = self.load_transitions(compElement)

    def load_locations(self, compElement):
        locations = {}
        for l in compElement.findall("location"):
            loc = Location(l)
            locations[loc.id] = loc
        return locations

    def load_transitions(self, compElement):
        return [Transition(tran) for tran in compElement.findall("transition")]

    def get_graph(self):
        graph = nx.MultiDiGraph()
        graph.add_nodes_from(self.locations.keys())
        for tran in self.transitions:
            graph.add_edge(tran.sourceId,tran.targetId)
        return graph

    def get_cycles(self):
        return list(nx.simple_cycles(self.get_graph()))

    def verify_cycle(self, cycle):
        # Suposes a single clock name x and checks for "x=0" in assignments
        # Suposes that a ">" is sufficient
        reset = False
        time_req = False
        for i in range(len(cycle)):
            for transition in self.transitions:
                if transition.sourceId == cycle[i] and transition.targetId == cycle[(i+1) % len(cycle)]: 
                    #print(transition)
                    reset = reset or transition.reset
                    time_req = time_req or transition.time_req
                    if reset and time_req:
                        break
        return reset and time_req

    def get_verified_cycles(self):
        return [()]

class Location:
    def __init__(self, locElement):
        self.id = locElement.attrib['id']
        self.name = locElement.find("name").text

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

class Transition:
    def __init__(self, transElement):
        self.sourceId = transElement.find("source").attrib["ref"]
        self.targetId = transElement.find("target").attrib["ref"]
        labels =  transElement.findall("label")
        self.reset = any([label.attrib["kind"] == "assignment" and ("x=0" in label.text.replace(" ","")) for label in labels])
        self.time_req = any([label.attrib["kind"] == "guard" and ">" in label.text.replace(" ","") for label in labels])

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return  f'{self.sourceId} --> {self.targetId}'

root = ET.parse("fischer.xml")

components = [Component(c) for c in root.findall("template")]

print(components[0].locations)
print(components[0].transitions)
#print(root.findall("template")[0].findall("location"))

graph = components[0].get_graph()
print(list(nx.simple_cycles(graph)))
print(nx.find_cycle(graph),list(nx.simple_cycles(graph)))
print(components[0].verify_cycle(list(nx.simple_cycles(graph))[1]))

#print(graph.nodes)
nx.draw(components[0].get_graph(),with_labels=True, connectionstyle='arc3, rad = 0.1')
plt.show()