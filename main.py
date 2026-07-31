from __future__ import annotations
import random
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import json


from render import render
from stack import Stack
from logger import setup_logging, get_logger

setup_logging()
log_assets = get_logger("Assets", "Loader")
log_struct = get_logger("Generation","StructurePlacer")
log_snake = get_logger("Generation", "SnakePass")
log_tree = get_logger("Generation", "TreePass")
log_loop = get_logger("Generation", "LoopPass")
log_main = get_logger("Generation", "Main")

PROJECT_ROOT = Path(__file__).parent

@dataclass
class Cell:
    id: int = 0
    hash: int = 0
    connections: list[Cell] = field(default_factory=list)
    pos: tuple[int, int] = (0, 0)
    placed: bool = False
    customData: dict = field(default_factory=dict)


DIR_VECTORS = {0: (0, -1), 1: (-1, 0), 2: (0, 1), 3: (1, 0)}

@dataclass
class Structure:
    name: str = ""
    explicitPlacing: bool = False
    pos: tuple[int, int] = (0, 0)
    size:tuple[int, int] = (0, 0)
    rotation: int = 0
    weight: int = 0
    grid: list[list[Cell]] = field(default_factory=list)


STRUCT_CELL_TYPES = {"air": Cell(),
                     "cell": Cell(id=-2, placed=True, customData={"reserved": True}),
                     "gate": Cell(id=-3, placed=True, customData={ "isGate": True}),
                     "anchor": Cell(id=-4, placed=True, customData={"reserved": True, "isAnchor": True})}
structureSet = []

size = 100
center = round(size / 2)
grid = [[Cell() for _ in range(size)] for _ in range(size)]


def MakeHash() -> int:
    return random.getrandbits(255)


def GenerateStructureData(structureDir: Path):
    log_assets.info(f"loading structure files from {structureDir}")
    for file in structureDir.glob("*.json"):
        try:
            data: dict = json.loads(file.read_text())
            jsonGrid: list[list[str]] = data["grid"]
            legend: dict = data["legend"]
            log_assets.debug(f"unpacked json for: {data['name']}")
            newStruct = Structure(name=data["name"],
                                  explicitPlacing=bool(data["preset_location"]),
                                  pos=tuple(data["preset_location"]) if data["preset_location"] else (0, 0),
                                  weight=data["weight"]
                                  )
            log_assets.debug("generated structure object")
            newStructGrid = [[Cell() for _ in range(len(jsonGrid[0]))] for _ in range(len(jsonGrid))]
            for y, row in enumerate(jsonGrid):
                for x, cell in enumerate(row):
                    newStructCell = STRUCT_CELL_TYPES.get(legend[cell], STRUCT_CELL_TYPES["cell"])
                    newStructGrid[y][x] = newStructCell
            log_assets.debug("generated structure tile list")
            newStruct.grid = newStructGrid
            newStruct.size = (len(newStruct.grid)-1,len(newStruct.grid[0])-1)
            structureSet.append(newStruct)
            log_assets.info(f"loaded structure: {data['name']}")
        except Exception as e:
            log_assets.warning(f"struct generation failed for {file.name}, reason: {e}")

def aabb_overlap(a :Structure,b :Structure):
    return (a.pos[0] < b.pos[0] + b.size[0] and a.pos[0] + a.size[0] > b.pos[0]) and (a.pos[1] < b.pos[1] + b.size[1] and a.pos[1] + a.size[1] > b.pos[1])

def in_bound(a :Structure):
    return a.pos[0] >= 0 and a.pos[1] >= 0 and a.pos[0] + a.size[0] <= size and a.pos[1] + a.pos[1] <= size

def PlaceStructure(structureToPlace: Structure, pos:tuple[int,int] = (0,0)) -> bool:
    structPos = structureToPlace.pos if structureToPlace.explicitPlacing else pos
    log_struct.info(f"placing structure: {structureToPlace.name}, at position: {structPos}")

    anchorLocal = (0, 0)
    for y, row in enumerate(structureToPlace.grid):
        for x, cell in enumerate(row):
            if cell.customData.get("isAnchor"):
                anchorLocal = (x, y)

    for y, row in enumerate(structureToPlace.grid):
        for x, cell in enumerate(row):
            worldX = structPos[0] + (x - anchorLocal[0])
            worldY = structPos[1] + (y - anchorLocal[1])
            cellToUse = deepcopy(cell)
            cellToUse.pos = (worldX, worldY)
            cellToUse.hash = MakeHash()
            cellToUse.customData["name"] = structureToPlace.name
            if in_bound(structureToPlace):
                grid[worldY][worldX] = cellToUse
            else:
                return False
            return True

