from humans.human_appearance import HumanAppearance
from humans.human_configs import HumanConfigs
from utils.utils import print_colors, generate_name
from simulators.agent import Agent
import math, sys, os, pickle
import numpy as np



class Human(Agent):
    def __init__(self, name, appearance, start_configs, trajectory=None):
        self.name = name
        self.appearance = appearance
        super().__init__(start_configs.get_start_config(), start_configs.get_goal_config(), name)

    # Getters for the Human class
    # NOTE: most of the dynamics/configs implementation is in Agent.py
    def get_name(self):
        return self.name

    def get_appearance(self):
        return self.appearance

    @staticmethod
    def generate_human(appearance, configs, name=None, max_chars=20, verbose=False):
        """
        Sample a new random human from all required features
        """
        human_name = None
        if(name is None):
            human_name = generate_name(max_chars)
        else:
            human_name = name
        # In order to print more readable arrays
        np.set_printoptions(precision=2)
        pos_2 = (configs.get_start_config().position_nk2().numpy())[0][0]
        goal_2 = (configs.get_goal_config().position_nk2().numpy())[0][0]
        if(verbose):
            print(" Human", human_name, "at", pos_2, "with goal", goal_2)
        return Human(human_name, appearance, configs)

    @staticmethod
    def generate_human_with_appearance(appearance,
                                       environment,
                                       center=np.array([0., 0., 0.])):
        """
        Sample a new human with a known appearance at a random 
        config with a random goal config.
        """
        configs = HumanConfigs.generate_random_human_config( HumanConfigs, environment, center)
        return Human.generate_human(appearance, configs)

    @staticmethod
    def generate_human_with_configs(configs, name=None, verbose=False):
        """
        Sample a new random from known configs and a randomized
        appearance, if any of the configs are None they will be generated
        """
        appearance = HumanAppearance.generate_random_human_appearance(HumanAppearance)
        return Human.generate_human(appearance, configs, verbose=verbose, name=name)

    @staticmethod
    def generate_random_human_from_environment(environment,
                                               center=np.array([0., 0., 0.]),
                                               radius=5.,
                                               generate_appearance=False):
        """
        Sample a new human without knowing any configs or appearance fields
        NOTE: needs environment to produce valid configs
        """
        appearance = None
        if generate_appearance:
            appearance = HumanAppearance.generate_random_human_appearance(HumanAppearance)
        configs = HumanConfigs.generate_random_human_config(environment,
                                                            center,
                                                            radius=radius)
        return Human.generate_human(appearance, configs)
