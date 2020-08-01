import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.preprocessing.text import Tokenizer
    tf.enable_eager_execution()
import threading
import socket
import time
from simulators.joystick import Joystick
from utils.utils import print_colors


def test_joystick():
    # TODO: rename controller to joystick
    J = Joystick()
    J.establish_robot_sender_connection()
    J.establish_robot_receiver_connection()
    J.update()


if __name__ == '__main__':
    test_joystick()
