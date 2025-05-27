## Project: bdapt (Bundle APT)

**Goal:** Create a Python CLI tool to manage groups (bundles) of APT packages as dependencies for externally installed software, using `equivs` metapackages for seamless integration with APT's dependency management and removal.

**Core Principles Reaffirmed:**

1. **Immediate System Impact:** Actions like `add`, `rm`, `new` (with packages), `del` directly modify the system state via `dpkg` and `apt`.
2. **Sudo Requirement:** Any command causing system modification *must* invoke `sudo` for the relevant package management commands. The `bdapt` script itself shouldn't require root, but it will execute `sudo dpkg/apt`.
3. **Stateless (No History):** Bundle definitions represent the *current desired state*. Changes overwrite previous states.
4. **Simple Verbs:** `new`, `add`, `rm`, `del`, `ls`, `show`, `clean` provide an intuitive interface.
5. **Automatic Dependency Handling (via APT):** `bdapt` focuses on defining *direct* dependencies in the metapackage; `apt` handles the installation of transitive dependencies and removal via `autoremove`.

## Implementation Plan

### 1. Technology Stack & Libraries

* **Language & Packaging:** Python 3 + UV
* **CLI Framework:** Typer
* **System Interaction:** `subprocess` module and invoke `equivs` & `apt`
* **Temporary Files:** `tempfile` module
* **Storage Location:** `pathlib` module for handling paths robustly. Default location `~/.local/share/bdapt` respects XDG Base Directory Specification (partially, should ideally use `XDG_DATA_HOME`).

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
      * `version`: String (optional) - specific version to install (e.g., "1.18.0-6ubuntu14.4")

    ```json
    {
      "web-stack": {
        "description": "Web services",
        "packages": {
          "nginx": {
            "version": "1.18.0-6ubuntu14.4"
          },
          "postgresql": {},
          "redis": {
            "version": "7.0.15-1",
          }
        }
      },
      "dev-tools": {
        "description": "",
        "packages": {
          "build-essential": {},
          "git": {
            "version": "2.34.1-1ubuntu1.10",
          },
          "vim": {}
        }
      }
    }
    ```

* **Concurrency Control:** Implement a simple file lock (using `fcntl` on Unix and a lock file like `.bdapt.lock`) within the data directory to prevent race conditions if multiple `bdapt` instances run concurrently. Use contextlib.contextmanager to handle the lock.

### 3. Core `equivs` Interaction Logic

* **Metapackage Handling:** Metapackages are ephemeral, generated fresh for each operation, get cleaned up after each operation completes.
* **Metapackage Naming:** `bdapt-<bundle-name>`. Not allow spaces/special chars, otherwise raise an error.
* **Control File Generation:**
  * Create a function `generate_control_file(bundle_name, description, package_list)` that returns the control file content as a string or writes it to a temporary file.
  * **Essential Fields:**
    * `Package: bdapt-<bundle-name>`
    * `Version:` Use a timestamp stored per-bundle. E.g., `1.0~YYYYMMDDHHMMSS`.
    * `Maintainer:` A placeholder `bdapt <bdapt@localhost>`.
    * `Architecture: all`
    * `Description:` The user-provided description.
    * `Depends:` Comma-separated list of packages from the `packages` list in `bundles.json`. Ensure proper formatting (e.g., handle potential version constraints if ever added).
* **New / Update Workflow:**
    1. Check if the bundle definition already exists in `bundles.json`, load or raise an error.
    2. Create a temporary directory using `tempfile.TemporaryDirectory()`
    3. Generate the control file content and run `equivs-build <control-file-path>` with `cwd` set to the temporary directory
    4. Run `sudo dpkg -i <path-to-generated.deb>`
    5. Run `sudo apt install -f` to handle dependencies:
       * Do not use `-y` flag on apt unless we get `-y` flag from `bdapt` command line
       * Pass out apt's output to the user for confirmation
       * If user cancels, run `sudo dpkg -r bdapt-<bundle-name>` to revert the metapackage installation
    6. All temporary files (control file, .deb) are automatically cleaned up
    7. Update `bundles.json` to add the bundle definition
