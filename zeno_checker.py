import xml.etree.ElementTree as ET
import networkx as nx
import matplotlib.pyplot as plt
import re

#OOPing

class Model:
    def __init__(self, xmlFile):
        root = ET.parse(xmlFile)

        # GET DECLARATIONS

        self.components = [Component(c, self) for c in root.findall("template")]

        self.channels = []
        self.single_loops = []
        self.synced_loops = []

        for component in self.components:
            for cycle in component.get_cycles():
                syncs = component.get_cycle_synchronisation(cycle)
                if len(syncs) == 0:
                    self.single_loops.append(cycle)
                else:
                    self.synced_loops.append(cycle)

        self.matched_loops = self.get_matched_loops()

    def get_matched_loops(self):
        loops = self.synced_loops

        matched_loops = []
        for loop in loops:
            pass

class Cycle:
    def __init__(self, component, transitions):
        self.component = component
        self.transitions = transitions
        self.safe = self.verify()

    def verify(self):
        clocks = self.component.clocks
        
        for c in clocks:
            reset = False
            time_req = False
            for transition in self.transitions:
                reset = reset or transition.tests_reset(c)
                time_req = time_req or transition.tests_time_req(c)
                if reset and time_req:
                    return True                
        return False


class Channel:
    def __init__(self, model, name, emmiterTrans, receiverTrans):
        self.model = model
        self.name = name
        self.elements = (emmiterTrans, receiverTrans)
        self.broadcast = isinstance(receiverTrans, set)
    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

class Component:
    def __init__(self, compElement, model):
        self.model = model
        self.local_declarations = self.load_local_declarations(compElement)
        self.declarations = self.local_declarations # GET GLOBAL DECLARATIONS TOO

        self.locations = self.load_locations(compElement)
        self.initial = compElement.find("init").attrib["ref"]
        self.transitions = self.load_transitions(compElement)

        self.graph = self.get_graph()

        clocks = []
        for dec in self.declarations:
            if re.match("clock ", dec):
                clocks = re.split(" |,", dec)[1:]
                try:
                    clocks.remove("")
                except:
                    None
        self.clocks = clocks

    def load_locations(self, compElement):
        locations = {}
        for l in compElement.findall("location"):
            loc = Location(l, self)
            locations[loc.id] = loc
        return locations

    def load_transitions(self, compElement):
        return [Transition(tran, self) for tran in compElement.findall("transition")]
        
    def load_local_declarations(self, compElement):
        return compElement.find("declaration").text.replace("\n","").split(";")

    def get_graph(self):
        graph = nx.MultiDiGraph()
        graph.add_nodes_from(self.locations.keys())
        for tran in self.transitions:
            graph.add_edge(tran.sourceId,tran.targetId)
        return graph

    def get_cycles(self):
        return list(nx.simple_cycles(self.graph))

    def get_cycle_transitions(self, cycle):
        transitions = []
        for i in range(len(cycle)):
                for transition in self.transitions:
                    if transition.sourceId == cycle[i] and transition.targetId == cycle[(i+1) % len(cycle)]:
                        transitions.append(transition)
        return transitions

    def get_verified_cycles(self):
        all_cycles = self.get_cycles()
        return [c for c in all_cycles if self.verify_cycle(c)]

    def get_cycle_synchronisation(self, cycle):
        base_syncs = set([transition.synchronisation for transition in self.get_cycle_transitions(cycle) if transition.synchronisation])
        syncs = set()
        for sync in base_syncs:
            sync = re.sub("\[.*\]","",sync)
            sync = (sync[0:-1],sync[-1])
            syncs.add(sync)
            
        return syncs


class Location:
    def __init__(self, locElement, component):
        self.id = locElement.attrib['id']
        self.name = locElement.find("name").text if locElement.find("name") is not None else "noname" 

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

class Transition:
    def __init__(self, transitionElement, component):
        self.sourceId = transitionElement.find("source").attrib["ref"]
        self.targetId = transitionElement.find("target").attrib["ref"]
        self.labels =  transitionElement.findall("label")
        self.declarations = component.declarations

        self.synchronisation = ""
        for label in self.labels:
            if label.attrib["kind"] == "synchronisation":
                self.synchronisation = label.text

    def tests_reset(self,clock):
        return any([label.attrib["kind"] == "assignment" and (f"{clock}=0" in label.text.replace(" ","")) for label in self.labels]) # add comp to :=

    def tests_time_req(self,clock):
        for label in self.labels:
            if label.attrib["kind"] == "guard":
                for atom in label.text.replace(" ","").split("&&"):
                    if clock in atom:
                        conds = [f"{clock}>=", f"<={clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)
                            compared.remove("")

                            if self.evaluate(compared[0].replace("(","").replace(")","")) > 0:
                                return True

                        conds = [f"{clock}>", f"<{clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)

                            if self.evaluate(compared[0]) >= 0: # add an error if evaluation returns None
                                return True
        return False
        
    def evaluate(self, k):
        try:
            return int(k)
        except:
            for dec in self.declarations:
                if re.match(f"(const|constant) int {k} *:?= *", dec):
                    return int(re.split(f"(const|constant) int {k} *:?= *", dec)[-1])


    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return  f'{self.sourceId} --> {self.targetId}'



model = Model("fischer.xml")
model = Model("train-gate.xml")
components = model.components


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


print("---DEBUG SYNCS")
components[0].get_cycle_synchronisation(components[0].get_cycles()[0])

print("Synced", model.synced_loops)
print("Single", model.single_loops)

#nx.draw(components[0].get_graph(),with_labels=True, connectionstyle='arc3, rad = 0.1')
#plt.show()