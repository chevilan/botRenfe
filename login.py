import sys
import os
import json
import asyncio
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                            QDateEdit, QComboBox, QMessageBox, QGroupBox,
                            QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem,
                            QHeaderView, QProgressBar, QSplitter, QDialog,
                            QRadioButton, QButtonGroup, QFrame)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QObject, QThread, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QMovie
from playwright.async_api import async_playwright, Page, Browser
import base64
import re

# archivo de config
CONFIG_FILE = "renfe_config.json"

class LoginDialog(QDialog):
    """dialog para el inicio de sesion manual"""
    login_completed = pyqtSignal() # senal de inicio de sesion
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inicio de sesión manual")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        layout = QVBoxLayout(self) # diseno para colocar widgets verticalmente
        
        # mensaje hecho x ia
        message = QLabel("Por favor, complete el proceso de inicio de sesión manualmente:\n\n"
                        "1. Verifique que sus credenciales se han completado\n"
                        "2. Complete el captcha si aparece\n"
                        "3. Haga clic en el botón de inicio de sesión\n"
                        "4. Complete cualquier verificación adicional\n\n"
                        "Cuando haya iniciado sesión completamente, haga clic en el botón de abajo:")
        message.setWordWrap(True) # el texto se ajusta al ancho
        layout.addWidget(message) # añade el label al layout
        
        # crear el boton de ya iniciar sesion
        continue_button = QPushButton("Ya he iniciado sesión")
        continue_button.clicked.connect(self.accept) # cuando se clica se llama a la clase accept de QDialog (que cierra y setea el dialog)
        layout.addWidget(continue_button) # lo anade al layout

class AbonoInfo: 
    """clase pa almacenar to la info de los abonos"""
    def __init__(self, id, tipo, origen, destino, validez, viajes_disponibles=None, formalization_id=None, localizador=None):
        self.id = id
        self.tipo = tipo
        self.origen = origen
        self.destino = destino
        self.validez = validez # el tiempo que le queda al abono
        self.viajes_disponibles = viajes_disponibles or "N/A"  # los viajes que hay dispos
        self.formalization_id = formalization_id  # id del boton de formalizacion
        self.localizador = localizador # el localizador es un codigo que facilita encontrar el formalization_id
        
    def __str__(self): # modificar el toString por si se quiere imprimir el objeto
        return f"{self.tipo}: {self.origen} - {self.destino} (Validez: {self.validez} días)"

