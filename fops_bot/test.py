import redis

# Connect to local Redis server (default host and port)
r = redis.Redis(host="localhost", port=6379, db=0)
