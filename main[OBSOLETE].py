from dataclasses import dataclass
from enum import Enum
import random
from pprint import pprint
import copy


class RoomType(Enum):
    Null = 0
    Straight = 1
    Turn = 2

class Side(Enum):
    North = (0, -1)
    East = (1, 0)
    South = (0, 1)
    West = (-1, 0)

    def __add__(self, other):
        return self.value[0] + other.value[0], self.value[1] + other.value[1]

    def __sub__(self, other):
        return self.value[0] - other.value[0], self.value[1] - other.value[1]

@dataclass
class Anchor:
    facing: Side
    open: bool

@dataclass
class Room:
    name: str = "None"
    type: RoomType = RoomType.Null
    anchors: list[Anchor] = None
    open: bool = True
    facing: Side = Side.North
    pos: tuple[int, int] = (0, 0)


anchorTemplate = {
    RoomType.Turn: [Anchor(facing=Side.South,open=True),Anchor(facing=Side.East,open=True)],
    RoomType.Straight: [Anchor(facing=Side.South,open=True),Anchor(facing=Side.North,open=True)],
}

size = 11
grid = [[0]*size for i in range(size)]

rng = random.Random(12345)



def MatchAnchors(anchor1: Anchor, anchor2: Anchor, currentRotation: Side) -> tuple[Side, int]:
    side_list = list(Side)
    test_facing = anchor1.facing
    for i in range(4):
        if (test_facing + anchor2.facing) == (0, 0):
            rotation = side_list[(side_list.index(currentRotation) + i) % 4]
            return rotation, i
        test_facing = side_list[(side_list.index(test_facing) + 1) % 4]
    print("sm fucked up(Match Anchors)")
    return Side.North, 0

def AdjustAllAnchors(steps: int, curAnchors: list[Anchor]):
    side_list = list(Side)
    new_anchor_list = copy.deepcopy(curAnchors)
    for i,anchor in enumerate(new_anchor_list):
        for _ in range(0,steps):
            anchor.facing = side_list[(side_list.index(anchor.facing) + 1) % 4]
    return new_anchor_list



def GenerateRoom(previous_room : Room, interation : str) -> Room:

    seed = rng.randint(0, 100)

    new_room = Room(name=interation)

    # choose type
    threshold = 20 if previous_room.type == RoomType.Turn else 50
    if seed < threshold:
        new_room.type = RoomType.Turn
    else:
        new_room.type = RoomType.Straight

    #anchors
    new_room.anchors = copy.deepcopy(anchorTemplate[new_room.type])
    local_anchor = new_room.anchors[rng.randint(0, len(new_room.anchors) - 1)]
    local_anchor.open = False

    other_available_anchors = [anchor for anchor in previous_room.anchors if anchor.open]
    other_anchor = other_available_anchors[rng.randint(0,len(other_available_anchors) - 1)]
    other_anchor.open = False

    #side
    new_room.facing, steps_to_rotate = MatchAnchors(local_anchor,other_anchor,new_room.facing)
    new_room.anchors = AdjustAllAnchors(steps_to_rotate,new_room.anchors)

    return new_room

def generate():
    for i in range(0,20):
        choice = GenerateRoom()
        if choice == RoomType.Turn and len(current_rooms) != 0 and current_rooms[i - 1 if len(current_rooms) > 0 else 1] == RoomType.Turn:
            choice = RoomType.Straight
        current_rooms.append(choice)

    print(current_rooms)

pprint(grid)




