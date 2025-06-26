# Project: bdapt (Bundle APT)

**Goal:** Create a Python CLI tool to manage groups (bundles) of APT packages as dependencies for externally installed software, using `equivs` metapackages for seamless integration with APT's dependency management and removal.

## Implementation Plan

### 1. Technology Stack & Libraries

* **Language:** Python 3
* **Packaging:** UV
* **CLI Framework:** Typer
* **System Interaction:** `subprocess` module and invoke `equivs` & `apt`
* **Temporary Files:** `tempfile` module
* **Storage Location:** `pathlib` module for handling paths robustly

### 2. Data Storage

* **Location:** `Path(os.path.expanduser("~/.local/share/bdapt"))`.
* **Implementation:** With `pydantic` for serialisation/deserialisation.
* **Persistence Model:**
  * Only the JSON data storage is persistent, containing bundle definitions
  * Equivs metapackages are generated on-demand and temporary
  * Each operation that modifies a bundle generates a fresh metapackage
  * Generated `.deb` files are cleaned up after installation
* **Structure:** A single JSON file (e.g., `bundles.json`) within the data directory.
  * Format: A dictionary where keys are bundle names (strings) and values are dictionaries containing:
    * `description`: String (optional, default to empty).
    * `packages`: Dictionary where keys are package names and values are package specifications:
      * `version`: String (optional) - version constraint using APT syntax (e.g., ">= 2.34.1", "~= 2.34", "= 1.18.0-6ubuntu14.4")

    ```json
    {
      "web-stack": {
        "description": "Web services",
        "packages": {
          "nginx": {
            "version": ">= 1.18.0"
          },
          "postgresql": {},
          "redis": {
            "version": "~= 7.0"
          }
        }
      },
      "dev-tools": {
        "description": "",
        "packages": {
          "build-essential": {},
          "git": {
            "version": ">= 2.34.1"
          },
          "vim": {}
        }
      }
    }
    ```

* **Concurrency Control:** Implement a simple file lock (using `fcntl` on Unix and a lock file like `.bdapt.lock`) within the data directory to prevent race conditions if multiple `bdapt` instances run concurrently. Use contextlib.contextmanager to handle the lock.

### 3. Core Logic

* **Metapackage Handling:** Metapackages are ephemeral, generated fresh for each operation, get cleaned up after each operation completes.
* **Metapackage Naming:** `bdapt-<bundle-name>`. Not allow spaces/special chars, otherwise raise an error.
* **Control File:**
  * **Essential Fields:**
    * `Package: bdapt-<bundle-name>`
    * `Version:` Use a timestamp stored per-bundle. E.g., `1.0~YYYYMMDDHHMMSS`.
    * `Maintainer:` A placeholder `bdapt <bdapt@localhost>`.
    * `Architecture: all`
    * `Description:` The user-provided description.
    * `Depends:` Comma-separated list of packages from the `packages` list in `bundles.json`. Ensure proper formatting (e.g., handle potential version constraints if ever added).
* **Sync Bundle Workflow:**
    1. New bundle definition provided.
    2. Create a temporary directory using `tempfile.TemporaryDirectory()`
    3. Generate the control file content and run `equivs-build <control-file-path>` with `cwd` set to the temporary directory
    4. Run `sudo dpkg -i <path-to-generated.deb>`.
       * **If this step succeeds, update `bundles.json` to add the bundle definition.**
       * Otherwise, raise an error.
    5. Run `sudo apt install -f` to handle dependencies:
       * Do not use `-y` flag on apt unless we get `-y` flag from `bdapt` command line
       * Pass out apt's output to the user for confirmation
       * On failure or cancellation: **keep the updated `bundles.json`**, prompt user to fix or remove the bundle manually
    6. All temporary files (control file, .deb) are automatically cleaned up

### 4. Command Implementation Details

* Load/Save `bundles.json` safely (handle file not found, JSON errors, use locking).
* Handle global options (`-q`, `-y`) early via Typer callback.
* Specific commands implementation:
  * `new`, `add` and `sync`
    1. Check if the bundle definition already exists in `bundles.json`, load or raise an error.
    2. Sync the bundle.
  * `rm`
    1. Check if the bundle definition exists in `bundles.json`, load or raise an error.
    2. Sync the bundle with the new definition.
    3. If the removed package is not in any other bundle and is not manually installed, remove the package from the system.
  * `del`
    1. Check if the bundle definition exists in `bundles.json`, load or raise an error.
    2. Remove `bdapt-<bundle-name>` metapackage.
    3. If `--keep-pkgs` is provided, mark the packages as manually installed.
    4. Remove the bundle definition from `bundles.json`.

