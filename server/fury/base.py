import json
import inspect
import logging
import traceback
from hashlib import sha256
from typing import Any, Union, Optional, Dict, List, Tuple, Callable
from collections import deque, defaultdict


def get_logger(name):
    temp_logger = logging.getLogger(name)
    temp_logger.setLevel(logging.DEBUG)
    return temp_logger


logger = get_logger("fury-core")


class Secret(str):
    """This class just means that in TemplateField it will be taken as a password field"""


#
# TemplateFields: this is the base class for all the fields that the user can provide from the front end
#


class TemplateField:
    def __init__(
        self,
        type: Union[str, List["TemplateField"]],
        format: str = "",
        items: List["TemplateField"] = [],
        additionalProperties: Union[Dict, "TemplateField"] = {},
        password: bool = False,
        #
        required: bool = False,
        placeholder: str = "",
        show: bool = False,
        name: str = "",
    ):
        self.type = type
        self.format = format
        self.items = items or []
        self.additionalProperties = additionalProperties
        self.password = password
        #
        self.required = required
        self.placeholder = placeholder
        self.show = show
        self.name = name

    def __repr__(self) -> str:
        return f"TemplateField(type={self.type}, format={self.format}, items={self.items}, additionalProperties={self.additionalProperties})"

    def to_dict(self) -> Dict[str, Any]:
        d = {"type": self.type}
        if (
            type(self.type) == list
            and len(self.type)
            and type(self.type[0]) == TemplateField
        ):
            d["type"] = [x.to_dict() for x in self.type]
        if self.format:
            d["format"] = self.format
        if self.items:
            d["items"] = [item.to_dict() for item in self.items]
        if self.additionalProperties:
            if isinstance(self.additionalProperties, TemplateField):
                d["additionalProperties"] = self.additionalProperties.to_dict()
            else:
                d["additionalProperties"] = self.additionalProperties
        if self.password:
            d["password"] = self.password
        #
        if self.required:
            d["required"] = self.required
        if self.placeholder:
            d["placeholder"] = self.placeholder
        if self.show:
            d["show"] = self.show
        if self.name:
            d["name"] = self.name
        return d


def pyannotation_to_json_schema(x) -> TemplateField:
    if isinstance(x, type):
        if x == str:
            return TemplateField(type="string")
        elif x == int:
            return TemplateField(type="integer")
        elif x == float:
            return TemplateField(type="number")
        elif x == bool:
            return TemplateField(type="boolean")
        elif x == bytes:
            return TemplateField(type="string", format="byte")
        elif x == list:
            return TemplateField(type="array", items=[TemplateField(type="string")])
        elif x == dict:
            return TemplateField(
                type="object", additionalProperties=TemplateField(type="string")
            )
        elif x == Secret:
            return TemplateField(type="string", password=True)
        else:
            raise ValueError(f"i0: Unsupported type: {x}")
    elif isinstance(x, str):
        return TemplateField(type="string")
    elif hasattr(x, "__origin__") and hasattr(x, "__args__"):
        if x.__origin__ == list:
            return TemplateField(
                type="array", items=[pyannotation_to_json_schema(x.__args__[0])]
            )
        elif x.__origin__ == dict:
            if len(x.__args__) == 2 and x.__args__[0] == str:
                return TemplateField(
                    type="object",
                    additionalProperties=pyannotation_to_json_schema(x.__args__[1]),
                )
            else:
                raise ValueError(f"i2: Unsupported type: {x}")
        elif x.__origin__ == tuple:
            return TemplateField(
                type="array",
                items=[pyannotation_to_json_schema(arg) for arg in x.__args__],
            )
        elif x.__origin__ == Union:
            # Unwrap union types with None type
            types = [arg for arg in x.__args__ if arg is not None]
            if len(types) == 1:
                return pyannotation_to_json_schema(types[0])
            else:
                return TemplateField(
                    type=[pyannotation_to_json_schema(typ) for typ in types]
                )
        else:
            print(x.__origin__)
            raise ValueError(f"i3: Unsupported type: {x}")
    elif isinstance(x, tuple):
        return TemplateField(
            type="array",
            items=[TemplateField(type="string"), pyannotation_to_json_schema(x[1])]
            * len(x),
        )
    else:
        raise ValueError(f"i4: Unsupported type: {x}")


