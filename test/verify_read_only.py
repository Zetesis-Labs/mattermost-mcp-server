#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

MATTERMOST = "http://127.0.0.1:18065"
MCP = "http://127.0.0.1:18080/mcp"
COMPOSE = ["docker", "compose", "-f", str(Path(__file__).with_name("compose.yaml"))]
PASSWORD = "Prueba-de-solo-lectura-1"

READ_TOOLS = frozenset("""
get_bot get_channel_groups get_channel_info get_channel_member get_channel_member_counts get_channel_members
get_channel_members_by_ids get_channel_members_by_status get_channel_moderations get_channel_stats get_channel_unread
get_dm_common_teams get_file_info get_file_link get_group_info get_me get_mentions get_new_users_in_team get_post_files
get_post_info get_post_reactions get_posts_around_unread get_role get_team_groups get_team_info get_team_member
get_team_members get_team_stats get_threads get_unread_counts get_user get_user_by_email get_user_by_username
get_user_channel_memberships get_user_channels get_user_cpa_values get_user_custom_status get_user_groups get_user_stats
get_user_status get_user_teams get_users_by_ids get_users_by_usernames get_users_in_group_channels get_users_in_team
get_users_not_in_channel get_users_not_in_team get_users_statuses list_agents list_archived_channels list_bots
list_channel_bookmarks list_cpa_fields list_custom_emoji list_drafts list_groups list_outgoing_webhooks list_pinned_posts
list_saved_posts list_scheduled_posts list_sidebar_categories list_team_channels read_channel read_file read_post
search_channels search_custom_emoji search_files search_posts search_teams search_users search_users_in_channel
search_users_in_team
""".split())

BLOCKED_TOOLS = frozenset("""
acknowledge_post add_channel_member add_channel_members add_reaction add_team_member add_team_members archive_channel
convert_channel_privacy create_channel create_channel_bookmark create_draft create_post create_post_as_user
create_scheduled_post create_team create_user delete_channel_bookmark delete_draft delete_post delete_scheduled_post dm
group_message invite_users_to_team invite_users_to_team_and_channels list_incoming_webhooks mark_channel_read
mark_channels_viewed mark_post_unread pin_post remove_channel_member remove_reaction remove_team_member restore_channel
save_post set_channel_favorite set_channel_mute set_dnd set_post_reminder set_status set_thread_follow unpin_post
update_channel update_channel_bookmark update_channel_member_roles update_channel_notify_props update_post
update_scheduled_post update_team update_team_member_roles update_user upload_file
""".split())

EXPECTED_READ_FAILURES = {
    **dict.fromkeys(
        """
        get_channel_groups get_channel_moderations get_group_info get_team_groups get_user_cpa_values get_user_groups
        list_channel_bookmarks list_cpa_fields list_groups list_scheduled_posts
        """.split(),
        "license",
    ),
    "list_agents": "AI plugin returned status 500",
    "read_file": "read file failed with status 500",
}

READ_ONLY_POSTS = tuple(
    re.compile(pattern)
    for pattern in (
        r"/api/v4/channels/search",
        r"/api/v4/channels/stats/member_count",
        r"/api/v4/channels/[a-z0-9]{26}/members/ids",
        r"/api/v4/emoji/search",
        r"/api/v4/posts/search",
        r"/api/v4/teams/[a-z0-9]{26}/files/search",
        r"/api/v4/teams/[a-z0-9]{26}/posts/search",
        r"/api/v4/teams/search",
        r"/api/v4/users/group_channels",
        r"/api/v4/users/ids",
        r"/api/v4/users/search",
        r"/api/v4/users/status/ids",
        r"/api/v4/users/usernames",
    )
)


def http(method, url, body=None, headers=None, raw=False):
    data = body if isinstance(body, bytes) else None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            return response.status, response.headers, payload if raw else parse_json(payload)
    except urllib.error.HTTPError as error:
        payload = error.read()
        return error.code, error.headers, payload if raw else parse_json(payload)


