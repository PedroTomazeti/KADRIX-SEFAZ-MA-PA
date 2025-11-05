import fitz  # PyMuPDF
import os

def verifica_unidade(unidade):
    if unidade == "":
        unidade_desejada = 1
    elif unidade == "":
        unidade_desejada = 2

    return unidade_desejada

def ler_primeira_pagina(caminho_pdf):
    with fitz.open(caminho_pdf) as doc:
        primeira_pagina = doc[0]
        texto = primeira_pagina.get_text()
    return texto

def extrair_dados(texto):
    dados = {}
    linhas = texto.splitlines()

    for i, linha in enumerate(linhas):
        if 'Nº FRS' in linha:
            dados['frs'] = linha.split(':')[-1].strip()
        elif 'Nº RF' in linha:
            dados['rf'] = linha.split(':')[-1].strip()
        elif 'Nº Pedido/item' in linha:
            num_pedido = linha.split(':')[-1].strip()
            dados['pedido_item'] = num_pedido.split("/", 1)[0]
        elif 'Razão Social:' in linha:
            dados['razao_social_cliente'] = linha.split(':')[-1].strip()
        elif 'CNPJ:' in linha and 'I.E.' in linha:
            cnpj_ie = linha.split('CNPJ:')[-1]
            dados['cnpj_cliente'] = cnpj_ie.split('I.E.')[0].strip().replace(".", "").replace("-", "").replace("/", "")
        elif 'Razão Social:KAIROS' in linha:
            dados['razao_social_fornecedor'] = linha.split(':')[-1].strip()
        elif 'CNPJ:' in linha:
            dados['cnpj_fornecedor'] = linha.split(':')[-1].strip().replace(".", "").replace("-", "").replace("/", "")
        elif 'Valor do Serviço(s)' in linha:
            dados['valor_bruto'] = linhas[i+1].strip()
        elif 'INSS:' in linha:
            dados['iss'] = linhas[i+1].split()[0].strip()
            
    return dados

def verificar_ocorrencias(dados_extraidos, texto_base, log_queue):
    # Lista de chaves que você deseja verificar
    chaves_para_verificar = ['frs', 'rf', 'pedido_item']
    campos_faltantes = []

    for chave in chaves_para_verificar:
        valor = dados_extraidos.get(chave, '')
        if valor and valor in texto_base:
            print(f"✅ Valor '{valor}' encontrado no texto.")
            log_queue.put(f"✅ Valor '{valor}' encontrado no texto.")
        
        elif valor:
            print(f"❌ Valor '{valor}' NÃO encontrado no texto.")
            log_queue.put(f"❌ Valor '{valor}' NÃO encontrado no texto.")

            campos_faltantes.append(chave)
    
    return campos_faltantes

def analise_arquivo(filename, descricao, log_queue):
    # Caminho completo do PDF
    caminho_pdf = os.path.join('C:/Users/Pedro/Documents/KADRIX-SEFA/anexos_email', filename)
    print(f"\n📄 Processando arquivo: {filename}")
    log_queue.put(f"\n📄 Processando arquivo: {filename}")
    # Verifica se o arquivo é um PDF e se existe
    if not (filename.lower().endswith(".pdf") and os.path.isfile(caminho_pdf)):
        print("⚠️ Arquivo inválido ou inexistente.")
        log_queue.put("⚠️ Arquivo inválido ou inexistente.")
        return

    try:
        # Ler conteúdo da primeira página
        texto = ler_primeira_pagina(caminho_pdf)

        # Extrair dados do texto
        dados_extraidos = extrair_dados(texto)

        # Mostrar resultados
        if dados_extraidos:
            print("✅ Dados extraídos:")
            log_queue.put("✅ Dados extraídos:")
            for chave, valor in dados_extraidos.items():
                print(f"🔸 {chave}: {valor}")
                log_queue.put(f"🔸 {chave}: {valor}")
            
            sefa_estado = verifica_unidade(dados_extraidos['cnpj_fornecedor'])

            campos_incorretos = verificar_ocorrencias(dados_extraidos, descricao, log_queue)
            
            if len(campos_incorretos) == 0:
                print("Todas as informações estão corretas.")
                log_queue.put("\nTodas as informações estão corretas.")
                
                return True, dados_extraidos, sefa_estado
            else:
                print(f"Campos que estão incorretos: {', '.join(campos_incorretos)}")
                log_queue.put(f"\nCampos que estão incorretos: {', '.join(campos_incorretos)}")

                return False, dados_extraidos, sefa_estado

        else:
            print("⚠️ Nenhum dado relevante encontrado no PDF.")
            
            return False, dados_extraidos, sefa_estado
        
    except Exception as e:
        print(f"❌ Erro ao processar o PDF: {e}")

        return False, dados_extraidos, sefa_estado
