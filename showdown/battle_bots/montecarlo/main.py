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


bannedMoves = set(['voltswitch', 'uturn', 'outrage'])
iterations = 100
explorationConstant = math.sqrt(2)

class MCTSNode():
    def __init__(self,state): 
        self.wins = 0
        self.total = 0
        #state this node represents
        self.state = state
        #map from movepair to child node
        self.children = {}
        self.nextMoves = getAvailableMoves(state)

    def runIteration(self):
        leaf = not len(self.children) == len(self.nextMoves) 
        if leaf:
            gameOverCheck = self.state.battle_is_finished()
            if gameOverCheck:
                if gameOverCheck == 1:
                    self.wins += 1
                self.total += 1
                return gameOverCheck

            #if leaf:
            #   -choose child
            #   -run simulation starting from that child
            #   -update child win/loss and our win/loss
            #   -return result of win/loss
            nextMove = random.choice(list(set(self.nextMoves) - set(self.children.keys())))
            nextState = applyMove(self.state,nextMove,True)
            self.children[nextMove] = MCTSNode(nextState)
            result = runSimulation(nextState)
            if result:
                self.wins += 1
                self.children[nextMove].wins += 1
            self.total += 1      
            self.children[nextMove].total += 1
            return result



        else:
            #if non-leaf:
            #   -choose child node
            #   -call runIteration on child
            #   -update win/loss when value is returned
            maxScore = float("-inf")
            maxChild = None
            for move,child in self.children.items():
                score = getExplorationScore(self,child)
                if score > maxScore:
                    maxScore = score
                    maxChild = child

            result = maxChild.runIteration()
            if result:
                self.wins += 1
            self.total += 1
            return result

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

#state -> boolean
def runSimulation(state):
    depth = 1
    currentState = copy.deepcopy(state)
    while simulationOngoing(currentState):
        depth += 1
        possibleMoves = getAvailableMoves(currentState)
        nonSwitchPossibleMoves = [pM for pM in possibleMoves if "switch" not in pM[0] and "switch" not in pM[1]]
        nextMove = random.choice(possibleMoves)
        print(str(nextMove))
        nextState = applyMove(currentState, nextMove)
        currentState = copy.deepcopy(nextState)

    return not currentState.battle_is_finished() == -1

#state -> boolean
def simulationOngoing(state):
    #whether there is more to simulate in the battle
    if state.battle_is_finished():
        return False
    oppHP = state.opponent.active.hp 
    oppHP += sum([pok.hp for pok in state.opponent.reserve.values()])
    if oppHP == 0:
        return False
    return True


#state movepair -> state
def applyMove(state, move, likeliest=False):
    outcomes = get_all_state_instructions(StateMutator(state),move[0],move[1])
    if likeliest:
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
        
    else:
        #use outcome% to get random state
        rand = random.random()
        randOutcome = None
        curPercent = 0
        #may need to normalize?
        for outcome in outcomes:
            
            curPercent = curPercent + outcome.percentage
            if curPercent > rand:
                randOutcome = outcome

        mutator = StateMutator(copy.deepcopy(state))
        #apply random instruction based on percentages
        mutator.apply(randOutcome.instructions)

        return mutator.state

#Node Node -> Number
def getExplorationScore(parentNode, childNode):
    exploitation = childNode.wins / childNode.total
    exploration = explorationConstant * math.sqrt(math.log(parentNode.total) / childNode.total)
    return exploitation + exploration

#State -> Action
def monteCarloTreeSearch(state):
    root = MCTSNode(state)
    for i in range(iterations):
        root.runIteration()
    return root.mostPlayedMove()


#state -> list of pair of moves
def getAvailableMoves(state):
    userOptions, opponentOptions = state.get_all_options()
    userOptions = list(set(userOptions) - bannedMoves)
    return list(itertools.product(userOptions, opponentOptions))

#list of pair of value and move -> move
#given the best move/value from each possible version of the battle, return a given move
def pickMoveFromBattles(bestMovesList):
    moveCounter = Counter(bestMovesList)
    return moveCounter.most_common(1)[0][0]

class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def find_best_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        bestMovesList = []
        for b in battles:
            print("b")
            bestMove = monteCarloTreeSearch(b.create_state())
            print("b over")
            bestMovesList.append(bestMove)
        print("so close")
        bestMove = pickMoveFromBattles(bestMovesList)
        print("done")
        return format_decision(self, bestMove)