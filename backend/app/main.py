"""Plataforma de Awareness - camada sobre o GoPhish (MVP).

Perfis:
  - si     : acesso total (lanca campanhas + ve relatorios)
  - gestor : somente leitura (ve o dashboard/relatorios)
"""
import base64
import csv
import io
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from starlette.middleware.sessions import SessionMiddleware

from . import db
from .config import settings
from .gophish import GoPhish

BASE_DIR = os.path.dirname(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Plataforma de Awareness", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# Marca disponivel em todos os templates (valores vindos do .env).
templates.env.globals["brand"] = settings.brand


def _user(request: Request):
    return request.session.get("user")


def _totals(campaigns):
    t = {"total": 0, "sent": 0, "opened": 0, "clicked": 0, "submitted": 0}
    for c in campaigns:
        s = c.get("stats", {}) or {}
        t["total"] += s.get("total", 0)
        t["sent"] += s.get("sent", 0)
        t["opened"] += s.get("opened", 0)
        t["clicked"] += s.get("clicked", 0)
        t["submitted"] += s.get("submitted_data", 0)
    return t


# --------------------------------------------------------------------------- #
#  Autenticacao
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if not _user(request):
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if _user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    row = db.verify_user(username, password)
    if not row:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuario ou senha invalidos."},
            status_code=401,
        )
    request.session["user"] = {"username": row["username"], "role": row["role"]}
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# --------------------------------------------------------------------------- #
#  Dashboard (SI e gestor)
# --------------------------------------------------------------------------- #
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    error = None
    campaigns = []
    try:
        summary = GoPhish().summary()
        campaigns = summary.get("campaigns", []) or []
    except Exception as exc:  # noqa: BLE001
        error = f"Nao foi possivel consultar o GoPhish: {exc}"

    campaigns.sort(key=lambda c: c.get("id", 0), reverse=True)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "campaigns": campaigns,
            "totals": _totals(campaigns),
            "error": error,
        },
    )


# --------------------------------------------------------------------------- #
#  Lancar campanha (somente SI)
# --------------------------------------------------------------------------- #
def _launch_options():
    gp = GoPhish()
    data = {"templates": [], "pages": [], "smtp": [], "groups": [], "error": None}
    try:
        data["templates"] = gp.templates()
        data["pages"] = gp.pages()
        data["smtp"] = gp.smtp()
        data["groups"] = gp.groups()
    except Exception as exc:  # noqa: BLE001
        data["error"] = f"Nao foi possivel consultar o GoPhish: {exc}"
    return data


@app.get("/campaigns/launch", response_class=HTMLResponse)
def launch_form(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    opts = _launch_options()
    return templates.TemplateResponse(
        "launch.html", {"request": request, "user": user, "ok": None, **opts}
    )


@app.post("/campaigns/launch", response_class=HTMLResponse)
def launch(
    request: Request,
    name: str = Form(...),
    template: str = Form(...),
    page: str = Form(...),
    smtp: str = Form(...),
    url: str = Form(...),
    group: str = Form(...),
):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    payload = {
        "name": name,
        "template": {"name": template},
        "page": {"name": page},
        "smtp": {"name": smtp},
        "url": url,
        "launch_date": datetime.now(timezone.utc).isoformat(),
        "groups": [{"name": group}],
    }

    opts = _launch_options()
    try:
        GoPhish().create_campaign(payload)
    except Exception as exc:  # noqa: BLE001
        opts["error"] = f"Erro ao criar campanha: {exc}"
        return templates.TemplateResponse(
            "launch.html", {"request": request, "user": user, "ok": None, **opts},
            status_code=400,
        )

    return RedirectResponse("/dashboard", status_code=303)


# --------------------------------------------------------------------------- #
#  Grupos de alvos (somente SI) - cadastro manual + import de CSV
# --------------------------------------------------------------------------- #
# Cabecalhos de CSV reconhecidos (PT/EN) -> campo do GoPhish.
_HEADER_MAP = {
    "first_name": "first_name", "firstname": "first_name", "first name": "first_name",
    "nome": "first_name", "primeiro nome": "first_name",
    "last_name": "last_name", "lastname": "last_name", "last name": "last_name",
    "sobrenome": "last_name", "ultimo nome": "last_name",
    "email": "email", "e-mail": "email", "mail": "email",
    "position": "position", "cargo": "position", "funcao": "position",
    "setor": "position", "departamento": "position",
}


def _target(first, last, email, position):
    email = (email or "").strip()
    if not email or "@" not in email:
        return None
    return {
        "first_name": (first or "").strip(),
        "last_name": (last or "").strip(),
        "email": email,
        "position": (position or "").strip(),
    }


def _cells_to_target(cells):
    """Monta um alvo a partir de uma lista de colunas, localizando a coluna
    de e-mail automaticamente (robusto a ordens diferentes)."""
    cells = [(c or "").strip() for c in cells]
    email_i = next((i for i, c in enumerate(cells) if "@" in c), None)
    if email_i is None:
        return None
    before = [c for c in cells[:email_i] if c]
    after = [c for c in cells[email_i + 1:] if c]
    first = before[0] if before else ""
    last = " ".join(before[1:]) if len(before) > 1 else ""
    position = after[0] if after else ""
    return _target(first, last, cells[email_i], position)


def _parse_csv(raw: bytes):
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except Exception:  # noqa: BLE001
        delim = ";" if sample.count(";") > sample.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)
            if any((c or "").strip() for c in r)]
    if not rows:
        return []

    mapped = [_HEADER_MAP.get((c or "").strip().lower()) for c in rows[0]]
    targets = []
    if any(mapped):  # tem cabecalho reconhecido
        idx = {field: i for i, field in enumerate(mapped) if field}

        def col(r, f):
            i = idx.get(f)
            return r[i] if i is not None and i < len(r) else ""

        for r in rows[1:]:
            t = _target(col(r, "first_name"), col(r, "last_name"),
                        col(r, "email"), col(r, "position"))
            if t:
                targets.append(t)
    else:  # sem cabecalho: detecta e-mail em cada linha
        for r in rows:
            t = _cells_to_target(r)
            if t:
                targets.append(t)
    return targets


