import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    root = LaunchConfiguration('cam_root')
    defaults = {
        'cam_root': os.environ.get('NXTCART_CAM_PATH', os.path.expanduser('~/NXTCart-System/pc')),
        'model_path': PathJoinSubstitution([root, 'ml', 'mobilenet_v2.onnx']),
        'database_path': PathJoinSubstitution([root, 'embedding_db.pkl']),
        'catalog_path': '', 'preview': 'false',
        'debug_dir': PathJoinSubstitution([root, 'debug_frames']),
        'config_file': PathJoinSubstitution([root, 'config', 'verification.yaml']),
    }
    args = [DeclareLaunchArgument(k, default_value=v) for k,v in defaults.items()]
    params = {k: ParameterValue(LaunchConfiguration(k), value_type=bool if k == 'preview' else str)
              for k in defaults if k != 'config_file'}
    return LaunchDescription(args + [Node(package='nxtcart_vision', executable='vision_verify_node',
        output='screen', parameters=[LaunchConfiguration('config_file'), params])])