def func_to_template_fields(func) -> List[TemplateField]:
    """
    Extracts the signature of a function and converts it to an array of TemplateField objects.
    """
    signature = inspect.signature(func)
    fields = []
    for param in signature.parameters.values():
        schema = pyannotation_to_json_schema(param.annotation)
        schema.required = param.default is inspect.Parameter.empty
        schema.name = param.name
        schema.placeholder = (
            str(param.default) if param.default is not inspect.Parameter.empty else ""
        )
        if not schema.name.startswith("_"):
            schema.show = True
        fields.append(schema)
    return fields


#
# Model: Each model is the processing engine of the AI actions. It is responsible for keeping
#        the state of each of the wrapped functions for different API calls.
#


class ModelTags:
    TEXT_TO_TEXT = "text_to_text"
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"


class Model:
    model_tags = ModelTags

    def __init__(
        self,
        collection_name,
        model_id,
        fn: object,
        description,
        template_fields: List[TemplateField],
        tags=[],
    ):
        self.collection_name = collection_name
        self.model_id = model_id
        self.fn = fn
        self.description = description
        self.template_fields = template_fields
        self.tags = tags

    def __repr__(self) -> str:
        return f"Model('{self.collection_name}', '{self.model_id}')"

    def to_dict(self):
        return {
            "collection_name": self.collection_name,
            "model_id": self.model_id,
            "description": self.description,
            "tags": self.tags,
            "template_fields": [x.to_dict() for x in self.template_fields],
        }

    def __call__(self, model_data: Dict[str, Any]):
        try:
            out = self.fn(**model_data)  # type: ignore
            return out, None
        except Exception as e:
            return traceback.format_exc(), e


#
# Node: Each box that is drag and dropped in the UI is a Node, it will tell what kind of things are
#       its inputs, outputs and fields that are shown in the UI. It can be of different types and
#       it only wraps teh
#


class NodeType:
    PROGRAMATIC = "programatic"
    AI = "ai-powered"


class NodeConnection:
    def __init__(
        self, id: str, name: str = "", required: bool = False, description: str = ""
    ):
        self.id = id
        self.name = name
        self.required = required
        self.description = description


class Node:
    types = NodeType()

    def __init__(
        self,
        id: str,
        type: str,
        fn: object,  # the function to call
        description: str = "",
        inputs: List[NodeConnection] = [],
        fields: List[TemplateField] = [],
        outputs: List[NodeConnection] = [],
        #
        # things for when procesing engine is a model
        model: Model = None,
        model_params: Dict[str, Any] = {},
    ):
        # when this is a Model processed action things are a bit more complicated. The main problems are:
        # - state management of the inputs to the model which can come from model_params, fields or user
        #   defined function
        if type == NodeType.AI:
            if model is None:
                raise ValueError("Model node requires a model")

        # when action is programatic then it is pretty simple to use, there are no extra arguments
        # we know all the things that might be needed via the fields
        elif type == NodeType.PROGRAMATIC:
            if model is not None or model_params:
                raise ValueError("Cannot pass AI actions arguments in programatic node")

        else:
            raise ValueError(
                f"Invalid node type: {type}, see Node.types for valid types"
            )

        # set the values
        self.id = id
        self.type = type
        self.description = description
        self.inputs = inputs
        self.fields = fields
        self.outputs = outputs
        self.fn = fn

    def __repr__(self) -> str:
        out = f"CFNode('{self.id}', '{self.type}', fields: [{len(self.fields)}, inputs:{len(self.inputs)}, outputs:{len(self.outputs)})"
        for f in self.fields:
            out += f"\n      {f},"
        out += "\n])"
        return out

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "fields": [field.to_dict() for field in self.fields],
        }

    def __call__(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Exception]:
        # this is the ultimate function that will make the node usable, there are
        # three seperate parts this function will do:
        # 1. it will validate the input that it is getting
        # 2. based on the type call the underlying function:
        #  - for programatic function we will simple pass all the values to the
        #    self.fn and return the result
        #  - for the AI functions we need to see which the model_id in the input
        #    and then call that one specific item from the registry
        #  * in both the cases raise appropriate errors and inform the user who
        #    f-ed up
        # 3. serialise the result and return it, note the job of this function is
        #    not related with anything in the larger chainfury ecosystem, it is
        #    the API functions responsibility to store it in the DB and all that

        # logger.info(f"node called: {self.id}")
        # logger.info(f"Calling node with data: {data}")
        # logger.info(f"function is: {self.fn}")

        if self.type == NodeType.PROGRAMATIC:
            fn_to_call = self.fn
        elif self.type == NodeType.AI:
            pass

        try:
            out = fn_to_call(**data)
            return {"out": out}, None
        except Exception as e:
            tb = traceback.format_exc()
            return tb, e


