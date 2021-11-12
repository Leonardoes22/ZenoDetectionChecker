import xml.etree.ElementTree as ET
import networkx as nx
import matplotlib.pyplot as plt
import re

class Model:
    def __init__(self, xmlFile):
        self.root = ET.parse(xmlFile)

        self.channels = []
        self.global_declarations = self.load_global_declarations()
        self.components = [Component(c, self) for c in self.root.findall("template")]
        self.channels = self.load_channels(self.channels)


    def evaluate_match(self,match):
        if match[1]:
            return match[0][0].safe
        else:
            return any([loop.safe for loop in match[0]])

    def get_matched_loops(self):
        matched_loops = []
        for c in self.channels:
            for emitter_trans in c.elements[0]:
                for emitter_loop in self.get_loops(emitter_trans):
                    match = [emitter_loop]
                    all_matches = []
                    for receiver_trans in c.elements[1]:
                        for receiver_loop in self.get_loops(receiver_trans):
                            if not (receiver_loop.component is emitter_loop.component):
                                missed = []
                                if not any([receiver_loop.component is n.component for n in match]):
                                    match.append(receiver_loop)
                                else:
                                    missed.append(receiver_loop)
                                matches = [match]
                                for mis in missed:
                                    matched2 = []
                                    for n in matches:
                                        matched2 = [mis if mis.component is m.component else m for m in n]
                                    matches.append(matched2)
                                    all_matches.extend(matches)

                    if len(all_matches) == 0 and c.broadcast:
                        matched_loops.append((match, True))

                    for m in all_matches:
                        matched_loops.append((m,c.broadcast))
        return matched_loops

    def get_single_loops(self):
        matched_loops = set()
        for match in self.get_matched_loops():
            for loop in match[0]:
                matched_loops.add(loop)
        
        
        loops = set()
        for c in self.components:
            for loop in c.cycles:
                loops.add(loop)

        return loops-matched_loops
    def get_loops(self, transition):
        loops = []  
        for c in self.components:
            for loop in c.cycles:
                for t in loop.transitions:
                    if t is transition:
                        loops.append(loop)
        return loops


    def load_global_declarations(self):
        raw = self.root.find("declaration").text
        commentless = re.sub(r"\/\/.*|\/\*(.|\n)*?\*\/","",raw) # remove comments
        return list(map(str.strip,commentless.replace("\n","").split(";")))
        

    def load_channels(self, lista):
        broadcast_channels = []
        simple_channels = []
        for dec in self.global_declarations:
            if bool(re.search(r"\bchan\b",dec)):
                parsed = dec.split("chan")
                channels = re.sub(r"\[.*?\]","",parsed[1]) # remove arrays
                channels = list(map(str.strip,channels.split(","))) # clean spaces
                if "broadcast" in parsed[0]: # check if broadcast
                    broadcast_channels = broadcast_channels + channels
                else:
                    simple_channels = simple_channels + channels
        
        channels = broadcast_channels + simple_channels

        output = []
        listNames = []
        for l in lista:
            name = l[0].replace("?","").replace("!","").replace(" ","")
            name = re.sub(r"\[.*?\]","",name) # remove arrays
            if not name in listNames:
                listNames.append(name)
                emmitterTrans=[]
                receiverTrans=[]
                for l2 in lista:
                    if name in l2[0]:
                        if "?" in l2[0]:
                            receiverTrans.append(l2[1])
                        elif "!" in l2[0]:
                            emmitterTrans.append(l2[1])
                broadcast = name in broadcast_channels
                output.append(Channel(self, name, emmitterTrans, receiverTrans, broadcast))
        return output

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
            time_inv = False
            for transition in self.transitions:
                reset = reset or transition.tests_reset(c)
                time_req = time_req or transition.tests_time_req(c)
                targetLoc = [self.component.locations[l] for l in self.component.locations if transition.targetId==l][0]
                time_inv = time_inv or targetLoc.tests_time_inv(c)
                if reset and (time_req or time_inv):
                    return True                
        return False
    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '['+', '.join([t.__str__() for t in self.transitions])+']'

class Channel:
    def __init__(self, model, name, emmitterTrans, receiverTrans, broadcast):
        self.model = model
        self.name = name
        self.elements = (emmitterTrans, receiverTrans)
        self.broadcast = broadcast
    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

