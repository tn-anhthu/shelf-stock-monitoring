from src.detection.train.convert import coco_bbox_to_yolo_line, coco_objects_to_yolo_lines


def test_coco_bbox_to_yolo_line_converts_center_and_normalizes():
    # box at (10, 20) size 30x40 in a 100x200 image
    # center = (10+15, 20+20) = (25, 40) -> normalized (0.25, 0.2)
    # size normalized = (30/100, 40/200) = (0.3, 0.2)
    line = coco_bbox_to_yolo_line((10.0, 20.0, 30.0, 40.0), image_width=100, image_height=200)
    assert line == "0 0.250000 0.200000 0.300000 0.200000"


def test_coco_bbox_to_yolo_line_uses_given_class_id():
    line = coco_bbox_to_yolo_line((0.0, 0.0, 10.0, 10.0), image_width=10, image_height=10, class_id=3)
    assert line.startswith("3 ")


def test_coco_objects_to_yolo_lines_handles_multiple_boxes():
    bboxes = [(0.0, 0.0, 10.0, 10.0), (5.0, 5.0, 10.0, 10.0)]
    lines = coco_objects_to_yolo_lines(bboxes, image_width=20, image_height=20)
    assert len(lines) == 2
    assert lines[0] == "0 0.250000 0.250000 0.500000 0.500000"
    assert lines[1] == "0 0.500000 0.500000 0.500000 0.500000"


def test_coco_objects_to_yolo_lines_empty_returns_empty():
    assert coco_objects_to_yolo_lines([], image_width=100, image_height=100) == []