def _parse_manual(text: str):
    targets = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        cells = line.replace("\t", ";").replace(",", ";").split(";")
        t = _cells_to_target(cells)
        if t:
            targets.append(t)
    return targets


def _dedup(targets):
    seen, out = set(), []
    for t in targets:
        key = t["email"].lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


@app.get("/groups", response_class=HTMLResponse)
def groups_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    error = None
    groups = []
    try:
        groups = GoPhish().groups() or []
    except Exception as exc:  # noqa: BLE001
        error = f"Nao foi possivel consultar o GoPhish: {exc}"
    groups.sort(key=lambda g: g.get("name", "").lower())
    return templates.TemplateResponse(
        "groups.html",
        {"request": request, "user": user, "groups": groups, "error": error, "ok": None},
    )


@app.post("/groups/new", response_class=HTMLResponse)
def groups_new(
    request: Request,
    name: str = Form(...),
    members: str = Form(""),
    file: UploadFile = File(None),
):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    targets = []
    if file is not None and file.filename:
        try:
            targets += _parse_csv(file.file.read())
        except Exception as exc:  # noqa: BLE001
            return _groups_error(request, user, f"Falha ao ler o CSV: {exc}")
    targets += _parse_manual(members)
    targets = _dedup(targets)

    if not targets:
        return _groups_error(
            request, user,
            "Nenhum alvo valido encontrado. Informe ao menos um e-mail (via CSV ou na lista).",
        )

    try:
        GoPhish().create_group(name.strip(), targets)
    except Exception as exc:  # noqa: BLE001
        return _groups_error(request, user, f"Erro ao criar o grupo: {exc}")

    return RedirectResponse("/groups", status_code=303)


