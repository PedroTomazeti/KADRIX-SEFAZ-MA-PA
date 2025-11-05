import imaplib
import email
import os
import time
from email.header import decode_header
import re
from unidecode import unidecode
from process_pdf.ler_pdf import analise_arquivo
from web.web_app_prp import iniciar_driver_prp
from web.web_app_slz import iniciar_driver_slz

# === CONFIGURAÇÕES PERSONALIZADAS ===
IMAP_SERVER = "imap.email-ssl.com.br"
EMAIL_ACCOUNT = "CONTA EMAIL"
EMAIL_PASSWORD = "senha"
SMTP_SERVER = "smtp.email-ssl.com.br"
SMTP_PORT = 587  # Porta para STARTTLS (mais comum)

def encontrar_obs(body, log_queue):
    # Limpar caracteres especiais e normalizar texto
    texto_limpo = re.sub(r"[*•–—]+", "", body)  # remove bullets, traços longos
    texto_limpo = re.sub(r"\s{2,}", " ", texto_limpo)  # remove espaços duplicados
    texto_limpo = unidecode(texto_limpo)  # remove acentos

    # Expressão mais flexível para OBSERVACOES até Valor
    match = re.search(r"OB.{0,10}?ES[:\s-]*([\s\S]+?)Valor", texto_limpo, re.IGNORECASE)
    
    if match:
        trecho_desejado = match.group(1).strip()
        print(f"\n📌 Trecho extraído:\n{trecho_desejado}")
        log_queue.put(f"\n📌 Trecho extraído:\n{trecho_desejado}")

        return trecho_desejado
    else:
        print("\n❌ Nenhum trecho encontrado entre 'OBSERVAÇÕES' e 'Valor'.")
        log_queue.put("\n❌ Nenhum trecho encontrado entre 'OBSERVAÇÕES' e 'Valor'.")

def encerrar_driver(driver, log_queue):
    driver.quit()
    print("\n🛑 Driver encerrado.")
    log_queue.put("\n🛑Driver encerrado.")

