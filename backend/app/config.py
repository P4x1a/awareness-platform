"""Configuracao via variaveis de ambiente. Nenhum dado da empresa fica no codigo."""
import os


class Settings:
    # URL do GoPhish (API de administracao). Ex.: https://gophish:3333 (mesma rede docker)
    # ou https://IP-DA-VM:3333.
    GOPHISH_URL: str = os.getenv("GOPHISH_URL", "https://gophish:3333")
    # Chave de API do GoPhish (Account Settings -> API Key).
    GOPHISH_API_KEY: str = os.getenv("GOPHISH_API_KEY", "")
    # O GoPhish usa certificado self-signed por padrao; deixe "false" para nao validar.
    VERIFY_SSL: bool = os.getenv("GOPHISH_VERIFY_SSL", "false").lower() == "true"

    # Chave para assinar os cookies de sessao. TROQUE por um valor aleatorio longo.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "troque-esta-chave")

    # Usuario administrador (perfil SI) criado automaticamente no primeiro start.
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")

    # Caminho do banco SQLite da propria plataforma (usuarios/papeis).
    DB_PATH: str = os.getenv("DB_PATH", "/data/app.db")

    # ------------------------------------------------------------------ #
    #  Identidade visual (marca) - 100% por env, sem dados no codigo.
    #  Deixe em branco/padrao para a versao generica; preencha no .env
    #  para dar a cara da sua organizacao.
    # ------------------------------------------------------------------ #
    BRAND_NAME: str = os.getenv("BRAND_NAME", "Security Awareness")
    BRAND_SHORT: str = os.getenv("BRAND_SHORT", "Awareness")
    BRAND_TAGLINE: str = os.getenv("BRAND_TAGLINE", "Conscientizacao em Seguranca da Informacao")
    # URL de um logo (opcional). Vazio -> usa um icone padrao + o nome.
    BRAND_LOGO_URL: str = os.getenv("BRAND_LOGO_URL", "")
    # Favicon (opcional). Vazio -> usa o logo, se houver, senao um escudo padrao.
    BRAND_FAVICON_URL: str = os.getenv("BRAND_FAVICON_URL", "")
    # Paleta. Padroes neutros; troque no .env pela cor da sua marca.
    BRAND_PRIMARY: str = os.getenv("BRAND_PRIMARY", "#0a5bd3")
    BRAND_PRIMARY_DARK: str = os.getenv("BRAND_PRIMARY_DARK", "#083f93")
    BRAND_ACCENT: str = os.getenv("BRAND_ACCENT", "#f39200")

    # Escudo padrao (data URI) usado como favicon quando nao ha logo/favicon.
    _DEFAULT_FAVICON = (
        "data:image/svg+xml,"
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
        "fill='%230a5bd3'%3E%3Cpath d='M12 2 4 5v7c0 6 8 10 8 10s8-4 8-10V5z'/"
        "%3E%3C/svg%3E"
    )

    @property
    def brand(self) -> dict:
        favicon = self.BRAND_FAVICON_URL or self.BRAND_LOGO_URL or self._DEFAULT_FAVICON
        return {
            "name": self.BRAND_NAME,
            "short": self.BRAND_SHORT,
            "tagline": self.BRAND_TAGLINE,
            "logo_url": self.BRAND_LOGO_URL,
            "favicon": favicon,
            "primary": self.BRAND_PRIMARY,
            "primary_dark": self.BRAND_PRIMARY_DARK,
            "accent": self.BRAND_ACCENT,
        }


settings = Settings()
