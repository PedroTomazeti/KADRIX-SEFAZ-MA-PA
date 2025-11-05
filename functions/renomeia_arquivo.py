import json
import os
from process_pdf.test_pdf import analise_arquivo

#descricao = "OS: 1664-PO PAG. 60 DIAS, BANCO DO BRASIL, AG: 3650-1, C/C: 27191-8, RF.: : 6202731515,CONTRATO: 5900112784, PEDIDO.: 4511900618,FRS.: 1006757415; REFERENTE A PRESTAÇÃO DE SERVIÇOS DE MANUTENÇÃO PREVENTIVA E/OU CORRETIVA EM MOTORES ELÉTRICOS DE PROPRIEDADE DA VALE."

# Função para carregar os dados do JSON
def carregar_dados(json_path):
    # Carregando os dados
    try:
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                cnpj_dict = json.load(f)
            print("Dados carregados com sucesso!")
            return cnpj_dict
        
        return {}
    except FileNotFoundError:
        print("Arquivo não encontrado.")
    except json.JSONDecodeError:
        print("Erro ao decodificar o JSON.")

def busca_cnpj(cnpj, log_queue):
    """
    Busca CNPJ na lista de clientes que existe para renomear o arquivo.
    """
    # Caminho do arquivo JSON
    json_path = r"caminho/json"
    
    cnpj_dict = carregar_dados(json_path)

    print("Encontrado.")
    log_queue.put("Encontrado.")

    nome = cnpj_dict.get(cnpj, "NOT FOUND")
    print(f"Nome do fornecedor: {nome}")
    log_queue.put(f"Nome do fornecedor: {nome}")

    return nome

def nomear_pdf(cnpj_cliente, num_nota, caminho_pdf, log_queue):
    nome_cliente = busca_cnpj(cnpj_cliente, log_queue)

    arquivos = os.listdir(caminho_pdf)

    # Loop para renomear cada arquivo
    for arquivo in arquivos:
        if not arquivo.startswith("NFE"):
            if arquivo.endswith('.pdf'):
                try:
                    os.rename(f"{caminho_pdf}/{arquivo}", f"{caminho_pdf}/NFE {num_nota} - {nome_cliente}.pdf")
                    print("Arquivo renomeado com sucesso.")
                    log_queue.put("\nArquivo renomeado com sucesso.")
                except FileNotFoundError:
                    print("O arquivo não foi encontrado.")
                    log_queue.put("\nO arquivo não foi encontrado.")
                except Exception as e:
                    print(f"Erro ao renomear arquivo: {e}")
                    log_queue.put(f"Erro ao renomear arquivo: {e}")