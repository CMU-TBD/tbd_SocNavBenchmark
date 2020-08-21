import numpy as np
import os
import sys
import math
import matplotlib.pyplot as plt

from params.central_params import create_sbpd_simulator_params, create_base_params
from trajectory.trajectory import SystemConfig
from simulators.sbpd_simulator import SBPDSimulator
from humanav.humanav_renderer_multi import HumANavRendererMulti
from humans.human import Human
from humanav import sbpd
from random import seed, random, randint
from utils.utils import touch


def create_params():
    p = create_base_params()

    # Set any custom parameters
    return p


def test_planner():
    p = create_params()
    # Create planner parameters
    sim_params = create_simulator_params()
    sim = SBPDSimulator(sim_params)

    # Spline trajectory params
    n = 1
    dt = 0.1

    # Goal states and initial speeds
    goal_pos_n11 = np.array([[[12., 18.75]]
                             ])  # Goal position (must be 1x1x2 array)
    goal_heading_n11 = np.array([[[-np.pi / 2.]]])
    # Start states and initial speeds
    start_pos_n11 = np.array([[[27.75, 25.]]
                              ])  # Goal position (must be 1x1x2 array)
    start_heading_n11 = np.array([[[np.pi]]])
    start_speed_nk1 = np.ones((1, 1, 1), dtype=np.float32)
    # Define start and goal configurations
    start_config = SystemConfig(dt,
                                n,
                                k=1,
                                position_nk2=start_pos_n11,
                                heading_nk1=start_heading_n11,
                                speed_nk1=start_speed_nk1,
                                variable=False)
    goal_config = SystemConfig(dt,
                               n,
                               k=1,
                               position_nk2=goal_pos_n11,
                               heading_nk1=goal_heading_n11,
                               variable=True)
    sim.reset_with_start_and_goal(start_config, goal_config)
    sim.simulate()
    # Visualization
    fig = plt.figure(figsize=(30, 10))
    plt.rcParams.update({'font.size': 22})
    ax = fig.add_subplot(1, 3, 1)
    sim.render(ax, markersize=10)
    ax = fig.add_subplot(1, 3, 2)
    sim.render(ax, zoom=4, markersize=20)
    ax = fig.add_subplot(1, 3, 3)
    sim.vehicle_trajectory.render(ax, freq=1, plot_quiver=False)
    sim._render_waypoints(ax,
                          plot_quiver=True,
                          plot_text=False,
                          text_offset=(0, 0),
                          markersize=20)
    file_name = os.path.join(p.humanav_dir,
                             'tests/visual-nav/test_simulator.png')
    if (not os.path.exists(file_name)):
        print('\033[31m', "Failed to find:", file_name, '\033[33m',
              "and therefore it will be created", '\033[0m')
        touch(file_name)  # Just as the bash command
    fig.savefig(file_name, bbox_inches='tight', pad_inches=0)
    print('\033[32m', "Successfully rendered:", file_name, '\033[0m')


if __name__ == '__main__':
    test_planner()
