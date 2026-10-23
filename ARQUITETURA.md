# Arquitetura

## Visao geral

```
+---------------------+        API REST (Bearer)        +-----------+        SMTP        +--------------+
|  Plataforma (web)   |  ----------------------------->  |  GoPhish  |  --------------->  | Servidor     |
|  FastAPI + Jinja2   |   /api/templates, /campaigns...  |  (motor)  |   (Zimbra etc.)    | de e-mail    |
|  SQLite (usuarios)  |  <-----------------------------  |           |                    +--------------+
+---------------------+        resultados/stats          +-----------+
        |                                                      |
   cookie de sessao                                       phish server
   (SI / gestor)                                       (landing + tracking)
```

- O **GoPhish** continua sendo o motor: envia os e-mails, hospeda a landing page
  e registra abertura/clique/submit.
- A **plataforma** nao reimplementa nada disso: ela orquestra o GoPhish pela API
  e guarda apenas o que e dela (usuarios e papeis) num SQLite proprio.

## Decisoes

| Tema            | Decisao                                   | Porque |
|-----------------|-------------------------------------------|--------|
| Linguagem       | Python 3.12 + FastAPI                     | Leve, facil de manter, otimo p/ integrar API |
| Frontend        | Jinja2 + Bootstrap (server-rendered)      | "Frontend simples", sem build de SPA |
| Auth            | Sessao por cookie + bcrypt                | Simples e adequado a app interna |
| Papeis          | `si` (total) / `gestor` (leitura)         | Requisito: gestores so veem relatorios |
| Config          | 100% por variaveis de ambiente            | Sem dados da empresa no codigo -> versionavel |
| Deploy          | Container ao lado do GoPhish              | Mesma VM, mesma rede docker |

## Fluxos

### Lancar campanha (perfil SI)
1. A plataforma consulta no GoPhish: templates, landing pages, perfis SMTP e grupos.
2. Monta o formulario com essas opcoes.
3. No submit, faz `POST /api/campaigns/` no GoPhish com os nomes escolhidos + URL.
4. O GoPhish dispara; a plataforma volta ao dashboard.

### Dashboard (SI e gestor)
1. `GET /api/campaigns/summary` no GoPhish.
2. Agrega totais (alvos, enviados, aberturas, cliques, submits) e lista por campanha.
3. Calcula taxa de clique por campanha.

## Seguranca
- Nenhum segredo no codigo; tudo em `.env` (git-ignorado).
- Senha de usuario com hash **bcrypt**.
- Admin de perfil SI por padrao; gestores entram como leitura.
- Recomenda-se expor a plataforma apenas na rede interna (como o painel do GoPhish).

## Pontos de evolucao (mapeados, fora do MVP)
- **Por departamento:** hoje o GoPhish nao tem "setor" nativo. Opcoes: usar 1 grupo
  por setor, ou um prefixo/convencao no nome do grupo, ou enriquecer via campo de
  `Position`. A camada de agregacao por setor entra quando definirmos a convencao.
- **Importar alvos:** endpoint para upload de CSV -> cria/atualiza grupos via API.
- **Follow-up educativo:** redirect da landing para pagina de conscientizacao +
  (futuro) e-mail automatico de "voce caiu num teste" via webhook do GoPhish.
- **Webhooks do GoPhish:** receber eventos em tempo real em vez de so fazer polling.
