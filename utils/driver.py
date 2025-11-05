class Driver():
    '''
    Classe que define os parâmetros utilizado no driver de configuração do site.
    '''
    def __init__(self, driver):
        self._driver = driver

    @property
    def driver(self):
        return self._driver

    @driver.setter
    def driver(self, driver):
        self._driver = driver
    