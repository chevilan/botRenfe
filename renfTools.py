#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Libraries
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from colorama import init, Fore, Style
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from twilio.rest import Client
from selenium import webdriver
from datetime import datetime
import getpass
import json
import time
import glob
import re
import os


class tools:
    def __init__(self,show_start:bool,debug:bool=False)->None:
        if show_start:
            print(f"RenForm Linux/Chrome v0.0.1-beta") # TODO: Manejar diferentes versiones
            print(f"Bienvenido al formulador automático de Renfe [aún en desarrollo]")
            debug = input("¿Quieres iniciar el programa viendo lo que ocurre en el navegador? (recomendado si has sufrido un error) (yes/no): ")
            self.conex_mult:int = input("Indica si tienes buena conexión (1-5) siendo 1 la mejor conexión y 5 la peor: ")
            
            if self.conex_mult not in [1,2,3,4,5]: self.conex_mult = 1
            # 1.5 2 2.5 3
            if self.conex_mult in [2,3]: self.conex_mult = 1 + (self.conex_mult - 1) / 2
            elif self.conex_mult in [4,5]: self.conex_mult = 2 + (self.conex_mult - 3) / 2
            
            if debug == 'yes':
                self.debug = True
            else: self.debug = False
        
        
        self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)
        self.encrypted_password = None
        
        load_dotenv()
        try:
            self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            self.client = Client(self.account_sid, self.auth_token)
        except Exception as e:
            print(f"Error al configurar el aviso al móvil: {e}")
        
        self.user=''
        self.phone_number=''
        self.twof_code=''
        self.get=''
        
        self.url_abono=''
        self.url_list_trains=''
        self.selected_route=''
        self.selected_date=datetime.now().strftime("%d/%m/%Y")
        
        chrome_options = Options()
        chrome_options.add_argument("--start-minimized") 
        if not self.debug:
            chrome_options.add_argument("--headless")  # Ejecutar en modo headless
            chrome_options.add_argument("--disable-gpu")  # Deshabilitar GPU (opcional)
            chrome_options.add_argument("--no-sandbox")  # Deshabilitar sandbox (opcional)
            chrome_options.add_argument("--disable-dev-shm-usage")  # Deshabilitar uso compartido de memoria (opcional)
    
        service = Service(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service,options=chrome_options)  # Usa el controlador de Chrome
        
        
    def set_password(self, password: str) -> None:
        # Cifrar la contraseña
        self.encrypted_password = self.cipher_suite.encrypt(password.encode())

    def get_password(self) -> str:
        # Descifrar la contraseña
        if self.encrypted_password:
            return self.cipher_suite.decrypt(self.encrypted_password).decode()
        return ''
    """
    def save_cookies(self, path):
        with open(path, 'w') as file:
            json.dump(self.driver.get_cookies(), file)
    
    def load_cookies(self, path):
        with open(path, 'r') as file:
            cookies = json.load(file)
            for cookie in cookies:
                self.driver.add_cookie(cookie)
    """
    def log_in(self,ask_user:bool=True,failed_pass:bool=False)->None:
        
        self.driver.get("https://venta.renfe.com/vol/loginParticular.do")
        
        time.sleep(1*self.conex_mult)

        username_input=WebDriverWait(self.driver,10*self.conex_mult).until(
            EC.element_to_be_clickable((By.NAME, "userId"))
        )
        password_input = self.driver.find_element(By.NAME, "password")
        
        if ask_user:
            if not failed_pass: self.phone_number="+34"+input("Introduce tu número de teléfono (opcional): ")
            self.user=input("Introduce tu correo electrónico: ")
            self.set_password(getpass.getpass("Introduce tu contraseña: "))
        
        username_input.send_keys(self.user)
        password_input.send_keys(self.get_password())
        
        password_input.send_keys(Keys.RETURN)
        time.sleep(4)
        time.sleep(2*self.conex_mult)
        flag=False
        if (self.driver.title=="Login"):
            #TODO: Contemplar si falla la contraseña
            #class = floating-input form-step-field invalid
            #id = "myModalLabel"
            try:
                #self.driver.fullscreen_window()
                try:
                    codigo_2f = WebDriverWait(self.driver, 2*self.conex_mult).until(
                        EC.visibility_of_element_located((By.ID, "codigoValidaLogin2F"))
                    )
                    if codigo_2f:
                        self.twof_code = input("Introduce el código de verificación de doble factor: ")
                        codigo_2f.send_keys(self.twof_code)
                        try:
                            enviarcodigo = self.driver.find_element(By.ID,"idBotonValDispositivo")
                            enviarcodigo.click()
                            time.sleep(2*self.conex_mult)
                            flag=True
                        except Exception as e:
                            print(f"Error al enviar el codigo2f: {e}")
                        
                except:
                    pass
                if not flag:
                    try:
                        aviso_element = WebDriverWait(self.driver, 5*self.conex_mult).until(
                            EC.visibility_of_element_located((By.ID, "myModalLabel"))
                        )
                        if aviso_element:
                            print("Contraseña incorrecta...")
                            if ask_user: self.log_in(True,True)
                            else: self.log_in(False, True)
                            return
                    except:
                        pass
                    
                    print("Ha sucedido un error inesperado, puede que la conexión sea mala o que renfe haya solicitado un captcha. Prueba a cambiar el índice de conexión o a ejecutar en modo debug")
                    #self.driver.fullscreen_window()
                    #self.driver.save_screenshot("test.png")
                
            except Exception as e:
                #Aquí hay que identificar si error de contraseña, codigo u otro
                print(f"Error al iniciar sesión: {e}")
        
        url_actual = self.driver.current_url
        match = re.search(r"\?(.*?)&", url_actual)
        
        if match:
            self.get=match.group(1)
        else:
            match = re.search(r"\?(.*)",url_actual)
            self.get = match.group(1) if match else None
        
        
    def new_formal(self)->None:
        
        url_siguiente = "https://venta.renfe.com/vol/myPassesCard.do?"
        
        try:
            url_siguiente += self.get
        except Exception as e:
            print(f"Error al acceder al apartado de bonos: {e}")
        
        self.url_abono=url_siguiente
        self.driver.get(url_siguiente)
        
        time.sleep(3)
        
        try:
            formalizacion = WebDriverWait(self.driver, 10*self.conex_mult).until(
                EC.element_to_be_clickable((By.XPATH, "//a[text()='Nueva formalización']"))
            )
            self.driver.execute_script("arguments[0].click();", formalizacion)
        except Exception as e:
            print(f"Error al acceder a formalización: {e}")
        time.sleep(1)
    
    def select_travel(self,ask_user:bool=True)->None:

        input_element = self.driver.find_element(By.ID, "journeyStationOriginDescription")
        
        if ask_user:
            ida_value = input_element.get_attribute("placeholder")
            print("Ida:", ida_value)

        input_element = self.driver.find_element(By.ID, "journeyStationDestinDescription")
        
        if ask_user:
            vuelta_value = input_element.get_attribute("placeholder")
            print("Vuelta:", vuelta_value)

            # Pedirle al usuario el sentido de la ruta
            self.selected_route=input("Selecciona: ")

        # Seleccionar la ruta
        if(self.selected_route.lower()=='ida'):
            try:
                origen = WebDriverWait(self.driver, 10*self.conex_mult).until(
                    EC.element_to_be_clickable((By.ID, "journeyStationOrigin"))
                )
                # Hacer clic en el elemento usando JavaScript
                self.driver.execute_script("arguments[0].click();", origen)
            except Exception as e:
                print(f"Error al seleccionar la ida: {e}")
        elif(self.selected_route.lower()=='vuelta'):
            try:
                destino = WebDriverWait(self.driver, 10*self.conex_mult).until(
                    EC.element_to_be_clickable((By.ID, "journeyStationDestin"))
                )
                # Hacer clic en el elemento usando JavaScript
                self.driver.execute_script("arguments[0].click();", destino)
            except Exception as e:
                print(f"Error al seleccionar la vuelta: {e}")
        else: print("Destino no disponible")
        
        if ask_user:
            date=input("Introduce la fecha del viaje (DD/MM/YYYY)(Enter para hoy): ")
            if date!='':
                self.selected_date=date

        if ask_user:print(f"Buscando para la fecha {self.selected_date}...")

        # Introducir la fecha deseada
        fecha = self.driver.find_element(By.ID,"fecha1")
        fecha.clear()
        fecha.send_keys(self.selected_date)

        # Acceder a la zona de escoger los trenes
        try:
            siguiente = WebDriverWait(self.driver, 10*self.conex_mult).until(
                EC.element_to_be_clickable((By.ID, "submitSiguiente"))
            )
            self.driver.execute_script("arguments[0].click();", siguiente)
        except Exception as e:
            print(f"Error al acceder la zona de los trenes: {e}")
        
        time.sleep(1)
        self.url_list_trains=self.driver.current_url

    def print_trains_select(self)->None:
        time.sleep(2)
        try:
            tbody = WebDriverWait(self.driver, 10*self.conex_mult).until(
                EC.presence_of_element_located((By.ID, "listTrainsTableTbodyNEW"))
            )
            
            # Encontrar todos los tr dentro del tbody
            rows = tbody.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                # Encontrar todos los td dentro de cada tr
                cells = row.find_elements(By.TAG_NAME, "td")
                print("\n---------------------------------------------------------------------------------")
                count=0
                for cell in cells:
                    # Para count==0 hay que coger el id del campo, luego asi saber el id del boton
                    if count==0:
                        print("Tren:",end=' ')
                        numtren=cell.get_attribute("id")
                        numtren=re.sub(r'\D', '', numtren)
                        print(f"{Fore.GREEN}{numtren}{Style.RESET_ALL}",end=' ')
                    elif count==1:
                        print("Salida:", end=' ')
                        print(f"{Fore.YELLOW}{cell.text}{Style.RESET_ALL}", end=' ')
                    elif count==2:
                        print("Llegada:", end=' ')
                        print(f"{Fore.YELLOW}{cell.text}{Style.RESET_ALL}", end=' ')
                    elif count==3:
                        print("Duración:", end=' ')
                        print(f"{Fore.BLUE}{cell.text}{Style.RESET_ALL}", end=' ')
                    elif count==4:
                        print("-", end=' ')
                        print(f"{Fore.RED}{cell.text}{Style.RESET_ALL}", end=' ')
                    elif count==5:
                        print("-", end=' ')
                        resultado=''
                        if cell.text=='Tren Completo':
                            resultado=f'{Fore.RED}No disponible{Style.RESET_ALL}'
                        else: resultado=f'{Fore.GREEN}Disponible{Style.RESET_ALL}'
                        print(resultado, end=' ')

                    count+=1
                    
        except Exception as e:
            print(f"Error al recoger los datos de los trenes: {e}")
            
        print("Si el tren no está disponible puedes seleccionarlo igualmente, el programa lo intentará coger hasta que esté disponible")
        
        self.id_tren = input("Introduce el id del tren que quieras coger: ")
    
    def close(self)->None:
        self.driver.quit()
    
    def send_message(self,message)->None:

        message = self.client.messages.create(
            body=message,
            from_='+14243560902',
            to=self.phone_number
        )
    
    def coger_tren(self, show_user:bool=True)->None:
        if show_user:print(f"Buscando el tren {self.id_tren}, si no está disponible la página se refrescará hasta que lo esté, esto puede tardar mucho tiempo...")
        
        id_boton = "continuar" + self.id_tren
        
        max_retries = 100000  
        retries = 0
        
        #self.driver.fullscreen_window()

        while retries < max_retries:
            #TODO: Comprobar si ha sido redirigido a la pagina de renfe otra vez y volver a iniciar sesion
            if(self.url_list_trains!=self.driver.current_url):
                self.log_in(ask_user=False)
                self.new_formal()
                self.select_travel(False)
                time.sleep(2*self.conex_mult)
                self.coger_tren(False)
                return
            try:
                boton = WebDriverWait(self.driver, 5*self.conex_mult).until(
                    EC.element_to_be_clickable((By.ID, id_boton))
                )
                self.driver.execute_script("arguments[0].click();", boton)
                #self.driver.fullscreen_window()
                break  
            except Exception as e:
                #self.driver.fullscreen_window()
                now=datetime.now()
                archivos = glob.glob("last_try_*.png")
                for archivo in archivos:
                    os.remove(archivo)
                moment=f"{now.hour}:{now.minute}:{now.second}"
                
                filename="last_try_"+moment+".png"
                self.driver.save_screenshot(filename)
                
                retries += 1
                self.driver.refresh()
                self.driver.set_window_position(-10000, 0)
                time.sleep(1*self.conex_mult)  

        if retries == max_retries:
            print(f"Después de {retries} intentos no se ha podido conseguir el tren {self.id_tren} ")
    
    def confirmar_venta(self)->None:
        #self.driver.fullscreen_window()
        time.sleep(2*self.conex_mult)
        try:
            boton = WebDriverWait(self.driver, 10*self.conex_mult).until(
                EC.element_to_be_clickable((By.ID, "submitSiguiente"))
            )
            self.driver.execute_script("arguments[0].click();", boton)
            
            time.sleep(self.conex_mult*2)
            
            try:
                confirmacion = WebDriverWait(self.driver, 5*self.conex_mult).until(
                    EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'La formalización se ha realizado correctamente.')]"))
                )
            except:
                #TODO: contemplar otros errores, como tren no compatible con otro
                print("Ha habido un error al confirmar la compra, volviendolo a intentar... ")
                #self.driver.fullscreen_window()
                now=datetime.now()
                moment=f"{now.hour}:{now.minute}:{now.second}"
                filename="not_confirm_"+moment+".png"
                archivos = glob.glob("not_confirm_*.png")
                for archivo in archivos:
                    os.remove(archivo)
                self.driver.save_screenshot(filename) #TODO: que guarde la fecha en el nombre del archivo
                self.new_formal()
                self.select_travel(False)
                self.coger_tren(False)
                self.confirmar_venta()
                return
            
            print(f"{Fore.GREEN}Tren reservado con éxito!{Style.RESET_ALL}")
            message=f"\nTren {self.id_tren} reservado con éxito!"
            try:
                self.send_message(message)
            except Exception as e:
                print(f"Error al enviar el mensaje: {e}")
            #TODO: Mandar mensaje al movil    
        except Exception as e:
            print(f"Error en confirmar_venta: {e}")

