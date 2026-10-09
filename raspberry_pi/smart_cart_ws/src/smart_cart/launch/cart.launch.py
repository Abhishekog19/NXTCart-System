"""Compatibility entry point for the Pi runtime."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    path = os.path.join(get_package_share_directory('smart_cart'), 'launch', 'pi_sensors.launch.py')
    return LaunchDescription([IncludeLaunchDescription(PythonLaunchDescriptionSource(path))])
