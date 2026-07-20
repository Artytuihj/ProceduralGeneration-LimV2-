import random
from dataclasses import dataclass, field

from render import render
from stack import Stack

@dataclass
class Cell:
    id:int = 0
    hash:int = 0
    connections:list[Cell] = field(default_factory=list)
    pos:tuple[int,int] = (0,0)
    placed:bool = False

DIR_VECTORS = {0:(0,-1),1:(-1,0),2:(0,1),3:(1,0)}

size = 100
center = round(size/2)
grid = [[Cell() for _ in range(size)] for _ in range(size)]

def MakeHash() -> int:
    return random.getrandbits(255)

def SnakePass(starting_point,steps,give_up_on_backtrack_threshold,give_up_instead_of_cut:bool = False,give_up_instead_of_backtrack:bool=False):

    roomStack = Stack()
    roomStack.pushEnd(starting_point)

    tried = {}

    backTrackAttempts = 0
    attempts = 0
    while attempts < steps:
        print(f"[ \nentering cycle: {attempts}")

        currentCell = roomStack.peakEnd()
        currentCellId = currentCell.hash
        print(f"generating from: ({roomStack.peakEnd().pos[0]},{roomStack.peakEnd().pos[1]}) of object : {currentCellId}")
        possible_dirs = [d for d in DIR_VECTORS if DIR_VECTORS[d] not in tried.setdefault(currentCellId, set())]


        if possible_dirs:
            print("attempting to generate dir vector")
            direction = DIR_VECTORS[possible_dirs[random.randint(0, len(possible_dirs) - 1)]]
            tried[currentCellId].add(direction)
            newX, newY = currentCell.pos[0] + direction[0], currentCell.pos[1] + direction[1]
            print(f"dir vector and next coords are generated: coords:({newX}, {newY}), dir: {direction}")
        elif backTrackAttempts < give_up_on_backtrack_threshold:
            if give_up_instead_of_backtrack: return True
            print("attempting to backtrack")
            currentCell = roomStack.pullEnd()

            if not roomStack.actual_list:
                print(f"!!fully backtracked to start!! at attempt: {attempts}\n]")
                return False

            parentCell = roomStack.peakEnd()

            tried[parentCell.hash].add(( currentCell.pos[0] - parentCell.pos[0],currentCell.pos[1] - parentCell.pos[1]))

            print(f"backtracked cycle: {attempts} from cell: {currentCell.pos} to cell: {roomStack.peakEnd().pos}")
        
            for i, connection in enumerate(currentCell.connections):
                connection.connections.remove(currentCell)

            grid[currentCell.pos[1]][currentCell.pos[0]] = Cell(pos= currentCell.pos)
            if currentCell.hash in tried:
                del tried[currentCell.hash]

            print(f"cleared cell {currentCell.pos}")
            attempts -=1
            backTrackAttempts += 1
            continue
        else:
            if give_up_instead_of_cut: return True
            print("backtrack failed... abandoning tail")
            times = 0
            print(roomStack.getLen())
            for i in range(0,random.randint(0,roomStack.getLen())):
                roomStack.pullEnd()
                times +=1
            print(roomStack.getLen())
            if roomStack.getLen() == 0:
                print("!!Stack completely wiped during tail abandonment!!")
                return False

            print(f"pulled: {times}")
            continue

        if not (0 <= newX < size and 0 <= newY < size) or grid[newY][newX].placed:
            print("!placement problem! retrying... \n]")
            continue

        new_cell = grid[newY][newX]
        new_cell.id = attempts

        new_cell.placed = True

        currentCell.connections.append(new_cell)
        new_cell.connections.append(currentCell)

        new_cell.pos = (newX,newY)
        new_cell.hash = MakeHash()

        roomStack.pushEnd(new_cell)
        attempts += 1

        print(f"generated cycle: {attempts}") #on pos: {newX},{newY}\n ]")
    return True

def TreePass(branchGridSweeps:int= 2,branchCount:int= 10, give_up_on_backtrack_threshold:int= 1000, branch_step_range:tuple[int, int]= (5, 25)):
    for sweep in range(0,branchGridSweeps):
        placed_cells = [cell for row in grid for cell in row if cell.placed]
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

def LoopPass(loopGridSweeps: int = 2, loopGenerationChance: int = 2):
    print("starting loop pass")
    for sweep in range(0, loopGridSweeps):
        placed_cells = [cell for row in grid for cell in row if cell.placed]
        if not placed_cells:
            return

        for i in range(0, len(placed_cells)):

            loopCandidate: Cell = random.choice(placed_cells)

            if len(loopCandidate.connections) >= 4:
                continue

            print(f"Cell selected for loopback: {loopCandidate.pos}")

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
            print(f"placed and connected: {loopCandidate.pos}, {otherCell.pos}")




def Gen(seed:int=random.randint(0,255),
        snakeSteps:int=100, startingPoint:tuple[int,int] = (center,center), attemptsBeforeBacktrackGiveUp:int=1000,noTailCutting:bool=False, noBacktracking:bool=False,
        branchCount:int=20,branchingAttemptsBeforeBacktrackGiveUpOverride:int=1000,branchingGridSweeps:int=2,branch_step_range:tuple[int, int]= (5, 25)):
    random.seed(seed)
    print(seed)
    grid[startingPoint[0]][startingPoint[1]] = Cell(id=-1, placed=True, pos=(center, center), hash=MakeHash())
    print("starting generation")
    status = SnakePass(starting_point=grid[startingPoint[0]][startingPoint[1]],
                       steps=snakeSteps,
                       give_up_on_backtrack_threshold=attemptsBeforeBacktrackGiveUp,
                        give_up_instead_of_cut = noTailCutting,
                        give_up_instead_of_backtrack = noBacktracking
                       )
    print(f"the generation of the initial snake was complete with status: {"Step target reached successfully" if status else "Failed to reach step target"}")
    render(grid, size, pass_name="Snake Pass")
    TreePass(branchGridSweeps=branchingGridSweeps,
             branchCount=branchCount,
             give_up_on_backtrack_threshold=branchingAttemptsBeforeBacktrackGiveUpOverride,
             branch_step_range=branch_step_range
             )
    print("rendered map")
    print("All Finished")
    render(grid, size, pass_name="Tree Pass")
    LoopPass()
    render(grid, size, pass_name="Loop Pass")


Gen(snakeSteps=2000,attemptsBeforeBacktrackGiveUp=100000,branchCount=25,branchingGridSweeps=4,branch_step_range=(50,100))
