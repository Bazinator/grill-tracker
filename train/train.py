import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the steak detector")
    parser.add_argument("--data", required=True, help="Path to the dataset data.yaml")
    parser.add_argument("--model", default="yolov12n.pt", help="Base or checkpoint weights")
    parser.add_argument("--epochs", type=int, default=150)
    args = parser.parse_args()

    YOLO(args.model).train(
        data=args.data,
        epochs=args.epochs,
        imgsz=640,
        batch=0.8,
        device=0,
        lr0=0.01,
        mosaic=1.0,
        degrees=15.0,
        hsv_v=0.2,
        hsv_s=0.3,
        patience=75,
    )


if __name__ == "__main__":
    main()
