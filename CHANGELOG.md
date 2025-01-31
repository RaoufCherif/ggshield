# Changelog

<a id='changelog-1.15.0'></a>

## 1.15.0 — 2023-04-25

### Changed

- `ggshield secret scan` output now includes a link to the incident if the secret is already known on the user's GitGuardian dashboard.

- `ggshield secret scan docker` no longer rescans known-clean layers, speeding up subsequent scans. This cache is tied to GitGuardian secrets engine version, so all layers are rescanned when a new version of the secrets engine is deployed.

### Fixed

- Fixed an issue where the progress bar for `ggshield secret scan` commands would sometimes reach 100% too early and then stayed stuck until the end of the scan.

### Removed

- The deprecated commands `ggshield scan` and `ggshield ignore` have been removed. Use `ggshield secret scan` and `ggshield secret ignore` instead.

<a id='changelog-1.14.5'></a>

## 1.14.5 — 2023-03-29

### Changed

- `ggshield iac scan` can now be called without arguments. In this case it scans the current directory.

- GGShield now displays an easier-to-understand error message when no API key has been set.

### Fixed

- Fixed GGShield not correctly reporting misspelled configuration keys if the key name contained `-` characters (#480).

- When called without an image tag, `ggshield secret scan docker` now automatically uses the `:latest` tag instead of scanning all versions of the image (#468).

- `ggshield secret scan` now properly stops with an error message when the GitGuardian API key is not set or invalid (#456).

<a id='changelog-1.14.4'></a>

## 1.14.4 — 2023-02-23

### Fixed

- GGShield Docker image can now be used to scan git repositories even if the repository is mounted outside of the /data directory.

- GGShield commit hook now runs correctly when triggered from Visual Studio (#467).

<a id='changelog-1.14.3'></a>

## 1.14.3 — 2023-02-03

### Fixed

- `ggshield secret scan pre-receive` no longer scans deleted commits when a branch is force-pushed (#437).

- If many GGShield users are behind the same IP address, the daily update check could cause GitHub to rate-limit the IP. If this happens, GGShield honors GitHub rate-limit headers and no longer checks for a new update until the rate-limit is lifted (#449).

- GGShield once again prints a "No secrets have been found" message when a scan does not find any secret (#448).

- Installing GGShield no longer creates a "tests" directory in "site-packages" (#383).

- GGShield now shows a clear error message when it cannot use git in a repository because of dubious ownership issues.

### Deprecated

- The deprecation message when using `ggshield scan` instead of `ggshield secret scan` now states the `ggshield scan` commands are going to be removed in GGShield 1.15.0.

<a id='changelog-1.14.2'></a>

## 1.14.2 — 2022-12-15

### Changed

- It is now possible to use generic command-line options like `--verbose` anywhere on the command line and scan options anywhere after the `scan` word (#197).

- `ggshield iac scan` now shows the severity of the detected vulnerabilities.

### Fixed

- If a file containing secrets has been committed in two different branches, then `ggshield secret scan repo` would show 4 secrets instead of 2. This has been fixed (#428).

- ggshield now uses different error codes when a scan succeeds but finds problems and when a scan does not finish (#404).

- ggshield now correctly handles the case where git is not installed (#329).

<a id='changelog-1.14.1'></a>

## 1.14.1 — 2022-11-16

### Fixed

- Fixed dependency on pygitguardian, which blocked the release on pypi.

<a id='changelog-1.14.0'></a>

## 1.14.0 — 2022-11-15

### Added

- ggshield scan commands now accept the `--ignore-known-secrets` option. This option is useful when working on an existing code-base while secrets are being remediated.

- ggshield learned a new secret scan command: `docset`. This command can scan any content as long as it has been converted into our new docset file format.

### Changed

- `ggshield auth login --method=token` can now read its token from the standard input.

### Fixed

- ggshield now prints clearer error messages if the .gitguardian.yaml file is invalid (#377).

- When used with the [pre-commit](https://pre-commit.com) framework, ggshield would sometimes scan commits with many files more than once. This has been fixed.

<a id='changelog-1.13.6'></a>

## 1.13.6 — 2022-10-19

### Fixed

- `ggshield auth login` no longer fails when called with `--lifetime`.

- pre-receive and pre-push hooks now correctly handle the case where a branch with no new commits is pushed.

- ggshield no longer fails when scanning paths longer than 256 characters (#391).

<a id='changelog-1.13.5'></a>

## 1.13.5 — 2022-10-12

### Fixed

- Fix crash at startup if the home directory is not writable.

<a id='changelog-1.13.4'></a>

## 1.13.4 — 2022-10-12

### Added

- ggshield now checks for update once a day and notifies the user if a new version is available. This check can be disabled with the `--no-check-for-updates` command-line option (#299).

### Changed

- Scanning Git repositories is now faster.

- `ggshield secret scan path` now shows a progress bar.

- When used as a pre-push or pre-receive hook, ggshield no longer scans more commits than necessary when a new branch is pushed (#303, #369).

### Fixed

- ggshield no longer declares two separate instances if the instance URL is set with and without a trailing slash (#357).

- Fixed a regression where ggshield would not load the .env from the current working directory.

- ggshield no longer silently ignores network issues.
