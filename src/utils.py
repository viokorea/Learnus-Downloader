import re

def sanitize_filename(filename):
    """
    Removes illegal characters from filenames.
    """
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()
