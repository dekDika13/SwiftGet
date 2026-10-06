"""Efek kaca NATIVE macOS (eksperimental). Butuh: pip install pyobjc-framework-Cocoa

Di macOS 26 (Tahoe) memakai NSGlassEffectView (Liquid Glass asli) bila tersedia; kalau tidak, NSVisualEffectView (blur).
Qt tidak bisa menggambar Liquid Glass sendiri, jadi lapisan kaca ditaruh di belakang tampilan Qt."""
import sys


def apply(widget) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import objc
        from AppKit import NSColor
        view = objc.objc_object(c_void_p=int(widget.winId()))
        win = view.window()
        if win is None:
            return False
        glass = None
        try:
            glass = objc.lookUpClass("NSGlassEffectView").alloc().initWithFrame_(view.frame())
        except Exception:
            glass = None
        win.setOpaque_(False)
        win.setBackgroundColor_(NSColor.clearColor())
        win.setTitlebarAppearsTransparent_(True)
        if glass is not None:
            glass.setAutoresizingMask_(18)       # lebar + tinggi mengikuti jendela
            win.setContentView_(glass)
            glass.setContentView_(view)
            view.setFrame_(glass.bounds())
            view.setAutoresizingMask_(18)
            return True
        from AppKit import NSVisualEffectView, NSWindowBelow
        eff = NSVisualEffectView.alloc().initWithFrame_(view.frame())
        eff.setMaterial_(21)                      # underWindowBackground
        eff.setBlendingMode_(0)                   # behindWindow
        eff.setState_(1)                          # selalu aktif
        eff.setAutoresizingMask_(18)
        content = win.contentView()
        if content.isEqual_(view):
            win.setContentView_(eff)
            eff.addSubview_(view)
            view.setFrame_(eff.bounds())
            view.setAutoresizingMask_(18)
        else:
            content.addSubview_positioned_relativeTo_(eff, NSWindowBelow, view)
        return True
    except Exception:
        return False
