import re
import unicodedata

def sanitize_filename(filename):
    """
    Removes illegal characters from filenames and normalizes Unicode (NFC).
    """
    # Normalize unicode to NFC (standard for web/linux/windows) to avoid mac NFD issues
    filename = unicodedata.normalize('NFC', filename)
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()
