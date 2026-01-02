"""
grid.py

Grid mapping module for ResQ-Drone Simulator.
Assigns detected victims to grid coordinates for spatial organization.
"""

def assign_grid(
    victim: dict,
    image_width: int,
    image_height: int,
    rows: int = 10,
    cols: int = 10
) -> dict:
    """
    Assign grid coordinates to a single victim detection.

    Args:
        victim: Detection dictionary containing bbox_xyxy
        image_width: Width of the image in pixels
        image_height: Height of the image in pixels
        rows: Number of grid rows
        cols: Number of grid columns

    Returns:
        Victim dictionary enriched with:
        - grid: [row, col]
    """

    x1, y1, x2, y2 = victim["bbox_xyxy"]

    # Compute center of bounding box
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    # Normalize coordinates
    nx = cx / image_width
    ny = cy / image_height

    # Map to grid
    grid_col = int(nx * cols)
    grid_row = int(ny * rows)

    # Clamp values
    grid_col = max(0, min(grid_col, cols - 1))
    grid_row = max(0, min(grid_row, rows - 1))

    victim["grid"] = [grid_row, grid_col]

    return victim
