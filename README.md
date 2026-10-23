# Plataforma de Awareness (camada sobre o GoPhish)

Console web que usa a **API REST do GoPhish** como motor de envio e tracking e
entrega, por cima dele, uma interface simples e visual para a equipe de
Segurança da Informação: montar grupos, perfis de envio (SMTP), templates e
landing pages, lançar campanhas e acompanhar resultados — tudo pela própria
plataforma, sem precisar abrir o painel cru do GoPhish.

> **Uso autorizado apenas.** Esta é uma ferramenta de *phishing simulado* para
> treinamento e conscientização interna. Use somente em ambientes e contra
> pessoas que você está formalmente autorizado a testar.

> **Projeto genérico:** nenhuma informação de empresa fica no código. Tudo que é
> sensível (URL do GoPhish, API key, senhas, marca) vem de variáveis de
> ambiente (`.env`), que **não** é versionado. Seguro para guardar em
> repositório privado.

---

## O que a plataforma faz

| Área | Descrição |
|------|-----------|
| **Dashboard** | Totais consolidados + tabela por campanha com taxa de clique e de submissão. |
| **Grupos** | Importa alvos por **CSV** ou manualmente, sem sair da plataforma. |
| **SMTP (Sending Profiles)** | Cria, edita, ativa e remove perfis de envio. |
| **Templates** | Cria e edita templates de e-mail (HTML). |
| **Landing Pages** | Cria e edita páginas de captura, com opção de capturar (ou não) os dados submetidos. |
| **Lançar campanha** | Junta template + landing + SMTP + grupo + URL e cria a campanha no GoPhish. |
| **Detalhe da campanha** | Mostra **quem abriu, quem clicou e quem submeteu dados**, com linha do tempo. |
| **Diretoria** | Visão executiva: gráfico de risco, ranking e indicadores para liderança. |
| **Follow-up educativo** | Quem "cai" é levado a uma página que explica o teste e dispara um **arquivo de teste inofensivo (EICAR)** para validar o antivírus. |

### Perfis de acesso

| Perfil   | Pode fazer                                      |
|----------|-------------------------------------------------|
| `si`     | Tudo: montar campanhas, lançar e ver relatórios |
| `gestor` | Somente visualizar dashboard e relatórios       |

---

## Stack
- **Backend:** Python 3.12 + FastAPI
- **Frontend:** Jinja2 + Bootstrap 5 (renderizado no servidor)
- **Auth:** sessão por cookie; usuários em SQLite (senha com bcrypt)
- **Integração:** API REST do GoPhish (Bearer token)
- **Deploy:** Docker + docker-compose

---

## Pré-requisitos
- Um **GoPhish** já rodando (idealmente via Docker na mesma VM).
- **Docker** e **docker compose** instalados.
- A **API Key** do GoPhish (em *Account Settings → API Key*).

---

## Instalação

```bash
# 1. Clone o repositório
git clone <URL-DO-SEU-REPO>.git
cd gophish-platform

# 2. Configure o ambiente
cp .env.example .env
nano .env   # preencha GOPHISH_API_KEY, SECRET_KEY e ADMIN_PASSWORD
```

No `.env`, o mínimo a ajustar:

| Variável | O que colocar |
|----------|---------------|
| `GOPHISH_URL` | `https://gophish:3333` (mesma rede docker) ou `https://IP-DA-VM:3333` |
| `GOPHISH_API_KEY` | a API Key do GoPhish |
| `SECRET_KEY` | uma chave aleatória longa — gere com `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_USER` / `ADMIN_PASSWORD` | o admin inicial (perfil `si`), criado no primeiro start |

**Marca (opcional):** as variáveis `BRAND_*` dão a cara da sua organização
(nome, logo, favicon, cores). Deixe em branco para a aparência genérica.

```bash
# 3. Confirme o nome da rede docker do GoPhish e ajuste no docker-compose.yml
#    (campo networks.gophish-net.name)
docker network ls | grep gophish

# 4. Suba a plataforma
docker compose up -d --build
docker compose logs -f awareness-platform

# 5. Acesse no navegador
#    http://IP-DA-VM:8000   (entre com o ADMIN_USER / ADMIN_PASSWORD do .env)
```

### Sem rede docker compartilhada?
Troque no `.env` para falar com o GoPhish pelo IP:
```
GOPHISH_URL=https://IP-DA-VM:3333
```
e remova o bloco `networks:` do `docker-compose.yml` (o serviço fica na rede padrão).

---

## Tutorial de uso (fluxo de uma campanha)

1. **Grupos** → crie o grupo de alvos. Importe um CSV (modelo em
   `docs/exemplo-grupo.csv`) ou cadastre manualmente.
2. **SMTP** → cadastre um perfil de envio (servidor, porta, usuário, senha,
   remetente) e deixe-o ativo.
3. **Templates** → crie o e-mail. Use `{{.FirstName}}`, `{{.URL}}` (link
   rastreado) e `{{.Tracker}}` (pixel de abertura).
4. **Landing Pages** → crie a página de captura. Para simulação, deixe
   **"capturar senha" DESLIGADO** (não guarde a senha real do colaborador) e
   configure o *redirect* para a página educativa (`/educativo`).
5. **Lançar** → escolha template + landing + SMTP + grupo, informe a **URL**
   que os alvos vão acessar e dispare.
6. **Dashboard / Detalhe da campanha** → acompanhe em tempo real quem abriu,
   clicou e submeteu dados.
7. **Diretoria** → visão consolidada para apresentar à liderança.

### Campanha educativa (bloqueio pelo antivírus)
Há um fluxo pronto em `campanhas/` (tema "expiração de senha do Teams"): quem
submete as credenciais é levado a `/educativo`, que explica o teste e baixa um
**arquivo EICAR** — um arquivo-padrão **inofensivo** que todo antivírus detecta.
Serve para demonstrar, com segurança, o bloqueio do endpoint. **Não** há malware
real em nenhum momento.

---

## Segurança e boas práticas
- **Autorização formal** da liderança antes de qualquer disparo contra colegas.
- Mantenha o repositório **privado**.
- Nunca versione o `.env` (já está no `.gitignore`).
- Se a API Key ou alguma senha vazar (ex.: em um print), **rotacione** na hora.
- Capturar senha real: mantenha **desligado**.
- Use um **domínio próprio** com SPF/DMARC no remetente para entrega e legitimidade.

---

## Estrutura
```
gophish-platform/
├── docker-compose.yml
├── .env.example
├── README.md
├── ARQUITETURA.md
├── docs/
│   └── exemplo-grupo.csv        # modelo de importação de alvos
├── campanhas/                   # modelos de campanha (uso autorizado)
│   ├── email-teams-expiracao.html
│   ├── landing-teams-login.html
│   └── deploy-logo.sh
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py              # rotas (auth, dashboard, console, campanhas, educativo)
        ├── config.py            # configuração e marca via env
        ├── db.py                # usuários/perfis (SQLite + bcrypt)
        ├── gophish.py           # cliente da API do GoPhish
        ├── static/              # style.css, app.js, marca
        └── templates/           # páginas (base, login, dashboard, grupos, smtp, ...)
```
