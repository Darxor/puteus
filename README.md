# Puteus <img align="right" width="128" height="128" src="assets/puteus.png">

## Overview
Puteus is a FastAPI and SQLModel based application designed to provide robust RESTful endpoints and seamless integration with various databases. It leverages modern Python features and SQLAlchemy event listeners for advanced model behaviors, ensuring maintainability and scalability for production systems.

## Features
- **Modern API**: Built with FastAPI for high performance.
- **ORM Integration**: Uses SQLModel with SQLAlchemy for relational database operations.
- **Mixin Support**: Provides reusable mixins (e.g., UUIDMixin, TimeAuditMixin, SoftDeletionMixin) for automatic handling of common model properties.
- **Soft Deletion**: Implements soft deletions with an event listener to manage deletion timestamps.
- **Source Watcher**: Monitors data sources, including automatic updates and checks.
- **Easy Configuration**: Uses a `.env` file for environment-specific settings.

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd puteus
   ```

2. Install dependencies using the [uv package manager](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```

## Configuration
Create a `.env` file in the project root with the following variables:
- `PUTEUS_DB_URI`: The database connection URI (e.g., `sqlite+aiosqlite:///mydb.sqlite`).
- `PUTEUS_DB_NAME`: The name of the database.
- `PUTEUS_CHECK_SOURCE_INTERVAL`: The interval for checking all sources (in seconds).
- `PUTEUS_DEBUG`: Enables debug mode to log detailed information.
- `PUTEUS_DEV_DROP_DB`: Allows dropping the database in development mode.
- Additional environment variables as required by your deployment.

A sample `.env.example` file is provided for reference.

## Usage
To bootstrap the database with initial data, run:
```bash
uv run python -m scripts.bootstrap_db
```

To run the application with hot reload on localhost, execute:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config=log_config.yml --reload
```

The application will be accessible at `http://localhost:8000`.
OpenAPI documentation is available at `http://localhost:8000/docs` (or `http://localhost:8000/redoc`) and admin interface at `http://localhost:8000/admin`.

For production deployment, adjust the log levels and disable hot reloading.

## Development
- **Code Style**: Follow PEP 8. Use numpydoc style for Python docstrings.
- **Mixins**: Explore the mixin classes located in `app/models/mixins.py` for advanced model functionality.
- **Testing**: In progress.

To run linting use:
```bash
uvx ruff check
```
and for type checking:
```bash
uvx pyright
```

## Contributing
Contributions are welcome! Please ensure:
- Tests are written for new features.
- Code follows the existing style guidelines.
- Pull requests are well documented and clear.

## License
Distributed under the MIT License. See `LICENSE` for more information.

## Additional Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