def parse_json(payload):
    try:
        return json.loads(payload) if payload else None
    except ValueError:
        return payload.decode(errors="replace")


class Api:
    def __init__(self, token=None):
        self.token = token

    def call(self, method, path, body=None, headers=None):
        all_headers = dict(headers or {})
        if self.token:
            all_headers["Authorization"] = f"Bearer {self.token}"
        status, response_headers, payload = http(method, f"{MATTERMOST}/api/v4{path}", body, all_headers)
        if status >= 300:
            raise RuntimeError(f"{method} {path}: {status} {payload}")
        return payload, response_headers


def upload_file(api, channel_id):
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="channel_id"\r\n\r\n{channel_id}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="nota.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\ncontenido del archivo\r\n--{boundary}--\r\n"
    ).encode()
    request = urllib.request.Request(f"{MATTERMOST}/api/v4/files", data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    request.add_header("Authorization", f"Bearer {api.token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["file_infos"][0]["id"]


def seed():
    run = uuid.uuid4().hex[:8]
    email = f"admin-{run}@example.test"
    username = f"admin-{run}"
    public = Api()
    admin_user, _ = public.call("POST", "/users", {"email": email, "username": username, "password": PASSWORD})
    _, login_headers = public.call("POST", "/users/login", {"login_id": username, "password": PASSWORD})
    admin = Api(login_headers["Token"])
    colleague, _ = admin.call(
        "POST", "/users", {"email": f"colega-{run}@example.test", "username": f"colega-{run}", "password": PASSWORD}
    )
    team, _ = admin.call("POST", "/teams", {"name": f"equipo-{run}", "display_name": "Equipo", "type": "O"})
    admin.call("POST", f"/teams/{team['id']}/members", {"team_id": team["id"], "user_id": colleague["id"]})
    channel, _ = admin.call(
        "POST", "/channels", {"team_id": team["id"], "name": f"canal-{run}", "display_name": "Canal", "type": "O"}
    )
    admin.call("POST", f"/channels/{channel['id']}/members", {"user_id": colleague["id"]})
    file_id = upload_file(admin, channel["id"])
    post, _ = admin.call(
        "POST", "/posts", {"channel_id": channel["id"], "message": "mensaje semilla", "file_ids": [file_id]}
    )
    incoming, _ = admin.call("POST", "/hooks/incoming", {"channel_id": channel["id"], "display_name": "entrada"})
    outgoing, _ = admin.call(
        "POST",
        "/hooks/outgoing",
        {
            "team_id": team["id"],
            "channel_id": channel["id"],
            "display_name": "salida",
            "trigger_words": ["disparo"],
            "callback_urls": ["http://example.invalid/salida"],
        },
    )
    token, _ = admin.call("POST", f"/users/{admin_user['id']}/tokens", {"description": "prueba"})
    bot, _ = admin.call("POST", "/bots", {"username": f"bot-{run}", "display_name": "Bot"})
    direct, _ = admin.call("POST", "/channels/direct", [admin_user["id"], colleague["id"]])
    return {
        "bot_id": bot["user_id"],
        "direct_id": direct["id"],
        "admin": admin,
        "token": token["token"],
        "user_id": admin_user["id"],
        "username": username,
        "email": email,
        "colleague_id": colleague["id"],
        "colleague_username": colleague["username"],
        "team_id": team["id"],
        "team_name": team["name"],
        "channel_id": channel["id"],
        "channel_name": channel["name"],
        "post_id": post["id"],
        "file_id": file_id,
        "incoming_id": incoming["id"],
        "outgoing_token": outgoing["token"],
    }


class McpClient:
    def __init__(self, token):
        self.token = token
        self.session = None
        self.next_id = 1
        self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "verify-read-only", "version": "1"},
            },
        )
        self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def post(self, message):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        status, response_headers, payload = http("POST", MCP, message, headers, raw=True)
        self.session = response_headers.get("Mcp-Session-Id") or self.session
        return status, payload.decode(errors="replace")

    def rpc(self, method, params):
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}
        self.next_id += 1
        status, text = self.post(message)
        for line in text.splitlines():
            if line.startswith("data:"):
                response = json.loads(line[5:])
                if response.get("id") == message["id"]:
                    return response
        try:
            return json.loads(text)
        except ValueError as error:
            raise RuntimeError(f"{method}: HTTP {status}: {text[:300]}") from error

    def tools(self):
        return self.rpc("tools/list", {})["result"]["tools"]

    def call(self, name, arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments})


