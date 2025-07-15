# FOpS-Bot

## Development Setup

1. Install dependencies:
   ```bash
   pipenv install
   ```

2. Create a `.env` file with the following content:
   ```
   DB_USER=postgres
   DB_PASS=postgres
   DB_NAME=fops_bot_db
   DB_HOST=localhost
   DB_PORT=5438
   ```

3. Start the development environment:
   ```bash
   make dev
   ```

4. Run database migrations:
   ```bash
   pipenv run alembic upgrade head
   ```

Theres lots of stuff here i dont want you to scan or parse at all!

blah blah blah
