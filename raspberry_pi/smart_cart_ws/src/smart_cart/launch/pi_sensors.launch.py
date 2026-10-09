"""All cart hardware and display on the Pi. No inference or cloud API here."""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    defaults = {'serial_port': '/dev/ttyACM0', 'baud_rate': '115200',
                'qr_camera': '/dev/video0', 'verification_camera': '/dev/video2',
                'catalog_path': os.path.expanduser('~/nxtcart/inventory.db'),
                'state_path': os.path.expanduser('~/nxtcart/cart_state.db'), 'upi_payee': ''}
    args = [DeclareLaunchArgument(k, default_value=v) for k, v in defaults.items()]
    def value(name, kind=str):
        return ParameterValue(LaunchConfiguration(name), value_type=kind)
    nodes = [
        Node(package='smart_cart', executable='core_logic', output='screen', parameters=[{
            'catalog_path': value('catalog_path'), 'state_path': value('state_path'),
            'upi_payee': value('upi_payee')}]),
        Node(package='smart_cart', executable='real_weight_node', output='screen', parameters=[{
            'serial_port': value('serial_port'), 'baud_rate': value('baud_rate', int)}]),
        Node(package='smart_cart', executable='qr_scanner_node', output='screen',
             parameters=[{'camera_source': value('qr_camera')}]),
        Node(package='smart_cart', executable='camera_stream_node', output='screen',
             parameters=[{'camera_source': value('verification_camera')}]),
        Node(package='smart_cart', executable='gui_display', output='screen')]
    return LaunchDescription(args+nodes)
