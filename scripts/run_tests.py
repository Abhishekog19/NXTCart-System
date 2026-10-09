"""Run source checks and hardware-independent suites from any directory."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def source_checks():
    ignored = {'build', 'build-v2', 'install', 'install-v2', 'log', 'log-v2', '__pycache__', '.venv', '.venV'}
    count = 0
    for root in [ROOT/'pc', ROOT/'raspberry_pi', ROOT/'tests', ROOT/'scripts']:
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ignored and not d.endswith('.egg-info')]
            for name in files:
                path = Path(folder)/name
                if path.suffix == '.py':
                    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
                    count += 1
                elif name == 'package.xml':
                    ET.parse(path)
    pi = ROOT/'raspberry_pi/smart_cart_ws/src/smart_cart_interfaces'
    pc = ROOT/'pc/vision_ws/src/smart_cart_interfaces'
    for path in pi.rglob('*'):
        if path.is_file():
            other = pc/path.relative_to(pi)
            if not other.is_file() or path.read_bytes() != other.read_bytes():
                raise RuntimeError(f'ROS contracts differ: {path.relative_to(pi)}; run scripts/sync_interfaces.py')
    for folder, forbidden in [
        (ROOT/'raspberry_pi/smart_cart_ws/src/smart_cart/smart_cart', {'ml', 'torch', 'tensorflow', 'onnxruntime', 'nxtcart_vision'}),
        (ROOT/'pc/vision_ws/src/nxtcart_vision/nxtcart_vision', {'smart_cart'}),
    ]:
        for path in folder.glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                if any(module.split('.')[0] in forbidden for module in modules):
                    raise RuntimeError(f'Deployment boundary violation: {path}')
    print(f'PASS: {count} Python sources, package XML, ROS contracts and deployment boundaries', flush=True)


def main():
    source_checks()
    env = os.environ.copy()
    env['NXTCART_PI_PATH'] = str(ROOT/'raspberry_pi')
    env['PYTHONPATH'] = str(ROOT/'pc')
    for cwd, arguments in [
        (ROOT, ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        (ROOT/'pc', ['-m', 'unittest', 'test_ai_references', '-v']),
        (ROOT/'pc', ['test_verify.py']),
    ]:
        subprocess.run([sys.executable, '-B', *arguments], cwd=cwd, env=env, check=True)
    print('All software checks passed.', flush=True)


if __name__ == '__main__':
    main()
