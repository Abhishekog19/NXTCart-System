path = '/home/vandan/NXTCart-System/pc/vision_ws/src/nxtcart_vision/nxtcart_vision/node.py'
text = open(path).read()
text = text.replace(
    "self.get_logger().error(f'Backend unavailable: {exc}')",
    "import traceback\n            traceback.print_exc()\n            self.get_logger().error(f'Backend unavailable: {exc}')"
)
open(path, 'w').write(text)
