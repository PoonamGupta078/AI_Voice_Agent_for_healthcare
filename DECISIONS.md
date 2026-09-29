# Decisions and Assumptions

- **M0**: Using standard `pytest` directly instead of `make test` for Windows compatibility, as `make` is not available by default on this system.
- **M0**: Config loading uses PyYAML and standard python datatypes matching pydantic models.
