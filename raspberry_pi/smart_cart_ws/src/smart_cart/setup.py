import os
from glob import glob
from setuptools import setup

package_name = 'smart_cart'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'database'),
            glob('database/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vandant',
    maintainer_email='vandant@todo.todo',
    description='Smart shopping cart verification system',
    license='MIT',
    entry_points={
        'console_scripts': [
            'core_logic         = smart_cart.core_logic:main',
            'gui_display        = smart_cart.gui_display:main',
            'qr_scanner_node    = smart_cart.qr_scanner_node:main',
            'real_weight_node   = smart_cart.real_weight_node:main',
            'camera_stream_node = smart_cart.camera_stream_node:main',
        ],
    },
)
