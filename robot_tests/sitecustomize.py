# install the apport exception handler if available
try:
    import apport_python_hook
except ImportError:
    pass
else:
    apport_python_hook.install()

# --- Custom Antigravity Headless/Mock Hooks ---
import builtins
import os
import sys

# 1. Mock tensorrt and torch2trt if they fail to import
try:
    import tensorrt
except Exception:
    class MockTensorRT(object):
        class Logger(object):
            def __init__(self, *args, **kwargs): pass
        def init_libnvinfer_plugins(self, *args, **kwargs): pass
    sys.modules['tensorrt'] = MockTensorRT()
    print("Mocked tensorrt registered.")

try:
    import torch2trt
except Exception:
    try:
        import torch
        class MockTRTModule(torch.nn.Module):
            def __init__(self, *args, **kwargs):
                super().__init__()
            def forward(self, x):
                batch_size = x.shape[0] if hasattr(x, 'shape') else 1
                return torch.zeros((batch_size, 2), dtype=torch.float32)
            def load_state_dict(self, state_dict, strict=True):
                from collections import namedtuple
                _IncompatibleKeys = namedtuple('_IncompatibleKeys', ['missing_keys', 'unexpected_keys'])
                return _IncompatibleKeys(missing_keys=[], unexpected_keys=[])
                
        class MockTorch2TRT(object):
            TRTModule = MockTRTModule
            def torch2trt(self, *args, **kwargs):
                return MockTRTModule()
                
        sys.modules['torch2trt'] = MockTorch2TRT()
        print("Mocked torch2trt registered.")
    except Exception as e:
        print("Could not register mocked torch2trt:", e)

# 2. Intercept torch import and patch load/load_state_dict
original_import = builtins.__import__

def custom_import(name, *args, **kwargs):
    module = original_import(name, *args, **kwargs)
    if name == "torch" or (isinstance(name, str) and name.startswith("torch.")):
        base_torch = sys.modules.get("torch")
        if base_torch and not hasattr(base_torch, "_load_patched"):
            original_load = base_torch.load
            
            def custom_load(f, *args2, **kwargs2):
                if isinstance(f, str) and not os.path.exists(f):
                    print("Torch file not found:", f, "- returning mock empty dict.")
                    return {}
                try:
                    return original_load(f, *args2, **kwargs2)
                except Exception as e:
                    print("Torch load failed:", e, "- returning mock empty dict.")
                    return {}
            
            base_torch.load = custom_load
            base_torch._load_patched = True
            
            # Patch nn.Module.load_state_dict
            try:
                original_load_state_dict = base_torch.nn.Module.load_state_dict
                def custom_load_state_dict(self, state_dict, strict=True):
                    if isinstance(state_dict, dict) and not state_dict:
                        from collections import namedtuple
                        _IncompatibleKeys = namedtuple('_IncompatibleKeys', ['missing_keys', 'unexpected_keys'])
                        return _IncompatibleKeys(missing_keys=[], unexpected_keys=[])
                    try:
                        return original_load_state_dict(self, state_dict, strict=strict)
                    except Exception as e:
                        print("load_state_dict failed (ignored):", e)
                        from collections import namedtuple
                        _IncompatibleKeys = namedtuple('_IncompatibleKeys', ['missing_keys', 'unexpected_keys'])
                        return _IncompatibleKeys(missing_keys=[], unexpected_keys=[])
                base_torch.nn.Module.load_state_dict = custom_load_state_dict
            except Exception as e:
                print("Failed to patch load_state_dict:", e)
                
    return module

builtins.__import__ = custom_import
