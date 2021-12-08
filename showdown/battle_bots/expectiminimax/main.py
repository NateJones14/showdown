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

bannedMoves = set(['voltswitch', 'uturn', 'outrage', 'petaldance', 'partingshot'])

#state depth -> value move
def expectiminimax(state,depth):
    #if depth = 0 or game_over return value - in expectiminimax
    gameOver = state.battle_is_finished()
    if gameOver:
        if gameOver == 1:
            return (float("inf"), None)
        else:
            return (float("-inf"), None)

    if depth == 0:
        return (evaluate(state), None)
    #get all availible moves - get_transitions()
    possibleMoves = getAvailableMoves(state)
    moveValueDict = {}
    for movePair in possibleMoves:
        #apply movePair -> get all possible states + probability
        stateProbList = getResultingStatesAndProbs(state, movePair)
        totalValue = 0
        for stateProb in stateProbList:
            #call expectiminimax on the next states -> get that state's value
            val = expectiminimax(stateProb[0], depth - 1)[0]
            #multiply probability * value and add them up
            totalValue = totalValue + (val * stateProb[1])
        moveValueDict[movePair] = totalValue
    #Best Min Pair of Value and Bot_Move
    bestMinPair = calculateBestPair(moveValueDict)

    #return the "best" new_state (and maybe the move associated with it) - in get_dominant_move
    return bestMinPair
    
#dict [(movePair) -> (value)] -> value move
def calculateBestPair(moveValueDict):
    moveMins = {}
    
    #find the minimum of each move
    for movePair in moveValueDict:
        if movePair[0] not in moveMins:
            moveMins[movePair[0]] = moveValueDict[movePair]
        else:
            if moveMins[movePair[0]] > moveValueDict[movePair]:
                moveMins[movePair[0]] = moveValueDict[movePair]
    
    #take the maximum of those minimums
    bestMinPair = None
    for move in moveMins:
        if bestMinPair == None:
            bestMinPair = (moveMins[move], move)
        else:
            if bestMinPair[0] < moveMins[move]:
                bestMinPair = (moveMins[move], move)

    return bestMinPair

#state [pair of moves] -> list of pair of state and float
def getResultingStatesAndProbs(state,movePair):
    StateProbPairs = []
    #get list of possible outcomes (as instructions to state on how to proceed)
    outcomes = get_all_state_instructions(StateMutator(state),movePair[0],movePair[1])
    for outcome in outcomes:
        mutator = StateMutator(copy.deepcopy(state))
        #apply the instructions to get the outcome
        mutator.apply(outcome.instructions)
        newState = mutator.state
        #add the outcome state and outcome percentage to list
        StateProbPairs.append((newState,outcome.percentage))
    return StateProbPairs
        
#state -> list of pair of moves
def getAvailableMoves(state):
    userOptions, opponentOptions = state.get_all_options()
    userOptions = list(set(userOptions) - bannedMoves)
    return list(itertools.product(userOptions, opponentOptions))

#list of pair of value and move -> move
#given the best move/value from each possible version of the battle, return a given move
def pickMoveFromBattles(bestMovesList):
    moveCounter = Counter([moveVal[1] for moveVal in bestMovesList])
    return moveCounter.most_common(1)[0][0]

class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def find_best_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        bestMovesList = []
        for b in battles:
            val, bestMove = expectiminimax(b.create_state(), config.search_depth)
            bestMovesList.append((val,bestMove))
        bestMove = pickMoveFromBattles(bestMovesList)
        return format_decision(self, bestMove)
        