class BrowserWorker(QObject):
    """el QObject maneja las operaciones del navegador, QObject permite señales y slots
    (un slot es una funcion que se ejecuta cuando se emite una señal)"""
    login_status = pyqtSignal(bool, str) # estado del login
    search_results = pyqtSignal(list) # resultados de la busquda
    booking_status = pyqtSignal(bool, str) 
    progress_update = pyqtSignal(int, str) # barra de progreso y mensaje
    show_login_dialog = pyqtSignal() # la senal del dialog de inicio manual
    abonos_loaded = pyqtSignal(list)  # senal pa cuando se cargan los abonos
    train_booked = pyqtSignal(str) # senal para cuando se reserva un tren
    
    def __init__(self):
        super().__init__() # variables defecto
        self.browser = None
        self.page = None
        self.manual_login_mode = True 
        self.logged_in = False
        self.credentials = {} # diccionario pa almacenar las credenciales
        self.login_dialog_result = asyncio.Event() # basicamente es una barrera, si no esta set los awaits se bloquean
        self.abonos = []  # lista pa almacenar los abonos

    async def init_browser(self):
        """función asíncrona para iniciar el navegador con playwright"""
        self.progress_update.emit(10, "Iniciando navegador...") # actualizar la barra de progreso
        playwright = await async_playwright().start() # inicia playwright
        self.browser = await playwright.chromium.launch(headless=not self.manual_login_mode) # inciarlo en funcion del modo
        self.page = await self.browser.new_page() # crear una nueva pagina
        self.progress_update.emit(20, "Navegador iniciado")
        return True # una vez termina devuelve true
        
    def set_login_completed(self):
        """esta funcion establece el dialog de login en set (cuando se presiona el boton)"""
        self.login_dialog_result.set()
    
    async def login(self, username, password):
        """funcion de log in"""
        try:
            if not self.page: # si no hay ninguna pagina abierta espera a que se inicie el navegador
                await self.init_browser()
                
            self.progress_update.emit(30, "Accediendo a Renfe...")
            
            # ir a la pagin de log in de renfe
            self.progress_update.emit(40, "Accediendo al formulario de login...")
            await self.page.goto('https://venta.renfe.com/vol/loginParticular.do')
            await self.page.wait_for_load_state('networkidle') # la pagina ha cargado al completo (networkidle = pocas peticiones de red)
            
            # aceptar las cookies d mierda
            try:
                await self.page.locator('button[id="onetrust-accept-btn-handler"]').click(timeout=5000) # localiza con id
            except:
                pass  # si pasa el tiempo y no lo encuentra no pasa nada
            
            # rellena los campos de login con las credenciales
            self.progress_update.emit(50, "Rellenando credenciales...")
            await self.page.fill('#num_tarjeta', username) # num_tarjeta y pass-login son los ids de los inputs
            await self.page.fill('#pass-login', password)
            
            if self.manual_login_mode:
                # en modo manual se muestra el dialog de inicio de sesion y se espra a que el user termine
                self.progress_update.emit(60, "Esperando a que el usuario complete el proceso de inicio de sesión...")
                self.login_dialog_result.clear() # pone la barrera a unset
                self.show_login_dialog.emit() # emite una señal para que ejecute la funcion asociada (el dialog)
                print("Esperando a que el usuario complete el inicio de sesión...") # print de dbug
                try:
                    # esperar 50 secs que estaba dando fallos y si no es conazo pa depurar
                    await asyncio.wait_for(self.login_dialog_result.wait(), timeout=50)  # 50 s
                    print("Usuario ha indicado que ha completado el inicio de sesión.")
                except asyncio.TimeoutError:
                    print("Ha pasado demasiado tiempo") # en teoria si se pasa del tiempo habria que cerrar o algo pero ns
                    
                # check si el login fue exitoso
                await self.page.wait_for_load_state('networkidle') # esperar a que se cargue la pagina
                print("Verificando si el login fue exitoso...")
                # para comprobar si se ha iniciado correctamente vemos si la url es la de home
                current_url = self.page.url
                print(f"Current URL after login: {current_url}")
                if "home.do" in current_url:
                    self.progress_update.emit(100, "Sesión iniciada correctamente!")
                    self.logged_in = True
                    self.credentials = {"username": username, "password": password}
                    
                    # asi como se inicia sesion cargar los abonos del usuario
                    await self.load_abonos()
                    
                    self.login_status.emit(True, "Login successful") # envia la señal del login
                    return True
                else: # si no esta en home
                    error_message = "No se pudo verificar el inicio de sesión. Asegúrese de haber completado correctamente el proceso."
                    self.login_status.emit(False, error_message)
                    return False
            else:
                # modo normal, imposible si se solicitan captchas #TODO: que soporte 2fcodes 
                self.progress_update.emit(60, "Enviando credenciales...")
                await self.page.locator('button[type="submit"]').click() #localiza el boton de iniciar sesion (tipo submit)
                await self.page.wait_for_load_state('networkidle')
                
                # lo mismo de antes (TODO: se podría hacer una funcion aparte)
                current_url = self.page.url
                if "home.do" in current_url:
                    self.progress_update.emit(100, "Sesión iniciada correctamente!")
                    self.logged_in = True
                    self.credentials = {"username": username, "password": password}
                    
                    await self.load_abonos()
                    
                    self.login_status.emit(True, "Login successful")
                    return True
                else:
                    error_message = "Error al iniciar sesión. Por favor, compruebe sus credenciales."
                    self.login_status.emit(False, error_message)
                    return False
                
        except Exception as e:
            self.login_status.emit(False, f"Error: {str(e)}")
            return False

    async def load_abonos(self):
        """cargar los abonos que tiene el usuario"""
        try:
            self.progress_update.emit(10, "Accediendo a la página de abonos...") 
            await self.page.goto('https://venta.renfe.com/vol/myPassesCard.do') # enlace donde aparecen los abonos
            await self.page.wait_for_load_state('networkidle')
            
            self.progress_update.emit(50, "Extrayendo información de abonos...")
            
            # fvk javascript, extraer los dtos de los abonos
            abonos_data = await self.page.evaluate('''() => {
                const abonos = [];
                
                // busca todos los titulos que empiecen por PassesCardTitle
                const titulos = document.querySelectorAll('h3[id^="PassesCardTitle"]');
                
                titulos.forEach(titulo => { // for each pa cada titulo
                    // pilla el id del titulo y extrae los numeros siguientes
                    const idMatch = titulo.id.match(/PassesCardTitle(\\d+)/);
                    if (idMatch && idMatch[1]) { // si matchea y encontro los numeros
                        const abonoId = idMatch[1]; // los numeros son el id del abono
                        
                        const abonoContainer = titulo.closest('.passeCard') || 
                                            titulo.closest('.card') || 
                                            titulo.parentNode.parentNode; 
                        
                        const tipo = titulo.textContent.trim();
                        
                        // origen y destino
                        const origen = document.querySelector(`#origen${abonoId}`)?.textContent.trim() || '';
                        const destino = document.querySelector(`#destino${abonoId}`)?.textContent.trim() || '';
                        
                        const validez = document.querySelector(`#endDate${abonoId}`)?.textContent.trim() || '';
                        
                        const id_localizador = "localizador" + abonoId;
                        const localizador = document.querySelector(`#${id_localizador}`)?.textContent.trim() || '';
                        
                        const formalizationId = "new" + localizador;
                        
                        abonos.push({
                            id: abonoId,
                            tipo: tipo,
                            origen: origen,
                            destino: destino,
                            validez: validez,
                            formalization_id: formalizationId,
                            localizador: localizador
                        });
                    }
                });
                
                return abonos;
            }''')
            
            # convertir los datos al objeto abono
            self.abonos = []
            for abono_data in abonos_data:
                abono = AbonoInfo(
                    id=abono_data.get('id', ''),
                    tipo=abono_data.get('tipo', ''),
                    origen=abono_data.get('origen', ''),
                    destino=abono_data.get('destino', ''),
                    validez=abono_data.get('validez', ''),
                    formalization_id=abono_data.get('formalization_id', ''),
                    localizador=abono_data.get('localizador', '')
                )
                self.abonos.append(abono)
                
            self.progress_update.emit(100, f"Se han cargado {len(self.abonos)} abonos")
            self.abonos_loaded.emit(self.abonos)
                
            if not self.abonos:
                self.progress_update.emit(100, "No se encontraron abonos disponibles")
                self.abonos_loaded.emit([])
                
        except Exception as e:
            print(f"Error cargando abonos: {str(e)}")
            self.progress_update.emit(100, f"Error cargando abonos: {str(e)}")
            self.abonos_loaded.emit([])

    async def search_trains_with_abono(self, abono_id, formalization_id, localizador, date, sentido="ida"):
        """buscar los trenes para un abono"""
        try:
            if not self.logged_in:
                self.search_results.emit([])
                return
                
            self.progress_update.emit(10, "Preparando búsqueda con abono...")
            await self.page.goto('https://venta.renfe.com/vol/myPassesCard.do')
            await self.page.wait_for_load_state('networkidle')
            
            # clic en nueva formalizacion
            print(f"Buscando trenes con abono ID: {abono_id}, Formalization ID: {formalization_id}, Localizador: {localizador}, Fecha: {date}, Sentido: {sentido}")
            if formalization_id:
                self.progress_update.emit(20, "Iniciando nueva formalización...")

                await self.page.evaluate(f'''
                    document.querySelector('[id*="{formalization_id.strip()}"]').click();
                ''')
                await self.page.wait_for_load_state('networkidle')
            else:
                self.progress_update.emit(0, "No se ha encontrado el botón de formalización")
            
            # seleccionar ida o vuelta
            try:
                self.progress_update.emit(30, f"Seleccionando sentido: {sentido}")
                if sentido == "ida":
                    await self.page.click('input#journeyStationOrigin')
                else:  # vuelta
                    await self.page.click('input#journeyStationDestin')
            except:
                pass
            
            # fecha
            self.progress_update.emit(50, "Seleccionando fecha...")
            formatted_date = date.replace("-", "/")  # formato DD/MM/YYYY

            try:
                date_selector = '#fecha1'
                await self.page.fill(date_selector, formatted_date, timeout=5000)
                    
            except Exception as e:
                print(f"Error seleccionando fecha: {e}")
            
            self.progress_update.emit(70, "Buscando trenes disponibles...")
            
            search_button = 'button#submitSiguiente'
            button_clicked = False
            
            await self.page.click(search_button)
            button_clicked = True
                    
            if not button_clicked:
                raise Exception("No se pudo encontrar el botón de búsqueda")
                
            await self.page.wait_for_load_state('networkidle')
            
            self.progress_update.emit(90, "Procesando resultados...")

            try:
                tbody = await self.page.wait_for_selector('#listTrainsTableTbodyNEW', timeout=10000)

                rows = await tbody.query_selector_all('tr')

                trains = []
                for row in rows:
                    cells = await row.query_selector_all('td')

                    numtren = ''
                    departure = ''
                    arrival = ''
                    duration = ''
                    status = ''
                    available = False

                    for count, cell in enumerate(cells):
                        cell_text = await cell.text_content() or ''
                        cell_text = cell_text.strip()

                        if count == 0:
                            cell_id = await cell.get_attribute('id') or ''
                            numtren = re.sub(r'\D', '', cell_id)
                        elif count == 1:
                            departure = cell_text
                        elif count == 2:
                            arrival = cell_text
                        elif count == 3:
                            duration = cell_text
                        elif count == 4:
                            train_type = cell_text
                        elif count == 5:
                            if cell_text == 'Tren Completo':
                                available = False
                            else:
                                available = True
                    if not numtren:
                        continue
                    print(f"Tren encontrado: {numtren}, Salida: {departure}, Llegada: {arrival}, Duración: {duration}, Estado: {status}, Disponible: {available}")
                    trains.append({
                        'numtren': numtren,
                        'departure': departure,
                        'arrival': arrival,
                        'duration': duration,
                        'train_type': train_type,
                        'available': available
                    })

                self.progress_update.emit(100, f"¡{len(trains)} trenes encontrados!")
                self.search_results.emit(trains)
                return trains

            except Exception as e:
                print(f"Error buscando trenes: {str(e)}")
                self.search_results.emit([])
                self.progress_update.emit(100, f"Error: {str(e)}")
                return []
            
        except Exception as e:
            print(f"Error buscando trenes con abono: {str(e)}")
            self.search_results.emit([])
            self.progress_update.emit(100, f"Error: {str(e)}")
            return []
    
    async def book_train_with_abono(self, train_id):
        """funcion asincron para reservar un tren con abono"""
        try:
            self.progress_update.emit(10, "Iniciando proceso de reserva con abono...")
            
            selector = f'#continuar{train_id.strip()}'
            button = await self.page.query_selector(selector)
            
            if not button:
                return False
            
            self.progress_update.emit(30, "Seleccionando tren...")
            
            await button.click()
            await self.page.wait_for_load_state('networkidle')
            
            self.progress_update.emit(50, "Confirmando reserva...")
            
            confirm_selector = '#submitSiguiente'
            
            confirm_button = await self.page.query_selector(confirm_selector)
            if not confirm_button:
                self.booking_status.emit(False, "Botón de confirmación no encontrado.")
                return False
            
            await confirm_button.click()
            
            try:
                await asyncio.sleep(5) 
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                
                current_url = self.page.url
                print(f"Current URL after confirmation: {current_url}")
                
                if 'buyFormalization' in current_url:
                    self.progress_update.emit(100, "Reserva confirmada con éxito! Puede cerrar la aplicación o buscar más trenes.")
                    self.train_booked.emit(train_id)  # Emitir señal con el ID del tren reservado
                    return True
                else:
                    self.progress_update.emit(70, "Verificando disponibilidad del tren...")
                    print(f"URL actual no esperada: {self.page.url}, volviendo atrás...")
                    
                    try:
                        await self.page.keyboard.press('Escape')
                        await self.page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as e:
                        print(f"Error al hacer clic en cualquier botón: {str(e)}")
                    
                    try:
                        volver_button = await self.page.query_selector('#botonVolver')
                        if volver_button:
                            await volver_button.click()
                            await self.page.wait_for_load_state('networkidle')
                        else:
                            await self.page.go_back()
                            await self.page.wait_for_load_state('networkidle')
                    except Exception as e:
                        print(f"Error al hacer clic en botón volver: {str(e)}")
                        await self.page.go_back()
                        await self.page.wait_for_load_state('networkidle')
                    
                    self.progress_update.emit(0, "Tren no disponible, volviendo a intentar...")
                    return False
                    
            except Exception as e:
                print(f"Error durante la navegación: {str(e)}")
                return False
                    
        except Exception as e:
            print(f"Error reservando tren con abono: {str(e)}")
            return False

    async def close_browser(self):
        """Close the browser instance"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
            self.logged_in = False


class BrowserThread(QThread):
    """Thread that runs the browser operations"""
    
    def __init__(self):
        super().__init__()
        self.worker = BrowserWorker()
        self.task = None
        self.loop = None
    
    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait()
    
    def execute_task(self, coro):
        if self.loop:
            self.task = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return self.task


class RenfeBot(QMainWindow):
    """ventana principal"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bot Renfe - Gestor de Abonos")
        self.setMinimumSize(800, 600)
        
        self.browser_thread = BrowserThread()
        self.browser_thread.start()
        self.worker = self.browser_thread.worker
        
        self.abonos = []
        self.selected_abono = None
        
        self.worker.login_status.connect(self.on_login_status)
        self.worker.search_results.connect(self.on_search_results)
        self.worker.booking_status.connect(self.on_booking_status)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.show_login_dialog.connect(self.show_login_dialog)
        self.worker.abonos_loaded.connect(self.on_abonos_loaded)
        self.worker.train_booked.connect(self.on_train_booked) 
        
        self.setup_ui()
        
        self.load_credentials()

    def on_train_booked(self, train_id):
        """dialogo de reserva tren"""
        QMessageBox.information(self, "Reserva Exitosa", 
                            f"¡El tren {train_id} ha sido reservado con éxito!")
        
        
    def setup_ui(self):
        """Setup the user interface"""
        # widget y layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # tabs
        self.tabs = QTabWidget()
        
        # lgin
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)
        login_group = QGroupBox("Iniciar sesión en Renfe")
        login_form = QVBoxLayout()
        
        # campos de login
        username_layout = QHBoxLayout()
        username_layout.addWidget(QLabel("Usuario:"))
        self.username_input = QLineEdit()
        username_layout.addWidget(self.username_input)
        login_form.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Contraseña:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.password_input)
        login_form.addLayout(password_layout)
        
        # recordar
        remember_layout = QHBoxLayout()
        self.remember_checkbox = QCheckBox("Recordar credenciales")
        remember_layout.addWidget(self.remember_checkbox)
        login_form.addLayout(remember_layout)
        
        # login manual
        manual_layout = QHBoxLayout()
        self.manual_checkbox = QCheckBox("Modo de inicio de sesión manual (para captchas y verificaciones)")
        self.manual_checkbox.setChecked(True)
        manual_layout.addWidget(self.manual_checkbox)
        login_form.addLayout(manual_layout)
        
        # boton de login
        self.login_button = QPushButton("Iniciar sesión")
        self.login_button.clicked.connect(self.login)
        login_form.addWidget(self.login_button)
        
        madeby_layout = QHBoxLayout()
        madeby_layout.addWidget(QLabel("feito por:"))
        madeby_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        login_form.addLayout(madeby_layout)
        
        logo_layout = QHBoxLayout()
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.logo_movie = QMovie("assets/logo.gif")

        self.logo_movie.setScaledSize(QSize(120, 120))
        self.logo_label.setMovie(self.logo_movie)
        self.logo_movie.start()
        logo_layout.addWidget(self.logo_label)
        login_form.addLayout(logo_layout)
        
        login_form.addStretch()
        
        login_group.setLayout(login_form)
        login_layout.addWidget(login_group)
        
        # abonos
        abonos_tab = QWidget()
        abonos_layout = QVBoxLayout(abonos_tab)
        
        # abonos groupbox
        abonos_group = QGroupBox("Mis abonos disponibles")
        abonos_group_layout = QVBoxLayout()
        
        # tabla de abonos
        self.abonos_table = QTableWidget(0, 5)
        self.abonos_table.setHorizontalHeaderLabels(["Tipo", "Origen", "Destino", "Validez (días)", "ID"])
        self.abonos_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.abonos_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.abonos_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.abonos_table.itemSelectionChanged.connect(self.on_abono_selected)
        abonos_group_layout.addWidget(self.abonos_table)
        
        # boton pa recargar abonos
        reload_abonos_button = QPushButton("Recargar abonos")
        reload_abonos_button.clicked.connect(self.reload_abonos)
        abonos_group_layout.addWidget(reload_abonos_button)
        
        abonos_group.setLayout(abonos_group_layout)
        abonos_layout.addWidget(abonos_group)
        
        # busqueda de trenes
        search_group = QGroupBox("Buscar trenes para abono seleccionado")
        search_form = QVBoxLayout()
        
        # sentido
        sentido_layout = QHBoxLayout()
        sentido_layout.addWidget(QLabel("Sentido:"))
        self.ida_radio = QRadioButton("Ida")
        self.ida_radio.setChecked(True)
        self.vuelta_radio = QRadioButton("Vuelta")
        sentido_group = QButtonGroup(self)
        sentido_group.addButton(self.ida_radio)
        sentido_group.addButton(self.vuelta_radio)
        sentido_layout.addWidget(self.ida_radio)
        sentido_layout.addWidget(self.vuelta_radio)
        sentido_layout.addStretch()
        search_form.addLayout(sentido_layout)
        
        # fecha
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Fecha:"))
        self.abono_date_picker = QDateEdit()
        self.abono_date_picker.setDisplayFormat("dd/MM/yyyy")
        self.abono_date_picker.setDate(QDate.currentDate())
        self.abono_date_picker.setCalendarPopup(True)
        date_layout.addWidget(self.abono_date_picker)
        search_form.addLayout(date_layout)
        
        # trenes
        self.abono_search_button = QPushButton("Buscar trenes")
        self.abono_search_button.clicked.connect(self.search_trains_with_abono)
        self.abono_search_button.setEnabled(False)
        search_form.addWidget(self.abono_search_button)
        
        search_group.setLayout(search_form)
        abonos_layout.addWidget(search_group)
        
        # resultados
        results_group = QGroupBox("Resultados")
        results_layout = QVBoxLayout()
        
        self.abono_results_table = QTableWidget(0, 7)
        self.abono_results_table.setHorizontalHeaderLabels(["ID", "Salida", "Llegada", "Tipo", "Duración", "Disponible", "Seleccionar"])
        self.abono_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.abono_results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.abono_results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        results_layout.addWidget(self.abono_results_table)
        
        # boton para coger los trenes
        self.abono_book_button = QPushButton("Coger trenes seleccionados") #TODO: crear un boton de parar de buscar
        self.abono_book_button.clicked.connect(self.book_train_with_abono)
        self.abono_book_button.setEnabled(False)
        results_layout.addWidget(self.abono_book_button)
        
        results_group.setLayout(results_layout)
        abonos_layout.addWidget(results_group)
        
        # tabs
        self.tabs.addTab(login_tab, "Login")
        self.tabs.addTab(abonos_tab, "Gestión de abonos")
        
        # barra de estado
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Listo")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.status_label, 7)
        status_layout.addWidget(self.progress_bar, 3)
        
        # anadir los widgets
        main_layout.addWidget(self.tabs)
        main_layout.addLayout(status_layout)
        
        self.setCentralWidget(main_widget)
    
    def on_abono_selected(self):
        """cuando se selecciona un abono"""
        selected_items = self.abonos_table.selectedItems()
        if selected_items:
            selected_row = selected_items[0].row()
            if 0 <= selected_row < len(self.abonos):
                self.selected_abono = self.abonos[selected_row]
                self.abono_search_button.setEnabled(True)
            else:
                self.selected_abono = None
                self.abono_search_button.setEnabled(False)
        else:
            self.selected_abono = None
            self.abono_search_button.setEnabled(False)
    
    def reload_abonos(self):
        """recargar los abons"""
        if self.worker.logged_in:
            self.browser_thread.execute_task(self.worker.load_abonos())
            self.status_label.setText("Recargando abonos...")
            self.progress_bar.setValue(0)
        else:
            QMessageBox.warning(self, "Error", "Debe iniciar sesión primero")
    
    def on_abonos_loaded(self, abonos):
        """cuando cargan"""
        self.abonos = abonos
        
        # actualizar tabla
        self.abonos_table.setRowCount(0)
        
        if abonos:
            self.abonos_table.setRowCount(len(abonos))
            for i, abono in enumerate(abonos):
                self.abonos_table.setItem(i, 0, QTableWidgetItem(abono.tipo))
                self.abonos_table.setItem(i, 1, QTableWidgetItem(abono.origen))
                self.abonos_table.setItem(i, 2, QTableWidgetItem(abono.destino))
                self.abonos_table.setItem(i, 3, QTableWidgetItem(abono.validez))
                self.abonos_table.setItem(i, 4, QTableWidgetItem(abono.id))
            
            self.status_label.setText(f"Se han cargado {len(abonos)} abonos")
            
            # cuando se cargan cambiar a la pestana
            self.tabs.setCurrentIndex(1)
        else:
            self.status_label.setText("No se encontraron abonos disponibles")
    
    def search_trains_with_abono(self):
        """buscar trenes con el abono seleccionado"""
        if not self.selected_abono:
            QMessageBox.warning(self, "Error", "Debe seleccionar un abono primero")
            return
        
        date = self.abono_date_picker.date().toString("dd-MM-yyyy")
        sentido = "ida" if self.ida_radio.isChecked() else "vuelta"
        
        self.abono_search_button.setEnabled(False)
        self.abono_book_button.setEnabled(False)
        self.abono_results_table.setRowCount(0)
        self.status_label.setText("Buscando trenes con abono...")
        self.progress_bar.setValue(0)
        
        self.browser_thread.execute_task(self.worker.search_trains_with_abono(
            self.selected_abono.id, 
            self.selected_abono.formalization_id,
            self.selected_abono.localizador,
            date, 
            sentido))
    
    def book_train_with_abono(self):
        """reservar los trenes seleccionados con abono"""
        selected_rows = []
        
        # para todos los trenes dispos
        for row in range(self.abono_results_table.rowCount()):
            checkbox = self.abono_results_table.cellWidget(row, 6)
            if checkbox and checkbox.isChecked(): # solo coge los que esten seleccionados
                selected_rows.append(row)
        
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Por favor, selecciona al menos un tren para reservar")
            return
        
        # procesar las filas
        print(f"Filas seleccionadas: {selected_rows}")
        self.status_label.setText("Reservando trenes seleccionados...")
        self.progress_bar.setValue(0)
        
        async def execute_reservations():
            success = False
            attempted_train = None
            
            while not success:
                for row in selected_rows:
                    # pillar numero de tren
                    numtren_item = self.abono_results_table.item(row, 0)
                    if numtren_item:
                        numtren = numtren_item.text()
                        attempted_train = numtren
                        print(f"Intentando reservar tren con ID: {numtren}")
                        
                        try:
                            result = await self.worker.book_train_with_abono(numtren)
                            if result: 
                                print(f"Reserva exitosa para el tren con ID: {numtren}")
                                self.status_label.setText(f"Reserva completada para el tren {numtren}")
                                success = True
                                return  
                        except Exception as e:
                            print(f"Error al reservar tren {numtren}: {str(e)}")
                    else:
                        print(f"No se encontró el ID del tren en la fila {row}")
                        
                await asyncio.sleep(5) # esperar para volver a intentarlo
            
        self.browser_thread.execute_task(execute_reservations())
    
    def show_login_dialog(self):
        """dialog de login manual"""
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.worker.set_login_completed()
    
    def load_credentials(self):
        """cargar las contrasenas"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as file:
                    config = json.load(file)
                    
                    if 'remember_credentials' in config and config['remember_credentials']:
                        if 'username' in config:
                            self.username_input.setText(config['username'])
                            
                        if 'password' in config:
                            # desencriptar (base64)
                            encrypted_password = config.get('password', '')
                            try:
                                decoded = base64.b64decode(encrypted_password).decode('utf-8')
                                self.password_input.setText(decoded)
                            except:
                                pass
                            
                        self.remember_checkbox.setChecked(True)
                        
                    if 'manual_login' in config:
                        self.manual_checkbox.setChecked(config['manual_login'])
                        
        except Exception as e:
            print(f"Error cargando credenciales: {e}")
    
    def save_credentials(self, username, password, remember, manual_login):
        """guardar credenciales en archivo"""
        try:
            config = {}
            
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as file:
                    config = json.load(file)
            
            # config
            config['remember_credentials'] = remember
            config['manual_login'] = manual_login
            
            if remember:
                config['username'] = username
                config['password'] = base64.b64encode(password.encode('utf-8')).decode('utf-8')
            else:
                if 'username' in config:
                    del config['username']
                if 'password' in config:
                    del config['password']
            
            # save
            with open(CONFIG_FILE, 'w') as file:
                json.dump(config, file)
                
        except Exception as e:
            print(f"Error guardando credenciales: {e}")
        
    def login(self):
        """boton de login"""
        username = self.username_input.text()
        password = self.password_input.text()
        remember = self.remember_checkbox.isChecked()
        manual_login = self.manual_checkbox.isChecked()
        
        if not username or not password:
            QMessageBox.warning(self, "Error", "Por favor, introduce usuario y contraseña")
            return
            
        self.save_credentials(username, password, remember, manual_login)
        
        self.worker.manual_login_mode = manual_login
        
        self.login_button.setEnabled(False)
        self.status_label.setText("Iniciando sesión...")
        self.progress_bar.setValue(0)
        
        self.browser_thread.execute_task(self.worker.login(username, password))
        
    def on_login_status(self, success, message):
        """resultado de login"""
        self.login_button.setEnabled(True)
        
        if success:
            # No cambiamos automáticamente de pestaña, ya que se manejará
            # en on_abonos_loaded cuando se reciban los abonos
            self.status_label.setText("Sesión iniciada correctamente")
        else:
            QMessageBox.warning(self, "Error de inicio de sesión", message)
            self.status_label.setText("Error al iniciar sesión")
        
    def on_search_results(self, trains):
        """Handle search results"""
        self.abono_search_button.setEnabled(self.selected_abono is not None)
        
        # Determinar qué pestaña está activa para actualizar la tabla correcta
        current_tab_index = self.tabs.currentIndex()
        
        # Seleccionar la tabla correspondiente
        results_table = self.abono_results_table
        book_button = self.abono_book_button
        
        # Limpiar y actualizar la tabla
        results_table.setRowCount(0)
        
        if not trains:
            self.status_label.setText("No se encontraron trenes")
            return
            
        # Añadir trenes a la tabla
        results_table.setRowCount(len(trains))
        for i, train in enumerate(trains):
            results_table.setItem(i, 0, QTableWidgetItem(train.get('numtren', '')))
            results_table.setItem(i, 1, QTableWidgetItem(train.get('departure', '')))
            results_table.setItem(i, 2, QTableWidgetItem(train.get('arrival', '')))
            results_table.setItem(i, 3, QTableWidgetItem(train.get('train_type', '')))
            results_table.setItem(i, 4, QTableWidgetItem(train.get('duration', '')))
            results_table.setItem(i, 5, QTableWidgetItem('Si' if train.get('available', False) else 'No'))
            
            # Añadir un checkbox en la columna "Seleccionar"
            checkbox = QCheckBox()
            checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")  # Centrar el checkbox
            results_table.setCellWidget(i, 6, checkbox)
        
        # Habilitar botón de reserva si hay resultados
        if len(trains) > 0:
            book_button.setEnabled(True)
            self.status_label.setText(f"{len(trains)} trenes encontrados")
        
    def book_train(self):
        """Handle book button click"""
        selected_rows = self.results_table.selectedIndexes()
        
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Por favor, selecciona un tren para reservar")
            return
            
        selected_row = selected_rows[0].row()
        
        # Check if the train is available
        available_item = self.results_table.item(selected_row, 4)
        if available_item and available_item.text() != 'Si':
            QMessageBox.warning(self, "Error", "Este tren no está disponible para reserva")
            return
            
        self.status_label.setText("Reservando tren...")
        self.progress_bar.setValue(0)
        
        # Execute booking in browser thread
        self.browser_thread.execute_task(self.worker.book_train(selected_row))
        
    def on_booking_status(self, success, message):
        """Handle booking result"""

        self.abono_book_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Reserva exitosa", message)
            self.status_label.setText("Reserva completada")
        else:
            QMessageBox.warning(self, "Error en la reserva", message)
            self.status_label.setText("Error en la reserva")
            
    def update_progress(self, value, message):
        """Update progress bar and status message"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        
    def closeEvent(self, event):
        """Handle window close event"""
        # Close browser
        if self.browser_thread.isRunning():
            self.browser_thread.execute_task(self.worker.close_browser())
            self.browser_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look and feel
    window = RenfeBot()
    window.show()
    sys.exit(app.exec())