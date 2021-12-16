from constants import BOOST_RESET_MOVES
from showdown.battle import Battle
from showdown.engine.evaluate import evaluate
from showdown.engine.find_state_instructions import get_all_state_instructions
from ..helpers import format_decision
from showdown.engine.objects import State
from showdown.engine.objects import StateMutator
from showdown.engine.select_best_move import pick_safest
from showdown.engine.select_best_move import get_payoff_matrix

import config
from collections import Counter
import logging
logger = logging.getLogger(__name__)
import itertools
import math
import copy
import random
import time
#outline of file:
#BattleBot has find_best_move() which calls monteCarloTreeSearch()
# - monteCarloTreeSearch() calls:
#   - runIteration (runs a playout)
#       - getExplorationScore (gets exploration score for nodes)
#       - getAvailableMoves (gets possible next moves from a state)
#       - applyMove (applies the given move)
#   - runSimulation (runs random simulation/playout from the node)
#       - getRandomOutcome (selects a random outcome after applying a move)
#   - mostPlayedMove (selects the child node with the most playouts)



#moves that alter tree shape/structure through two moves in one turn
bannedMoves = set(['voltswitch', 'uturn', 'outrage', 'petaldance', 'partingshot', 'flipturn', 'teleport'])
oppBannedMoves = set(['voltswitch', 'uturn', 'partingshot', 'flipturn', 'teleport'])
#constants used in MCTS 
iterations = 2500 #number of playouts
explorationConstant = math.sqrt(2)
maxdepth = 20

#class representing a node in a tree that is used for MCTS
#has the ability to run a MCTS playout from this node and return the best move from this node
class MCTSNode():
    def __init__(self,state,depth): 
        self.wins = 0
        self.total = 0
        #state this node represents
        self.state = state
        #map from movepair to child node
        self.children = {}
        self.nextMoves = getAvailableMoves(state)
        self.leaf = True
        self.endNode = state.battle_is_finished() 
        self.depth = depth

    # float -> boolean
    #runs a MCTS iteration (selection,expansion,simulation,backpropagation)
    #boolean returned = if this node resulted in a win or loss (during backpropgataion)
    #starting_eval used when maxDepth is reached to decide if playout should be marked as a win or loss
    def runIteration(self, starting_eval):
        self.total += 1
        #edge cases: game is over; there is nothing left to simulate (all of opponents pokemon unknown); max depth reached
        if self.endNode == 1:
            self.wins += 1
            return True
        if self.endNode == -1:
            return False
        if not simulationOngoing(self.state) or self.depth >= maxdepth:
            if starting_eval <= evaluate(self.state):
                self.wins += 1
                return True
            else:
                return False

        #if leaf
        # -choose an unexplored child node
        # -run simulation from that child
        # -update win/loss when value returned
        if self.leaf: 
            nextMove = random.choice(list(set(self.nextMoves) - set(self.children.keys())))
            nextState = applyMove(self.state,nextMove)
            self.children[nextMove] = MCTSNode(nextState, self.depth + 1)
            result = runSimulation(nextState, self.depth + 1, starting_eval)
            if result:
                self.wins += 1
                self.children[nextMove].wins += 1
            self.children[nextMove].total += 1
            if len(self.children) == len(self.nextMoves):
                self.leaf = False
            return result
        else:

            #if non-leaf:
            #   -choose child node (based on exploration score equation)
            #   -call runIteration on child
            #   -update win/loss when value is returned
            maxScore = float("-inf")
            maxChild = None
            for move,child in self.children.items():
                score = getExplorationScore(self,child)
                if score > maxScore:
                    maxScore = score
                    maxChild = child

            result = maxChild.runIteration(starting_eval)
            if result:
                self.wins += 1
            return result

    #return the move with the most playouts
    def mostPlayedMove(self):
        #choose move with highest denominator
        highestTotal = 0
        mostPlayedMove = None
        for movepair,child in self.children.items():
            if mostPlayedMove is None:
                mostPlayedMove = movepair
                highestTotal = child.total
            if highestTotal < child.total:
                mostPlayedMove = movepair
                highestTotal = child.total

        return mostPlayedMove[0]

#state int float -> boolean
#runs a random-move simulation from the starting point 
#   - starting_depth is how deep the starting node is (runs until maxDepth)
#   - starting_eval is evaluation of root node (used to compare vs final node to decide if win or loss)
#returns true if win should be recorded
#returns false if loss should be recorded
def runSimulation(state, starting_depth, starting_eval):
    moveSimList = []
    depth = starting_depth
    sim_count = 0
    simulationState = StateMutator(copy.deepcopy(state))
    while simulationOngoing(simulationState.state):
        if depth > maxdepth:
            break
        depth += 1
        possibleMoves = getAvailableMoves(simulationState.state)
        nextMove = random.choice(possibleMoves)
        simulationState = getRandomOutcome(simulationState, nextMove)
        #print(sim_count)
        moveSimList.append(nextMove)
        if sim_count == 100:
            print(moveSimList)
            print(simulationState.state)
            print(possibleMoves)
        sim_count += 1
    return starting_eval <= evaluate(simulationState.state)

