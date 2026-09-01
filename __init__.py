"""Quick N-panel extension entry point."""


def register():
    from .registration import register_addon

    register_addon()


def unregister():
    from .registration import unregister_addon

    unregister_addon()