def iniciar_monitoramento(PASTA_ANEXOS, log_queue):
    os.makedirs(PASTA_ANEXOS, exist_ok=True)
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        remetente_alvo = "remetente"
        status, messages = mail.search(None, 'UNSEEN', 'FROM', f'"{remetente_alvo}"')

        if status != "OK":
            log_queue.put("❌ Erro ao buscar e-mails.")
            return

        email_ids = messages[0].split()

        agrupados_por_unidade = []

        count_email = 0
        c_prp = 0
        c_slz = 0
        unidade = None
        ultima_unidade = None
        last_driver = [0]

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")

                    if not re.search(r"\bfaturamento de serviços\b", subject, re.IGNORECASE):
                        continue
                    if re.search(r"\b(MT|MATERIAL)\b", subject, re.IGNORECASE):
                        continue

                    from_email = email.utils.parseaddr(msg["From"])[1]
                    to_emails = msg.get_all("To", [])
                    cc_emails = msg.get_all("Cc", [])
                    all_recipients = email.utils.getaddresses(to_emails + cc_emails)
                    destinatarios = [addr for name, addr in all_recipients if addr != EMAIL_ACCOUNT]
                    msg_id = msg.get("Message-ID")
                    descricao = ""
                    dados_extraidos = {}
                
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))

                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                for enc in ['utf-8', 'latin1', 'iso-8859-1']:
                                    try:
                                        body = payload.decode(enc)
                                        break
                                    except UnicodeDecodeError:
                                        continue
                                else:
                                    body = payload.decode(errors='replace')

                                descricao = encontrar_obs(body, log_queue)

                            if "attachment" in content_disposition:
                                filename = part.get_filename()
                                if filename:
                                    filename, enc = decode_header(filename)[0]
                                    if isinstance(filename, bytes):
                                        filename = filename.decode(enc if enc else "utf-8")
                                    filepath = os.path.join(PASTA_ANEXOS, filename)
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    
                                    valido, dados_extraidos, unidade = analise_arquivo(filepath, descricao, log_queue)
                                    
                                    print(ultima_unidade)

                                    if ultima_unidade == None:
                                        print("\nPrimeira emissão do dia.")
                                        log_queue.put("\nPrimeira emissão do dia.")
                                    elif ultima_unidade != unidade:
                                        print("\n⏸ Encerrando unidade anterior.")
                                        log_queue.put("\nn⏸ Encerrando unidade anterior.")
                                        encerrar_driver(last_driver[0], log_queue)
                                    elif ultima_unidade == unidade:
                                        print("\nNota ainda se encontra na mesma unidade, continuando...")
                                        log_queue.put("\nNota ainda se encontra na mesma unidade, continuando...")

                                    if valido and unidade:
                                        agrupados_por_unidade.append({
                                            "assunto": subject,
                                            "remetente": from_email,
                                            "destinatarios": destinatarios,
                                            "msg_id": msg_id,
                                            "descricao": descricao,
                                            "dados": dados_extraidos,
                                            "filename": filepath,
                                            "unidade": unidade
                                        })
                                    
                                        dados_unidade = agrupados_por_unidade[count_email]
                                        dados = dados_unidade["dados"]
                                        descricoes = dados_unidade["descricao"]
                                        unidade_nota = dados_unidade["unidade"]

                                        if unidade_nota == 1:
                                            c_prp = 0
                                            url = "https://stm.semfaz.saoluis.ma.gov.br/sistematributario/jsp/login/login.jsf"
                                            driver = iniciar_driver_slz(last_driver[0], url, c_slz, dados, descricoes, dados_unidade, log_queue)
                                            
                                            if c_slz == 0:
                                                last_driver[0] = driver
                                                print(f"Último driver: {last_driver}")
                                                log_queue.put(f"Último driver: {last_driver}")

                                            c_slz+=1

                                        elif unidade_nota == 2:
                                            c_slz = 0
                                            url = "https://parauapebas.desenvolvecidade.com.br/nfsd/acessoSistema.jsf"
                                            driver = iniciar_driver_prp(last_driver[0], url, c_prp, dados, descricoes, dados_unidade, log_queue)
                                            
                                            if c_prp == 0:
                                                last_driver[0] = driver
                                                print(f"Último driver: {last_driver}")
                                                log_queue.put(f"Último driver: {last_driver}")

                                            c_prp+=1
                                            
                                        count_email+=1

                                        ultima_unidade = unidade_nota
                                        
                                        # Marcar como lido
                                        mail.store(e_id, '+FLAGS', '\\Seen')
                                        
                                        time.sleep(2)

        print("\n⏸ Encerrando driver da última nota.")
        log_queue.put("\n⏸ Encerrando driver da última nota.")
        print(f"Último driver: {last_driver}")
        encerrar_driver(last_driver[0], log_queue)

        # Decide qual unidade processar primeiro
        if not agrupados_por_unidade:
            log_queue.put("🔍 Nenhum e-mail válido encontrado.")
            return

        # Tenta fazer logout apenas se a conexão ainda estiver ativa
        try:
            mail.noop()  # Verifica se ainda está conectado
            mail.logout()
        except imaplib.IMAP4.error as e:
            if 'LOGOUT' in str(e).upper() or 'EOF' in str(e).upper():
                log_queue.put("⚠️ Conexão IMAP já encerrada antes do logout.")
            else:
                log_queue.put(f"❌ Erro no logout do IMAP: {e}")
        except Exception as e:
            log_queue.put(f"❌ Erro inesperado ao encerrar IMAP: {e}")
    
    except imaplib.IMAP4.error as e:
        log_queue.put(f"❌ Erro de autenticação/conexão: {e}")
    except Exception as e:
        import traceback
        log_queue.put("❌ Erro inesperado:")
        log_queue.put(f"{str(traceback.print_exc())}")