def mattermost_requests():
    output = subprocess.run(
        [*COMPOSE, "logs", "--no-log-prefix", "--no-color", "mattermost"], capture_output=True, text=True, check=True
    ).stdout
    requests = []
    for line in output.splitlines():
        try:
            entry = json.loads(line)
        except ValueError as error:
            if "Received HTTP request" in line:
                raise RuntimeError(f"registro de Mattermost ilegible: {line[:200]}") from error
            continue
        if entry.get("msg") == "Received HTTP request":
            requests.append((entry.get("method"), entry.get("url"), entry.get("status_code")))
    return requests


def settled_requests():
    seen = mattermost_requests()
    for _ in range(15):
        time.sleep(2)
        latest = mattermost_requests()
        if len(latest) == len(seen):
            return latest
        seen = latest
    raise RuntimeError("los registros de Mattermost no dejan de crecer")


def read_arguments(tool, seeded):
    values = {
        "bot_user_id": seeded["bot_id"],
        "channel_id": seeded["channel_id"],
        "channel_ids": [seeded["channel_id"]],
        "email": seeded["email"],
        "file_id": seeded["file_id"],
        "group_id": "a" * 26,
        "post_id": seeded["post_id"],
        "query": "semilla",
        "team_id": seeded["team_id"],
        "term": "admin",
        "terms": "nota",
        "user_id": seeded["colleague_id"],
        "user_ids": [seeded["colleague_id"]],
        "username": seeded["colleague_username"],
        "usernames": [seeded["colleague_username"]],
    }
    overrides = {
        "get_channel_info": {"channel_id": seeded["channel_id"]},
        "get_dm_common_teams": {"channel_id": seeded["direct_id"]},
        "get_role": {"role_name": "system_user"},
        "get_team_info": {"team_id": seeded["team_id"]},
    }
    if tool["name"] in overrides:
        return overrides[tool["name"]]
    required = tool.get("inputSchema", {}).get("required") or []
    return {name: values[name] for name in required}


def result_text(response):
    result = response.get("result")
    if result is None:
        return True, json.dumps(response.get("error"))
    text = " ".join(item.get("text", "") for item in result.get("content", []))
    return bool(result.get("isError")), text


def post_count(seeded):
    posts, _ = seeded["admin"].call("GET", f"/channels/{seeded['channel_id']}/posts?per_page=200")
    return len(posts["order"])


def wait_until_ready():
    for _ in range(120):
        try:
            mattermost_ready, _, _ = http("GET", f"{MATTERMOST}/api/v4/system/ping")
            mcp_ready, _, _ = http("POST", MCP, {})
            if mattermost_ready == 200 and mcp_ready == 401:
                return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("el entorno de prueba no ha arrancado")


