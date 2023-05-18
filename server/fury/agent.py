"""
# Agent

This file contains methods and functions that are used to create an agent, i.e.
- model registry
- memory registry
- functional node registry
"""

import traceback
from functools import lru_cache
from typing import Any, List, Optional, Union, Dict

from fury.base import (
    logger,
    func_to_template_fields,
    Node,
    Model,
    ModelTags,
    Chain,
)

"""
## Models

All the things below are for the models that are registered in the model registry, so that they can be used as inputs
in the chain. There can be several models that can put as inputs in a single chatbot.
"""


class ModelRegistry:
    tags_types = ModelTags

    def __init__(self):
        self.models: Dict[str, Model] = {}
        self.counter: Dict[str, int] = {}
        self.tags_to_models: Dict[str, List[str]] = {}

    def has(self, model_id: str):
        return model_id in self.models

    def register(
        self,
        fn: object,
        collection_name: str,
        model_id: str,
        description: str,
        tags: List[str] = [],
    ):
        id = f"{model_id}"
        logger.info(f"Registering model {model_id} at {id}")
        if id in self.models:
            raise Exception(f"Model {model_id} already registered")
        self.models[id] = Model(
            collection_name=collection_name,
            model_id=model_id,
            fn=fn,
            description=description,
            template_fields=func_to_template_fields(fn),
            tags=tags,
        )
        for tag in tags:
            self.tags_to_models[tag] = self.tags_to_models.get(tag, []) + [id]

    def get_tags(self) -> List[str]:
        return list(self.tags_to_models.keys())

    def get_models(self, tag: str = "") -> List[Dict[str, Any]]:
        return [{k: v.to_dict()} for k, v in self.models.items()]

    def get(self, model_id: str) -> Optional[Model]:
        self.counter[model_id] = self.counter.get(model_id, 0) + 1
        out = self.models.get(model_id, None)
        if out is None:
            logger.warning(f"Model {model_id} not found")
        return out

    def get_count_for_model(self, model_id: str) -> int:
        return self.counter.get(model_id, 0)


model_registry = ModelRegistry()


"""
## Programtic Actions Registry

Programtic actions are nodes that are software 1.0 nodes, i.e. they are not trainable. They are used for things like
calling an API, adding 2 numbers, etc. Since they are not trainable the only way to get those is the source code for
the server.
"""


class ProgramaticActionsRegistry:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.counter: Dict[str, int] = {}
        self.tags_to_nodes: Dict[str, List[str]] = {}

    def register(
        self, fn: object, node_id: str, description: str, tags: List[str] = []
    ):
        logger.info(f"Registering p-node '{node_id}'")
        if node_id in self.nodes:
            raise Exception(f"Node '{node_id}' already registered")
        self.nodes[node_id] = Node(
            id=node_id,
            type=Node.types.PROGRAMATIC,
            fn=fn,
            description=description,
            fields=func_to_template_fields(fn),
        )
        for tag in tags:
            self.tags_to_nodes[tag] = self.tags_to_nodes.get(tag, []) + [node_id]

    def get_tags(self) -> List[str]:
        return list(self.tags_to_nodes.keys())

    def get_nodes(self, tag: str = "") -> List[Dict[str, Any]]:
        return [{k: v.to_dict()} for k, v in self.nodes.items()]

    def get(self, node_id: str) -> Optional[Node]:
        self.counter[node_id] = self.counter.get(node_id, 0) + 1
        out = self.nodes.get(node_id, None)
        if out is None:
            logger.warning(f"p-node '{node_id}' not found")
        return out

    def get_count_for_nodes(self, node_id: str) -> int:
        return self.counter.get(node_id, 0)


programatic_actions_registry = ProgramaticActionsRegistry()


"""
## AI Actions Registry

For everything that cannot be done by we have the AI powered actions Registry. This registry
will not include all the things that are available to the outer service, but those that are
hardcoded in the entire thing somewhere.
"""


def ai_action_fn():
    return None


class AIActionsRegistry:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.counter: Dict[str, int] = {}
        self.tags_to_nodes: Dict[str, List[str]] = {}

    def register(
        self,
        node_id: str,
        description: str,
        model_id: str,
        model_params: Dict[str, Any],
        fn: object = None,
        tags: List[str] = [],
    ):
        if not model_registry.has(model_id):
            raise Exception(f"Model {model_id} not registered")
        logger.info(f"Registering ai-node '{node_id}'")
        self.nodes[node_id] = Node(
            id=node_id,
            fn=ai_action_fn if fn is None else fn,
            type=Node.types.MODEL,
            description=description,
            model=model_registry.get(model_id),
            model_params=model_params,
        )
        for tag in tags:
            self.tags_to_nodes[tag] = self.tags_to_nodes.get(tag, []) + [node_id]

    def get_tags(self) -> List[str]:
        return list(self.tags_to_nodes.keys())

    def get_nodes(self, tag: str = "") -> List[Dict[str, Any]]:
        return [{k: v.to_dict()} for k, v in self.nodes.items()]

    def get(self, node_id: str) -> Optional[Node]:
        self.counter[node_id] = self.counter.get(node_id, 0) + 1
        out = self.nodes.get(node_id, None)
        if out is None:
            logger.warning(f"ai-node '{node_id}' not found")
        return out

    def get_count_for_nodes(self, node_id: str) -> int:
        return self.counter.get(node_id, 0)


ai_actions_registry = AIActionsRegistry()

# class Memory:
#     def __init__(self, memory_id):
#         self.node = Node(id=f"cf-memory-{memory_id}", type=Node.types.MEMORY)

#     # user can subclass this and override the following functions
#     def get(self, key: str):
#         ...

#     def put(self, key: str, value: Any):
#         ...


# # the main class, user can either subclass this or prvide the chain
# class Agent:
#     def __init__(self, models: List[Model], chain: Chain):
#         self.models = models
#         self.chain = chain

#     def __call__(self, user_input: Any):
#         return self.chain(user_input)


# # we LRU cache this to save time on ser / deser
# @lru_cache(128)
# def get_agent(models: List[Model], chain: Chain) -> Agent:
#     return Agent(
#         models=models,
#         chain=chain,
#     )


if __name__ == "__main__":
    pass