### 5. Points for Extra Attention

* **Error Handling:** Wrap external command calls (`subprocess.run`) in `try...except` blocks, check return codes, parse stderr for common APT/dpkg errors, provide informative messages to the user. For apt operations, carefully handle user cancellations and ensure proper state rollback.
* **Sudo Handling:** Detect if `sudo` is needed. Use `subprocess.run(['sudo', 'command', ...])` for package operations. Ensure `sudo` is available. Handle potential password prompts (though `-y` implies non-interactive `sudo` if possible, or assumes passwordless sudo / user interaction).
* **Package Name Validity:** Consider adding an optional check using `apt-cache policy <pkg>` or `apt-cache show <pkg>` when adding packages to verify they exist, potentially preventing errors later during `equivs-build` or `apt install`.
* **Idempotency:** Commands should ideally be idempotent where possible (e.g., adding an existing package is a no-op, removing a non-existent package warns but doesn't fail).
* **User Experience (UX):** Provide clear feedback (use `rich` library for better output), handle `-q` and `-y` flags consistently, confirm destructive actions.
* **Security:** Strictly avoid `shell=True` in `subprocess`. Sanitize bundle names if used directly in file paths or command arguments beyond the metapackage name.
* **Edge Cases:** Empty bundles, bundles with no packages, packages with complex dependencies or conflicts (though `apt` should handle most). What happens if `equivs` or `apt` commands are interrupted? The state might be inconsistent.

### 6. Testing Strategy

* **Unit Tests:** Use `pytest`. Mock `subprocess.run`, `pathlib` operations, `json.load/dump` to test:
  * CLI argument parsing (via Typer/Click testing tools).
  * `bundles.json` manipulation logic.
  * `equivs` control file generation logic.
  * Parsing logic for `apt-cache` (for `show --tree`).
* **Integration Tests:** Essential due to system interaction.
  * **Docker Environment (Required):** All tests MUST run in Docker containers to avoid polluting the host system:
    * Base image: `debian:stable-slim` for a clean, isolated Debian environment
    * Create a Dockerfile that:
      * Installs test dependencies (`pytest`, `equivs`, etc.)
      * Sets up a non-root test user with sudo access
      * Mounts the project directory as a volume
    * Provide a test runner script that:
      * Builds the test container
      * Executes tests inside the container
      * Cleans up after tests complete
  * Test Coverage:
    * Correct exit codes
    * Expected changes in `bundles.json`
    * Expected packages installed/removed (check using `dpkg -l bdapt-<bundle-name>` and `dpkg -l <dependency>`)
    * Verify no leftover `.deb` files or control files after operations
    * Verify metapackage regeneration on each modification
    * Verify proper cleanup after interrupted operations
    * `apt autoremove` behavior after `rm` and `del`
    * Correct output for `ls`, `show`
    * Edge cases like interrupted operations and package conflicts

### 7. Class and File Structure

#### 7.1 Project Structure

```plaintext
bdapt/
├── pyproject.toml              # UV project configuration
├── README.md
├── IMPL.md
├── Dockerfile                  # For testing environment
├── test_runner.sh             # Docker test runner script
├── src/
│   └── bdapt/
│       ├── __init__.py
│       ├── __main__.py        # Entry point for `python -m bdapt`
│       ├── cli.py             # Typer CLI interface
│       ├── core/
│       │   ├── __init__.py
│       │   ├── bundle.py      # Bundle data model and operations
│       │   ├── storage.py     # Data persistence and locking
│       │   ├── equivs.py      # Equivs metapackage operations
│       │   └── apt.py         # APT system interaction
│       ├── models/
│       │   ├── __init__.py
│       │   └── bundle.py      # Pydantic models
│       ├── exceptions/
│       │   ├── __init__.py
│       │   └── errors.py      # Custom exception classes
│       └── utils/
│           ├── __init__.py
│           ├── system.py      # System utilities (sudo, validation)
│           └── output.py      # Rich output formatting
└── tests/
    ├── __init__.py
    ├── conftest.py            # Pytest configuration
    ├── unit/
    │   ├── __init__.py
    │   ├── test_bundle.py
    │   ├── test_storage.py
    │   ├── test_equivs.py
    │   └── test_apt.py
    ├── integration/
    │   ├── __init__.py
    │   └── test_cli.py
    └── docker/
        ├── Dockerfile
        └── test_entrypoint.sh
```
