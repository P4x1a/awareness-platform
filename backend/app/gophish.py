"""Cliente fino para a API REST do GoPhish."""
import requests
import urllib3

from .config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GoPhishError(Exception):
    pass


class GoPhish:
    def __init__(self) -> None:
        self.base = settings.GOPHISH_URL.rstrip("/")
        self.key = settings.GOPHISH_API_KEY
        self.verify = settings.VERIFY_SSL

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str):
        r = requests.get(self.base + path, headers=self._headers,
                         verify=self.verify, timeout=15)
        if r.status_code >= 400:
            raise GoPhishError(f"{r.status_code}: {r.text[:200]}")
        return r.json()

    def _post(self, path: str, data: dict):
        r = requests.post(self.base + path, headers=self._headers, json=data,
                          verify=self.verify, timeout=15)
        if r.status_code >= 400:
            raise GoPhishError(f"{r.status_code}: {r.text[:300]}")
        return r.json()

    def _put(self, path: str, data: dict):
        r = requests.put(self.base + path, headers=self._headers, json=data,
                         verify=self.verify, timeout=15)
        if r.status_code >= 400:
            raise GoPhishError(f"{r.status_code}: {r.text[:300]}")
        return r.json()

    def _delete(self, path: str):
        r = requests.delete(self.base + path, headers=self._headers,
                            verify=self.verify, timeout=15)
        if r.status_code >= 400:
            raise GoPhishError(f"{r.status_code}: {r.text[:300]}")
        return r.json()

    # --- Leitura (usada para montar o formulario de campanha e o dashboard) ---
    def templates(self):
        return self._get("/api/templates/")

    def pages(self):
        return self._get("/api/pages/")

    def smtp(self):
        return self._get("/api/smtp/")

    def groups(self):
        return self._get("/api/groups/")

    def campaigns(self):
        return self._get("/api/campaigns/")

    def summary(self):
        return self._get("/api/campaigns/summary")

    def campaign(self, campaign_id: int):
        return self._get(f"/api/campaigns/{campaign_id}")

    def group(self, group_id: int):
        return self._get(f"/api/groups/{group_id}")

    def smtp_profile(self, smtp_id: int):
        return self._get(f"/api/smtp/{smtp_id}")

    def template(self, template_id: int):
        return self._get(f"/api/templates/{template_id}")

    def page(self, page_id: int):
        return self._get(f"/api/pages/{page_id}")

    # --- Escrita ---
    def create_campaign(self, payload: dict):
        return self._post("/api/campaigns/", payload)

    # --- Grupos (escrita) ---
    def create_group(self, name: str, targets: list):
        return self._post("/api/groups/", {"name": name, "targets": targets})

    def update_group(self, group_id: int, name: str, targets: list):
        return self._put(
            f"/api/groups/{group_id}",
            {"id": group_id, "name": name, "targets": targets},
        )

    def delete_group(self, group_id: int):
        return self._delete(f"/api/groups/{group_id}")

    # --- Perfis de envio SMTP (escrita) ---
    def create_smtp(self, profile: dict):
        return self._post("/api/smtp/", profile)

    def update_smtp(self, smtp_id: int, profile: dict):
        payload = dict(profile)
        payload["id"] = smtp_id
        return self._put(f"/api/smtp/{smtp_id}", payload)

    def delete_smtp(self, smtp_id: int):
        return self._delete(f"/api/smtp/{smtp_id}")

    # --- Templates de e-mail (escrita) ---
    def create_template(self, tpl: dict):
        return self._post("/api/templates/", tpl)

    def update_template(self, template_id: int, tpl: dict):
        payload = dict(tpl)
        payload["id"] = template_id
        return self._put(f"/api/templates/{template_id}", payload)

    def delete_template(self, template_id: int):
        return self._delete(f"/api/templates/{template_id}")

    # --- Landing pages (escrita) ---
    def create_page(self, page: dict):
        return self._post("/api/pages/", page)

    def update_page(self, page_id: int, page: dict):
        payload = dict(page)
        payload["id"] = page_id
        return self._put(f"/api/pages/{page_id}", payload)

    def delete_page(self, page_id: int):
        return self._delete(f"/api/pages/{page_id}")