#state -> boolean
#whether there is more to simulate in the battle
def simulationOngoing(state):
    if state.battle_is_finished():
        return False
    oppHP = state.opponent.active.hp 
    oppHP += sum([pok.hp for pok in state.opponent.reserve.values()])
    if oppHP <= 0:
        return False
    return True

#StateMutator MovePair -> StateMutator
#returns a statemutator based on picking a random outcome from a move (random = based on outcome probabilties)
def getRandomOutcome(stateMutator,move):
    outcomes = get_all_state_instructions(stateMutator,move[0],move[1])
    #use outcome% to get random state
    rand = random.random()
    randOutcome = None
    curPercent = 0

    for outcome in outcomes:
        
        curPercent = curPercent + outcome.percentage
        if curPercent > rand:
            randOutcome = outcome
            break

    #apply random instruction based on percentages
    stateMutator.apply(randOutcome.instructions)

    return stateMutator

#state movepair -> state
#returns the state of the likeliest outcome after the move is applied
def applyMove(state, move):
    outcomes = get_all_state_instructions(StateMutator(state),move[0],move[1])
    #return most likely state
    mostLikely = None
    bestPercent = 0
    for outcome in outcomes:
        #find most likely outcome
        if mostLikely is None:
            mostLikely = outcome
            bestPercent = outcome.percentage
        if outcome.percentage > bestPercent:
            mostLikely = outcome
            bestPercent = outcome.percentage
    mutator = StateMutator(copy.deepcopy(state))
    mutator.apply(mostLikely.instructions)

    return mutator.state

#Node Node -> Number
def getExplorationScore(parentNode, childNode):
    exploitation = childNode.wins / childNode.total
    exploration = explorationConstant * math.sqrt(math.log(parentNode.total) / childNode.total)
    return exploitation + exploration

#State -> Action
#performs a MCTS from a given root state
def monteCarloTreeSearch(state):
    #special case where a switch is forced for both players
    if state.self.active.hp <= 0 and state.opponent.active.hp <= 0:
        userOptions, _ = state.get_all_options()
        userOptions = [uO for uO in userOptions if "switch" in uO]
        return random.choice(userOptions)

    #run for at least 5 seconds regardless of iterations (can go over the max_num to reach 5 seconds)
    #don't run for more than 15 seconds (stops short of max_num if hits 15 seconds)
    root = MCTSNode(state,0)
    starting_eval = evaluate(state)
    t_min = time.time() + 5
    t_max = time.time() + 15
    iterationCount = 0
    while time.time() < t_max:
        if iterationCount >= iterations and t_min > time.time():
            break
        root.runIteration(starting_eval)
        iterationCount += 1
    return root.mostPlayedMove()


#state -> list of pair of moves
#gets all the possible move pairs that exist in a position
def getAvailableMoves(state):
    userOptions, opponentOptions = state.get_all_options()
    userOptions = list(set(userOptions) - bannedMoves)
    opponentOptions = list(set(opponentOptions) - oppBannedMoves)
    return list(itertools.product(userOptions, opponentOptions))

"""
#list of pair of value and move -> move
#given the best move/value from each possible version of the battle, return a given move
def pickMoveFromBattles(bestMovesList):
    moveCounter = Counter(bestMovesList)
    return moveCounter.most_common(1)[0][0]
"""

#class representing a bot that selects move based on a MCTS algorithm
class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)
    
    # -> move
    #selects the best move in the position
    def find_best_move(self):
        #prepare_battles -> creates multiple battle instances where each permutation of possible move sets is a new battle
        #   ex: opponent can have either moves 1,2,3,4 or moves 1,2,3,5 so creates 2 battles for each permutation
        battles = self.prepare_battles(join_moves_together=True)
        #pick a random instantiation or calculate for each
        #   -random instantiation is a close enough approximation since one move different doesn't change a lot
        #   -random instantiation saves a LOT of time as well
        """
        bestMovesList = []
        for b in battles:
            bestMove = monteCarloTreeSearch(b.create_state())
            bestMovesList.append(bestMove)
        bestMove = pickMoveFromBattles(bestMovesList)
        """
        bestMove = monteCarloTreeSearch(random.choice(battles).create_state())
        return format_decision(self, bestMove)