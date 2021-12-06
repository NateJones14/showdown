import constants
from data import all_move_json
from showdown.battle import Battle
from showdown.engine.damage_calculator import calculate_damage
from showdown.engine.find_state_instructions import update_attacking_move
from ..helpers import format_decision
import random

class BattleBot(Battle):
    def init(self, args, **kwargs):
        super(BattleBot, self).init(args, **kwargs)

    def find_best_move(self):
        state = self.create_state()
        my_options = self.get_all_options()[0]
        choice = random.choice(my_options)
        return format_decision(self, choice)