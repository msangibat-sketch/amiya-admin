"""
Central path configuration for the assembly package. ASSET_ROOT is set from
the environment (see main.py) so this works both in local testing and on
the deployed service.
"""
import os

ASSET_ROOT = os.environ.get("ASSET_ROOT", "/app/assets")

SPREADS_DIR = os.path.join(ASSET_ROOT, "spreads")
LETTERS_DIR = os.path.join(ASSET_ROOT, "letters")
LETTERS_NIGHT_DIR = os.path.join(ASSET_ROOT, "letters_night")
FONTS_DIR = os.path.join(ASSET_ROOT, "fonts")

FONT_PLAYPEN = os.path.join(FONTS_DIR, "PlaypenSans-Regular.ttf")
FONT_NEXA = os.path.join(FONTS_DIR, "NexaScript-Regular.ttf")
FONT_NUNITO = os.path.join(FONTS_DIR, "Nunito-Custom450.ttf")
