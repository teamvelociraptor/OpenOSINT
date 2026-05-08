import urllib.parse

def search_face(image_url):
    """Generate reverse image search URLs for a given image URL."""
    encoded = urllib.parse.quote(image_url, safe='')
    results = [
        "[+] Reverse Image Search Links:",
        f"  Google Images:  https://www.google.com/searchbyimage?image_url={encoded}",
        f"  TinEye:         https://tineye.com/search?url={encoded}",
        f"  Bing Visual:    https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{encoded}",
        f"  Yandex:         https://yandex.com/images/search?url={encoded}&rpt=imageview",
        f"  FaceCheck.ID:   https://facecheck.id (manual upload required)",
    ]
    return "\n".join(results)
