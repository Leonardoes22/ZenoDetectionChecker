import xml.etree.ElementTree as ET
import networkx as nx
import matplotlib.pyplot as plt
import re

class Component:
    def __init__(self, compElement):
        self.declarations = self.load_local_declarations(compElement)

        self.locations = self.load_locations(compElement)
        self.initial = compElement.find("init").attrib["ref"]
        self.transitions = self.load_transitions(compElement)


        self.graph = self.get_graph()

    def load_locations(self, compElement):
        locations = {}
        for l in compElement.findall("location"):
            loc = Location(l)
            locations[loc.id] = loc
        return locations

    def load_transitions(self, compElement):
        return [Transition(tran, self.declarations) for tran in compElement.findall("transition")]
        
    def load_local_declarations(self, compElement):
        return [dec.text.replace("\n","").split(";") for dec in compElement.findall("declaration")][0]

    def get_graph(self):
        graph = nx.MultiDiGraph()
        graph.add_nodes_from(self.locations.keys())
        for tran in self.transitions:
            graph.add_edge(tran.sourceId,tran.targetId)
        return graph

    def get_cycles(self):
        return list(nx.simple_cycles(self.graph))

    def verify_cycle(self, cycle):
        clocks = []
        for dec in self.declarations:
            if re.match("clock ", dec):
                clocks = re.split(" |,", dec)[1:]
                try:
                    clocks.remove("")
                except:
                    None

        for c in clocks:
            reset = False
            time_req = False
            for i in range(len(cycle)):
                for transition in self.transitions:
                    if transition.sourceId == cycle[i] and transition.targetId == cycle[(i+1) % len(cycle)]:
                        reset = reset or transition.tests_reset(c)
                        time_req = time_req or transition.tests_time_req(c)
                        if reset and time_req:
                            return True                
        return False

    def get_verified_cycles(self):
        all_cycles = self.get_cycles()
        return [c for c in all_cycles if self.verify_cycle(c)]

class Location:
    def __init__(self, locElement):
        self.id = locElement.attrib['id']
        self.name = locElement.find("name").text

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

class Transition:
    def __init__(self, transitionElement, localDeclarations):
        self.sourceId = transitionElement.find("source").attrib["ref"]
        self.targetId = transitionElement.find("target").attrib["ref"]
        self.labels =  transitionElement.findall("label")
        self.declarations = localDeclarations
        #self.reset = any([label.attrib["kind"] == "assignment" and ("x=0" in label.text.replace(" ","")) for label in labels])
        """
        for label in labels:
            if label.attrib["kind"] == "guard":
                for atom in label.text.replace(" ","").split("&&"):
                    if ">" in atom:
                        self.time_req = True
                        return None
        self.time_req = False
        """
        #self.time_req = any([label.attrib["kind"] == "guard" and ">" in label.text.replace(" ","") for label in labels])

    def tests_reset(self,clock):
        return any([label.attrib["kind"] == "assignment" and (f"{clock}=0" in label.text.replace(" ","")) for label in self.labels])

    def tests_time_req(self,clock):
        for label in self.labels:
            if label.attrib["kind"] == "guard":
                for atom in label.text.replace(" ","").split("&&"):
                    if clock in atom:
                        conds = [f"{clock}>=", f"<={clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)

                            if self.evaluate(compared[0]) > 0:
                                return True

                        conds = [f"{clock}>", f"<{clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)

                            if self.evaluate(compared[0]) >= 0:
                                return True
        return False
        
    def evaluate(self, k):
        try:
            return int(k)
        except:
            for dec in self.declarations:
                if re.match(f"(const|constant) int {k} *= *", dec):
                    return int(re.split(f"(const|constant) int {k} *= *", dec)[-1])


    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return  f'{self.sourceId} --> {self.targetId}'

root = ET.parse("fischer.xml")

components = [Component(c) for c in root.findall("template")]

print("---")
print("all locations:")
print(components[0].locations)
print("---")
print("all transitions:")
print(components[0].transitions)

graph = components[0].graph
print("---")
print("all cycles:")
all_cycles=list(nx.simple_cycles(graph))
print(all_cycles)

print("---")
print(nx.find_cycle(graph), all_cycles)
print("---")
print(components[0].verify_cycle(all_cycles[0]))


print("---")
print("cycles satisfing sufficient condition:")
print(components[0].get_verified_cycles())

#nx.draw(components[0].get_graph(),with_labels=True, connectionstyle='arc3, rad = 0.1')
#plt.show()