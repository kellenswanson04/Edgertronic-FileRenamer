# Edgertronic Renamer

Renames bullpen MOV clips on an Edgertronic SD card so each file matches the pitch in a Trackman CSV.

## Needs/Assumptions
- Windows
- Python with pandas installed (pip install pandas)
- The Trackman bullpen CSV
- The SD card plugged in so the clips are at D:\DCIM

The CSV must have these columns: PlayID, Pitcher, PitchNo, TaggedPitchType.

## How to run
1. Plug in the SD card.
2. Run: python edge-renamer.py
3. Select the bullpen CSV. You can pick more than one.
4. Check the counts in the popup, then confirm.

## What it does
Each MOV file is named with a Trackman PlayID. If that PlayID is in the CSV, the clip is renamed to:

FirstnameLastname-PitchCount-PitchType.MOV

## Example
Swanson, Kellen, his first pitch in the file, a fastball:
KellenSwanson-1-Fastball.MOV

PitchCount starts at 1 for each pitcher. It is that pitcher's own pitch number in the CSV, not the PitchNo column. PitchNo 123 is still 1 if it is that pitcher's first pitch.

Pitcher names are flipped from "Last, First" to FirstLast, with the space removed.

A few Trackman pitch tags are shortened to match the reports:
- FourSeamFastBall becomes Fastball
- TwoSeamFastBall and OneSeamFastBall become Sinker
- Changeup becomes ChangeUp

## What gets deleted
After the rename, everything else on D:\DCIM is deleted. That includes other file types, folders, and MOV files that did not match a PlayID.

Clips that already have the FirstnameLastname-PitchCount-PitchType name are left alone, so running the script again will not delete them.

The popup lists what will be renamed and deleted before anything is changed. The full list is also printed in the console.

## Credit

- Author: Kellen Swanson