def StructurePass(emptyChance:int = 20, structureAmount:int = 10, placingRetryAttempts:int=10):
    weightList = {s.name: s.weight for s in structureSet if not s.explicitPlacing}
    weightList["nothing"] = emptyChance
    totalWeights = sum(weightList.values())

    for structureIndex in range(structureAmount):
        chosenStructure = structureSet[0]

        roll = random.randint(0,totalWeights)
        cumulative = 0
        futureName = ""
        for name , weight in weightList.items():
            cumulative += weight
            if roll <= cumulative:
                futureName = name
                break

        if futureName == "nothing":
            log_struct.info("skipped!!!!")
            continue

        chosenStructure = next(s for s in structureSet if s.name == futureName)


        unplaced = [(r, c) for r, row in enumerate(grid) for c, cell in enumerate(row) if not cell.placed]
        randX, randY = random.choice(unplaced)
        log_struct.info(f"placed {futureName} at: {randX}{randY}")
        for i in range(placingRetryAttempts):
            status = PlaceStructure(chosenStructure, (randX,randY))
            if status:
                structureIndex -= 1
                continue
            else:
                continue

def SnakePass(starting_point, steps, give_up_on_backtrack_threshold, give_up_instead_of_cut: bool = False,give_up_instead_of_backtrack: bool = False):
    roomStack = Stack()
    roomStack.pushEnd(starting_point)

    tried = {}

    backTrackAttempts = 0
    attempts = 0
    while attempts < steps:
        log_snake.debug(f"entering cycle: {attempts}")

        currentCell = roomStack.peakEnd()
        currentCellId = currentCell.hash
        log_snake.debug(
            f"generating from: ({roomStack.peakEnd().pos[0]},{roomStack.peakEnd().pos[1]}) of object : {currentCellId}")
        possible_dirs = [d for d in DIR_VECTORS if DIR_VECTORS[d] not in tried.setdefault(currentCellId, set())]

        if possible_dirs:
            direction = DIR_VECTORS[possible_dirs[random.randint(0, len(possible_dirs) - 1)]]
            tried[currentCellId].add(direction)
            newX, newY = currentCell.pos[0] + direction[0], currentCell.pos[1] + direction[1]
            log_snake.debug(f"dir vector and next coords are generated: coords:({newX}, {newY}), dir: {direction}")
        elif backTrackAttempts < give_up_on_backtrack_threshold:
            if give_up_instead_of_backtrack: return True
            currentCell = roomStack.pullEnd()

            if not roomStack.actual_list:
                log_snake.info(f"fully backtracked to start at attempt: {attempts}")
                return False

            parentCell = roomStack.peakEnd()

            tried[parentCell.hash].add((currentCell.pos[0] - parentCell.pos[0], currentCell.pos[1] - parentCell.pos[1]))

            log_snake.debug(
                f"backtracked cycle: {attempts} from cell: {currentCell.pos} to cell: {roomStack.peakEnd().pos}")

            for i, connection in enumerate(currentCell.connections):
                connection.connections.remove(currentCell)

            grid[currentCell.pos[1]][currentCell.pos[0]] = Cell(pos=currentCell.pos)
            if currentCell.hash in tried:
                del tried[currentCell.hash]

            attempts -= 1
            backTrackAttempts += 1
            continue
        else:
            if give_up_instead_of_cut: return True
            log_snake.info("backtrack failed, abandoning tail")
            times = 0
            for i in range(0, random.randint(0, roomStack.getLen())):
                roomStack.pullEnd()
                times += 1
            if roomStack.getLen() == 0:
                log_snake.warning("stack completely wiped during tail abandonment")
                return False

            log_snake.debug(f"pulled: {times}")
            continue

        if not (0 <= newX < size and 0 <= newY < size) or grid[newY][newX].placed:
            log_snake.debug("placement problem, retrying")
            continue

        new_cell = grid[newY][newX]
        new_cell.id = attempts

        new_cell.placed = True

        currentCell.connections.append(new_cell)
        new_cell.connections.append(currentCell)

        new_cell.pos = (newX, newY)
        new_cell.hash = MakeHash()

        roomStack.pushEnd(new_cell)
        attempts += 1

        log_snake.debug(f"generated cycle: {attempts}")
    return True

