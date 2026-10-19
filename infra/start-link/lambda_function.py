"""CareBridge start link: opening the URL starts the server (if stopped) and shows a page that waits until the app
answers, then goes to it. Needs ?key=<START_KEY>. Env: INSTANCE_ID, APP_URL, START_KEY."""
import html, os, urllib.request, boto3
ec2 = boto3.client("ec2")
IID, APP, KEY = os.environ["INSTANCE_ID"], os.environ["APP_URL"], os.environ["START_KEY"]

def page(title, msg, refresh=True):
    meta = '<meta http-equiv="refresh" content="10">' if refresh else ""
    return {"statusCode": 200, "headers": {"content-type": "text/html; charset=utf-8", "cache-control": "no-store"},
            "body": f"""<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">{meta}
<title>CareBridge</title><style>body{{font:17px -apple-system,Segoe UI,sans-serif;max-width:32em;margin:15vh auto;padding:0 16px;color:#1d1d1f}}
h1{{font-size:24px}}a{{color:#0071e3}}</style></head><body><h1>{html.escape(title)}</h1><p>{msg}</p></body></html>"""}

def healthy():
    try:
        with urllib.request.urlopen(APP + "/api/health", timeout=4) as r:
            return b'"ready":true' in r.read()
    except Exception:
        return False

def lambda_handler(event, context):
    if (event.get("queryStringParameters") or {}).get("key") != KEY:
        return {"statusCode": 403, "body": "Not allowed"}
    state = ec2.describe_instances(InstanceIds=[IID])["Reservations"][0]["Instances"][0]["State"]["Name"]
    if state == "stopped":
        ec2.start_instances(InstanceIds=[IID])
        return page("Starting CareBridge…", "The server is starting. This page checks every 10 seconds; allow about 3 minutes.")
    if state in ("pending", "stopping"):
        return page("Starting CareBridge…", f"Server is {state}. This page refreshes by itself.")
    if state == "running" and healthy():
        return {"statusCode": 302, "headers": {"location": APP}, "body": ""}
    if state == "running":
        return page("Loading the speech and translation models…", "Almost there. This page refreshes by itself.")
    return page("CareBridge can't start", f"Server state: {html.escape(state)}.", refresh=False)
