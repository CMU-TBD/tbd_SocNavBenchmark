from utils.utils import print_colors, generate_name
from simulators.agent import Agent
from humans.human_configs import HumanConfigs
from trajectory.trajectory import SystemConfig
import numpy as np
import socket, time, threading

class RoboAgent(Agent):
    def __init__(self, name, start_configs, trajectory=None):
        self.name = name
        self.commands = []
        self.running = False
        self.freq = 100. # update frequency
        # sockets for communication
        self.controller_socket = None
        self.port = 6000
        self.host = None
        super().__init__(start_configs.get_start_config(), start_configs.get_goal_config(), name)

    # Getters for the Human class
    # NOTE: most of the dynamics/configs implementation is in Agent.py
    def get_name(self):
        return self.name

    @staticmethod
    def generate_robot(configs, name=None, verbose=False):
        """
        Sample a new random robot agent from all required features
        """
        robot_name = None
        if(name is None):
            robot_name = generate_name(20)
        else:
            robot_name = name
        # In order to print more readable arrays
        np.set_printoptions(precision=2)
        pos_2 = (configs.get_start_config().position_nk2().numpy())[0][0]
        goal_2 = (configs.get_goal_config().position_nk2().numpy())[0][0]
        if(verbose):
            print("Robot", robot_name, "at", pos_2, "with goal", goal_2)
        return RoboAgent(robot_name, configs)

    @staticmethod
    def generate_random_robot_from_environment(environment,
                                               center=np.array([0., 0., 0.]),
                                               radius=5.):
        """
        Sample a new robot without knowing any configs or appearance fields
        NOTE: needs environment to produce valid configs
        """
        configs = HumanConfigs.generate_random_human_config(environment,
                                                            center,
                                                            radius=radius)
        return RoboAgent.generate_robot(configs)

    def execute(self, command_indx):
        current_config = self.get_current_config()
        # TODO: perhaps make the control loop run multiple commands rather than one
        command = np.array([[self.commands[command_indx]]], dtype=np.float32)
        # NOTE: the format for the acceleration commands to the open loop for the robot is:
        # np.array([[[L, A]]], dtype=np.float32) where L is linear, A is angular
        t_seg, actions_nk2 = self.apply_control_open_loop(current_config,   
                                                        command, 1, sim_mode='ideal'
                                                        )
        # act trajectory segment
        self.current_config = \
                    SystemConfig.init_config_from_trajectory_time_index(
                    t_seg,
                    t=-1
                )
        if (self.params.verbose):
            print(self.get_current_config().to_3D_numpy())

    def update(self):
        print("Robot powering on")
        listen_thread = threading.Thread(target=self.listen, args=(None,None))
        listen_thread.start()
        self.running = True
        self.last_command = None
        num_executed = 0 # keeps track of the latest command that is to be executed
        while(self.running):
            # only execute the most recent commands
            if(num_executed < len(self.commands)):
                self.execute(num_executed)
                num_executed += 1
            time.sleep(1./self.freq)
        print("\nRobot powering off, took", len(self.commands),"commands")
        listen_thread.join()
 

    """BEGIN socket utils"""

    def update_host_port(self, host, port):
        # Define host
        if(host is None):
            self.host = socket.gethostname()
        else:
            self.host = host
        # Define the communication port
        if (port is None):
            self.port = 6000 # default port
        else:
            self.port = port

    def listen(self, host=None, port=None):
        self.controller_socket.listen(10)
        self.running = True # initialize listener
        while(self.running):
            connection, client = self.controller_socket.accept()
            while(True): # constantly taking in information until breaks
                # TODO: allow for buffered data, thus no limit
                data = connection.recv(128)
                # quickly close connection to open up for the next input
                connection.close()
                # NOTE: data is in the form (running, time, lin_command, ang_command)
                # TODO: use ast.literal_eval instead of eval to
                data = eval(data)
                np_data = np.array([data[2], data[3]], dtype=np.float32)
                # NOTE: commands can also be a dictionary indexed by time
                self.commands.append(np_data)
                if(data[0] is False):
                    self.running = False
                break
        self.controller_socket.close()
        self.controller_socket.shutdown()

    def establish_controller_connection(self, port, host=None):
        """This is akin to a server connection (controller is server)"""
        self.controller_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.update_host_port(host, port)
        self.controller_socket.bind((self.host, self.port))
        # wait for a connection
        self.controller_socket.listen(1)
        connection, client = self.controller_socket.accept()
        return connection, client

    """ END socket utils """