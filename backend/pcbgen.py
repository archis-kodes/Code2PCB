# pcbgen.py  — dynamic JSON → KiCad board + Gerbers (KiCad 6)


# Run this
# & "C:\Program Files\KiCad\6.0\bin\python.exe" "C:\Users\Archisman\Videos\codetopcb\backend\pcbgen.py" "C:\Users\Archisman\Videos\codetopcb\backend\design.json" dynamic_pcb

import pcbnew
import os
import json
import glob
import re

# Map: footprint_name -> list of .pretty directories that contain it
FOOTPRINT_INDEX = {}  # {"R_0805_2012Metric": [".../Resistor_SMD.pretty", ...], ...}
DEFAULT_PLACEHOLDER = ("Resistor_SMD", "R_0805_2012Metric")  # fallback

def _existing_dirs(paths):
    return [p for p in paths if p and os.path.isdir(p)]

def _guess_kicad_share_dirs():
    # Try KiCad 8/7/6 env vars first, then Program Files fallbacks
    envs = [
        os.getenv("KICAD8_FOOTPRINT_DIR"),
        os.getenv("KICAD7_FOOTPRINT_DIR"),
        os.getenv("KICAD6_FOOTPRINT_DIR"),
    ]
    pf = r"C:\Program Files\KiCad"
    candidates = []
    for major in ("8.0", "7.0", "6.0"):
        d = os.path.join(pf, major, "share", "kicad", "footprints")
        candidates.append(d)
    return _existing_dirs(envs + candidates)

def build_footprint_index(extra_search_paths=None):
    """
    Build index of footprint names -> .pretty directory paths.
    Scans KiCad stock libs and any user-provided folders (.pretty or parent).
    """
    global FOOTPRINT_INDEX
    FOOTPRINT_INDEX.clear()

    search_roots = _guess_kicad_share_dirs()
    if extra_search_paths:
        # Accept both .pretty and parent dirs; expand to .pretty
        for p in extra_search_paths:
            if p.lower().endswith(".pretty"):
                search_roots.append(p)
            elif os.path.isdir(p):
                # Add all .pretty under this folder
                search_roots.extend(glob.glob(os.path.join(p, "*.pretty")))

    search_roots = _existing_dirs(list(dict.fromkeys(search_roots)))  # dedupe & keep order

    print("🔍 Scanning libraries:")
    for root in search_roots:
        print("   •", root)
        pretty_dirs = [root] if root.lower().endswith(".pretty") else glob.glob(os.path.join(root, "*.pretty"))
        for libdir in pretty_dirs:
            for modpath in glob.glob(os.path.join(libdir, "*.kicad_mod")):
                name = os.path.splitext(os.path.basename(modpath))[0]
                FOOTPRINT_INDEX.setdefault(name, []).append(libdir)

    print(f"✅ Indexed {len(FOOTPRINT_INDEX)} unique footprints")

def _fuzzy_find_name(requested):
    """Best-effort fuzzy match: ignore non-alnum, case-insensitive, allow substrings."""
    norm = re.sub(r"[^A-Za-z0-9]", "", requested).lower()
    if not norm:
        return None
    # Exact ignoring punctuation
    for cand in FOOTPRINT_INDEX.keys():
        if re.sub(r"[^A-Za-z0-9]", "", cand).lower() == norm:
            return cand
    # Substring match
    for cand in FOOTPRINT_INDEX.keys():
        if norm in re.sub(r"[^A-Za-z0-9]", "", cand).lower():
            return cand
    return None

def _resolve_footprint_path(name):
    """
    Given a footprint base name, return (pretty_dir, footprint_name)
    using our index. Picks the first path if multiple.
    """
    if name in FOOTPRINT_INDEX and FOOTPRINT_INDEX[name]:
        return FOOTPRINT_INDEX[name][0], name
    # try fuzzy
    fuzzy = _fuzzy_find_name(name)
    if fuzzy and FOOTPRINT_INDEX.get(fuzzy):
        print(f"⚠️ Fuzzy matched '{name}' -> '{fuzzy}'")
        return FOOTPRINT_INDEX[fuzzy][0], fuzzy
    return None, None

def _placeholder_path():
    """Find placeholder R_0805_2012Metric anywhere."""
    libnick, fpname = DEFAULT_PLACEHOLDER
    # Prefer a library dir that looks like the nickname
    for name, dirs in FOOTPRINT_INDEX.items():
        if name == fpname and dirs:
            return dirs[0], fpname
    # Last resort: any 0805 resistor variant
    for k, dirs in FOOTPRINT_INDEX.items():
        if "0805" in k and "R_" in k and dirs:
            return dirs[0], k
    return None, None  # should not happen if stock libs exist

