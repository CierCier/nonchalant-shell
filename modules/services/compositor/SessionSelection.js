.pragma library

function select(explicit, niriSocket, hyprlandSignature, desktop) {
    if (explicit)
        return explicit === "niri" || explicit === "hyprland" ? explicit : "unsupported";
    if (niriSocket && hyprlandSignature) {
        const names = desktop.toLowerCase().split(":");
        if (names.includes("niri") && !names.includes("hyprland"))
            return "niri";
        if (names.includes("hyprland") && !names.includes("niri"))
            return "hyprland";
        return "ambiguous";
    }
    return niriSocket ? "niri" : (hyprlandSignature ? "hyprland" : "unsupported");
}