def verify():
    failures = []
    seeded = seed()

    before = post_count(seeded)
    hook_status, _, _ = http("POST", f"{MATTERMOST}/hooks/{seeded['incoming_id']}", {"text": "sin autenticar"})
    if hook_status != 200 or post_count(seeded) != before + 1:
        failures.append("control: el ID de un webhook de entrada ya no permite publicar sin autenticarse")

    client = McpClient(seeded["token"])
    posts_before = post_count(seeded)
    mark = len(settled_requests())

    tools ={tool["name"]: tool for tool in client.tools()}
    for name in sorted(set(tools) - READ_TOOLS):
        failures.append(f"herramienta no permitida en la lista: {name}")
    for name in sorted(READ_TOOLS - set(tools)):
        failures.append(f"falta la herramienta de lectura: {name}")
    for name, tool in sorted(tools.items()):
        if name in READ_TOOLS and not tool.get("annotations", {}).get("readOnlyHint"):
            failures.append(f"sin marca de solo lectura: {name}")

    blocked_arguments = {
        "create_post": {
            "channel_id": seeded["channel_id"],
            "channel_display_name": "Canal",
            "team_display_name": "Equipo",
            "message": "esto no debe publicarse",
        },
    }
    for name in sorted(BLOCKED_TOOLS):
        _, text = result_text(client.call(name, blocked_arguments.get(name, {})))
        if "available at Enterprise and above" not in text and "unknown tool" not in text:
            failures.append(f"no la rechaza el filtro: {name}: {text[:120]}")

    secrets = {
        "ID de webhook de entrada": seeded["incoming_id"],
        "token de webhook de salida": seeded["outgoing_token"],
        "token personal": seeded["token"],
    }
    read_failures = {}
    for name, tool in sorted(tools.items()):
        if name not in READ_TOOLS:
            continue
        is_error, text = result_text(client.call(name, read_arguments(tool, seeded)))
        if is_error:
            read_failures[name] = text
        for label, secret in secrets.items():
            if secret in text:
                failures.append(f"{name} devuelve una credencial: {label}")
    if "list_incoming_webhooks" in tools:
        _, text = result_text(client.call("list_incoming_webhooks", {}))
        if seeded["incoming_id"] in text:
            failures.append("list_incoming_webhooks devuelve una credencial: ID de webhook de entrada")

    for name in sorted(set(read_failures) - set(EXPECTED_READ_FAILURES)):
        failures.append(f"falla contra este Mattermost: {name}: {read_failures[name][:160]}")
    for name, reason in sorted(EXPECTED_READ_FAILURES.items()):
        if name not in read_failures:
            failures.append(f"ya funciona, hay que quitarla de los fallos esperados: {name}")
        elif reason not in read_failures[name]:
            failures.append(f"falla por otro motivo: {name}: {read_failures[name][:160]}")

    mcp_logs = subprocess.run(
        [*COMPOSE, "logs", "--no-color", "mcp"], capture_output=True, text=True, check=True
    ).stdout
    for label, secret in secrets.items():
        if secret in mcp_logs:
            failures.append(f"el MCP registra una credencial: {label}")

    requests = settled_requests()[mark:]
    if post_count(seeded) != posts_before:
        failures.append("el canal ha cambiado: se ha publicado a través del MCP")
    if not any(method == "GET" for method, _, _ in requests):
        failures.append("control: no se ha registrado ninguna lectura, la vigilancia no está mirando")
    writes = sorted(
        {
            (method, re.sub(r"[a-z0-9]{26}", "<id>", url))
            for method, url, _ in requests
            if method != "GET" and not (method == "POST" and any(p.fullmatch(url) for p in READ_ONLY_POSTS))
        }
    )
    for method, url in writes:
        failures.append(f"petición que no es de lectura a Mattermost: {method} {url}")

    print(f"Herramientas expuestas: {len(tools)}. Peticiones vigiladas: {len(requests)}.")
    print(f"Fallos de lectura contra este Mattermost: {sorted(read_failures)}")
    return failures


def main():
    subprocess.run([*COMPOSE, "down", "-v", "--remove-orphans"], check=True, capture_output=True)
    subprocess.run([*COMPOSE, "up", "-d", "--build", "--wait", "mysql"], check=True)
    subprocess.run([*COMPOSE, "up", "-d", "--build"], check=True)
    try:
        wait_until_ready()
        failures = verify()
    finally:
        if "--keep" not in sys.argv:
            subprocess.run([*COMPOSE, "down", "-v", "--remove-orphans"], check=True, capture_output=True)
    for failure in failures:
        print(f"FALLO: {failure}")
    print("La imagen es de solo lectura." if not failures else f"{len(failures)} fallos.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