def _place_footprint_props(footprint, comp):
    footprint.Reference().SetText(comp["name"])
    footprint.Value().SetText(comp.get("value", comp.get("type", comp["name"])))
    footprint.SetPosition(pcbnew.wxPointMM(comp["position"]["x"], comp["position"]["y"]))
    footprint.SetOrientationDegrees(float(comp.get("rotation", 0.0)))
    return footprint

def load_footprint(comp):
    """
    Load a footprint robustly:
      1) exact match by file name,
      2) fuzzy match,
      3) placeholder
    Returns a placed FOOTPRINT ready to add to board.
    """
    req = str(comp["footprint"]).strip()
    pretty_dir, fpname = _resolve_footprint_path(req)

    if pretty_dir and fpname:
        fp = pcbnew.FootprintLoad(pretty_dir, fpname)
        if fp:
            print(f"✅ {comp['name']}: {fpname}  ← {os.path.basename(pretty_dir)}")
            return _place_footprint_props(fp, comp)
        else:
            print(f"⚠️ Failed to load {fpname} from {pretty_dir}, will use placeholder")

    # Placeholder
    pdir, pname = _placeholder_path()
    if pdir and pname:
        fp = pcbnew.FootprintLoad(pdir, pname)
        if fp:
            print(f"⚠️ {comp['name']}: using placeholder {pname} from {os.path.basename(pdir)}")
            return _place_footprint_props(fp, comp)

    raise RuntimeError(f"Could not load footprint for {comp['name']} (requested '{req}')")

def generate_pcb(pcb_json, project_name="dynamic_pcb"):
    # Optional: user-provided extra library roots
    extra_paths = []
    libs = pcb_json.get("libraries")
    if isinstance(libs, dict):
        extra_paths = libs.get("footprint_paths", []) or []
    build_footprint_index(extra_paths)

    board = pcbnew.BOARD()

    # Board outline (use mm consistently)
    width_mm = float(pcb_json["board"]["size"]["width"])
    height_mm = float(pcb_json["board"]["size"]["height"])
    outline = [
        pcbnew.wxPointMM(0, 0),
        pcbnew.wxPointMM(width_mm, 0),
        pcbnew.wxPointMM(width_mm, height_mm),
        pcbnew.wxPointMM(0, height_mm),
        pcbnew.wxPointMM(0, 0),
    ]
    for i in range(len(outline) - 1):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(outline[i])
        seg.SetEnd(outline[i + 1])
        seg.SetLayer(pcbnew.Edge_Cuts)
        board.Add(seg)

    # Place components
    for comp in pcb_json.get("components", []):
        try:
            fp = load_footprint(comp)
            board.Add(fp)
        except Exception as e:
            print(f"❌ Failed to place {comp.get('name','?')}: {e}")

    # Save .kicad_pcb
    out_dir = os.path.abspath(project_name)
    os.makedirs(out_dir, exist_ok=True)
    board_file = os.path.join(out_dir, f"{project_name}.kicad_pcb")
    pcbnew.SaveBoard(board_file, board)
    print(f"✅ PCB saved to {board_file}")

    # Plot Gerbers
    gerber_dir = os.path.join(out_dir, "gerbers")
    os.makedirs(gerber_dir, exist_ok=True)

    pc = pcbnew.PLOT_CONTROLLER(board)
    po = pc.GetPlotOptions()
    po.SetOutputDirectory(gerber_dir)
    po.SetUseGerberProtelExtensions(True)
    po.SetExcludeEdgeLayer(True)
    po.SetScale(1.0)

    layers = [
        (pcbnew.F_Cu, "F_Cu"),
        (pcbnew.B_Cu, "B_Cu"),
        (pcbnew.F_SilkS, "F_SilkS"),
        (pcbnew.B_SilkS, "B_SilkS"),
        (pcbnew.F_Mask, "F_Mask"),
        (pcbnew.B_Mask, "B_Mask"),
        (pcbnew.Edge_Cuts, "Edge_Cuts"),
    ]
    for layer, name in layers:
        pc.SetLayer(layer)
        pc.OpenPlotfile(name, pcbnew.PLOT_FORMAT_GERBER, name)
        pc.PlotLayer()
    pc.ClosePlot()
    print(f"✅ Gerbers written to {gerber_dir}")

    return board_file, gerber_dir

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: pcbgen.py <design.json> [project_name]")
        sys.exit(1)

    json_file = sys.argv[1]
    project_name = sys.argv[2] if len(sys.argv) > 2 else "dynamic_pcb"

    with open(json_file, "r", encoding="utf-8") as f:
        pcb_json = json.load(f)

    generate_pcb(pcb_json, project_name)
