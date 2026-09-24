"""Rename Edgertronic MOV clips on the SD card from a Trackman bullpen CSV.

Clips in D:\\DCIM whose file name is a PlayID are renamed to
FirstnameLastname-PitchCount-TaggedPitchType. PitchCount is how many pitches
that pitcher has thrown in the CSV, starting at 1. Every file that is not
renamed, including unmatched MOV files, is deleted, along with folders.
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd

DCIM_DIR = r"D:\DCIM"
REQUIRED_COLUMNS = ("PlayID", "Pitcher", "PitchNo", "TaggedPitchType")
INVALID_FILENAME_CHARS = '<>:"/\\|?*'

PITCH_TYPE_REPLACEMENTS = {
    "FourSeamFastBall": "Fastball",
    "TwoSeamFastBall": "Sinker",
    "OneSeamFastBall": "Sinker",
    "Four-Seam": "Fastball",
    "Changeup": "ChangeUp",
}


def sanitize_filename_part(value):
    text = "".join(
        ch for ch in str(value).strip()
        if ch not in INVALID_FILENAME_CHARS and ord(ch) >= 32
    )
    text = text.strip().rstrip(".")
    return text or "Unknown"


def pitcher_file_name(pitcher):
    """Turn 'Last, First' into FirstLast."""
    text = str(pitcher).strip()
    if "," in text:
        last, first = text.split(",", 1)
        text = f"{''.join(first.split())}{''.join(last.split())}"
    else:
        text = "".join(text.split())
    return sanitize_filename_part(text)


def clip_name(pitcher, pitch_count, pitch_type):
    return (
        f"{pitcher_file_name(pitcher)}"
        f"-{int(pitch_count)}"
        f"-{sanitize_filename_part(pitch_type)}"
    )


def load_plays(csv_paths):
    frames = []
    for path in csv_paths:
        frame = pd.read_csv(path)
        frame.columns = frame.columns.str.strip()
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "CSV is missing required column(s): " + ", ".join(missing)
        )

    df["TaggedPitchType"] = df["TaggedPitchType"].replace(PITCH_TYPE_REPLACEMENTS)
    df["_pitch_no_num"] = pd.to_numeric(df["PitchNo"], errors="coerce")
    df["_row"] = range(len(df))

    plays = {}
    skipped = 0
    duplicates = 0
    numbered = df[df["Pitcher"].notna() & df["_pitch_no_num"].notna()]
    skipped += int((df["Pitcher"].isna() | df["_pitch_no_num"].isna()).sum())

    for _, group in numbered.groupby("Pitcher", sort=False):
        ordered = group.sort_values(["_pitch_no_num", "_row"])
        for pitch_count, (_, row) in enumerate(ordered.iterrows(), start=1):
            play_id = "" if pd.isna(row["PlayID"]) else str(row["PlayID"]).strip()
            if not play_id or play_id.lower() == "nan":
                skipped += 1
                continue

            pitch_type = row["TaggedPitchType"]
            if pd.isna(pitch_type) or not str(pitch_type).strip():
                pitch_type = "Undefined"

            key = play_id.lower()
            if key in plays:
                duplicates += 1
                continue
            plays[key] = {
                "play_id": play_id,
                "filename": clip_name(row["Pitcher"], pitch_count, pitch_type),
            }

    return plays, skipped, duplicates


def scan_dcim(root):
    movs = []
    other_files = []
    folders = []
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.normcase(os.path.abspath(dirpath)) != os.path.normcase(os.path.abspath(root)):
            folders.append(dirpath)
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1].lower() == ".mov":
                movs.append(path)
            else:
                other_files.append(path)
    return movs, other_files, folders


def match_play(stem, plays):
    key = stem.strip().lower()
    if key in plays:
        return plays[key]
    hits = [plays[play_id] for play_id in plays if play_id and play_id in key]
    if len(hits) == 1:
        return hits[0]
    return None


def unique_destination(dest_dir, filename, used_names, src):
    base, ext = os.path.splitext(filename)
    candidate = filename
    suffix = 2
    while True:
        dest = os.path.join(dest_dir, candidate)
        same_file = os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dest))
        taken = candidate.lower() in used_names
        exists = os.path.exists(dest) and not same_file
        if not taken and not exists:
            used_names.add(candidate.lower())
            return dest
        candidate = f"{base}_{suffix}{ext}"
        suffix += 1


def plan_moves(movs, plays, dest_dir):
    used_names = set()
    expected = {}
    for play in plays.values():
        expected.setdefault(play["filename"].lower(), play)

    actions = []
    for src in movs:
        stem, ext = os.path.splitext(os.path.basename(src))
        play = match_play(stem, plays)
        if play is None:
            play = expected.get(stem.strip().lower())
        if play:
            filename = play["filename"] + ext
            dest = unique_destination(dest_dir, filename, used_names, src)
        else:
            dest = None
        actions.append({
            "src": src,
            "dest": dest,
            "play_id": None if play is None else play["play_id"],
            "matched": play is not None,
        })
    return actions


def same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def apply_plan(actions):
    renamed = []
    failures = []
    kept_paths = set()

    for action in actions:
        if not action["matched"]:
            continue
        src = action["src"]
        dest = action["dest"]
        if same_path(src, dest):
            renamed.append(action)
            kept_paths.add(os.path.normcase(os.path.abspath(dest)))
            continue
        try:
            shutil.move(src, dest)
        except OSError as exc:
            failures.append(f"{src} -> {dest}: {exc}")
            kept_paths.add(os.path.normcase(os.path.abspath(src)))
            continue
        renamed.append(action)
        kept_paths.add(os.path.normcase(os.path.abspath(dest)))

    deleted_files = 0
    for dirpath, _, filenames in os.walk(DCIM_DIR):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.normcase(os.path.abspath(path)) in kept_paths:
                continue
            try:
                os.remove(path)
                deleted_files += 1
            except OSError as exc:
                failures.append(f"{path}: {exc}")

    deleted_folders = 0
    for dirpath, _, _ in os.walk(DCIM_DIR, topdown=False):
        if same_path(dirpath, DCIM_DIR) or not os.path.isdir(dirpath):
            continue
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
                deleted_folders += 1
        except OSError as exc:
            failures.append(f"{dirpath}: {exc}")

    return renamed, deleted_files, deleted_folders, failures


def describe_plan(actions, other_files, folders, play_count):
    matched = [
        action for action in actions
        if action["matched"] and not same_path(action["src"], action["dest"])
    ]
    already = [
        action for action in actions
        if action["matched"] and same_path(action["src"], action["dest"])
    ]
    unmatched = [action for action in actions if not action["matched"]]
    lines = [
        f"CSV pitches with PlayID: {play_count}",
        f"MOV files found: {len(actions)}",
        f"Clips to rename: {len(matched) + len(already)}",
        f"Unmatched MOV files to delete: {len(unmatched)}",
        f"Other files to delete: {len(other_files)}",
        f"Folders to delete: {len(folders)}",
        "",
        "Renames:",
    ]
    if matched or already:
        for action in matched + already:
            lines.append(
                f"  {os.path.basename(action['src'])} -> {os.path.basename(action['dest'])}"
            )
    else:
        lines.append("  (none)")
    if unmatched:
        lines.extend(["", "Unmatched MOV files to delete:"])
        for action in unmatched:
            lines.append(f"  {os.path.basename(action['src'])}")
    return "\n".join(lines)


def main():
    root = tk.Tk()
    root.withdraw()

    csv_files = filedialog.askopenfilenames(
        title="Select CSV files",
        filetypes=(("CSV files", "*.csv"), ("all files", "*.*")),
    )
    if not csv_files:
        print("No CSV selected.")
        root.destroy()
        return

    if not os.path.isdir(DCIM_DIR):
        messagebox.showerror(
            "SD card not found",
            f"Could not find {DCIM_DIR}. Connect the Edgertronic card and try again.",
        )
        root.destroy()
        return

    try:
        plays, skipped, duplicates = load_plays(csv_files)
    except Exception as exc:
        messagebox.showerror("Could not read CSV", str(exc))
        root.destroy()
        return

    if not plays:
        messagebox.showerror(
            "No pitches",
            "No usable PlayID rows were found in the selected CSV.",
        )
        root.destroy()
        return

    movs, other_files, folders = scan_dcim(DCIM_DIR)
    actions = plan_moves(movs, plays, DCIM_DIR)
    summary = describe_plan(actions, other_files, folders, len(plays))
    if skipped:
        summary += f"\n\nSkipped CSV rows missing PlayID, Pitcher, or PitchNo: {skipped}"
    if duplicates:
        summary += f"\nDuplicate PlayIDs ignored: {duplicates}"

    print(summary)
    matched_count = sum(1 for action in actions if action["matched"])
    unmatched_count = len(actions) - matched_count
    proceed = messagebox.askyesno(
        "Rename Edgertronic clips",
        "\n".join([
            f"CSV pitches with PlayID: {len(plays)}",
            f"MOV files found: {len(actions)}",
            f"Clips to rename: {matched_count}",
            f"Unmatched MOV files to delete: {unmatched_count}",
            f"Other files to delete: {len(other_files)}",
            f"Folders to delete: {len(folders)}",
            "",
            "The full rename list is printed in the console.",
            "Rename matching clips and delete every file that is not renamed?",
        ]),
    )
    if not proceed:
        print("Cancelled.")
        root.destroy()
        return

    renamed, deleted_files, deleted_folders, failures = apply_plan(actions)
    result = [
        f"Renamed: {len(renamed)}",
        f"Files deleted: {deleted_files}",
        f"Folders deleted: {deleted_folders}",
    ]
    if failures:
        result.append("")
        result.append("Could not change:")
        result.extend(f"  {item}" for item in failures)
    result_text = "\n".join(result)
    print(result_text)
    messagebox.showinfo("Edgertronic clips", result_text)
    root.destroy()


if __name__ == "__main__":
    main()
