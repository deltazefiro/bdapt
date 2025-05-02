## Project: bdapt (Bundle APT)

**Goal:** Create a Python CLI tool to manage groups (bundles) of APT packages as dependencies for externally installed software, using `equivs` metapackages for seamless integration with APTITUDE's dependency management and removal.

**Core Principles Reaffirmed:**

1. **Immediate System Impact:** Actions like `add`, `rm`, `new` (with packages), `del` directly modify the system state via `dpkg` and `aptitude`.
2. **Sudo Requirement:** Any command causing system modification *must* invoke `sudo` for the relevant package management commands. The `bdapt` script itself shouldn't require root, but it will execute `sudo dpkg/aptitude`.
3. **Stateless (No History):** Bundle definitions represent the *current desired state*. Changes overwrite previous states.
4. **Simple Verbs:** `new`, `add`, `rm`, `del`, `ls`, `show`, `clean` provide an intuitive interface.
5. **Automatic Dependency Handling (via APTITUDE):** `bdapt` focuses on defining *direct* dependencies in the metapackage; `aptitude` handles the installation of transitive dependencies and removal via `autoremove`.

## Implementation Plan

### 1. Technology Stack & Libraries

* **Language & Packaging:** Python 3 + UV
* **CLI Framework:** Typer
* **System Interaction:** `subprocess` module and invoke `equivs` & `aptitude`
* **Temporary Files:** `tempfile` module
* **Storage Location:** `pathlib` module for handling paths robustly. Default location `~/.local/share/bdapt` respects XDG Base Directory Specification (partially, should ideally use `XDG_DATA_HOME`).

### 2. Data Storage

* **Location:** `Path(os.path.expanduser(config_path or "~/.local/share/bdapt"))`. Allow override via `--config`.
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

* **Concurrency Control:** Implement a simple file lock (e.g., using `fcntl` on Unix or a lock file like `.bdapt.lock`) within the data directory to prevent race conditions if multiple `bdapt` instances run concurrently.

### 3. Core `equivs` Interaction Logic

* **Metapackage Naming:** Define a clear convention, e.g., `bdapt-<bundle-name>`. Sanitize `bundle-name` if needed (i.e., not allow spaces/special chars).
* **Control File Generation:**
  * Create a function `generate_control_file(bundle_name, description, package_list)` that returns the control file content as a string or writes it to a temporary file.
  * **Essential Fields:**
    * `Package: bdapt-<bundle-name>`
    * `Version:` Use a timestamp (e.g., `YYYYMMDDHHMMSS`) or a simple incrementing number stored per-bundle (timestamp is easier, ensures upgrades). E.g., `1.0~<timestamp>`.
    * `Maintainer:` A placeholder like `bdapt <bdapt@localhost>`.
    * `Architecture: all`
    * `Description:` The user-provided description.
    * `Depends:` Comma-separated list of packages from the `packages` list in `bundles.json`. Ensure proper formatting (e.g., handle potential version constraints if ever added, although not currently specified).
* **Build & Install Workflow (`_update_metapackage` internal function):**
    1. Generate the control file content/path.
    2. Create a temporary directory using `tempfile.TemporaryDirectory()`.
    3. Run `equivs-build <control-file-path>` with `cwd` set to the temporary directory. Capture output/errors.
    4. Identify the generated `.deb` file (e.g., `bdapt-<bundle-name>_<version>_all.deb`).
    5. Run `sudo dpkg -i <path-to-generated.deb>`.
    6. Run `sudo aptitude -y install <package-name>` to handle any missing dependencies.
    7. The temporary directory and its contents (`.deb`, control file) are automatically cleaned up when exiting the `with tempfile.TemporaryDirectory():` block.
* **Removal Workflow (`_remove_metapackage` internal function):**
    1. Run `sudo aptitude remove -y bdapt-<bundle-name>`. Check exit code.
    2. Optionally (standard for `del`, conditional for `rm`), run `sudo aptitude -y markauto '~i!~M'`. This marks packages as automatically installed if they're not manually marked.
    3. Run `sudo aptitude -y autoremove` to remove automatically installed packages that are no longer needed.

### 4. Command Implementation Details

* **Shared Logic:**
  * Load/Save `bundles.json` safely (handle file not found, JSON errors, use locking).
  * Implement helper function `run_command(cmd_list, needs_sudo=False, check=True)` using `subprocess.run` to handle command execution, sudo elevation, error checking, and quiet mode.
  * Handle global options (`-y`, `-q`, `--config`) early, likely via Typer/Click context or decorators.
