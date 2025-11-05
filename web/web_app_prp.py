import threading
import traceback
import requests
import re
import os
from utils.services import Servico
from functions.renomeia_arquivo import nomear_pdf
from time import sleep, time
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    ElementNotInteractableException,
    JavascriptException,
)
from process_email.enviar_email import responder_email
from utils.driver import Driver

#variaveis
monitoring = True
connection_successful = False

def wait_for_element(driver, by, value, timeout=60):
    """Função para esperar um elemento aparecer no DOM"""
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def wait_for_click(host, by, value, timeout=60):
    return WebDriverWait(host, timeout).until(EC.element_to_be_clickable((by, value)))

def abrir_site(driver, url, log_queue):
    """
    Inicializa o navegador, acessa o site especificado e realiza interações iniciais necessárias.
    """
    try:
        driver.get(url)
        print(f"Site acessado: {url}")
        log_queue.put(f"Site acessado: {url}")
        # Lógica para interagir com elementos na página
        return True
    except Exception as e:
        print(f"Erro ao abrir o site: {e}")
        log_queue.put(f"Erro ao abrir o site: {e}")
        return False

def configurar_driver(download_dir_pdf, download_dir_xml):
    # Configurações do navegador
    chrome_options = Options()
    
    # 🟢 Executar em segundo plano (headless)
    #chrome_options.add_argument("--headless=new")  # modo invisível
    chrome_options.add_argument("--disable-gpu")  
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    chrome_options.add_argument("--start-maximized")  # (não faz diferença no headless)

    # Preferências para salvar automaticamente como PDF
    chrome_options.add_experimental_option("prefs", {
        "printing.print_preview_sticky_settings.appState": '''
        {
            "recentDestinations": [{
                "id": "Save as PDF",
                "origin": "local",
                "account": ""
            }],
            "selectedDestinationId": "Save as PDF",
            "version": 2
        }
        ''',
        "savefile.default_directory": download_dir_pdf.replace("\\", "\\\\"),
        "download.default_directory": download_dir_xml.replace("\\", "\\\\"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0,
        "plugins.always_open_pdf_externally": False
    })

    # Ativa impressão direta (sem abrir janela de diálogo)
    chrome_options.add_argument("--kiosk-printing")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver

def iniciar_driver_prp(driver, url, contador, dados_nota, desc_nota, info_nota, log_queue, max_tent = 10, tent=1):
    """
    Processa nota da unidade Parauapebas (KM-PRP). Tenta novamente até 10 vezes em caso de erro.
    """
    download_dir_pdf = r"C:\NotasFiscais\PA\pdf"
    download_dir_xml = r"C:\NotasFiscais\PA\xml"

    while tent <= max_tent:        
        try:
            if contador == 0 or tent > 1:
                # Configura o WebDriver
                driver = configurar_driver(download_dir_pdf, download_dir_xml)
                drv = Driver(driver)
                info_driver = drv._driver
                # Abre o site apenas uma vez
                site_aberto = abrir_site(driver, url, log_queue)
                if not site_aberto:
                    log_queue.put("\nFalha ao abrir o site.")
                    raise Exception("\nFalha ao abrir o site.")

                print("\nSite acessado com sucesso, iniciando nota...")
                log_queue.put("\nSite acessado com sucesso, iniciando nota...")

            print(f"[DEBUG] Tipo de dados_nota: {type(dados_nota)} - Conteúdo: {dados_nota}")

            infos = Servico(
            cnpj=dados_nota['cnpj_cliente'],
                valor=dados_nota['valor_bruto'].replace(".", ""),
                descricao=desc_nota,
                tributo=dados_nota['iss'],
                nota=''
            )

            print(f"\n▶️ Processando nota {contador} com FRS: {dados_nota.get('frs', 'desconhecido')}")
            log_queue.put(f"\n▶️ Processando nota {contador} com FRS: {dados_nota.get('frs', 'desconhecido')}")
            
            sucesso = main(driver, url, infos, download_dir_pdf, log_queue, execucao=contador)

            if not sucesso:
                msg = f"\n❌ Erro na tentativa {tent}: {e}"
                print(msg)
                log_queue.put(msg)
                tent += 1
                driver.quit()
                sleep(3)
            else:
                print("\n✅ Emissão concluída, preparando arquivo para envio do e-mail...")
                log_queue.put("\n✅ Emissão concluída, preparando arquivo para envio do e-mail...")

                responder_email(info_nota, log_queue)

                return info_driver if contador == 0 else None

        except Exception as e:
            msg = f"\n❌ Erro na tentativa {tent}: {e}"
            print(msg)
            log_queue.put(msg)
            tent += 1
            driver.quit()
            sleep(3)

def monitor_connection_thread(driver, url, stop_monitoring, log_queue):
    """
    Inicia a thread de monitoramento da conexão.
    """
    monitor_thread = threading.Thread(target=monitor_connection, args=(driver, url, stop_monitoring, log_queue))
    monitor_thread.start()
    return monitor_thread

def monitor_connection(driver, url, stop_monitoring, log_queue, max_attempts=5, check_interval=5):
    """
    Monitora a conexão em segundo plano e retenta se houver erro.
    Para a thread se `stop_monitoring` for acionado.
    """
    global connection_successful
    attempt = 0

    while not stop_monitoring.is_set() and attempt < max_attempts and not connection_successful:
        try:
            print(f"[Monitor] Tentativa {attempt + 1} de {max_attempts} para acessar {url}...")
            driver.get(url)

            # Aguarda a página carregar um elemento essencial
            wait_for_element(driver, By.XPATH, "/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div/ul/li[3]/a")
            print("[Monitor] Conexão bem-sucedida!")
            log_queue.put("[Monitor] Conexão bem-sucedida!")
            connection_successful = True
            return  # Sai da função ao conectar com sucesso

        except Exception as e:
            print(f"[Monitor] Erro ao tentar conectar: {e}")
            attempt += 1
            sleep(check_interval)

    if not connection_successful:
        print("[Monitor] Falha ao conectar após todas as tentativas.")

def login(driver, user, password, log_queue):
    clicar_cnpj = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div/ul/li[3]/a')
    print("Botão de CNPJ encontrado.")
    log_queue.put("\nBotão de CNPJ encontrado.")
    clicar_cnpj.click()

    sleep(2)

    input_cnpj = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div/div/div[3]/div[3]/input')
    print("Input para CNPJ encontrado.")
    log_queue.put("\nInput para CNPJ encontrado.")
    ActionChains(driver).move_to_element(input_cnpj).perform()
    sleep(0.3)
    input_cnpj.clear()
    input_cnpj.click()
    sleep(1)

    input_cnpj.send_keys(Keys.CONTROL, 'A')
    input_cnpj.send_keys(Keys.BACKSPACE)
    input_cnpj.send_keys(user)

    sleep(2)

    input_password = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div/div/div[3]/div[4]/div/input')
    print("Input para password encontrado.")
    log_queue.put("\nInput para password encontrado.")
    ActionChains(driver).move_to_element(input_password).perform()
    input_password.clear()
    input_password.click()
    input_password.send_keys(password)

    sleep(0.3)

    button_enter = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div/div/div[3]/div[5]/button')
    ActionChains(driver).move_to_element(button_enter).perform()
    button_enter.click()

def cabecalho_nota(driver, cnpj_tom, log_queue):
    cnpj_tomador = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[4]/div/div/input')

    print("Input para cnpj do tomador encontrado.")
    log_queue.put("\nInput para cnpj do tomador encontrado.")

    ActionChains(driver).move_to_element(cnpj_tomador).perform()

    cnpj_tomador.clear()

    cnpj_tomador.click()

    cnpj_tomador.send_keys(cnpj_tom)

    sleep(2)

    avancar = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[2]/button[2]')

    ActionChains(driver).move_to_element(avancar).perform()

    avancar.click()

    sleep(1)

    avancar_nov = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[2]/button[2]')

    ActionChains(driver).move_to_element(avancar_nov).perform()

    avancar_nov.click()
    
    sleep(1.3)
    print("Definindo estado da prestação do serviço.")
    log_queue.put("\nDefinindo estado da prestação do serviço.")
    estado_prestacao = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[1]/div[1]/div/div')

    ActionChains(driver).move_to_element(estado_prestacao).perform()

    estado_prestacao.click()

    sleep(0.3)

    item = wait_for_click(driver, By.XPATH, "//li[@data-label='PA']")
    item.click()
    
    sleep(0.5)

    print("Definindo local da prestação do serviço.")
    log_queue.put("\nDefinindo local da prestação do serviço.")
    local_prestacao = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[1]/div[2]/div/div/div/div')

    ActionChains(driver).move_to_element(local_prestacao).perform()

    local_prestacao.click()

    sleep(0.3)

    item = wait_for_click(driver, By.XPATH, "//li[@data-label='Parauapebas']")
    item.click()

    sleep(1)

    print("Definindo tipo de atividade.")
    log_queue.put("\nDefinindo tipo de atividade.")
    tipo_atividade = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[2]/div[1]/div')

    ActionChains(driver).move_to_element(tipo_atividade).perform()

    tipo_atividade.click()

    sleep(0.3)

    item = wait_for_click(driver, By.XPATH, "//li[@id='atividade_1']")
    item.click()

    sleep(1)

    avancar = wait_for_click(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[2]/button[2]')

    ActionChains(driver).move_to_element(avancar).perform()

    avancar.click()

def corpo_nota(driver, descricao, valor_total, log_queue):
    campo_desc = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[1]/div/textarea')

    print("Definindo descrição do serviço.")
    log_queue.put("Definindo descrição do serviço.")

    ActionChains(driver).move_to_element(campo_desc).perform()

    campo_desc.clear()

    campo_desc.click()

    campo_desc.send_keys(descricao)

    sleep(2)

    campo_valor = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[3]/div/div[2]/div[2]/div/div/div/div/div/div[1]/div[2]/div[1]/span/input[1]')

    print("Definindo valor do serviço.")
    log_queue.put("Definindo valor do serviço.")

    ActionChains(driver).move_to_element(campo_valor).perform()

    campo_valor.clear()

    campo_valor.click()

    campo_valor.send_keys(Keys.CONTROL, 'a')
    sleep(0.2)
    campo_valor.send_keys(Keys.BACKSPACE)
    sleep(0.1)
    campo_valor.send_keys(valor_total)
    sleep(0.1)
    campo_valor.send_keys(Keys.TAB)

    sleep(2)

    avancar = wait_for_click(driver, By.XPATH, '//*[@id="wizardEmisaoNotaFiscal_next"]')

    ActionChains(driver).move_to_element(avancar).perform()

    avancar.click()

    print("\nAvançando primeiro botão.")
    log_queue.put("\nAvançando primeiro botão.")

    sleep(2)

    confirmar = wait_for_click(driver, By.XPATH, '//*[@id="botaoAcaoConfirmarInclusao"]')

    ActionChains(driver).move_to_element(confirmar).perform()

    confirmar.click()
    
    sleep(3)

def aguardar_download(caminho_pasta, extensao=".pdf", timeout=15):
    """
    Aguarda até que um arquivo com a extensão desejada apareça na pasta.
    """
    print("⏳ Aguardando o download do arquivo...")
    tempo_inicial = time()

    while time() - tempo_inicial < timeout:
        arquivos = [f for f in os.listdir(caminho_pasta) if f.endswith(extensao)]
        if arquivos:
            print(f"✅ Arquivo baixado: {arquivos[0]}")
            return os.path.join(caminho_pasta, arquivos[0])
        time.sleep(1)
    
    raise TimeoutError("❌ Tempo excedido aguardando o download do arquivo.")

def baixar_pdf_xml(driver, infos, log_queue, dir_pdf=r"C:\NotasFiscais\PA\pdf", dir_xml=r"C:\NotasFiscais\PA\xml", numero_nota="0000"):
    try:
        print("🔍 Buscando botão para iniciar processo...")
        log_queue.put("🔍 Buscando botão para iniciar processo...")

        # 1. Clique no botão XML (apenas para garantir que a nota está carregada)
        btn_xml = driver.find_element(By.ID, "botaoAcaoVisualizarXml")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_xml)
        sleep(0.5)
        driver.execute_script("arguments[0].click();", btn_xml)
        log_queue.put("✅ Clique no botão XML realizado.")
        print("✅ Clique no botão XML realizado.")

        sleep(1.5)  # Aguarda alguma resposta/carregamento

        # 2. Captura cookies da sessão do navegador
        sessao = requests.Session()
        for cookie in driver.get_cookies():
            sessao.cookies.set(cookie['name'], cookie['value'])

        # 3. Captura o viewState
        view_state = driver.find_element(By.NAME, "javax.faces.ViewState").get_attribute("value")

        # 4. Cabeçalhos da requisição
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://parauapebas.desenvolvecidade.com.br/nfsd/pages/cadastro/notaFiscal/confirmacaoCadastro.jsf",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        }

        url_post = "https://parauapebas.desenvolvecidade.com.br/nfsd/pages/cadastro/notaFiscal/confirmacaoCadastro.jsf"

        # 5. Baixar XML
        log_queue.put("📡 Requisição HTTP para XML...")
        print("📡 Requisição HTTP para XML...")

        post_xml = {
            "formulario": "formulario",
            "email": "",
            "assunto": "",
            "mensagem": "",
            "botaoAcaoVisualizarXml": "",
            "tipoPessoaContribuinteEscolha_focus": "",
            "tipoPessoaContribuinteEscolha_input": "",
            "contribuinte_focus": "",
            "contribuinte_input": "",
            "javax.faces.ViewState": view_state,
        }

        r_xml = sessao.post(url_post, data=post_xml, headers=headers)

        if r_xml.status_code == 200 and b"<?xml" in r_xml.content[:100]:
            cd = r_xml.headers.get("Content-Disposition", "")
            match = re.search(r'filename="([^"]+\.xml)"', cd)
            if match:
                nome_arquivo_original = match.group(1)
                quatro_digitos = re.search(r'(\d{4})\.xml$', nome_arquivo_original)
                sufixo = quatro_digitos.group(1) if quatro_digitos else numero_nota
                nome_xml = f"nfse_{sufixo}.xml"
            else:
                nome_xml = f"nfse_{numero_nota}.xml"

            path_xml = os.path.join(dir_xml, nome_xml)
            with open(path_xml, "wb") as f:
                f.write(r_xml.content)

            log_queue.put(f"✅ XML salvo em: {path_xml}")
            print(f"✅ XML salvo em: {path_xml}")
        else:
            log_queue.put("❌ Falha ao baixar XML.")
            log_queue.put(r_xml.text[:500])
            print("❌ Falha ao baixar XML.")
            print(r_xml.text[:500])

        # 6. Baixar PDF
        log_queue.put("📡 Requisição HTTP para PDF...")
        print("📡 Requisição HTTP para PDF...")

        post_pdf = {
            "formulario": "formulario",
            "email": "",
            "assunto": "",
            "mensagem": "",
            "botaoAcaoVisualizarSolicitacao": "",
            "tipoPessoaContribuinteEscolha_focus": "",
            "tipoPessoaContribuinteEscolha_input": "",
            "contribuinte_focus": "",
            "contribuinte_input": "",
            "javax.faces.ViewState": view_state,
        }

        r_pdf = sessao.post(url_post, data=post_pdf, headers=headers)

        if r_pdf.status_code == 200 and b"%PDF" in r_pdf.content[:10]:
            cd = r_pdf.headers.get("Content-Disposition", "")
            match = re.search(r'filename="([^"]+\.pdf)"', cd)
            if match:
                nome_arquivo_original = match.group(1)
                quatro_digitos = re.search(r'(\d{4})\.pdf$', nome_arquivo_original)
                sufixo = quatro_digitos.group(1) if quatro_digitos else numero_nota
                nome_pdf = f"nfse_{sufixo}.pdf"
                infos.nota = sufixo
            else:
                nome_pdf = f"nfse_{numero_nota}.pdf"

            path_pdf = os.path.join(dir_pdf, nome_pdf)
            with open(path_pdf, "wb") as f:
                f.write(r_pdf.content)

            log_queue.put(f"✅ PDF salvo em: {path_pdf}")
            print(f"✅ PDF salvo em: {path_pdf}")
        else:
            log_queue.put("❌ Falha ao baixar PDF.")
            log_queue.put(r_pdf.text[:500])
            print("❌ Falha ao baixar PDF.")
            print(r_pdf.text[:500])

        log_queue.put("✅ Processo finalizado com sucesso.")
        print("✅ Processo finalizado com sucesso.")

    except Exception as e:
        log_queue.put(f"❌ Erro geral no processo: {e}")
        print(f"❌ Erro geral no processo: {e}")

def novo_arquivo(driver, log_queue):
    wait_for_click(driver, By.XPATH, '//*[@id="botaoAcaoNovoCadastro"]')
    btn_new = driver.find_element(By.ID, "botaoAcaoNovoCadastro")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_new)
    sleep(0.5)
    driver.execute_script("arguments[0].click();", btn_new)
    log_queue.put("✅ Clique no botão realizado.")

