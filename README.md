# rename-tool

Batch rename files and directories with pattern-based transformations.

## Install

```bash
uv tool install -e ~/repos/rename-tool
```

## Usage

```
rename INPUTS... arg1 arg2
```

The mode of operation is determined automatically from `arg1` and `arg2`:

| Mode | arg1 | arg2 | Example |
|---|---|---|---|
| **Replace** | `old` | `new` | `file_old.txt` → `file_new.txt` |
| **Prefix** | `sub-` | `''` | `240226A` → `sub-240226A` |
| **Suffix** | `''` | `.exclude` | `file.txt` → `file.txt.exclude` |
| **Delete** | `_Sim-Cre` | `''` | `sub-A_Sim-Cre` → `sub-A` |
| **Number offset** | `_T` | `+37` | `vid_T1.mp4` → `vid_T38.mp4` |
| **Full replace** | `*` | `ses-pre` | `ses-pre_LSD-0.4` → `ses-pre` |
| **Regex** | `\d{4}-\d{2}-\d{2}_` | `''` | `exp-2024-04-29_Saline` → `exp-Saline` |

Prefix vs Delete is disambiguated automatically: if `arg1` is found in the
name it's deleted, otherwise it's prepended.

## Why not Linux `rename`?

Linux `rename` (the Perl variant) handles simple substitutions well. This
tool adds:

- **Number offsetting** — increment/decrement embedded numbers
  (`_T1` → `_T38`), essential for reindexing trial sequences after merging
  recording sessions
- **Collision-safe reordering** — when renames overlap (T1→T38 and T38→T75),
  automatically determines a safe execution order instead of overwriting
- **Never overwrites** — skips if the target exists, retries in the next pass
- **Works on directories** — Linux `rename` only handles files
- **Single intuitive interface** — seven modes inferred from two arguments,
  no flags to remember

## Usage with DataLad

Pairing with `datalad run` adds glob-based targeting, provenance tracking,
and safe reversibility — no dry-run needed since every run is a commit you
can `git revert`. Preview first with `datalad run --dry-run command`.

```bash
# Reindex trial numbers across all sessions for a subject
datalad run \
    -m "Offset trial numbers by +37 for sub-240227P LSD post" \
    -i "sub-240227P/exp-LSD/ses-post/**/*.mp4" \
    "rename {inputs} '_T' '+37'"

# Strip date prefixes from experiment directories
datalad run \
    -m "Strip date prefix from experiment dirs" \
    -i "sub-*/exp-20*" \
    "rename {inputs} '\\d{{4}}-\\d{{2}}-\\d{{2}}_' ''"
```

DataLad expands the `-i` globs and passes matched paths as `{inputs}`.
For annexed files, it handles unlock/re-annex transparently.
Note: double-escape braces in regex (`{{4}}`) since datalad uses `{...}`
for its own substitution.
