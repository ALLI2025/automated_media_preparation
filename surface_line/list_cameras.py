import cv2

def list_cameras():
    print("Searching for cameras...")
    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"Found camera at index {i} (DSHOW)")
            available_cameras.append(i)
            cap.release()
        else:
            # Try default backend
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Found camera at index {i} (Default)")
                available_cameras.append(i)
                cap.release()
            else:
                print(f"No camera at index {i}")
    
    if not available_cameras:
        print("No cameras found.")
    else:
        print(f"Available camera indices: {available_cameras}")

if __name__ == "__main__":
    list_cameras()
