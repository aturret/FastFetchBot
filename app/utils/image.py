from PIL import Image
import asyncio
from app.config import env

DEFAULT_IMAGE_LIMITATION = env.get("DEFAULT_IMAGE_LIMITATION", 1600)


def get_image_dimension(image_file: str):
    image = Image.open(image_file)
    return image.size


def image_compressing(image: Image, limitation: int = DEFAULT_IMAGE_LIMITATION):
    new_image = image
    if image.size[0] > limitation or image.size[1] > limitation:
        if image.size[0] > image.size[1]:
            new_image = image.resize(
                (limitation, int(image.size[1] * limitation / image.size[0])),
                Image.Resampling.LANCZOS,
            )
        else:
            new_image = image.resize(
                (int(image.size[0] * limitation / image.size[1]), limitation),
                Image.Resampling.LANCZOS,
            )
    return new_image
