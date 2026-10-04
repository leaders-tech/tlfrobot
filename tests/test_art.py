"""The renderer drives the Timo art through its manifest; keep the two in step."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "art" / "workshop"
SVG = "{http://www.w3.org/2000/svg}"
ROBOT_PARTS = {"shadow", "drive", "body", "heading", "sensor", "gripper-base", "gripper-left",
               "gripper-right", "roller", "eraser", "cargo-hatch", "eyes", "eyelids"}


def test_manifest_assets_and_parts():
    manifest = json.loads((ART / "manifest.json").read_text())
    assert manifest["format"] == "tlfrobot-art/1"
    ids = {a["id"] for a in manifest["assets"]}
    assert {f"A{i:02d}" for i in range(1, 23)} <= ids
    for asset in manifest["assets"]:
        root = ET.parse(ART / asset["path"]).getroot()
        assert root.get("viewBox"), asset["path"]
        found = {el.get("id") for el in root.iter() if el.get("id")}
        assert set(asset.get("parts", [])) <= found, (asset["path"], set(asset["parts"]) - found)
        for el in root.iter():
            assert el.tag not in (SVG + "image", SVG + "script", SVG + "foreignObject"), asset["path"]
            href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href")
            assert href is None or href.startswith("#"), (asset["path"], href)


def test_robot_master_has_every_part():
    robot = next(a for a in json.loads((ART / "manifest.json").read_text())["assets"] if a["id"] == "A01")
    assert ROBOT_PARTS <= set(robot["parts"])
    for anchor in ("pivot", "cargo", "probe_origin", "grip_contact", "cell_object", "badge_region"):
        assert anchor in robot["anchors"]


def test_clips_cover_the_templates():
    clips = json.loads((ART / "animation" / "clips.json").read_text())
    assert {c["id"] for c in clips["items"]} >= {f"C{i:02d}" for i in range(1, 21)}
