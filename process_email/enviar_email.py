import imaplib
import smtplib
import os
import glob
import time
import shutil
import locale
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from mimetypes import guess_type

# === CONFIGURAÇÕES PERSONALIZADAS ===
IMAP_SERVER = "imap.email-ssl.com.br"
EMAIL_ACCOUNT = "CONTA DO EMAIL"
EMAIL_PASSWORD = "senha"
SMTP_SERVER = "smtp.email-ssl.com.br"
SMTP_PORT = 587  # Porta para STARTTLS (mais comum)

def responder_email(email_data, log_queue):
    if not email_data:
        return

    arquivos_para_mover = []  # Lista para armazenar caminhos a serem movidos depois
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

    hoje = datetime.today()
    mes_numero = hoje.strftime("%m")
    mes_letra = hoje.strftime("%B")
    ano = hoje.strftime("%Y")

    pasta_base = r''
    pasta_xml = r''

    print(email_data['unidade'])
    match email_data['unidade']:
        case 1:
            CAMINHO_ANEXO_PDF = r"C:\NotasFiscais\MA\pdf"
            CAMINHO_ANEXO_XML = r"C:\NotasFiscais\MA\xml"
            PASTA_PDF_FINAL = os.path.join(pasta_base, 'Notas Filial', f"Notas {ano}", f"{mes_numero} - {mes_letra}", "02 - Serviços")
            PASTA_XML_FINAL = os.path.join(pasta_xml, 'Notas Filial', f"Notas {ano}", f"{mes_numero} - {mes_letra}", "02 - Serviços")

        case 2:
            CAMINHO_ANEXO_PDF = r"C:\NotasFiscais\PA\pdf"
            CAMINHO_ANEXO_XML = r"C:\NotasFiscais\PA\xml"
            PASTA_PDF_FINAL = os.path.join(pasta_base, 'Notas Filial', f"Notas {ano}", f"{mes_numero} - {mes_letra}", "02 - Serviços")
            PASTA_XML_FINAL = os.path.join(pasta_xml, 'Notas Filial', f"Notas {ano}", f"{mes_numero} - {mes_letra}", "02 - Serviços")

    try:
        pdf_files = glob.glob(os.path.join(CAMINHO_ANEXO_PDF, "*.pdf"))
        xml_files = glob.glob(os.path.join(CAMINHO_ANEXO_XML, "*.xml"))

        if len(pdf_files) == 0 or len(pdf_files) == 0:
            log_queue.put("⚠️ Arquivo PDF ou XML ausente para o e-mail. Pulando...")
            return

        msg = EmailMessage()
        msg["From"] = EMAIL_ACCOUNT
        msg["To"] = email_data["remetente"]
        msg["Subject"] = f"Re: {email_data['assunto']}"
        msg["In-Reply-To"] = email_data["msg_id"]
        msg["References"] = email_data["msg_id"]
        if email_data["destinatarios"]:
            msg["Cc"] = ", ".join(email_data["destinatarios"])

        cid_logo_esq = make_msgid()[1:-1]
        cid_logo_cent = make_msgid()[1:-1]
        cid_logo_dir = make_msgid()[1:-1]
        cid_rodape   = make_msgid()[1:-1]

        html = f"""
            estrutura html da assinatura
            """
        msg.add_alternative(html, subtype='html')

        def embed_image(msg, path, cid):
            with open(path, 'rb') as f:
                img_data = f.read()
            mime_type, _ = guess_type(path)
            maintype, subtype = mime_type.split("/")
            msg.get_payload()[-1].add_related(
                img_data, maintype=maintype, subtype=subtype,
                cid=f"<{cid}>", disposition="inline"
            )

        embed_image(msg, r"pasta/das/imagens/da/assinatura", cid_logo_esq)
        embed_image(msg, r"pasta/das/imagens/da/assinatura", cid_logo_dir)
        embed_image(msg, r"pasta/das/imagens/da/assinatura", cid_rodape)
        embed_image(msg, r"pasta/das/imagens/da/assinatura", cid_logo_cent)

        for filepath in [pdf_files[0], xml_files[0]]:
            with open(filepath, 'rb') as f:
                file_data = f.read()
            mime_type, _ = guess_type(filepath)
            maintype, subtype = mime_type.split("/")
            msg.add_attachment(file_data, maintype=maintype, subtype=subtype,
                            filename=os.path.basename(filepath))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.send_message(msg)
        print(f"✅ Resposta enviada com sucesso para {email_data['remetente']}")
        log_queue.put(f"✅ Resposta enviada com sucesso para {email_data['remetente']}")

        raw_msg = msg.as_bytes()
        imap = imaplib.IMAP4_SSL(IMAP_SERVER)
        imap.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        imap.append('INBOX.enviadas', '', imaplib.Time2Internaldate(time.time()), raw_msg)
        imap.logout()
        server.quit()
            
        time.sleep(2)

        caminho_pdf = pdf_files[0]
        caminho_xml = xml_files[0]
        destino_pdf = os.path.join(PASTA_PDF_FINAL, os.path.basename(caminho_pdf))
        destino_xml = os.path.join(PASTA_XML_FINAL, os.path.basename(caminho_xml))
        arquivos_para_mover.append((caminho_pdf, destino_pdf, caminho_xml, destino_xml))

    except Exception as e:
        print(f"❌ Erro ao processar e-mail: {e}")
        log_queue.put(f"❌ Erro ao processar e-mail: {e}")

    # Após o envio de todos os e-mails, mover os arquivos
    if arquivos_para_mover:
        print("\n🔄 Iniciando movimentação de todos os arquivos após envio dos e-mails.")
        log_queue.put("\n🔄 Iniciando movimentação de todos os arquivos após envio dos e-mails.")

        for caminho_pdf, destino_pdf, caminho_xml, destino_xml in arquivos_para_mover:
            try:
                os.makedirs(os.path.dirname(destino_pdf), exist_ok=True)
                os.makedirs(os.path.dirname(destino_xml), exist_ok=True)

                shutil.move(caminho_pdf, destino_pdf)
                shutil.move(caminho_xml, destino_xml)

                print(f"📦 Movido: {os.path.basename(caminho_pdf)} e {os.path.basename(caminho_xml)}")
                log_queue.put(f"📦 Movido: {os.path.basename(caminho_pdf)} e {os.path.basename(caminho_xml)}")
            except Exception as e:
                print(f"❌ Erro ao mover arquivos {caminho_pdf} e {caminho_xml}: {e}")
                log_queue.put(f"❌ Erro ao mover arquivos {caminho_pdf} e {caminho_xml}: {e}")