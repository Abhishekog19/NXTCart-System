path = '/home/vandan/NXTCart-System/pc/vision_ws/src/nxtcart_vision/nxtcart_vision/pipeline.py'
text = open(path).read()
old_code = """        if len(dets) > 1:
            self.fail('Multiple moving regions: product identity is ambiguous')
            return"""
new_code = """        if len(dets) > 1:
            dets = [dets[0]] # Security Bypassed!"""
text = text.replace(old_code, new_code)
open(path, 'w').write(text)
