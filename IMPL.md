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
    4. Run `sudo dpkg --force-all -i install <path-to-generated.deb>`.
      * If failed, do not update `bundles.json`.
      * If succeeds, update `bundles.json` to add the bundle definition.
    5. All temporary files (control file, .deb) are automatically cleaned up

### 4. Command Implementation Details

* Load/Save `bundles.json` safely (handle file not found, JSON errors, use locking).
* Handle global options (`-q`, `-y`) early via Typer callback.
* Specific commands implementation:
  * `new`, `add` and `sync`
    1. Check or create bundle definition from `bundles.json`
    2. Sync the bundle.
    3. Check 
  * `rm`
    1. Check if the bundle definition exists in `bundles.json`, load or raise an error.
    2. Sync the bundle with the new definition.
    3. If the removed package is not in any other bundle and is not manually installed, remove the package from the system. (Behavoir can be changed by flags)
       * Forward apt's output to the user for confirmation
       * On failure or cancellation: **keep the updated `bundles.json`**, prompt user to remove the packages manually
  * `del`
    1. Check if the bundle definition exists in `bundles.json`, load or raise an error.
    2. Remove `bdapt-<bundle-name>` metapackage.
       * If success, remove the bundle definition from `bundles.json`.
    3. If the included packages are not in any other bundle and are not manually installed, remove the package from the system. (Behavoir can be changed by flags)
       * Forward apt's output to the user for confirmation
       * On failure or cancellation: **keep the updated `bundles.json`**, prompt user to run `apt autoremove` to remove the package from the system

### 5. Points for Extra Attention

* **Sudo Handling:** Detect if `sudo` is needed. Use `subprocess.run(['sudo', 'command', ...])` for package operations. Ensure `sudo` is available. Handle potential password prompts (though `-y` implies non-interactive `sudo` if possible, or assumes passwordless sudo / user interaction).
* **Package Name Validity:** Consider adding an optional check using `apt-cache policy <pkg>` or `apt-cache show <pkg>` when adding packages to verify they exist, potentially preventing errors later during `equivs-build` or `apt install`.
* **User Experience (UX):** Provide clear feedback (use `rich` library for better output), handle `-q` and `-y` flags consistently, confirm destructive actions.
* **Security:** Strictly avoid `shell=True` in `subprocess`. Sanitize bundle names if used directly in file paths or command arguments beyond the metapackage name.
* **Edge Cases:** Empty bundles, bundles with no packages, packages with complex dependencies or conflicts (though `apt` should handle most). What happens if `equivs` or `apt` commands are interrupted? The state might be inconsistent.

### 6. Testing Strategy

* **Unit Tests:** Use `pytest`.
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