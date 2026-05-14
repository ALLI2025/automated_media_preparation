import sys
try:
    import harvesters
    print("harvesters: installed")
except ImportError:
    print("harvesters: not installed")

try:
    import pylablib
    print("pylablib: installed")
except ImportError:
    print("pylablib: not installed")

try:
    import cv2
    print("cv2: installed")
except ImportError:
    print("cv2: not installed")
