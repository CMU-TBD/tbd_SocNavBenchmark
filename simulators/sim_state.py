import tensorflow as tf
from simulators.agent import Agent
from humans.human import Human

""" These are smaller "wrapper" classes that are visible by other 
agents/humans and saved during state deepcopies
NOTE: they are all READ-ONLY (only getters)
"""



class AgentState():
    def __init__(self, a, deepcpy=False):
        self.name = a.get_name()
        self.start_config = a.get_start_config()
        self.goal_config = a.get_goal_config()
        self.current_config = a.get_current_config(deepcpy=deepcpy)
        self.vehicle_trajectory = a.get_trajectory(deepcpy=deepcpy)
        self.collided = a.get_collided()
        self.end_acting = a.end_acting

    def get_name(self):
        return self.name
    def get_current_config(self):
        return self.current_config
    def get_start_config(self):
        return self.start_config
    def get_goal_config(self):
        return self.goal_config
    def get_trajectory(self):
        return self.vehicle_trajectory
    def get_collided(self):
        return self.collided

class HumanState(AgentState):
    def __init__(self, human, deepcpy=False):
        self.name = human.get_name()
        self.appearance = human.get_appearance()
        # Initialize the agent state class
        super().__init__(human, deepcpy=deepcpy)
    def get_appearance(self):
        return self.appearance

class SimState():
    def __init__(self, environment, agents, prerecs, robots, sim_time, wall_time):
        self.environment = environment
        self.agents = agents
        self.prerecs = prerecs
        self.robots = robots
        self.sim_t = sim_time
        self.wall_t = wall_time

    def get_environment(self):
        return self.environment

    def get_map(self):
        return self.environment["traversibles"][0]

    def get_agents(self):
        return self.agents

    def get_prerecs(self):
        return self.prerecs

    def get_robots(self):
        return self.robots

    def get_sim_t(self):
        return self.sim_t
    
    def get_wall_t(self):
        return self.wall_t