def main(driver, url, infos, dir_pdf, log_queue, execucao):
    """
    Gerencia o fluxo principal do processo.
    """
    global connection_successful, monitoring

    stop_monitoring = threading.Event()

    # Só inicia o monitoramento se for a primeira execução
    if execucao == 0:
        monitor_thread = monitor_connection_thread(driver, url, stop_monitoring, log_queue)

        # Aguardar conexão
        while not connection_successful:
            print("Aguardando conexão...")
            log_queue.put("Aguardando conexão...")
            sleep(1)

        print("Conexão estabelecida. Iniciando processamento!")
        log_queue.put("Conexão estabelecida. Iniciando processamento!")
        
        login(driver, "user", "password", log_queue)
        sleep(1.5)

        emitir = wait_for_element(driver, By.XPATH, '/html/body/div[6]/form/div[3]/div[1]/div/div[2]/div[2]/div[2]/a')

        ActionChains(driver).move_to_element(emitir).perform()

        emitir.click()

        sleep(0.3)

    else: 
        monitor_thread = None

    try:
        print("Iniciando o código principal...")
        log_queue.put("Iniciando o código principal...")

        if connection_successful:
            cabecalho_nota(driver, infos.cnpj, log_queue)
            print("Especificando observações e valor do serviço.")
            log_queue.put("\nEspecificando observações e valor do serviço.")
            sleep(1)
            corpo_nota(driver, infos.descricao, infos.valor, log_queue)
            print("Indo para o processo de baixar PDF/XML da nota e prepará-la para envio no e-mail.")
            log_queue.put("\nIndo para o processo de baixar PDF/XML da nota e prepará-la para envio no e-mail.")
            sleep(2)
            baixar_pdf_xml(driver, infos, log_queue)
            
            sleep(5)

            print("Renomeando arquivo para enviar via e-mail.")
            log_queue.put("\nRenomeando arquivo para enviar via e-mail.")

            nomear_pdf(infos.cnpj, infos.nota, dir_pdf, log_queue)
            
            sleep(0.3)

            novo_arquivo(driver, log_queue)
            if execucao == 0:
                monitoring = False
                stop_monitoring.set()
                monitor_thread.join()
                print("Finalizando monitoramento.")
                log_queue.put("Finalizando monitoramento.")

            return True
        
        else:
            print("Conexão não estabelecida. Verifique a lógica de monitoramento.")
            log_queue.put("Conexão não estabelecida. Verifique a lógica de monitoramento.")
        
    except (NoSuchElementException, ElementNotInteractableException, TimeoutException, JavascriptException, WebDriverException) as e:
        msg = f"Erro Selenium: {e}"
        print(msg)
        log_queue.put(f"Erro Selenium: {e}")
        print(traceback.format_exc())

        return False

    except Exception as e:
        msg = f"Erro no processo principal: {e}"
        print(msg)
        log_queue.put(f"Erro no processo principal: {e}")
        print(traceback.format_exc())

        return False