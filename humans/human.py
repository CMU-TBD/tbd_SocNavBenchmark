from humans.human_appearance import HumanAppearance
from humans.human_configs import HumanConfigs
from random import seed, random, randint
from utils.utils import print_colors
import random
import string
import math
import numpy as np
import sys
import os
import pickle


class Human():

    def __init__(self, name, appearance, configs, trajectory=None):
        self.name = name
        self.appearance = appearance
        # Identity is a hashable tuple of a human's name, gender, and shape
        if appearance is None:
            self.identity = (name)
        else:
            self.identity = (name, appearance.gender, appearance.shape)
        self.configs = configs
        self.trajectory = trajectory
        self.termination = None

    # Getters for the Human class

    def get_name(self):
        return self.name

    def get_identity(self):
        return self.identity

    def get_appearance(self):
        return self.appearance

    def get_start_config(self):
        return self.configs.get_start_config()

    def get_goal_config(self):
        return self.configs.get_goal_config()

    def update_trajectory(self, trajectory):
        self.trajectory = trajectory

    def get_trajectory(self):
        return self.trajectory

    def update_termination(self, cause):
        self.termination = cause

    def get_termination(self):
        return self.termination

    def _generate_name(self, max_chars):
        return "".join([
            random.choice(string.ascii_letters + string.digits)
            for n in range(max_chars)
        ])

    def generate_human(self, appearance, configs, max_chars=20, verbose=True):
        """
        Sample a new random human from all required features
        """
        # In order to print more readable arrays
        name = self._generate_name(self, max_chars)
        np.set_printoptions(precision=2)
        pos_2 = (configs.get_start_config().position_nk2().numpy())[0][0]
        goal_2 = (configs.get_goal_config().position_nk2().numpy())[0][0]
        if(verbose):
            print(" Human", name, "at", pos_2, "with goal", goal_2)
        return Human(name, appearance, configs)

    def generate_human_with_appearance(self,
                                       appearance,
                                       environment,
                                       center=np.array([0., 0., 0.])):
        """
        Sample a new human with a known appearance at a random 
        config with a random goal config.
        """
        configs = HumanConfigs.generate_random_human_config(
            HumanConfigs, environment, center)
        return self.generate_human(self, appearance, configs)

    def generate_human_with_configs(self, configs, verbose=True):
        """
        Sample a new random from known configs and a randomized
        appearance, if any of the configs are None they will be generated
        """
        appearance = HumanAppearance.generate_random_human_appearance(HumanAppearance)
        return self.generate_human(self, appearance, configs, verbose=verbose)

    def generate_random_human_from_environment(self,
                                               environment,
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
        configs = HumanConfigs.generate_random_human_config(HumanConfigs,
                                                            environment,
                                                            center,
                                                            radius=radius)
        return self.generate_human(self, appearance, configs)