def TreePass(branchGridSweeps: int = 2, branchCount: int = 10, give_up_on_backtrack_threshold: int = 1000, branch_step_range: tuple[int, int] = (5, 25)):
    log_tree.info(f"starting tree pass, sweeps={branchGridSweeps}, branches={branchCount}")
    for sweep in range(0, branchGridSweeps):
        placed_cells = [cell for row in grid for cell in row if cell.placed and not "reserved" in cell.customData]
        if not placed_cells:
            return
        for i in range(branchCount):
            start = random.choice(placed_cells)
            SnakePass(
                starting_point=start,
                steps=random.randint(branch_step_range[0], branch_step_range[1]),
                give_up_on_backtrack_threshold=give_up_on_backtrack_threshold,
                give_up_instead_of_cut=True,
                give_up_instead_of_backtrack=True,
            )
    log_tree.info("tree pass complete")

def LoopPass(loopGridSweeps: int = 2, loopGenerationChance: int = 2):
    log_loop.info("starting loop pass")
    for sweep in range(0, loopGridSweeps):
        placed_cells = [cell for row in grid for cell in row if cell.placed]
        if not placed_cells:
            return

        for i in range(0, len(placed_cells)):

            loopCandidate: Cell = random.choice(placed_cells)

            if len(loopCandidate.connections) >= 4:
                continue

            log_loop.debug(f"cell selected for loopback: {loopCandidate.pos}")

            possibleDirections = []
            for directionIndex in DIR_VECTORS:
                tempCellPos = (loopCandidate.pos[0] + DIR_VECTORS[directionIndex][0],
                               loopCandidate.pos[1] + DIR_VECTORS[directionIndex][1])

                if not (0 <= tempCellPos[1] < len(grid) and 0 <= tempCellPos[0] < len(grid[0])):
                    continue

                tempCell = grid[tempCellPos[1]][tempCellPos[0]]
                if not tempCell.placed:
                    continue

                if tempCell in loopCandidate.connections or loopCandidate in tempCell.connections:
                    continue

                if len(tempCell.connections) >= 4:
                    continue

                possibleDirections.append(DIR_VECTORS[directionIndex])

            if not possibleDirections:
                continue

            chosenDir = random.choice(possibleDirections)
            otherCellPos = (loopCandidate.pos[0] + chosenDir[0], loopCandidate.pos[1] + chosenDir[1])
            otherCell: Cell = grid[otherCellPos[1]][otherCellPos[0]]

            idGapBonus = 20 if abs(otherCell.id - loopCandidate.id) > 40 else 0
            if not random.randint(0, 100) < loopGenerationChance + idGapBonus:
                continue

            otherCell.connections.append(loopCandidate)
            loopCandidate.connections.append(otherCell)
            log_loop.debug(f"placed and connected: {loopCandidate.pos}, {otherCell.pos}")
    log_loop.info("loop pass complete")

def Gen(seed: int = random.randint(0, 255), structurePath:Path=Path(f"{PROJECT_ROOT}/structures"),
        snakeSteps: int = 100, startingPoint: tuple[int, int] = (center, center),
        attemptsBeforeBacktrackGiveUp: int = 1000, noTailCutting: bool = False, noBacktracking: bool = False,
        branchCount: int = 20, branchingAttemptsBeforeBacktrackGiveUpOverride: int = 1000, branchingGridSweeps: int = 2,
        branch_step_range: tuple[int, int] = (5, 25)):
    random.seed(seed)

    GenerateStructureData(structurePath)
    #PlaceStructure(next(s for s in structureSet if s.name == "starting_room"))
    #StructurePass(structureAmount=10) #TODO fix ts
    #render(grid, size, pass_name="Struct Pass")
    log_main.info(f"starting generation with seed: {seed}")
    grid[startingPoint[0]][startingPoint[1]] = Cell(id=-1, placed=True, pos=(center, center), hash=MakeHash())
    status = SnakePass(starting_point=grid[startingPoint[0]][startingPoint[1]],
                       steps=snakeSteps,
                       give_up_on_backtrack_threshold=attemptsBeforeBacktrackGiveUp,
                       give_up_instead_of_cut=noTailCutting,
                       give_up_instead_of_backtrack=noBacktracking
                       )
    log_main.info(f"initial snake pass complete: {'step target reached' if status else 'failed to reach step target'}")
    render(grid, size, pass_name="Snake Pass")
    TreePass(branchGridSweeps=branchingGridSweeps,
             branchCount=branchCount,
             give_up_on_backtrack_threshold=branchingAttemptsBeforeBacktrackGiveUpOverride,
             branch_step_range=branch_step_range
             )
    render(grid, size, pass_name="Tree Pass")
    LoopPass()
    render(grid, size, pass_name="Loop Pass")
    log_main.info("generation finished")


Gen(snakeSteps=200, attemptsBeforeBacktrackGiveUp=1000, branchCount=25, branchingGridSweeps=2,branch_step_range=(50, 100))