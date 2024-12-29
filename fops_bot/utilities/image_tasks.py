from PIL import Image
from utilities.image_utils import register_image_task
from utilities.perspective import generate_underlay


@register_image_task("browsingfox")
def browsing_fox_task(input_image: Image.Image) -> Image.Image:
    frame = Image.open("fops_bot/templates/browsing_fox_bk.png")

    # Get image dimensions from frame
    base_x, base_y = frame.size

    result = generate_underlay(
        base_x, base_y, (290, 180), (540, 170), (540, 345), (276, 350), input_image
    )

    result.paste(frame, (0, 0), frame)
    return result