* **`new <bundle> [pkgs...]`**:
    1. Check if bundle name exists in `bundles.json`. Error if yes.
    2. Add new entry to `bundles.json` with name, description (`-d`), and initial `pkgs`.
    3. Save `bundles.json`.
    4. If `pkgs` were provided: Call `_update_metapackage`. Requires sudo check.
* **`add <bundle> <pkgs...>`**:
    1. Check if bundle name exists. Error if no. Requires sudo check.
    2. Load `bundles.json`, add `pkgs` to the bundle's list (ensure uniqueness, maybe sort).
    3. Save `bundles.json`.
    4. Call `_update_metapackage`. The `--no-deps` flag seems moot with the `equivs` approach, as `apt` handles dependencies during install. Clarify its intent or ignore if redundant. If it means "don't add dependencies *of* the packages being added *to the bundle definition*", then the current plan already does that.
* **`rm <bundle> <pkgs...>`**:
    1. Check if bundle name exists. Error if no. Requires sudo check.
    2. Load `bundles.json`, remove `pkgs` from the bundle's list. Warn if a package wasn't found.
    3. Save `bundles.json`.
    4. Call `_update_metapackage` to rebuild/reinstall the metapackage with fewer dependencies.
    5. If `--keep-deps` is *not* specified, run `sudo aptitude -y autoremove`.
* **`del <bundle>`**:
    1. Check if bundle name exists. Error if no. Requires sudo check.
    2. If `--keep-pkgs` is *not* specified: Call `_remove_metapackage` (which includes `autoremove`).
    3. Load `bundles.json`, delete the bundle entry.
    4. Save `bundles.json`.
    5. (Optional) Clean up any specific persistent files for this bundle if any exist outside `bundles.json`.
* **`ls`**:
    1. Load `bundles.json`.
    2. Iterate and print bundle names and descriptions prettily.
* **`show <bundle>`**:
    1. Check if bundle name exists. Error if no.
    2. Load `bundles.json`, retrieve bundle data.
    3. Print description and package list.
    4. If `--tree`:
        * For each package in the list, run `apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances <pkg>` (or use `apt-rdepends`).
        * Parse the output to build and display a dependency tree structure. This requires careful parsing logic. Consider using an existing library if available, or keep it simple (e.g., text-based indenting).
* **`sync <bundle>`**:
    1. Check if bundle name exists. Error if no. Requires sudo check.
    2. If not `-y`/`--non-interactive`, confirm with user since this is a potentially disruptive operation.
    3. Load `bundles.json` to get bundle data.
    4. Call `_remove_metapackage` to remove the existing bundle installation.
    5. Call `_update_metapackage` to reinstall the bundle with current definition.
    6. This ensures the system state exactly matches the bundle definition, useful for fixing inconsistencies.

### 5. Points for Extra Attention

* **Error Handling:** Wrap external command calls (`subprocess.run`) in `try...except` blocks, check return codes, parse stderr for common APT/dpkg errors, provide informative messages to the user.
* **Sudo Handling:** Detect if `sudo` is needed. Use `subprocess.run(['sudo', 'command', ...])` for package operations. Ensure `sudo` is available. Handle potential password prompts (though `-y` implies non-interactive `sudo` if possible, or assumes passwordless sudo / user interaction).
* **Package Name Validity:** Consider adding an optional check using `apt-cache policy <pkg>` or `apt-cache show <pkg>` when adding packages to verify they exist, potentially preventing errors later during `equivs-build` or `apt install`.
* **Idempotency:** Commands should ideally be idempotent where possible (e.g., adding an existing package is a no-op, removing a non-existent package warns but doesn't fail).
* **User Experience (UX):** Provide clear feedback (use `rich` library for better output?), handle `-q` and `-y` flags consistently, confirm destructive actions (`del --all`).
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
    * `apt autoremove` behavior after `rm` and `del`
    * Correct output for `ls`, `show`
    * Edge cases like interrupted operations and package conflicts

### 7. Documentation

* Clear `README.md` explaining purpose, installation, usage (covering all commands and options with examples).
* Inline code comments for complex sections.
* Generated CLI help (`--help` for main command and subcommands) should be comprehensive thanks to Typer.
