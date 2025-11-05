# 🧾 KADRIX-SEFAZ  
### Automação de Emissão e Retorno de Notas Fiscais  
**Kairós Motores | Cliente: VALE**

---

## 📋 Descrição Geral

O **KADRIX-SEFAZ** é um sistema de automação desenvolvido pela **Kairós Motores** para o cliente **VALE**, responsável por gerenciar e automatizar todo o processo de **emissão, retorno e organização de Notas Fiscais de Serviço (NFS-e)** emitidas nas unidades da **Kairós de São Luís (MA)** e **Parauapebas (PA)**.

O sistema processa automaticamente os e-mails de faturamento recebidos, analisa os anexos **PDF**, realiza a **emissão de notas** nas plataformas da **SEFAZ-MA** e **SEFAZ-PA**, faz o **download dos arquivos PDF e XML numerados**, e envia o **retorno ao cliente** com os documentos anexados.

---

## ⚙️ Principais Funcionalidades

### 📨 Processamento Automático de E-mails
- Lê e processa automaticamente e-mails com o assunto **“FATURAMENTO DE SERVIÇOS”**.  
- Identifica e valida anexos **PDF**, evitando duplicidades.  
- Analisa o texto do corpo do e-mail e compara com a descrição dentro do PDF.  
- Realiza **correções automáticas** quando há divergência nas descrições de serviço.

### 🏢 Priorização por Unidade
- Determina qual unidade da Kairós (**MA ou PA**) possui **maior número de notas pendentes**.  
- Processa essa unidade primeiro, garantindo **maior eficiência operacional**.

---

## 📂 Estrutura do Projeto

```bash
KADRIX-SEFAZ
│
├── app/
│   ├── __init__.py
│   └── app.py                 # Ponto de entrada principal (GUI + inicialização)
│
├── build/                     # Diretório gerado automaticamente pelo PyInstaller
├── dist/                      # Contém o executável final (.exe)
├── env/                       # Ambiente virtual Python (não versionado)
│
├── functions/
│   └── renomeia_arquivo.py    # Renomeia e organiza arquivos após emissão
│
├── icons/
│   ├── icon_kadrix.png
│   ├── kadrix_sefaz.ico
│   ├── logo_cent.png
│   ├── logo_dir.png
│   ├── logo_esq.png
│   └── rodape.png
│
├── process_email/
│   ├── ler_email.py           # Lógica de leitura e filtragem de e-mails
│   └── enviar_email.py        # Envio de e-mail com PDF/XML gerados
│
├── process_pdf/
│   ├── ler_pdf.py             # Extração e leitura de dados dos PDFs anexados
│   └── test_pdf.py            # Testes e validação de leitura
│
├── utils/
│   ├── driver.py              # Inicialização e controle do Selenium WebDriver
│   ├── services.py            # Funções auxiliares e integrações diversas
│   └── cnpj.json              # Mapeamento de CNPJs das unidades VALE ↔ clientes Kairós
│
├── web/
│   ├── web_app_slz.py         # Fluxo SEFAZ-MA (São Luís)
│   ├── web_app_prp.py         # Fluxo SEFAZ-PA (Parauapebas)
│   └── teste_impr.py          # Teste de impressão/validação visual
│
├── requirements.txt           # Dependências do projeto
├── KADRIX SEFAZ.spec          # Configuração do PyInstaller
├── KADRIX SEFAZ V2.spec       # Versão atualizada do executável
└── README.md                  # Documentação do projeto

```
🧠 Fluxo de Execução

1. Monitoramento de E-mails
→ Leitura dos e-mails com assunto “FATURAMENTO DE SERVIÇOS”.

2. Validação e Análise de PDFs
→ Identifica os PDFs anexados e extrai informações relevantes.
→ Corrige descrições divergentes entre corpo do e-mail e arquivo.

3. Seleção da Unidade Prioritária
→ Verifica qual unidade (São Luís ou Parauapebas) possui mais notas pendentes.
→ Processa primeiro a unidade com maior volume.

4. Automação Web (Selenium)

SEFAZ-MA (web_app_slz.py): Emissão direta e download automático via interface.

SEFAZ-PA (web_app_prp.py): Captura de sessão e download via requisições autenticadas.

5. Renomeação e Organização de Arquivos
→ Os arquivos são salvos conforme o padrão:
```bash
NFE 4730 - FERROVIA.pdf
nfse_4730.xml
```

→ Movidos automaticamente para pastas específicas por cliente.

6. Envio de Retorno ao Cliente
→ Envia e-mail de resposta com PDF e XML anexados.
→ Mensagem segue o padrão corporativo da Kairós.
→ E-mail original é movido para a pasta de processados.

🧾 Estrutura de Clientes (cnpj.json)

Arquivo: utils/cnpj.json
```bash
{
    "CNPJ-CLIENTE": "FERROVIA",
    "CNPJ-CLIENTE": "PELOTIZACAO",
    "CNPJ-CLIENTE": "PORTO",
    "CNPJ-CLIENTE": "SALOBO",
    "CNPJ-CLIENTE": "ONCA PUMA",
    "CNPJ-CLIENTE": "S11D",
    "CNPJ-CLIENTE": "CARAJAS",
    "CNPJ-CLIENTE": "SERRA LESTE",
    "CNPJ-CLIENTE": "SOSSEGO",
    "CNPJ-CLIENTE": "TERMINAL DE COBRE"
}
```
Este dicionário identifica e classifica automaticamente o cliente e o destino da nota com base no CNPJ da VALE informado no PDF.

🧰 Tecnologias Utilizadas

Python 3.10+

Selenium WebDriver (automação de navegador)

PyInstaller (geração de executável .exe)

Requests, Imaplib, Smtplib, Email (integração com e-mails)

PyPDF2 / pdfplumber (leitura e extração de texto de PDFs)

CustomTkinter / PyQt5 (interface gráfica)

.env (configurações e credenciais)

💾 Estrutura de Saída

Os arquivos gerados são organizados automaticamente em:
```bash
C:\NotasFiscais\
│
├── MA\
│   ├── pdf\
│   │   └── NFE 4730 - FERROVIA.pdf
│   └── xml\
│       └── nfse_4730.xml
│
└── PA\
    ├── pdf\
    └── xml\
```

🔒 Segurança e Logs

Todas as ações (leituras, downloads, envios) são registradas em logs internos.

Credenciais de acesso ao e-mail e SEFAZ são armazenadas em variáveis de ambiente seguras (.env).

O executável final é compilado via PyInstaller, garantindo sigilo do código-fonte.

🧑‍💻 Execução
💻 Via Python
```bash
python -m app.app
```

⚙️ Via Executável
Executar KADRIX SEFAZ.exe dentro da pasta /dist/
A interface GUI será iniciada automaticamente.

🧩 Manutenção e Suporte
Desenvolvimento:
Equipe de Automação — Kairós Motores
Cliente:
VALE S.A. — Unidades Maranhão e Pará
Última atualização: Novembro/2025
