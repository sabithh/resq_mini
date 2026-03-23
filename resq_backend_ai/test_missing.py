from ultralytics import YOLO

def main():
    model = YOLO("yolov8m-pose.pt")
    results = model("static/latest_annotated.jpg", conf=0.15)
    
    print("\n--- yolov8m-pose.pt ---")
    persons = [box for r in results for box in r.boxes if int(box.cls) == 0]
    print(f"Total persons: {len(persons)}")
    for p in persons:
        print(f"Conf: {float(p.conf):.2f}, Box: {p.xyxy[0].tolist()}")

    print("\n--- yolov8m.pt ---")
    model2 = YOLO("yolov8m.pt")
    results2 = model2("static/latest_annotated.jpg", conf=0.15)
    persons2 = [box for r in results2 for box in r.boxes if int(box.cls) == 0]
    print(f"Total persons: {len(persons2)}")
    for p in persons2:
        print(f"Conf: {float(p.conf):.2f}, Box: {p.xyxy[0].tolist()}")


if __name__ == "__main__":
    main()