@app.post("/groups/{group_id}/delete")
def groups_delete(request: Request, group_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        GoPhish().delete_group(group_id)
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse("/groups", status_code=303)


def _groups_error(request: Request, user, msg: str):
    groups = []
    try:
        groups = GoPhish().groups() or []
    except Exception:  # noqa: BLE001
        pass
    groups.sort(key=lambda g: g.get("name", "").lower())
    return templates.TemplateResponse(
        "groups.html",
        {"request": request, "user": user, "groups": groups, "error": msg, "ok": None},
        status_code=400,
    )


# --------------------------------------------------------------------------- #
#  Perfis de envio SMTP (somente SI)
# --------------------------------------------------------------------------- #
def _smtp_list():
    try:
        return GoPhish().smtp() or [], None
    except Exception as exc:  # noqa: BLE001
        return [], f"Nao foi possivel consultar o GoPhish: {exc}"


def _render_smtp(request, user, error=None, status=200, edit=None):
    profiles, list_err = _smtp_list()
    profiles.sort(key=lambda p: (p.get("name") or "").lower())
    return templates.TemplateResponse(
        "smtp.html",
        {"request": request, "user": user, "profiles": profiles,
         "error": error or list_err, "edit": edit},
        status_code=status,
    )


def _smtp_header_from(from_header: str):
    return [{"key": "From", "value": from_header.strip()}] if from_header.strip() else []


@app.get("/smtp", response_class=HTMLResponse)
def smtp_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    return _render_smtp(request, user)


@app.get("/smtp/{smtp_id}/edit", response_class=HTMLResponse)
def smtp_edit_form(request: Request, smtp_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    try:
        profile = GoPhish().smtp_profile(smtp_id)
    except Exception as exc:  # noqa: BLE001
        return _render_smtp(request, user, error=f"Nao foi possivel carregar o perfil: {exc}",
                            status=400)
    # extrai o header From personalizado (se houver) para preencher o campo
    profile["from_header"] = next(
        (h.get("value", "") for h in (profile.get("headers") or [])
         if (h.get("key") or "").lower() == "from"), "")
    return _render_smtp(request, user, edit=profile)


@app.post("/smtp/new", response_class=HTMLResponse)
def smtp_new(
    request: Request,
    name: str = Form(...),
    from_address: str = Form(...),
    host: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    ignore_cert: str = Form(""),
    from_header: str = Form(""),
):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    profile = {
        "name": name.strip(),
        "interface_type": "SMTP",
        "from_address": from_address.strip(),
        "host": host.strip(),
        "username": username.strip(),
        "password": password,
        "ignore_cert_errors": bool(ignore_cert),
        "headers": _smtp_header_from(from_header),
    }
    try:
        GoPhish().create_smtp(profile)
    except Exception as exc:  # noqa: BLE001
        return _render_smtp(request, user, error=f"Erro ao criar o perfil: {exc}", status=400)
    return RedirectResponse("/smtp", status_code=303)


@app.post("/smtp/{smtp_id}/edit", response_class=HTMLResponse)
def smtp_update(
    request: Request,
    smtp_id: int,
    name: str = Form(...),
    from_address: str = Form(...),
    host: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    ignore_cert: str = Form(""),
    from_header: str = Form(""),
):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)

    gp = GoPhish()
    # Se a senha vier em branco, mantem a que ja esta salva no GoPhish.
    if not password:
        try:
            password = (gp.smtp_profile(smtp_id) or {}).get("password", "")
        except Exception:  # noqa: BLE001
            password = ""

    profile = {
        "name": name.strip(),
        "interface_type": "SMTP",
        "from_address": from_address.strip(),
        "host": host.strip(),
        "username": username.strip(),
        "password": password,
        "ignore_cert_errors": bool(ignore_cert),
        "headers": _smtp_header_from(from_header),
    }
    try:
        gp.update_smtp(smtp_id, profile)
    except Exception as exc:  # noqa: BLE001
        return _render_smtp(request, user, error=f"Erro ao atualizar o perfil: {exc}",
                            status=400)
    return RedirectResponse("/smtp", status_code=303)


@app.post("/smtp/{smtp_id}/delete")
def smtp_delete(request: Request, smtp_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        GoPhish().delete_smtp(smtp_id)
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse("/smtp", status_code=303)


# --------------------------------------------------------------------------- #
#  Templates de e-mail (somente SI)
# --------------------------------------------------------------------------- #
def _render_templates(request, user, error=None, status=200, edit=None):
    items, list_err = [], None
    try:
        items = GoPhish().templates() or []
    except Exception as exc:  # noqa: BLE001
        list_err = f"Nao foi possivel consultar o GoPhish: {exc}"
    items.sort(key=lambda t: (t.get("name") or "").lower())
    return templates.TemplateResponse(
        "templates.html",
        {"request": request, "user": user, "items": items,
         "error": error or list_err, "edit": edit},
        status_code=status,
    )


@app.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    return _render_templates(request, user)


@app.get("/templates/{template_id}/edit", response_class=HTMLResponse)
def template_edit_form(request: Request, template_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        edit = GoPhish().template(template_id)
    except Exception as exc:  # noqa: BLE001
        return _render_templates(request, user, error=f"Nao foi possivel carregar: {exc}",
                                 status=400)
    return _render_templates(request, user, edit=edit)


@app.post("/templates/new", response_class=HTMLResponse)
def template_new(request: Request, name: str = Form(...), subject: str = Form(""),
                 html: str = Form("")):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    if not html.strip():
        return _render_templates(request, user, error="O corpo (HTML) nao pode ficar vazio.",
                                 status=400)
    tpl = {"name": name.strip(), "subject": subject, "html": html, "text": ""}
    try:
        GoPhish().create_template(tpl)
    except Exception as exc:  # noqa: BLE001
        return _render_templates(request, user, error=f"Erro ao criar: {exc}", status=400)
    return RedirectResponse("/templates", status_code=303)


@app.post("/templates/{template_id}/edit", response_class=HTMLResponse)
def template_update(request: Request, template_id: int, name: str = Form(...),
                    subject: str = Form(""), html: str = Form("")):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    if not html.strip():
        return _render_templates(request, user, error="O corpo (HTML) nao pode ficar vazio.",
                                 status=400)
    tpl = {"name": name.strip(), "subject": subject, "html": html, "text": ""}
    try:
        GoPhish().update_template(template_id, tpl)
    except Exception as exc:  # noqa: BLE001
        return _render_templates(request, user, error=f"Erro ao atualizar: {exc}", status=400)
    return RedirectResponse("/templates", status_code=303)


@app.post("/templates/{template_id}/delete")
def template_delete(request: Request, template_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        GoPhish().delete_template(template_id)
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse("/templates", status_code=303)


# --------------------------------------------------------------------------- #
#  Landing pages (somente SI)
# --------------------------------------------------------------------------- #
def _render_pages(request, user, error=None, status=200, edit=None):
    items, list_err = [], None
    try:
        items = GoPhish().pages() or []
    except Exception as exc:  # noqa: BLE001
        list_err = f"Nao foi possivel consultar o GoPhish: {exc}"
    items.sort(key=lambda p: (p.get("name") or "").lower())
    return templates.TemplateResponse(
        "pages.html",
        {"request": request, "user": user, "items": items,
         "error": error or list_err, "edit": edit},
        status_code=status,
    )


def _page_payload(name, html, capture_credentials, capture_passwords, redirect_url):
    cc = bool(capture_credentials)
    return {
        "name": name.strip(),
        "html": html,
        "capture_credentials": cc,
        # senha so e capturada se credenciais tambem forem; desligada por padrao.
        "capture_passwords": cc and bool(capture_passwords),
        "redirect_url": redirect_url.strip(),
    }


@app.get("/pages", response_class=HTMLResponse)
def pages_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    return _render_pages(request, user)


@app.get("/pages/{page_id}/edit", response_class=HTMLResponse)
def page_edit_form(request: Request, page_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        edit = GoPhish().page(page_id)
    except Exception as exc:  # noqa: BLE001
        return _render_pages(request, user, error=f"Nao foi possivel carregar: {exc}", status=400)
    return _render_pages(request, user, edit=edit)


@app.post("/pages/new", response_class=HTMLResponse)
def page_new(request: Request, name: str = Form(...), html: str = Form(""),
             capture_credentials: str = Form(""), capture_passwords: str = Form(""),
             redirect_url: str = Form("")):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    if not html.strip():
        return _render_pages(request, user, error="O HTML da pagina nao pode ficar vazio.",
                             status=400)
    payload = _page_payload(name, html, capture_credentials, capture_passwords, redirect_url)
    try:
        GoPhish().create_page(payload)
    except Exception as exc:  # noqa: BLE001
        return _render_pages(request, user, error=f"Erro ao criar: {exc}", status=400)
    return RedirectResponse("/pages", status_code=303)


@app.post("/pages/{page_id}/edit", response_class=HTMLResponse)
def page_update(request: Request, page_id: int, name: str = Form(...), html: str = Form(""),
                capture_credentials: str = Form(""), capture_passwords: str = Form(""),
                redirect_url: str = Form("")):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    if not html.strip():
        return _render_pages(request, user, error="O HTML da pagina nao pode ficar vazio.",
                             status=400)
    payload = _page_payload(name, html, capture_credentials, capture_passwords, redirect_url)
    try:
        GoPhish().update_page(page_id, payload)
    except Exception as exc:  # noqa: BLE001
        return _render_pages(request, user, error=f"Erro ao atualizar: {exc}", status=400)
    return RedirectResponse("/pages", status_code=303)


@app.post("/pages/{page_id}/delete")
def page_delete(request: Request, page_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != "si":
        return RedirectResponse("/dashboard", status_code=303)
    try:
        GoPhish().delete_page(page_id)
    except Exception:  # noqa: BLE001
        pass
    return RedirectResponse("/pages", status_code=303)


# --------------------------------------------------------------------------- #
#  Detalhe da campanha (SI e gestor) - quem abriu, clicou, enviou
# --------------------------------------------------------------------------- #
_SENT_LIKE = {"Email Sent", "Email Opened", "Clicked Link", "Submitted Data", "Email Reported"}
_OPENED_LIKE = {"Email Opened", "Clicked Link", "Submitted Data"}
_CLICKED_LIKE = {"Clicked Link", "Submitted Data"}


def _result_stats(results):
    return {
        "total": len(results),
        "sent": sum(1 for r in results if r.get("status") in _SENT_LIKE),
        "opened": sum(1 for r in results if r.get("status") in _OPENED_LIKE),
        "clicked": sum(1 for r in results if r.get("status") in _CLICKED_LIKE),
        "submitted": sum(1 for r in results if r.get("status") == "Submitted Data"),
    }


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(request: Request, campaign_id: int):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    error, campaign, results, timeline, stats = None, None, [], [], _result_stats([])
    clicked_people, submitted_people = [], []
    try:
        campaign = GoPhish().campaign(campaign_id)
        results = campaign.get("results", []) or []
        timeline = campaign.get("timeline", []) or []
        stats = _result_stats(results)
        clicked_people = [r for r in results if r.get("status") in _CLICKED_LIKE]
        submitted_people = [r for r in results if r.get("status") == "Submitted Data"]
    except Exception as exc:  # noqa: BLE001
        error = f"Nao foi possivel carregar a campanha: {exc}"

    timeline = list(reversed(timeline))  # mais recentes primeiro
    return templates.TemplateResponse(
        "campaign_detail.html",
        {"request": request, "user": user, "campaign": campaign, "results": results,
         "timeline": timeline, "stats": stats, "error": error,
         "clicked_people": clicked_people, "submitted_people": submitted_people},
    )


# --------------------------------------------------------------------------- #
#  Diretoria / Executivo (SI e gestor) - visao de alto nivel
# --------------------------------------------------------------------------- #
@app.get("/diretoria", response_class=HTMLResponse)
def diretoria(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    error, campaigns = None, []
    try:
        campaigns = (GoPhish().summary().get("campaigns", []) or [])
    except Exception as exc:  # noqa: BLE001
        error = f"Nao foi possivel consultar o GoPhish: {exc}"

    totals = _totals(campaigns)
    sent = totals["sent"] or 0
    click_rate = round(totals["clicked"] / sent * 100, 1) if sent else 0.0
    open_rate = round(totals["opened"] / sent * 100, 1) if sent else 0.0
    submit_rate = round(totals["submitted"] / sent * 100, 1) if sent else 0.0

    # Classificacao de risco pela taxa de clique
    if click_rate >= 30:
        risk = {"label": "Alto", "cls": "risk-high"}
    elif click_rate >= 10:
        risk = {"label": "Medio", "cls": "risk-mid"}
    else:
        risk = {"label": "Baixo", "cls": "risk-low"}

    # ranking: campanhas por taxa de clique (piores primeiro)
    ranked = []
    for c in campaigns:
        s = c.get("stats", {}) or {}
        cs, cc = s.get("sent", 0) or 0, s.get("clicked", 0) or 0
        ranked.append({"name": c.get("name", ""), "id": c.get("id"),
                       "rate": round(cc / cs * 100, 1) if cs else 0.0,
                       "clicked": cc, "sent": cs})
    ranked.sort(key=lambda r: r["rate"], reverse=True)

    return templates.TemplateResponse(
        "diretoria.html",
        {"request": request, "user": user, "error": error, "totals": totals,
         "click_rate": click_rate, "open_rate": open_rate, "submit_rate": submit_rate,
         "risk": risk, "ranked": ranked, "n_campaigns": len(campaigns)},
    )


# --------------------------------------------------------------------------- #
#  Simulacao: pagina educativa + arquivo-teste de antivirus (EICAR)
#  Rotas PUBLICAS (sem login) - sao o destino do "Redirect to" da landing
#  no GoPhish. O arquivo servido e o EICAR padrao da industria: totalmente
#  inofensivo, mas reconhecido por qualquer antivirus/EDR (ex.: Sophos) como
#  ameaca, so para validar que a protecao detecta e bloqueia. O conteudo e
#  montado em runtime a partir de base64 para a assinatura nao ficar literal
#  no codigo-fonte (senao o proprio arquivo .py seria colocado em quarentena).
# --------------------------------------------------------------------------- #
_EICAR_B64 = ("WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5E"
              "QVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=")
# Nome "convincente" do arquivo entregue apos o envio dos dados.
_FAKE_FILENAME = "Teams_AtualizacaoDeSeguranca.exe"


@app.get("/educativo", response_class=HTMLResponse)
def educativo(request: Request):
    return templates.TemplateResponse(
        "educativo.html",
        {"request": request, "download_url": "/educativo/baixar",
         "fake_filename": _FAKE_FILENAME},
    )


@app.get("/educativo/baixar")
def educativo_baixar():
    data = base64.b64decode(_EICAR_B64)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{_FAKE_FILENAME}"'},
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
