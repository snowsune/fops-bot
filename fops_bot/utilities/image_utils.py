import io
import logging

from PIL import Image, UnidentifiedImageError, ImageDraw
from typing import Callable, Dict

# Registry for image manipulation tasks
IMAGE_TASKS: Dict[str, Callable[[Image.Image], Image.Image]] = {}


def register_image_task(name: str, requires_attachment: bool = True):
    """
    Decorator to register an image task.

    :param name: The name of the task.
    :param requires_attachment: Whether the task requires an image attachment.
    """

    def decorator(func: Callable[..., Image.Image]):
        IMAGE_TASKS[name] = {
            "func": func,
            "requires_attachment": requires_attachment,
        }
        logging.info(
            f"Registered task '{name}' (Attachment Required: {requires_attachment})"
        )
        return func

    return decorator


def apply_image_task(task_name: str, *args, **kwargs) -> Image.Image:
    """
    Apply a registered image task.

    :param task_name: The task to apply.
    :param args: Arguments to pass to the task.
    :param kwargs: Keyword arguments to pass to the task.
    :return: The resulting image.
    """
    if task_name not in IMAGE_TASKS:
        raise ValueError(f"Task '{task_name}' is not registered.")

    task_func = IMAGE_TASKS[task_name]["func"]
    return task_func(*args, **kwargs)


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """
    Load an PIL image from bytes.

    :param image_bytes: The image data in bytes.
    :return: A PIL Image.
    """
    try:
        return Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError as e:
        logging.error(f"Failed to load image: {e}")
        raise


def save_image_to_bytes(image: Image.Image) -> bytes:
    """
    Save a PIL Image to bytes.

    :param image: The PIL Image.
    :return: Image data as bytes.
    """
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()