* **Removal Workflow:**
    1. Run `sudo apt remove bdapt-<bundle-name>`:
       * Pass out apt's output to the user for confirmation
       * If user cancels, abort the removal operation
    2. Update `bundles.json` to remove the bundle definition

### 4. Command Implementation Details

* **Shared Logic:**
  * Load/Save `bundles.json` safely (handle file not found, JSON errors, use locking).
  * Implement helper function `run_apt_command(cmd_list)` to handle apt operations with dependency confirmation:
    * Run apt in simulation mode first to get package changes
    * Present changes to user in a clear format
    * If confirmed, execute the actual command
    * If cancelled, handle rollback operations as needed
  * Handle global options (`-q`, `-y`) early via Typer callback.

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

### 8. Class Design

```python
# Context manager for file locking
@contextmanager
def locked_file(file_path: Path):
    ...

# Pydantic model for package specifications
class PackageSpec(BaseModel):
    version: Optional[str] = None

# Pydantic model for a bundle
class Bundle(BaseModel):
    name: str
    description: str = ""
    packages: Dict[str, PackageSpec] = {}

@dataclass
class MetapackageManager:
    """Handles all APT and equivs-related operations."""
    
    def _generate_control_file(self, bundle: Bundle) -> str:
        """Generate the equivs control file content for a bundle."""
        pass

    def _build_metapackage(self, bundle: Bundle, temp_dir: Path) -> Path:
        """Build a .deb metapackage for the bundle in the given temporary directory.
        Returns the path to the generated .deb file."""
        pass

    def install_metapackage(self, bundle: Bundle, deb_path: Path, yes: bool = False) -> bool:
        """Install the metapackage using dpkg and apt.
        Returns True if installation was successful."""
        pass

    def remove_metapackage(self, bundle_name: str, yes: bool = False) -> bool:
        """Remove the metapackage using apt and trigger autoremove.
        Returns True if removal was successful."""
        pass

    def verify_package_exists(self, package_name: str) -> bool:
        """Verify if a package exists in APT repositories using apt-cache."""
        pass

    def simulate_changes(self, bundle: Bundle) -> str:
        """Run apt in simulation mode to preview package changes."""
        pass

    @staticmethod
    def _run_apt_command(cmd: List[str], sudo: bool = True) -> subprocess.CompletedProcess:
        """Helper method to run APT-related commands with proper error handling."""
        pass

class BundleManager:
    """Manages bundle definitions and orchestrates operations."""
    
    def __init__(self, data_dir: Path = Path.home() / ".local" / "share" / "bdapt") -> None:
        """Initialize the BundleManager with a data directory."""
        self.data_dir: Path = data_dir
        self.bundles_file: Path = data_dir / "bundles.json"
        self.lock_file: Path = data_dir / ".bdapt.lock"
        self.bundles: Dict[str, Bundle] = {}
        self.metapackage_mgr = MetapackageManager()

    def _load_bundles(self) -> None:
        """Load all bundles from the JSON file."""
        pass

    def _save_bundles(self) -> None:
        """Save all bundles to the JSON file."""
        pass

    def create_bundle(self, bundle: Bundle, yes: bool = False) -> None:
        """Create a new bundle and install its metapackage."""
        pass


    def delete_bundle(self, name: str, yes: bool = False) -> None:
        """Delete a bundle and remove its metapackage."""
        pass

    def update_bundle(self, bundle: Bundle, yes: bool = False) -> None:
        """Update an existing bundle with a new definition."""
        pass

    def list_bundles(self) -> List[Bundle]:
        """Return a list of all bundles."""
        pass

    def get_bundle(self, name: str) -> Bundle:
        """Retrieve a specific bundle by name."""
        pass

    def verify_packages(self, bundle: Bundle) -> List[str]:
        """Verify all packages in a bundle exist.
        Returns a list of non-existent packages."""
        pass

# CLI setup with Typer
...

```