#
# Edge: Each connection between two boxes on the UI is called an Edge, it is only a dataclass without any methods.
#


class Edge:
    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target

    def __repr__(self) -> str:
        return f"CFEdge('{self.source}', '{self.target}')"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            source=data["source"],
            target=data["target"],
        )

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
        }


#
# Dag: An entire flow is called the Chain
#


class Chain:
    def __init__(
        self,
        nodes: List[Node] = [],
        edges: List[Edge] = [],
    ):
        self.nodes = nodes
        self.edges = edges

    def __repr__(self) -> str:
        # return f"CFDag(nodes: {len(self.nodes)}, edges: {len(self.edges)})"
        out = "CFDag(\n  nodes: ["
        for n in self.nodes:
            out += f"\n    {n},"
        out += "\n  ],\n  edges: ["
        for e in self.edges:
            out += f"\n    {e},"
        out += "\n  ]\n)"
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            nodes=[Node.from_dict(x) for x in data.get("nodes", [])],
            edges=[Edge.from_dict(x) for x in data.get("edges", [])],
        )

    def to_dict(self):
        return {
            "nodes": [x.to_dict() for x in self.nodes],
            "edges": [x.to_dict() for x in self.edges],
        }

    def hash(self) -> str:
        return sha256(json.dumps(self.to_dict).encode("utf-8")).hexdigest()

    def build(self):
        # this function builds the final langchain dag that will be executed, in order to determine the order of execution in a DAG
        # the algorithm is called 'topological sort'
        out = topological_sort(self.edges)
        print(out)


# helper functions


class NotDAGError(Exception):
    pass


def edge_array_to_adjacency_list(edges: List[Edge]):
    """Convert silk format dag edges to adjacency list format"""
    adjacency_lists = {}
    for edge in edges:
        src = edge.source
        dst = edge.target
        if src not in adjacency_lists:
            adjacency_lists[src] = []
        adjacency_lists[src].append(dst)
    return adjacency_lists


def adjacency_list_to_edge_map(adjacency_list) -> List[Edge]:
    """Convert adjacency list format to silk format dag edges"""
    edges = []
    for src, dsts in adjacency_list.items():
        for dst in dsts:
            edges.append(Edge(source=src, target=dst))
    return edges


def topological_sort(edges: List[Edge]) -> List[str]:
    """Topological sort of a DAG, raises NotDAGError if the graph is not a DAG"""
    adjacency_lists = edge_array_to_adjacency_list(edges)
    in_degree = defaultdict(int)
    for src, dsts in adjacency_lists.items():
        for dst in dsts:
            in_degree[dst] += 1

    # Add all nodes with no incoming edges to the queue
    queue = deque()
    for node in adjacency_lists:
        if in_degree[node] == 0:
            queue.append(node)

    # For each node, remove it from the graph and add it to the sorted list
    sorted_list = []
    edge_nodes_cntr = 0
    while queue:
        node = queue.popleft()
        sorted_list.append(node)
        neighbours = adjacency_lists.get(node, [])
        if not neighbours:
            edge_nodes_cntr += 1
        for neighbor in neighbours:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check to see if all edges are removed
    if len(sorted_list) == len(adjacency_lists) + edge_nodes_cntr:
        return sorted_list
    else:
        raise NotDAGError("A cycle exists in the graph.")
