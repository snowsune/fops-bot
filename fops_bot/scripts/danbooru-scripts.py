import requests


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


# Create a post
def create_post(
    api_key, username, danbooru_url, upload_id, tags, rating, description=None
):
    url = f"{danbooru_url}/posts.json?api_key={api_key}&login={username}"
    data = {
        "upload_media_asset_id": upload_id,
        "post[tag_string]": f"{tags}",
        "post[rating]": rating,
    }

    if description:
        data["post[artist_commentary_desc]"] = description

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


def fetch_images_with_tag(
    tag, danbooru_url, api_key, username, limit=10, random=False, exclude=None
):
    url = f"{danbooru_url}/posts.json"

    # Base tags to include
    params = {"tags": tag, "limit": limit, "login": username, "api_key": api_key}

    # Add random ordering if requested
    if random:
        params["tags"] = f"{params['tags']} order:random"

    # Add excluded tags if any
    if exclude:
        exclude_tags = " ".join([f"-{ex}" for ex in exclude])
        params["tags"] = f"{params['tags']} {exclude_tags}"

    response = requests.get(url, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Failed to fetch images with tag '{tag}'. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return []


def tag_exists(tag, danbooru_url, api_key, username):
    url = f"{danbooru_url}/tags.json"
    params = {
        "search[name_matches]": tag,
        "limit": 1,
        "login": username,
        "api_key": api_key,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        tags = response.json()
        if tags:
            print(f"Tag '{tag}' exists on the server.")
            return True
        else:
            print(f"Tag '{tag}' does not exist on the server.")
            return False
    else:
        print(
            f"Failed to check if tag '{tag}' exists. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return False


def get_post_tags(post_id, danbooru_url, api_key, username):
    url = f"{danbooru_url}/posts/{post_id}.json"

    # Get the current tags of the post
    response = requests.get(url, auth=(username, api_key))
    if response.status_code == 200:
        post_data = response.json()
        tags = post_data.get("tag_string", "").split()
    else:
        print(
            f"Failed to fetch current tags for post {post_id}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return None

    return tags


def append_post_tags(post_id, new_tags, danbooru_url, api_key, username, clear_tags=[]):
    url = f"{danbooru_url}/posts/{post_id}.json"

    # Get the current tags
    current_tags = get_post_tags(post_id, danbooru_url, api_key, username)

    # Ensure we can iterate the tags even if they're not a list
    if not isinstance(new_tags, list):
        new_tags = [new_tags]

    # Combine current tags with new tags, avoiding duplicates
    combined_tags = list(set(current_tags + new_tags))

    # If there are any cleartags to remove, do so now
    for tag in clear_tags:
        try:
            combined_tags.remove(tag)
        except ValueError:
            print(f"Could not clear {tag} from {combined_tags}")

    headers = {
        "Content-Type": "application/json",
    }

    data = {
        "post": {"tag_string": " ".join(combined_tags)},
        "login": username,
        "api_key": api_key,
    }

    response = requests.put(url, json=data, headers=headers, auth=(username, api_key))
    if response.status_code == 200:
        print(f"Successfully updated tags for post {post_id}.")
        return response.json()
    else:
        print(
            f"Failed to update tags for post {post_id}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return None


def fetch_new_comments(danbooru_url, api_key, username, last_comment_id):
    url = f"{danbooru_url}/comments.json"
    params = {
        "search[id_gte]": int(last_comment_id) + 1,
        "login": username,
        "api_key": api_key,
        "limit": 100,
    }
    response = requests.get(url, params=params)

    filtered_response = []

    # No easy way (i think) to filter these so... here we go :3
    for comment in response.json():
        if int(comment["id"]) > int(last_comment_id):
            filtered_response.append(comment)

    if response.status_code == 200:
        return filtered_response
    else:
        print(f"Failed to fetch new comments. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []


def get_username(danbooru_url, api_key, username, user_id):
    url = f"{danbooru_url}/users/{user_id}.json"
    response = requests.get(url, auth=(username, api_key))

    if response.status_code == 200:
        user_data = response.json()
        user_name = user_data.get("name", "")
        print(f"User ID {user_id} corresponds to username '{user_name}'.")
        return user_name
    else:
        print(
            f"Failed to fetch username for user ID {user_id}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return None


def get_image_url(post_id, danbooru_url, api_key, username):
    url = f"{danbooru_url}/posts/{post_id}.json"

    # Fetch the post details
    response = requests.get(url, auth=(username, api_key))
    if response.status_code == 200:
        post_data = response.json()
        file_url = post_data.get("file_url", "")
        if file_url:
            print(f"Image URL for post ID {post_id} is {file_url}")
            return file_url
        else:
            print(f"No file URL found for post ID {post_id}.")
            return None
    else:
        print(
            f"Failed to fetch post details for ID {post_id}. Status code: {response.status_code}"
        )
        print(f"Response: {response.text}")
        return None


def append_source_to_post(post_id, source_url, danbooru_url, api_key, username):
    url = f"{danbooru_url}/posts/{post_id}.json"

    # Get current post data
    response = requests.get(url, auth=(username, api_key))

    if response.status_code == 200:
        post_data = response.json()
        current_source = post_data.get("source", "")

        # If the post already has a source, we can append the new one, separated by a newline or any other delimiter
        if current_source:
            updated_source = f"{current_source}\n{source_url}"
        else:
            updated_source = source_url

        data = {"post": {"source": updated_source}}

        headers = {
            "Content-Type": "application/json",
        }

        # Update the post with the new source
        update_response = requests.put(
            url, json=data, headers=headers, auth=(username, api_key)
        )

        if update_response.status_code == 200:
            print(f"Successfully updated source for post {post_id}.")
            return update_response.json()
        else:
            print(
                f"Failed to update source for post {post_id}. Status code: {update_response.status_code}"
            )
            print(f"Response: {update_response.text}")
            return None
    else:
        print(f"Failed to fetch post {post_id}. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return None


# Fetches a list of users from the server
def fetch_usernames(danbooru_url, api_key, username, limit=10):
    url = f"{danbooru_url}/users.json"

    params = {
        "limit": limit,
        "login": username,
        "api_key": api_key,
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return [user["name"] for user in response.json()]
    else:
        print(f"Failed to fetch usernames. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []
