import tensorflow as tf
import copy
from objectives.objective_function import ObjectiveFunction
from objectives.angle_distance import AngleDistance
from objectives.goal_distance import GoalDistance
from objectives.obstacle_avoidance import ObstacleAvoidance

from humans.human import Human
from trajectory.trajectory import SystemConfig, Trajectory
from utils.fmm_map import FmmMap
from utils.utils import print_colors
import random
import string
import math
import numpy as np
import sys
import os
import pickle


class Agent():
    def __init__(self, start, goal, planner=None):
        self.start_config = start
        self.current_config = copy.copy(start)
        self.goal_config = goal

        self.planner = planner

        self.obj_fn = None  # Until called by simulator
        self.obj_val = None

        self.fmm_map = None

        self.end_episode = False
        self.termination_cause = None
        self.episode_data = None
        self.vehicle_trajectory = None
        self.vehicle_data = None
        self.planner_data = None
        self.last_step_data_valid = None
        self.episode_type = None
        self.valid_episode = None
        self.commanded_actions_1kf = None
        self.commanded_actions_nkf = []

    def human_to_agent(self, human):
        """
        Sample a new agent from a human with configs
        """
        return Agent(human.get_start_config(), human.get_goal_config())

    def update_final(self, params):
        self.vehicle_trajectory = self.episode_data['vehicle_trajectory']
        self.vehicle_data = self.episode_data['vehicle_data']
        self.vehicle_data_last_step = self.episode_data['vehicle_data_last_step']
        self.last_step_data_valid = self.episode_data['last_step_data_valid']
        self.episode_type = self.episode_data['episode_type']
        self.valid_episode = self.episode_data['valid_episode']
        self.commanded_actions_1kf = self.episode_data['commanded_actions_1kf']
        self.obj_val = self._compute_objective_value(self.params)

    def update(self, params, system_dynamics, obstacle_map):
        if(not self.end_episode):
            if(params.verbose_printing):
                print(self.current_config.position_nk2().numpy())
            # Generate the next trajectory segment, update next config, update actions/data
            traj_segment, trajectory_data, commands_1kf = self._iterate(params, system_dynamics)
            # Append to Vehicle Data
            for key in self.vehicle_data.keys():
                self.vehicle_data[key].append(trajectory_data[key])
            self.vehicle_trajectory.append_along_time_axis(traj_segment)
            self.commanded_actions_nkf.append(commands_1kf)
            # overwrites vehicle data with last instance before termination
            # vehicle_data_last = copy.copy(vehicle_data) #making a hardcopy
            self._enforce_episode_termination_conditions(params, obstacle_map)

    def _iterate(self, params, system_dynamics):
        """ Runs the planner for one step from config to generate a
        subtrajectory, the resulting robot config after the robot executes
        the subtrajectory, and relevant planner data"""
        self.planner_data = self.planner.optimize(self.current_config, self.goal_config)
        traj_segment, trajectory_data, commands_1kf = \
            self._process_planner_data(params, system_dynamics)
        self.current_config = \
            SystemConfig.init_config_from_trajectory_time_index( traj_segment, t=-1 )
        return traj_segment, trajectory_data, commands_1kf

    def _process_planner_data(self, params, system_dynamics):
        """
        Process the planners current plan. This could mean applying
        open loop control or LQR feedback control on a system.
        """
        start_config = self.current_config
        # The 'plan' is open loop control
        if 'trajectory' not in self.planner_data.keys():
            trajectory, commanded_actions_nkf = \
                self.apply_control_open_loop(start_config,
                                             self.planner_data['optimal_control_nk2'],
                                             T=params.control_horizon-1,
                                             sim_mode=self.system_dynamics.simulation_params.simulation_mode)
        # The 'plan' is LQR feedback control
        else:
            # If we are using ideal system dynamics the planned trajectory
            # is already dynamically feasible. Clip it to the control horizon
            if system_dynamics.simulation_params.simulation_mode == 'ideal':
                trajectory = \
                    Trajectory.new_traj_clip_along_time_axis(self.planner_data['trajectory'],
                                                             params.control_horizon,
                                                             repeat_second_to_last_speed=True)
                _, commanded_actions_nkf = system_dynamics.parse_trajectory(trajectory)
            elif system_dynamics.simulation_params.simulation_mode == 'realistic':
                trajectory, commanded_actions_nkf = \
                    self.apply_control_closed_loop(start_config,
                                                   planner_data['spline_trajectory'],
                                                   planner_data['k_nkf1'],
                                                   planner_data['K_nkfd'],
                                                   T=params.control_horizon-1,
                                                   sim_mode='realistic')
            else:
                assert(False)

        self.planner.clip_data_along_time_axis(self.planner_data, params.control_horizon)
        return trajectory, self.planner_data, commanded_actions_nkf

    def _compute_objective_value(self, params):
        p = params.objective_fn_params
        if p.obj_type == 'valid_mean':
            self.vehicle_trajectory.update_valid_mask_nk()
        else:
            assert (p.obj_type in ['valid_mean', 'mean'])
        obj_val = tf.squeeze(
            self.obj_fn.evaluate_function(self.vehicle_trajectory))
        return obj_val

    def _init_obj_fn(self, p, obstacle_map):
        """
        Initialize the objective function given sim params
        """
        obj_fn = ObjectiveFunction(p.objective_fn_params)
        if not p.avoid_obstacle_objective.empty():
            obj_fn.add_objective(
                ObstacleAvoidance(params=p.avoid_obstacle_objective,
                                  obstacle_map=obstacle_map))
        if not p.goal_distance_objective.empty():
            obj_fn.add_objective(
                GoalDistance(params=p.goal_distance_objective,
                             fmm_map=obstacle_map.fmm_map))
        if not p.goal_angle_objective.empty():
            obj_fn.add_objective(
                AngleDistance(params=p.goal_angle_objective,
                              fmm_map=obstacle_map.fmm_map))
        return obj_fn

    def _init_planner(self, params):
        p = params
        return p.planner_params.planner(obj_fn=self.obj_fn,
                                        params=p.planner_params)

    def _update_fmm_map(self, params, obstacle_map):
        """
        For SBPD the obstacle map does not change,
        so just update the goal position.
        """
        goal_pos_n2 = self.goal_config.position_nk2()[:, 0]
        if self.fmm_map is not None:
            self.fmm_map.change_goal(goal_pos_n2)
        else:
            self.fmm_map = self._init_fmm_map(params, obstacle_map,
                                              goal_pos_n2)
        self._update_obj_fn(obstacle_map)

    def _init_fmm_map(self, params, obstacle_map, goal_pos_n2=None):
        p = params
        self.obstacle_occupancy_grid = \
            obstacle_map.create_occupancy_grid_for_map()

        if goal_pos_n2 is None:
            goal_pos_n2 = self.goal_config.position_nk2()[0]

        return FmmMap.create_fmm_map_based_on_goal_position(
            goal_positions_n2=goal_pos_n2,
            map_size_2=np.array(p.obstacle_map_params.map_size_2),
            dx=p.obstacle_map_params.dx,
            map_origin_2=p.obstacle_map_params.map_origin_2,
            mask_grid_mn=self.obstacle_occupancy_grid)

    def _update_obj_fn(self, obstacle_map):

        # Update the objective function to use a new
        # obstacle_map and fmm map
        # PROBABLY never going to use this

        for objective in self.obj_fn.objectives:
            if isinstance(objective, ObstacleAvoidance):
                objective.obstacle_map = obstacle_map
            elif isinstance(objective, GoalDistance):
                objective.fmm_map = self.fmm_map
            elif isinstance(objective, AngleDistance):
                objective.fmm_map = self.fmm_map
            else:
                assert (False)

    def _enforce_episode_termination_conditions(self, params, obstacle_map):
        p = params
        time_idxs = []
        for condition in p.episode_termination_reasons:
            time_idxs.append(
                self._compute_time_idx_for_termination_condition(
                    params, obstacle_map, condition))
        try:
            idx = np.argmin(time_idxs)
        except ValueError:
            idx = np.argmin([time_idx.numpy() for time_idx in time_idxs])

        try:
            termination_time = time_idxs[idx].numpy()
        except ValueError:
            termination_time = time_idxs[idx]

        if termination_time != np.inf:
            end_episode = True
            for i, condition in enumerate(p.episode_termination_reasons):
                if (time_idxs[i].numpy() != np.inf):
                    color = "green"
                    if (condition is "Timeout"):
                        color = "blue"
                    elif (condition is "Collision"):
                        color = "red"
                    self.termination_cause = color
                    print(print_colors()[color], "Terminated due to",
                          condition,
                          print_colors()["reset"])
                    if (condition is "Timeout"):
                        print(print_colors()["blue"], "Max time:",
                              p.episode_horizon,
                              print_colors()["reset"])
            # clipping the trajectory only ends it early, we want it to actually reach the goal
            # vehicle_trajectory.clip_along_time_axis(termination_time)
            self.planner_data, planner_data_last_step, last_step_data_valid = \
                self.planner.mask_and_concat_data_along_batch_dim(
                    self.planner_data,
                    k=termination_time
                )
            commanded_actions_1kf = tf.concat(self.commanded_actions_nkf,
                                              axis=1)[:, :termination_time]

            # If all of the data was masked then
            # the episode simulated is not valid
            valid_episode = True
            if self.planner_data['system_config'] is None:
                valid_episode = False
            episode_data = {
                'vehicle_trajectory': self.vehicle_trajectory,
                'vehicle_data': self.planner_data,
                'vehicle_data_last_step': planner_data_last_step,
                'last_step_data_valid': last_step_data_valid,
                'episode_type': idx,
                'valid_episode': valid_episode,
                'commanded_actions_1kf': commanded_actions_1kf
            }
        else:
            end_episode = False
            episode_data = {}
        self.end_episode = end_episode
        self.episode_data = episode_data

    def _compute_time_idx_for_termination_condition(self, params, obstacle_map,
                                                    condition):
        """
        For a given trajectory termination condition (i.e. timeout, collision, etc.)
        computes the earliest time index at which this condition is met. Returns
        infinity if a condition is not met.
        """
        if condition == 'Timeout':
            time_idx = self._compute_time_idx_for_timeout(params)
        elif condition == 'Collision':
            time_idx = self._compute_time_idx_for_collision(
                obstacle_map, params)
        elif condition == 'Success':
            time_idx = self._compute_time_idx_for_success(params)
        else:
            raise NotImplementedError

        return time_idx

    def _compute_time_idx_for_timeout(self, params):
        """
        If vehicle_trajectory has exceeded episode_horizon,
        return episode_horizon, else return infinity.
        """
        if self.vehicle_trajectory.k >= params.episode_horizon:
            time_idx = tf.constant(params.episode_horizon)
        else:
            time_idx = tf.constant(np.inf)
        return time_idx

    def _compute_time_idx_for_collision(self, obstacle_map, params):
        """
        Compute and return the earliest time index of collision in vehicle
        trajectory. If there is no collision return infinity.
        """
        pos_1k2 = self.vehicle_trajectory.position_nk2()
        obstacle_dists_1k = obstacle_map.dist_to_nearest_obs(pos_1k2)
        collisions = tf.where(tf.less(obstacle_dists_1k, 0.0))
        collision_idxs = collisions[:, 1]
        if tf.size(collision_idxs).numpy() != 0:
            time_idx = collision_idxs[0]
        else:
            time_idx = tf.constant(np.inf)
        return time_idx

    def _dist_to_goal(self, use_euclidean=False):
        """Calculate the FMM distance between
        each state in trajectory and the goal."""
        for objective in self.obj_fn.objectives:
            if isinstance(objective, GoalDistance):
                euclidean = 0
                # also compute euclidean distance as a heuristic
                if use_euclidean:
                    diff_x = self.vehicle_trajectory.position_nk2(
                    )[0][-1][0] - self.goal_config.position_nk2()[0][0][0]
                    diff_y = self.vehicle_trajectory.position_nk2(
                    )[0][-1][1] - self.goal_config.position_nk2()[0][0][1]
                    euclidean = np.sqrt(diff_x**2 + diff_y**2)
                dist_to_goal_nk = objective.compute_dist_to_goal_nk(
                    self.vehicle_trajectory) + euclidean
        return dist_to_goal_nk

    def _compute_time_idx_for_success(self, params):
        """
        Compute and return the earliest time index of success (reaching the goal region)
        in vehicle trajectory. If there is no collision return infinity.
        """
        dist_to_goal_1k = self._dist_to_goal(use_euclidean=False)
        successes = tf.where(tf.less(dist_to_goal_1k, params.goal_cutoff_dist))
        success_idxs = successes[:, 1]
        if tf.size(success_idxs).numpy() != 0:
            time_idx = success_idxs[0]
        else:
            time_idx = tf.constant(np.inf)
        return time_idx

    def apply_control_open_loop(self, start_config, control_nk2,
                                T, sim_mode='ideal'):
        """
        Apply control commands in control_nk2 in an open loop
        fashion to the system starting from start_config.
        """
        x0_n1d, _ = self.system_dynamics.parse_trajectory(start_config)
        applied_actions = []
        states = [x0_n1d*1.]
        x_next_n1d = x0_n1d*1.
        for t in range(T):
            u_n1f = control_nk2[:, t:t+1]
            x_next_n1d = self.system_dynamics.simulate(
                x_next_n1d, u_n1f, mode=sim_mode)

            # Append the applied action to the action list
            if sim_mode == 'ideal':
                applied_actions.append(u_n1f)
            elif sim_mode == 'realistic':
                # TODO: This line is intended for a real hardware setup.
                # If running this code on a real robot the user will need to
                # implement hardware.state_dx such that it reflects the current
                # sensor reading of the robot's applied actions
                applied_actions.append(
                    np.array(self.system_dynamics.hardware.state_dx*1.)[None, None])
            else:
                assert(False)

            states.append(x_next_n1d)

        commanded_actions_nkf = tf.concat([control_nk2[:, :T], u_n1f], axis=1)
        u_nkf = tf.concat(applied_actions, axis=1)
        x_nkd = tf.concat(states, axis=1)
        trajectory = self.system_dynamics.assemble_trajectory(x_nkd,
                                                              u_nkf,
                                                              pad_mode='repeat')
        return trajectory, commanded_actions_nkf

    def apply_control_closed_loop(self, start_config, trajectory_ref,
                                  k_array_nTf1, K_array_nTfd, T,
                                  sim_mode='ideal'):
        """
        Apply LQR feedback control to the system to track trajectory_ref
        Here k_array_nTf1 and K_array_nTfd are tensors of dimension
        (n, self.T-1, f, 1) and (n, self.T-1, f, d) respectively.
        """
        with tf.name_scope('apply_control'):
            x0_n1d, _ = self.system_dynamics.parse_trajectory(start_config)
            assert(len(x0_n1d.shape) == 3)  # [n,1,x_dim]
            angle_dims = self.system_dynamics._angle_dims
            commanded_actions_nkf = []
            applied_actions = []
            states = [x0_n1d*1.]
            x_ref_nkd, u_ref_nkf = self.system_dynamics.parse_trajectory(
                trajectory_ref)
            x_next_n1d = x0_n1d*1.
            for t in range(T):
                x_ref_n1d, u_ref_n1f = x_ref_nkd[:, t:t+1], u_ref_nkf[:, t:t+1]
                error_t_n1d = x_next_n1d - x_ref_n1d

                # TODO: Currently calling numpy() here as tfe.DEVICE_PLACEMENT_SILENT
                # is not working to place non-gpu ops (i.e. mod) on the cpu
                # turning tensors into numpy arrays is a hack around this.
                error_t_n1d = tf.concat([error_t_n1d[:, :, :angle_dims],
                                         angle_normalize(
                                             error_t_n1d[:, :, angle_dims:angle_dims+1].numpy()),
                                         error_t_n1d[:, :, angle_dims+1:]],
                                        axis=2)
                fdback_nf1 = tf.matmul(K_array_nTfd[:, t],
                                       tf.transpose(error_t_n1d, perm=[0, 2, 1]))
                u_n1f = u_ref_n1f + tf.transpose(k_array_nTf1[:, t] + fdback_nf1,
                                                 perm=[0, 2, 1])

                x_next_n1d = self.system_dynamics.simulate(
                    x_next_n1d, u_n1f, mode=sim_mode)

                commanded_actions_nkf.append(u_n1f)
                # Append the applied action to the action list
                if sim_mode == 'ideal':
                    applied_actions.append(u_n1f)
                elif sim_mode == 'realistic':
                    # TODO: This line is intended for a real hardware setup.
                    # If running this code on a real robot the user will need to
                    # implement hardware.state_dx such that it reflects the current
                    # sensor reading of the robot's applied actions
                    applied_actions.append(
                        np.array(self.system_dynamics.hardware.state_dx*1.)[None, None])
                else:
                    assert(False)

                states.append(x_next_n1d)

            commanded_actions_nkf.append(u_n1f)
            commanded_actions_nkf = tf.concat(commanded_actions_nkf, axis=1)
            u_nkf = tf.concat(applied_actions, axis=1)
            x_nkd = tf.concat(states, axis=1)
            trajectory = self.system_dynamics.assemble_trajectory(x_nkd,
                                                                  u_nkf,
                                                                  pad_mode='repeat')
            return trajectory, commanded_actions_nkf