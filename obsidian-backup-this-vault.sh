#!/usr/bin/env bash
set -euo pipefail

# Create a timestamped tar.gz backup of the current directory
# under ~/backups/obsidian/vaults using the current path relative
# to $HOME.
#
# Excluded directories can be customized in EXCLUDE_DIRS.
# The script keeps only the newest MAX_BACKUPS archives in the
# target backup directory.

home_dir="${HOME}"
current_dir="$(pwd -P)"

EXCLUDE_DIRS=(
  ".git"
)

MAX_BACKUPS=30

case "${current_dir}" in
  "${home_dir}"|"${home_dir}"/*)
    ;;
  *)
    printf 'ERROR: current directory is not under $HOME\n' >&2
    printf '  HOME: %s\n' "${home_dir}" >&2
    printf '  PWD:  %s\n' "${current_dir}" >&2
    exit 1
    ;;
esac

# Remove "$HOME/" prefix to get the relative path.
relative_path="${current_dir#${home_dir}/}"

# Special case if run directly from $HOME.
if [[ "${current_dir}" == "${home_dir}" ]]; then
  relative_path=""
fi

backup_root="${home_dir}/backups/obsidian/vaults"

if [[ -n "${relative_path}" ]]; then
  backup_dir="${backup_root}/${relative_path}"
  archive_base="${relative_path//\//_}"
else
  backup_dir="${backup_root}"
  archive_base="home"
fi

mkdir -p "${backup_dir}"

timestamp="$(date '+%Y-%m-%d-%H-%M')"
archive_name="${archive_base}_${timestamp}.tar.gz"
archive_path="${backup_dir}/${archive_name}"

tar_excludes=()
for dir_name in "${EXCLUDE_DIRS[@]}"; do
  tar_excludes+=(--exclude="./${dir_name}")
done

# Tar up the contents of the current directory, not the directory itself.
tar \
  -C "${current_dir}" \
  "${tar_excludes[@]}" \
  -czf "${archive_path}" \
  .

printf 'Backup created:\n%s\n' "${archive_path}"

# Remove older backups if the count exceeds MAX_BACKUPS.
mapfile -t backup_files < <(
  find "${backup_dir}" \
    -maxdepth 1 \
    -type f \
    -name "${archive_base}_*.tar.gz" \
    -printf '%T@ %p\n' \
    | sort -nr \
    | awk '{print $2}'
)

backup_count="${#backup_files[@]}"

if (( backup_count > MAX_BACKUPS )); then
  for old_backup in "${backup_files[@]:MAX_BACKUPS}"; do
    rm -f -- "${old_backup}"
    printf 'Removed old backup:\n%s\n' "${old_backup}"
  done
fi