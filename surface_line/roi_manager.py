import json
import os
import argparse

def save_roi(x1, y1, x2, y2, filepath="roi_config.json"):
    """保存 ROI 到 JSON 文件"""
    data = {
        "roi": [x1, y1, x2, y2]
    }
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"SUCCESS: Saved ROI {data['roi']} to {os.path.abspath(filepath)}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to save ROI: {e}")
        return False

def load_roi(filepath="roi_config.json"):
    """从 JSON 文件加载 ROI"""
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        roi = data.get("roi")
        if roi and len(roi) == 4:
            # 输出格式: x1,y1,x2,y2
            print(f"{roi[0]},{roi[1]},{roi[2]},{roi[3]}")
            return roi
        else:
            print("ERROR: Invalid ROI format in JSON")
            return None
    except Exception as e:
        print(f"ERROR: Failed to load ROI: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LabVIEW ROI Configuration Manager")
    parser.add_argument("--mode", choices=["save", "load"], required=True, help="Mode: save or load")
    parser.add_argument("--path", default="roi_config.json", help="Path to the JSON config file")
    
    # Save mode arguments
    parser.add_argument("--roi", type=str, help="ROI coordinates as 'x1,y1,x2,y2' (required for save mode)")
    
    args = parser.parse_args()
    
    if args.mode == "save":
        if not args.roi:
            print("ERROR: --roi argument is required for save mode")
        else:
            try:
                coords = [int(x) for x in args.roi.split(',')]
                if len(coords) != 4:
                    raise ValueError
                save_roi(coords[0], coords[1], coords[2], coords[3], args.path)
            except ValueError:
                print("ERROR: Invalid ROI format. Use 'x1,y1,x2,y2'")
                
    elif args.mode == "load":
        load_roi(args.path)
