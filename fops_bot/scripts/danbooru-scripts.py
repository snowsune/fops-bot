import os
import requests
import argparse


def check_image_exists(file_path, danbooru_url, api_key, username):
    url = f"{danbooru_url}/iqdb_queries.json"
    with open(file_path, "rb") as file:
        files = {"search[file]": file}

        print(f"Checking if {file_path} exists on the server via {url}")

        # Using HTTP Basic Auth for API key and username
        response = requests.post(url, files=files, auth=(username, api_key))

        if response.status_code == 201:
            results = response.json()
            # Assuming the first result is the most relevant
            if results and "post" in results[0]:
                if int(results[0]["score"]) < 85:
                    print("Confidence too low, assuming no matches")
                    return None

                post_id = results[0]["post_id"]
                print(f"Image {file_path} already exists with post ID {post_id}.")
                return post_id

            else:
                print(f"Image {file_path} does not exist on the server.")
                return None
        else:
            print(f"Failed to check {file_path}. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None


# Function to upload an image
def upload_image(api_key, username, danbooru_url, file_path):
    url = f"{danbooru_url}/uploads.json?api_key={api_key}&login={username}"

    files = {"upload[files][0]": open(file_path, "rb")}

    print(f"Uploading {file_path} to {url}")

    response = requests.post(url, files=files)

    if response.status_code == 201:
        print(f"File {file_path} uploaded")
        upload_id = response.json().get(
            "id"
        )  # This is the upload id, not the actual media ID.

        print(f"Getting ID for {upload_id}")
        req = requests.get(
            f"https://booru.kitsunehosting.net/uploads/{upload_id}.json?api_key={api_key}&login={username}"
        )
        asset_id = req.json()["upload_media_assets"][0]["id"]

        print(
            f"Uploaded {file_path} successfully with upload ID {upload_id}, asset ID {asset_id}."
        )
        return asset_id
    else:
        print(f"Failed to upload {file_path}. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return None


# Function to process an upload
def create_post(api_key, username, danbooru_url, upload_id, tags, rating):
    url = f"{danbooru_url}/posts.json?api_key={api_key}&login={username}"
    data = {
        "upload_media_asset_id": upload_id,
        "post[tag_string]": f" {tags}",
        "post[rating]": rating,
        # "post[artist_commentary_desc]": "File uploaded by Vixi's archive manager, there may be missing tags and data!",
    }

    print(f"Posting upload ID {upload_id}, tags '{tags}', rating {rating}")

    response = requests.post(url, data=data)
    if response.status_code == 201:
        post_id = response.json().get("id")

        print(f"Posted upload ID {upload_id} successfully, new post_id is {post_id}")

        return post_id
    else:
        print(
            f"Failed to post upload ID {upload_id}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")


def create_pool(api_key, username, danbooru_url, pool_name, pool_ids):
    url = f"{danbooru_url}/pools.json?api_key={api_key}&login={username}"

    data = {
        "pool[name]": pool_name,
        "pool[category]": "series",
        "pool[post_ids_string]": " ".join(str(_id) for _id in pool_ids),
    }

    print(f"Creating a pool with ids {pool_ids}, name '{pool_name}'")

    response = requests.post(url, data=data)

    if response.status_code == 201:
        print(f"Posted pool! '{pool_name}'")
    else:
        print(
            f"Failed to create pool '{pool_name}' with ids {pool_ids}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")


def main():
    parser = argparse.ArgumentParser(description="Upload images to a Danbooru server.")
    parser.add_argument("username", type=str, help="Your username")
    parser.add_argument("api_key", type=str, help="API key for the Danbooru server")
    parser.add_argument("danbooru_url", type=str, help="URL of the Danbooru server")
    parser.add_argument(
        "directory", type=str, help="Directory containing images to upload"
    )

    args = parser.parse_args()

    # Bools and storage
    generate_pool = False
    pool_ids = []

    # Get tags and rating from user
    tags = input("Enter tags (space-separated): ")
    rating = input("Enter rating (s for safe, q for questionable, e for explicit): ")
    pool_name = input("Generate a pool? (My_Pool_Name): ")
    generate_pool = len(pool_name) > 1

    if generate_pool:
        print(f"Will generate pool {pool_name}")
    print("\n")

    # Ensure rating is valid
    if rating not in ["s", "q", "e"]:
        print(
            "Invalid rating. Use 's' for safe, 'q' for questionable, 'e' for explicit."
        )
        exit(1)

    # List image files in the specified directory
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webm", ".mp4")
    image_files = [
        f for f in os.listdir(args.directory) if f.lower().endswith(image_extensions)
    ]

    # Upload each image file and process it
    for image_file in image_files:
        file_path = os.path.join(args.directory, image_file)
        upload_id = upload_image(
            args.api_key,
            args.username,
            args.danbooru_url,
            file_path,
        )
        if upload_id:
            post_id = create_post(
                args.api_key,
                args.username,
                args.danbooru_url,
                upload_id,  # Passed from prev command
                tags,
                rating,
            )

            if generate_pool:
                pool_ids.append(post_id)

    print("All images uploaded.")

    if create_pool:
        print("Generating pool...")
        create_pool(args.api_key, args.username, args.danbooru_url, pool_name, pool_ids)


if __name__ == "__main__":
    main()
