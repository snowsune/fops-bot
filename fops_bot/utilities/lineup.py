from PIL import Image, ImageDraw, ImageOps, ImageColor
import os
import json

# Define the root path for data and silhouettes
root_path = "species_data/"
silhouettes_dir = os.path.join(root_path, "silhouettes/")


def load_species_data():
    with open(os.path.join(root_path, "species_data.json"), "r") as file:
        return json.load(file)


species_data = load_species_data()


def load_image(file_path):
    try:
        img = Image.open(file_path)
        return img.convert("RGBA")  # Ensure all images are in RGBA mode
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None


def highlight_user_image(img, hex_color):
    """Highlight the user's image with the specified hex color while preserving transparency."""
    if img.mode == "RGBA":
        alpha = img.getchannel("A")
        img = ImageOps.colorize(ImageOps.grayscale(img), (0, 0, 0), hex_color)
        img.putalpha(alpha)
    return img


def add_grid(draw, image_width, image_height, foot_pixels=144):
    line_color = (169, 169, 169)  # Dark grey
    for y in range(0, image_height, foot_pixels):
        draw.line((0, y, image_width, y), fill=line_color)


def generate(user_species, user_gender, user_height):
    images = []
    relative_heights = sorted(species_data.items(), key=lambda x: x[1][user_gender])
    user_index = next(
        i for i, (spec, _) in enumerate(relative_heights) if spec == user_species
    )

    # Select two smaller and two larger species, if available
    species_indices = range(
        max(0, user_index - 1), min(len(relative_heights), user_index + 2)
    )
    selected_species = [relative_heights[i][0] for i in species_indices]

    # Calculate scaling factor for images
    user_spec_height = species_data[user_species][user_gender]
    standard_height = 1200  # Standard height for user's species
    max_above_standard = 400
    scale_factor = standard_height / user_spec_height

    # Load and scale images
    max_height = standard_height
    for species in selected_species:
        gender_key = f"{user_gender[0]}_{species}.png"
        img_path = os.path.join(silhouettes_dir, gender_key)
        img = load_image(img_path)
        if img:
            species_height = species_data[species][user_gender] * scale_factor
            scaled_img = img.resize(
                (int(img.width * species_height / img.height), int(species_height)),
                Image.Resampling.LANCZOS,
            )
            images.append((species, scaled_img))

            # This limits the maximum oversize-ness we can have
            max_height = min(
                max(max_height, scaled_img.height), standard_height + max_above_standard
            )

    # Create new image with background and grid
    width = sum(img.width for _, img in images) + 50
    height = int(1.05 * max_height)
    lineup_image = Image.new("RGBA", (width, height), (211, 211, 211, 255))
    draw = ImageDraw.Draw(lineup_image)
    add_grid(draw, width, height)

    # Paste images onto the canvas
    x_offset = 10
    for species, img in images:
        if species == user_species:
            img = highlight_user_image(img, species_data[species]["color"])
        paste_height = height - img.height - 10
        lineup_image.paste(
            img, (x_offset, paste_height), img if img.mode == "RGBA" else None
        )
        x_offset += img.width + 10

    # Save the final lineup image
    lineup_image.save("lineup.png")
    print("Lineup image saved as lineup.png")


if __name__ == "__main__":
    generate("fox", "male", 72)  # Example usage
