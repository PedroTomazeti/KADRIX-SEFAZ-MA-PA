import threading
import traceback
import requests
import re
import os
from datetime import datetime
from unidecode import unidecode
from utils.services import Servico
from functions.renomeia_arquivo import nomear_pdf
from time import sleep
from seleniumwire import webdriver
from selenium.webdriver.support.ui import Select
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

def format_desc(desc, log_queue):
    print("Definindo as descrições corretas...")
    log_queue.put("Definindo as descrições corretas...")
    desc_nota, desc_serv = desc.split(";", 1)
    print(f"Descrição da nota: {desc_nota}")
    print(f"Descrição do serviço: {desc_serv}")

    log_queue.put(f"Descrição da nota: {desc_nota}\nDescrição do serviço: {desc_serv}")

    return desc_nota, desc_serv

def acessar_valor(field):
    """
    Retorna o valor se for um input, senão o texto interno do elemento.
    """
    valor = field.get_attribute("value")
    return valor if valor else field.text.strip()

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
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")  # Tela cheia

    prefs = {
        # PDF
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
        # Downloads
        "savefile.default_directory": download_dir_pdf.replace("\\", "\\\\"),
        "download.default_directory": download_dir_xml.replace("\\", "\\\\"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0,
        "plugins.always_open_pdf_externally": False
    }

    chrome_options.add_experimental_option("prefs", prefs)

    # Remove prompt de segurança para download (ajuda a evitar bloqueios)
    chrome_options.add_argument("--safebrowsing-disable-download-protection")

    # Impressão direta, se usar PDF
    chrome_options.add_argument("--kiosk-printing")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def iniciar_driver_slz(driver, url, contador, dados_nota, desc_nota, info_nota, log_queue, max_tent = 10, tent=1):
    """
    Processa todas as notas da unidade São Luís (KM-SLZ).
    """
    download_dir_pdf = r"C:\NotasFiscais\MA\pdf"
    download_dir_xml = r"C:\NotasFiscais\MA\xml"
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
            
            sucesso = main(driver, url, infos, download_dir_pdf, download_dir_xml, log_queue, execucao=contador)

            if not sucesso:
                print(f"\n❌ Erro na tentativa {tent}: {e}")
                log_queue.put(f"\n❌ Erro na tentativa {tent}: {e}")
                tent += 1
                driver.quit()
                sleep(3)
            else:
                print("\n✅ Emissão concluída, preparando arquivo para envio do e-mail...")
                log_queue.put("\n✅ Emissão concluída, preparando arquivo para envio do e-mail...")

                responder_email(info_nota, log_queue)

                return info_driver if contador == 0 else None

        except Exception as e:
            print(f"\n❌ Erro na tentativa {tent}: {e}")
            log_queue.put(f"\n❌ Erro na tentativa {tent}: {e}")
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

            # Aguarda a página carregar um elemento essencial
            wait_for_element(driver, By.XPATH, "/html/body/div/div[1]/div/div[2]/div/div[2]/div/div/form/fieldset/footer/div/input")
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
        log_queue.put("[Monitor] Falha ao conectar após todas as tentativas.")

def login(driver, user, password, log_queue):
    input_cnpj = wait_for_element(driver, By.XPATH, '/html/body/div/div[1]/div/div[2]/div/div[2]/div/div/form/fieldset/label[1]/span/input')
    print("Input para CNPJ encontrado.")
    log_queue.put("\nInput para CNPJ encontrado.")
    ActionChains(driver).move_to_element(input_cnpj).perform()
    sleep(0.3)
    input_cnpj.clear()
    input_cnpj.click()
    sleep(0.3)

    input_cnpj.send_keys(Keys.CONTROL, 'A')
    input_cnpj.send_keys(Keys.BACKSPACE)
    input_cnpj.send_keys(user)

    sleep(0.5)

    input_password = wait_for_element(driver, By.XPATH, '/html/body/div/div[1]/div/div[2]/div/div[2]/div/div/form/fieldset/label[2]/span/input')
    print("Input para password encontrado.")
    log_queue.put("\nInput para password encontrado.")
    ActionChains(driver).move_to_element(input_password).perform()
    input_password.clear()
    input_password.click()
    input_password.send_keys(password)

    sleep(0.3)

    button_enter = wait_for_click(driver, By.XPATH, '/html/body/div/div[1]/div/div[2]/div/div[2]/div/div/form/fieldset/footer/div/input')
    ActionChains(driver).move_to_element(button_enter).perform()
    button_enter.click()

def cabecalho_nota(driver, cnpj_tom, tributo, log_queue):
    emitir = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/form/div/div/div/ul/li[5]/a')

    ActionChains(driver).move_to_element(emitir).perform()

    emitir.click()

    sleep(0.3)

    cnpj_tomador = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[1]/table/tbody/tr/td/span/div[2]/div[2]/div/input')

    print("Campo para definir cnpj do tomador encontrado.")
    log_queue.put("\nCampo para definir cnpj do tomador encontrado.")

    ActionChains(driver).move_to_element(cnpj_tomador).perform()

    cnpj_tomador.clear()

    cnpj_tomador.click()

    cnpj_tomador.send_keys(cnpj_tom)

    sleep(2)
    
    print("Pesquisando CNPJ do tomador.")
    log_queue.put("\nPesquisando CNPJ do tomador.")

    pesquisa = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[1]/table/tbody/tr/td/span/div[2]/div[2]/div/a[1]')

    ActionChains(driver).move_to_element(pesquisa).perform()

    pesquisa.click()

    sleep(1)

    print("Avançando para próxima tela.")
    log_queue.put("\nAvançando para próxima tela.")
    
    avancar = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[1]/table/tbody/tr/td/div[7]/div/div/a')

    ActionChains(driver).move_to_element(avancar).perform()

    avancar.click()

    sleep(1)

    print("Selecionando tipo de atividade.")
    log_queue.put("\nSelecionando tipo de atividade.")

    select_ativ = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[2]/table/tbody/tr/td/div[1]/div/div/select')

    # Cria um objeto Select
    select = Select(select_ativ)

    # Seleciona pela opção desejada (valor ou texto visível)
    select.select_by_value("331390100")  # ou select.select_by_visible_text("Parauapebas")

    sleep(0.6)

    print("Informando tipo de serviço feito.")
    log_queue.put("\nInformando tipo de serviço feito.")

    select_serv = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[2]/table/tbody/tr/td/span[1]/div/div/div/select')

    # Cria um objeto Select
    select = Select(select_serv)

    # Seleciona pela opção desejada (valor ou texto visível)
    select.select_by_value("1401")
    
    sleep(0.6)
    
    print("Informando tipo de tributação.")
    log_queue.put("\nInformando tipo de tributação.")

    select_tribut = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[2]/table/tbody/tr/td/span[2]/div[1]/div[2]/div/select')

    # Cria um objeto Select
    select = Select(select_tribut)

    # Seleciona pela opção desejada (valor ou texto visível)
    select.select_by_value("4")

    sleep(0.6)

    print("Selecionando tipo de recolhimento.")
    log_queue.put("\nSelecionando tipo de recolhimento.")
    select_recolh = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[2]/table/tbody/tr/td/span[2]/div[1]/div[3]/div/select')

    # Cria um objeto Select
    select = Select(select_recolh)

    if tributo == 'NAO':
        try:
            # Seleciona pela opção desejada (valor ou texto visível)
            select.select_by_value("1")
        except Exception as e:
            sleep(0.2)
            print(f"\nOpção desejada não encontrada. FRS com erro de tributação.")
            log_queue.put(f"\nOpção desejada não encontrada. FRS com erro de tributação.")

            return False
    else:
        try:
            # Seleciona pela opção desejada (valor ou texto visível)
            select.select_by_value("2")
        except Exception as e:
            sleep(0.2)
            print(f"\nOpção desejada não encontrada. FRS com erro de tributação.")
            log_queue.put(f"\nOpção desejada não encontrada. FRS com erro de tributação.")

            return False

    sleep(0.6)

    avancar_nov = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[2]/table/tbody/tr/td/span[2]/div[2]/div/div/a')

    ActionChains(driver).move_to_element(avancar_nov).perform()

    avancar_nov.click()

    sleep(1)

    return True

def corpo_nota(driver, descricao, valor_total, log_queue):
    campo_desc_nota = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[3]/div/div/textarea')

    print("Definindo descrição da nota.")
    log_queue.put("\nDefinindo descrição da nota.")

    ActionChains(driver).move_to_element(campo_desc_nota).perform()

    campo_desc_nota.clear()

    campo_desc_nota.click()

    descricao_nota, descricao_serv = format_desc(descricao, log_queue)

    campo_desc_nota.send_keys(descricao_nota)

    sleep(0.5)

    campo_desc_serv = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[5]/div[2]/div/input')

    print("Definindo descrição do serviço.")
    log_queue.put("\nDefinindo descrição do serviço.")

    ActionChains(driver).move_to_element(campo_desc_serv).perform()

    campo_desc_serv.clear()

    campo_desc_serv.click()

    campo_desc_serv.send_keys(descricao_serv)

    sleep(0.5)

    campo_quant_serv = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[5]/div[3]/div/input')

    print("Definindo quantidade do serviço.")
    log_queue.put("\nDefinindo quantidade do serviço.")

    ActionChains(driver).move_to_element(campo_quant_serv).perform()

    campo_quant_serv.clear()

    campo_quant_serv.click()

    campo_quant_serv.send_keys("1")

    sleep(0.5)

    campo_valor = wait_for_element(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[5]/div[4]/div/input')

    print("Definindo valor do serviço.")
    log_queue.put("\nDefinindo valor do serviço.")

    ActionChains(driver).move_to_element(campo_valor).perform()

    campo_valor.clear()

    campo_valor.click()

    campo_valor.send_keys(Keys.CONTROL, 'a')
    sleep(0.2)
    campo_valor.send_keys(Keys.BACKSPACE)
    sleep(0.1)
    campo_valor.send_keys(valor_total)
    sleep(0.3)

    xpath_alvo = '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[5]/div[4]/div/a'

    try:
        add_valor = wait_for_click(driver, By.XPATH, xpath_alvo)

        # scroll e hover opcional
        driver.execute_script("arguments[0].scrollIntoView(true);", add_valor)
        ActionChains(driver).move_to_element(add_valor).perform()
        sleep(0.5)

        # clique direto (padrão)
        add_valor.click()

    except Exception as e:
        print(f"❌ Erro Selenium: {e}")
        # fallback opcional:
        try:
            driver.execute_script("arguments[0].click();", add_valor)
            print("✅ Clique via JavaScript executado.")
        except Exception as js_e:
            print(f"❌ Falha no clique via JS: {js_e}")

def baixar_pdf(driver, infos, log_queue):
    try:
        # Acessa a tela principal de resultados (onde você clica pra ver a nota
        # === Clique no botão que abre a nota ===
        # OBS: Ajuste esse seletor para o botão correto
        # Exemplo genérico:

        print("Emitindo nota.")
        log_queue.put("\nEmitindo nota.")

        emitir_nota = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[3]/div/div/table/tbody/tr[2]/td[3]/table/tbody/tr/td/div[10]/div/div/a[1]')
        driver.execute_script("arguments[0].scrollIntoView(true);", emitir_nota)
        ActionChains(driver).move_to_element(emitir_nota).perform()
        sleep(0.2)

        # clique direto (padrão)
        emitir_nota.click()
        
        print("Confirmando emissão da nota.")
        log_queue.put("\nConfirmando emissão da nota.")

        sim = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[3]/div[2]/div[2]/a[1]')
        driver.execute_script("arguments[0].scrollIntoView(true);", sim)

        sleep(0.2)

        # clique direto (padrão)
        sim.click()

        print("Imprimindo nota para envio.")
        log_queue.put("\nImprimindo nota para envio.")
        
        imprimir_nota = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form[1]/div[4]/div/a[2]')
        driver.execute_script("arguments[0].scrollIntoView(true);", imprimir_nota)

        sleep(0.2)

        # clique direto (padrão)
        imprimir_nota.click()

        sleep(2)
        #============================================================================================================================

        # Salva as janelas abertas
        abas = driver.window_handles

        print("Mudando para a nova aba aberta.")
        log_queue.put("\nMudando para a nova aba aberta.")

        # Muda para a nova aba (onde está a nota)
        driver.switch_to.window(abas[-1])
        sleep(2)

        print("Força o Win + P com o PDF aberto.")
        log_queue.put("\nForça o Win + P com o PDF aberto.")

        # Força a impressão
        driver.execute_script("window.print();")
        sleep(5)

        print("Fecha a aba nova aberta.")
        log_queue.put("\nFecha a aba nova aberta.")

        # Fecha a aba da nota (opcional)
        driver.close()

        # Volta para a aba principal
        driver.switch_to.window(abas[0])

        print("Localizando o elemento que contém o texto da nota")
        log_queue.put("\nLocalizando o elemento que contém o texto da nota")
        # Localiza o elemento que contém o texto da nota
        mensagem = driver.find_element(By.XPATH, '//span[contains(text(), "Número da NFSe:")]').text

        # Extrai o número da nota
        match = re.search(r"Número da NFSe:\s*(\d+)", mensagem)
        if match:
            numero_nota = str(int(match.group(1)))  # Remove todos os zeros à esquerda corretamente
            print(f"Número da nota limpo: {numero_nota}")   # Ex: '4730'
            log_queue.put(f"Número da nota limpo: {numero_nota}")
            infos.nota = numero_nota

    finally:
        print("Download finalizado.")
        log_queue.put("\nDownload finalizado.")

def pesquisa_xml(driver, dir_xml, infos, log_queue):

    # Data atual
    hoje = datetime.today()

    # Formatar como mês/ano
    mes_ano = hoje.strftime("%m/%Y")  # Exemplo: '06/2025'

    def encontrar_linha_post(driver, numero_nota_alvo, log_queue=None):
        """
        Percorre as linhas da tabela, verifica a primeira coluna (número da nota),
        e retorna o índice POST correspondente se encontrar a nota desejada.
        """

        try:
            linhas = driver.find_elements(By.CSS_SELECTOR, "table[id='form1:dtNotaFiscal'] tbody tr")
            total_linhas = len(linhas)

            msg = f"🔍 Total de linhas encontradas: {total_linhas}"
            print(msg)
            if log_queue:
                log_queue.put(msg)

            for i, linha in enumerate(linhas):
                try:
                    colunas = linha.find_elements(By.TAG_NAME, "td")
                    if not colunas:
                        msg = f"⚠️ Linha {i} ignorada (sem colunas)."
                        print(msg)
                        if log_queue:
                            log_queue.put(msg)
                        continue

                    texto_coluna_0 = colunas[0].text.strip()
                    texto_limpo = texto_coluna_0.lstrip("0")
                    nota_limpa = numero_nota_alvo.lstrip("0")

                    msg = f"🔎 Linha {i}: primeira coluna = '{texto_coluna_0}' (limpa: '{texto_limpo}')"
                    print(msg)
                    if log_queue:
                        log_queue.put(msg)

                    if texto_limpo == nota_limpa:
                        msg = f"✅ Nota encontrada na linha {i}. Buscando índice POST..."
                        print(msg)
                        if log_queue:
                            log_queue.put(msg)

                        a_tag = linha.find_element(By.XPATH, ".//a[contains(@onclick, 'form1:dtNotaFiscal')]")
                        onclick = a_tag.get_attribute("onclick")

                        match = re.search(r"form1:dtNotaFiscal:(\d+):", onclick)
                        if match:
                            indice_post = match.group(1)
                            msg = f"✅ Índice POST encontrado: {indice_post}"
                            print(msg)
                            if log_queue:
                                log_queue.put(msg)
                            return indice_post
                        else:
                            msg = "❌ 'onclick' encontrado mas padrão 'form1:dtNotaFiscal:X:' não reconhecido."
                            print(msg)
                            if log_queue:
                                log_queue.put(msg)
                            return None

                except Exception as e:
                    msg = f"⚠️ Erro processando linha {i}: {e}"
                    print(msg)
                    if log_queue:
                        log_queue.put(msg)

            msg = f"❌ Nenhuma linha corresponde à nota {numero_nota_alvo}."
            print(msg)
            if log_queue:
                log_queue.put(msg)
            return None

        except Exception as e:
            msg = f"❌ Erro geral ao encontrar linha da nota: {e}"
            print(msg)
            if log_queue:
                log_queue.put(msg)
            return None


    # Acessa a aba de exportação XML
    pdf_to_xml = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/form/div/div/div/ul/li[16]/a')
    sleep(0.3)
    pdf_to_xml.click()

    # Define os períodos
    for i in range(2):
        periodo_input = wait_for_element(driver, By.XPATH, f'/html/body/div[1]/div[1]/div/form/span/div/div[2]/div[2]/div[{i+1}]/div/input')
        log_queue.put("Definindo período.")
        ActionChains(driver).move_to_element(periodo_input).perform()
        periodo_input.clear()
        periodo_input.click()
        periodo_input.send_keys(Keys.CONTROL, 'a')
        sleep(0.2)
        periodo_input.send_keys(Keys.BACKSPACE)
        sleep(0.1)
        periodo_input.send_keys(mes_ano)
        sleep(0.3)

    print("Consultando XML's.")
    log_queue.put("\nConsultando XML's.")
    # Consulta XML
    consulta_xml = wait_for_click(driver, By.XPATH, '/html/body/div[1]/div[1]/div/form/span/div/div[2]/div[3]/div/a[1]', 5)
    driver.execute_script("arguments[0].scrollIntoView(true);", consulta_xml)
    sleep(0.2)
    consulta_xml.click()

    sleep(5)

    numero_nota = infos.nota
    log_queue.put(f"\nNota para pesquisar: {numero_nota}")
    linha = encontrar_linha_post(driver, numero_nota, log_queue)
    if linha is not None:
        baixar_xml(driver, log_queue, mes_ano, dir_xml, numero_linha=linha, numero_nota=numero_nota)
    else:
        try:
            # Localiza o botão »»
            ultima_pag = wait_for_element(driver, By.XPATH, "//td[@class=' rich-datascr-button' and contains(text(), '»»')]", 5)
            
            # Tenta clicar normalmente
            driver.execute_script("arguments[0].scrollIntoView(true);", ultima_pag)
            sleep(0.2)
            ultima_pag.click()
            sleep(3)
            
            print("✅ Clicou normalmente no botão »» para última página.")
            log_queue.put("✅ Clicou normalmente no botão »» para última página.")
            linha = encontrar_linha_post(driver, numero_nota, log_queue)
            if linha is not None:
                baixar_xml(driver, log_queue, mes_ano, dir_xml, numero_linha=linha, numero_nota=numero_nota)

        except (ElementNotInteractableException, WebDriverException) as e:
            print("⚠️ Clique falhou, tentando disparar evento manualmente...")
            log_queue.put("⚠️ Clique falhou, tentando disparar evento manualmente...")
            
            try:
                # Fallback: dispara o evento JavaScript diretamente
                driver.execute_script(
                    "Event.fire(arguments[0], 'rich:datascroller:onscroll', {'page': 'last'});", 
                    ultima_pag
                )
                sleep(3)
                print("✅ Evento JavaScript disparado com sucesso para última página.")
                log_queue.put("✅ Evento JavaScript disparado com sucesso para última página.")
                if linha is not None:
                    baixar_xml(driver, log_queue, mes_ano, dir_xml, numero_linha=linha, numero_nota=numero_nota)
            except Exception as err:
                print(f"❌ Falha ao forçar o evento JavaScript: {err}")
                log_queue.put(f"❌ Falha ao forçar o evento JavaScript: {err}")

def baixar_xml(driver, log_queue, periodo, dir_xml, numero_linha, numero_nota):
    def montar_post_data(view_state, linha):
        return {
            "form1": "form1",
            "form1:j_id200": periodo,
            "form1:j_id203": periodo,
            "form1:j_id206": "1",
            "javax.faces.ViewState": view_state,
            f"form1:dtNotaFiscal:{linha}:j_id254": f"form1:dtNotaFiscal:{linha}:j_id254"
        }

    log_queue.put(f"Número da nota: {numero_nota}")
    print(f"Número da nota: {numero_nota}")

    # Cookies da sessão
    cookies = driver.get_cookies()
    sessao = requests.Session()
    for cookie in cookies:
        sessao.cookies.set(cookie['name'], cookie['value'])

    # Captura do ViewState
    view_state = driver.find_element(By.NAME, "javax.faces.ViewState").get_attribute("value")

    # Dados do POST
    dados_post = montar_post_data(view_state, numero_linha)
    url = "https://stm.semfaz.saoluis.ma.gov.br/sistematributario/jsp/exportarNotasXml/exportarNotasXmlFiltro.jsf"

    try:
        resposta = sessao.post(url, data=dados_post, timeout=15)

        if resposta.status_code == 200 and b"<nfse" in resposta.content:
            nome_arquivo_final = os.path.join(dir_xml, f"nfse_{numero_nota}.xml")
            with open(nome_arquivo_final, "wb") as f:
                f.write(resposta.content)
            print(f"✅ XML baixado com sucesso: {nome_arquivo_final}")
            log_queue.put(f"✅ XML baixado com sucesso: {nome_arquivo_final}")
        else:
            print(f"❌ Erro ao baixar XML - Código: {resposta.status_code}")
            print(resposta.text[:500])
            log_queue.put("❌ XML não retornado ou inválido.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro na requisição: {e}")
        log_queue.put(f"❌ Erro na requisição: {e}")

def voltar_home(driver, log_queue):
    print("Voltando contexto para a página inicial.")
    log_queue.put("\nVoltando contexto para a página inicial.")
    home = wait_for_click(driver, By.XPATH, "//a[@title='Página Inicial']")
    sleep(0.1)
    home.click()
    print("Contexto retornado.")
    log_queue.put("\nContexto retornado.")

def main(driver, url, infos, dir_pdf, dir_xml, log_queue, execucao):
    """
    Gerencia o fluxo principal do processo.
    """
    # Só inicia o monitoramento se for a primeira execução
    if execucao == 0:
        global connection_successful, monitoring

        stop_monitoring = threading.Event()
        
        monitor_thread = monitor_connection_thread(driver, url, stop_monitoring, log_queue)

        # Aguardar conexão
        while not connection_successful:
            print("Aguardando conexão...")
            log_queue.put("Aguardando conexão...")
            sleep(1)

        print("Conexão estabelecida. Iniciando processamento!")
        log_queue.put("Conexão estabelecida. Iniciando processamento!")
        
        login(driver, 'user', 'password', log_queue)
        sleep(1.5)
    else: 
        monitor_thread = None

    try:
        print("Iniciando o código principal...")
        log_queue.put("Iniciando o código principal...")

        falha_tributacao = cabecalho_nota(driver, infos.cnpj, infos.tributacao, log_queue)

        if not falha_tributacao:
            print("Erro encontrado na NFE. Passando para a próxima...")
            log_queue.put("\nErro encontrado na NFE. Passando para a próxima...")
            
            return

        print("Especificando observações e valor do serviço.")
        log_queue.put("\nEspecificando observações e valor do serviço.")
        sleep(1)

        corpo_nota(driver, infos.descricao, infos.valor, log_queue)

        sleep(1)

        baixar_pdf(driver, infos, log_queue)

        sleep(0.2)

        voltar_home(driver, log_queue)

        print("Exportando XML da nota.")
        log_queue.put("\nExportando XML da nota.")

        pesquisa_xml(driver, dir_xml, infos, log_queue)

        print("Renomeando arquivo para enviar via e-mail.")
        log_queue.put("\nRenomeando arquivo para enviar via e-mail.")

        nomear_pdf(infos.cnpj, infos.nota, dir_pdf, log_queue)

        sleep(0.5)

        voltar_home(driver, log_queue)

        if execucao == 0:
            monitoring = False
            stop_monitoring.set()
            monitor_thread.join()

        return True

    except (NoSuchElementException, ElementNotInteractableException, TimeoutException, JavascriptException, WebDriverException) as e:
        msg = f"Erro Selenium: {e}"
        print(msg)
        log_queue.put(msg)
        print(traceback.format_exc())

        return False
    
    except Exception as e:
        msg = f"Erro no processo principal: {e}"
        print(msg)
        log_queue.put(msg)
        print(traceback.format_exc())

        return False
