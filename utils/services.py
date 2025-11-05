class Servico():
    '''
    Classe que define os parâmetros utilizados na nota de serviço.
    '''
    def __init__(self, cnpj, valor, descricao, tributo, nota):
        self._cnpj = cnpj
        self._valor = valor
        self._descricao = descricao
        self._tributo = tributo
        self._nota = nota
    
    @property
    def cnpj(self):
        return self._cnpj
    
    @property
    def valor(self):
        return self._valor
    
    @property
    def descricao(self):
        return self._descricao
    
    @property
    def tributacao(self):
        return self._tributo
    
    @property
    def nota(self):
        return self._nota
    
    @nota.setter
    def nota(self, nota):
        self._nota = nota