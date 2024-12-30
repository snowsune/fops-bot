import logging

from PIL import Image, ImageDraw

from utilities.image_utils import register_image_task
from utilities.image_transforms import generate_underlay, fit_text_to_region


@register_image_task("Browsing Fox", requires_attachment=True)
def browsing_fox_task(input_image: Image.Image) -> Image.Image:
    frame = Image.open("fops_bot/templates/browsing_fox_bk.png")

    # Get image dimensions from frame
    base_x, base_y = frame.size

    result = generate_underlay(
        base_x, base_y, (290, 180), (540, 170), (540, 345), (276, 350), input_image
    )

    result.paste(frame, (0, 0), frame)
    return result


@register_image_task("Fox-Top", requires_attachment=True)
def browsing_fox_task(input_image: Image.Image) -> Image.Image:
    frame = Image.open("fops_bot/templates/foxtop.png")

    # Get image dimensions from frame
    base_x, base_y = frame.size

    result = generate_underlay(
        base_x, base_y, (110, 155), (260, 136), (267, 240), (119, 275), input_image
    )

    result.paste(frame, (0, 0), frame)
    return result


@register_image_task("Vixi Says", requires_attachment=False)
def vixi_says_task(message: str) -> Image.Image:
    logging.info(f"Processing vixisays with message: {message}")

    # Load the base template
    frame = Image.open("fops_bot/templates/vixisays.png")

    # Define text region (x, y, width, height)
    text_region = (360, 120, 900 - 360, 400 - 120)  # Adjust as needed for your template

    # Initialize drawing context
    draw = ImageDraw.Draw(frame)

    # Fit the text into the specified region
    font, lines = fit_text_to_region(
        draw, message, text_region, "fops_bot/templates/impact.ttf", max_font_size=100
    )

    # Get the position to start drawing text (top-left corner of the region)
    x, y, _, _ = text_region

    # Render the text onto the image
    draw.text((x, y), lines, font=font, fill=(255, 255, 255))

    return frame


@register_image_task("Soy Point", requires_attachment=True)
def browsing_fox_task(input_image: Image.Image) -> Image.Image:
    frame = Image.open("fops_bot/templates/soy.png")

    # Get image dimensions from frame
    base_x, base_y = frame.size

    result = generate_underlay(
        base_x,
        base_y,
        (1250, 700),  # Top Left
        (2960, 700),  # Top Right
        (2960, 2000),  # Bottom Right
        (1250, 2000),  # Bottom Left
        input_image,
        alpha=True,
    )

    result.paste(frame, (0, 0), frame)
    return result
