import json, re, urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "lt"}
LIMIT = 80


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return r.read().decode("utf-8")


def initial_data(html):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    return json.loads(m.group(1)) if m else {}


def walk(node, key):
    if isinstance(node, dict):
        if key in node:
            yield node[key]
        for v in node.values():
            yield from walk(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v, key)


def uploads(channel_id):
    data = initial_data(get(f"https://www.youtube.com/playlist?list=UULF{channel_id[2:]}"))
    videos = []
    for r in walk(data, "playlistVideoRenderer"):
        title = "".join(run.get("text", "") for run in r.get("title", {}).get("runs", []))
        if r.get("videoId") and r.get("isPlayable", True):
            videos.append({"id": r["videoId"], "title": title})
    for r in walk(data, "lockupViewModel"):
        if r.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO" and r.get("contentId"):
            title = r.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", "")
            videos.append({"id": r["contentId"], "title": title})
    return videos


def from_feed(channel_id):
    xml = get(f"https://www.youtube.com/feeds/videos.xml?playlist_id=UULF{channel_id[2:]}")
    entries = re.findall(r"<yt:videoId>([^<]+)</yt:videoId>\s*<yt:channelId>[^<]+</yt:channelId>\s*<title>([^<]*)</title>", xml)
    return [{"id": i, "title": t.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")} for i, t in entries]


def avatar(channel_id):
    html = get(f"https://www.youtube.com/channel/{channel_id}")
    m = re.search(r'"avatar":\{"thumbnails":\[\{"url":"([^"]+)"', html) or re.search(r'<meta property="og:image" content="([^"]+)"', html)
    return m.group(1) if m else ""


def main():
    channels = json.load(open("channels.json"))
    try:
        old = {c["id"]: c for c in json.load(open("videos.json"))}
    except (FileNotFoundError, ValueError):
        old = {}
    out = []
    for c in channels:
        prev = old.get(c["id"], {})
        fresh = []
        for source in (uploads, from_feed):
            try:
                fresh = source(c["id"])
            except Exception as e:
                print(c["name"], source.__name__, "failed:", e)
            if fresh:
                break
        seen = set()
        merged = []
        for v in fresh + prev.get("videos", []):
            if v["id"] not in seen:
                seen.add(v["id"])
                merged.append(v)
        try:
            pic = avatar(c["id"]) or prev.get("avatar", "")
        except Exception:
            pic = prev.get("avatar", "")
        out.append({"name": c["name"], "id": c["id"], "avatar": pic, "videos": merged[:LIMIT]})
        print(c["name"], len(fresh), "fresh,", len(merged[:LIMIT]), "kept")
    with open("videos.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


main()