class Component:
    def __init__(self, compElement, model):
        self.name = compElement.find("name").text
        self.model = model

        self.local_declarations = self.load_local_declarations(compElement)
        self.declarations = self.local_declarations + self.model.global_declarations

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
        self.cycles = self.get_cycles()
    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

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
        cycles_l = list(nx.simple_cycles(self.graph))
        cycles = []
        for cycle_l in cycles_l:
            cycle_vars = [[]]
            for k in range(len(cycle_l)):
                found_trans = []
                start = cycle_l[k]
                try:
                    end = cycle_l[k+1]
                except:
                    end = cycle_l[0]
                for transition in self.transitions:
                    if transition.sourceId==start and transition.targetId==end:
                        found_trans.append(transition)
                        new_vars = []
                        for c in cycle_vars:
                            if not any([f in c for f in found_trans]):
                                c.append(transition)
                            else:
                                c1 = c[:-1]
                                c1.append(transition)
                                new_vars.append(c1)
                        cycle_vars.extend(new_vars)
            cycles.extend(cycle_vars)
        return [Cycle(self, c) for c in cycles] 

    def evaluate(self, k):
        try:
            return int(k)
        except:
            for dec in self.declarations:
                if re.match(f"(const|constant) +int +{k} *:?= *", dec):
                    return int(re.split(f"(const|constant) +int +{k} *:?= *", dec)[-1])

class Location:
    def __init__(self, locElement, component):
        self.id = locElement.attrib['id']
        self.name = locElement.find("name").text if locElement.find("name") is not None else "noname"
        self.labels =  locElement.findall("label")
        self.component = component

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name

    def tests_time_inv(self,clock):
        for label in self.labels:
            if label.attrib["kind"] == "invariant":
                for atom in label.text.replace(" ","").split("&&"):
                    if clock in atom:
                        conds = [f"{clock}>=", f"<={clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)
                            compared.remove("")

                            if self.component.evaluate(compared[0].replace("(","").replace(")","")) > 0:
                                return True

                        conds = [f"{clock}>", f"<{clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)

                            if self.component.evaluate(compared[0]) >= 0: # add an error if evaluation returns None
                                return True
        return False

class Transition:
    def __init__(self, transitionElement, component):
        self.sourceId = transitionElement.find("source").attrib["ref"]
        self.targetId = transitionElement.find("target").attrib["ref"]
        self.labels =  transitionElement.findall("label")
        self.component = component

        for label in self.labels:
            if label.attrib["kind"] == "synchronisation":
                self.component.model.channels.append([label.text, self])

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

                            if self.component.evaluate(compared[0].replace("(","").replace(")","")) > 0:
                                return True

                        conds = [f"{clock}>", f"<{clock}"]
                        if any(re.match(cond, atom) for cond in conds):
                            compared = re.split("[><=]", atom)
                            compared.remove(clock)

                            if self.component.evaluate(compared[0]) >= 0: # add an error if evaluation returns None
                                return True
        return False

    
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return  f'{self.component.locations[self.sourceId]} --> {self.component.locations[self.targetId]}'
    


file = "train-gate-with-random-invariant.xml"
file = "train-gate.xml"
file = "fischer.xml"

model = Model(file)

print("Started...",f"\nVerifying {file}")

print("\n---------")
print("Model channels:")
print(model.channels)
for c in model.channels:
    print(f"{c} - emmitters: {c.elements[0]}, receivers: {c.elements[1]}, broadcast:{c.broadcast}")

print("\nList of Components")
for component in model.components:
    print("---------")
    print("component:",component)
    print("\nall locations:")
    print(component.locations)
    print("\nall transitions:")
    print(component.transitions)

    graph = component.graph
    print("\nall cycles:")
    print(component.cycles)
    

print("\n===================\nVERIFICATION RESULTS\n===================\n")

matches = model.get_matched_loops()
singles = model.get_single_loops()

unsafe = []

for loop in singles:
    if not loop.safe:
        unsafe.append(loop)

for match in matches:
    if not model.evaluate_match(match):
        unsafe.append(match)

if len(unsafe)==0:
    print("There are no unsafe loops, the model is non-zeno")
else:
    print("The checker couldn't guarantee the non-zenoness of the model. The following loops could cause zenoness:")
    for loop in unsafe:
        print("-->",loop)

