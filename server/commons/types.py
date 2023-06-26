from dataclasses import dataclass
from typing import Dict, Any, List

from database import Prompt as PromptModel
from pydantic import BaseModel


@dataclass
class CFPromptResult:
    result: str
    thought: list[dict[str, Any]]
    num_tokens: int
    prompt_id: int
    prompt: PromptModel


class Node(BaseModel):
    class Position(BaseModel):
        x: float
        y: float

    id: str
    cf_id: str = ""  # this is the id of the node in the chainfury graph
    position: Position
    type: str
    width: int
    height: int
    selected: bool = None  # type: ignore
    position_absolute: Position = None  # type: ignore
    dragging: bool = None  # type: ignore
    data: dict = {}


class Edge(BaseModel):
    id: str
    source: str
    sourceHandle: str = ""
    target: str
    targetHandle: str = ""


class Dag(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    sample: Dict[str, Any] = {}  # type: ignore
    main_in: str = ""
    main_out: str = ""
