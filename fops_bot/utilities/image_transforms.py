import cv2
import logging
import textwrap
import numpy as np


from PIL import Image, ImageDraw, ImageFont


def generate_underlay(
    base_x: int,
    base_y: int,
    top_left: tuple,
    top_right: tuple,
    bottom_right: tuple,
    bottom_left: tuple,
    sub_image: Image.Image,
) -> Image.Image:
    """
    Warps a smaller image onto a square region on a larger base image.
    Was REALLY unhappy that this was so hard to do in pillow so this is
    a DEDICATED function just to do this one kinda complex and annoying task.

    Args:
        base_x (int): Width of the base image.
        base_y (int): Height of the base image.
        top_left (tuple): (x, y) coordinates for the top-left corner.
        top_right (tuple): (x, y) coordinates for the top-right corner.
        bottom_right (tuple): (x, y) coordinates for the bottom-right corner.
        bottom_left (tuple): (x, y) coordinates for the bottom-left corner.
        sub_image (PIL.Image.Image): The smaller image to warp.

    Returns:
        PIL.Image.Image: The final image with the sub_image warped onto it.
    """
    # Create the base image
    base_image = np.zeros((base_y, base_x, 3), dtype=np.uint8)

    # Convert sub_image (PIL) to OpenCV format
    sub_image_cv = cv2.cvtColor(np.array(sub_image), cv2.COLOR_RGB2BGR)
    sub_h, sub_w, _ = sub_image_cv.shape

    # Define source and destination points for perspective warp
    src_pts = np.float32([[0, 0], [sub_w, 0], [sub_w, sub_h], [0, sub_h]])
    dst_pts = np.float32([top_left, top_right, bottom_right, bottom_left])

    # Compute perspective transform matrix
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # Warp the sub_image
    warped_sub_image = cv2.warpPerspective(sub_image_cv, matrix, (base_x, base_y))

    # Create a mask from the warped sub-image
    mask = np.zeros((base_y, base_x), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(dst_pts), 255)

    # Blend the images
    base_image = cv2.bitwise_and(base_image, base_image, mask=cv2.bitwise_not(mask))
    result = cv2.add(base_image, warped_sub_image)

    # Convert back to PIL for return
    final_image = Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    return final_image


def fit_text_to_region(
    draw: ImageDraw.Draw,
    text: str,
    region: tuple,
    font_path: str,
    max_font_size: int = 100,
) -> (tuple, str):
    """
    Fit text to a specified rectangular region with simple line wrapping.

    Args:
        draw (ImageDraw.Draw): ImageDraw instance for the image.
        text (str): Text to render.
        region (tuple): (x, y, width, height) defining the region.
        font_path (str): Path to the font file.
        max_font_size (int): Maximum font size to attempt.

    Returns:
        tuple: (ImageFont.FreeTypeFont, str) The best fitting font and wrapped text.
    """

    x, y, width, height = region
    font_size = max_font_size

    lines = textwrap.fill(text, width=24)

    logging.info(f"The text is {lines}")

    while font_size > 0:
        font = ImageFont.truetype(font_path, font_size)

        bbox = draw.textbbox((0, 0), lines, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if text_width <= width and text_height <= height:
            return font, lines
        font_size -= 1

    return (
        ImageFont.truetype(font_path, 1),
        lines,
    )  # Default to smallest font if none fits
